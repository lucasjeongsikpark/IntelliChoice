# Build context must be the repo ROOT, not this directory - this is a uv workspace
# monorepo (apps/learning-api depends on packages/{shared,adapters,db,curriculum,
# memory,observability} via `{workspace = true}`), so the whole workspace needs to be
# present for `uv sync` to resolve it the same way `make test`/CI already do.
#   docker build -f apps/learning-api/Dockerfile -t learning-api .

FROM python:3.14-slim AS builder

RUN pip install --no-cache-dir "uv>=0.9"

WORKDIR /app

# Copy the whole workspace (all apps/ + packages/, not just this app) - `uv sync`
# resolves against the workspace manifest in pyproject.toml/uv.lock, which lists every
# member; the small extra image size from the other app's source is worth not
# special-casing a partial-workspace sync.
COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY apps/learning-api/ apps/learning-api/
COPY apps/chat-api/ apps/chat-api/
# Static content the loader/ingest CLIs read from disk at runtime (not from the DB -
# these are the source files that get loaded INTO it), resolved relative to the source
# file's own location (`Path(__file__).resolve().parents[4] / "curriculum" / ...`,
# `.../ "knowledge-content" / ...`) - missing entirely from earlier image builds, which
# meant every ops-task content-load command failed with FileNotFoundError against a
# fresh deployment (found live during S32/D-084's holistic post-deploy testing, not in
# review). Tiny (32K + 200K) - copying both into every image isn't worth special-casing.
COPY curriculum/ curriculum/
COPY knowledge-content/ knowledge-content/

# --frozen: fail rather than silently re-resolve if uv.lock is out of date (same
# guarantee `make lint`/`test`/CI already rely on). --no-dev: uv treats a group literally
# named "dev" as auto-included by default (confirmed empirically - ruff/pyright/pytest/
# httpx2 showed up in the image without --all-groups); --no-dev is required to actually
# keep them out of the runtime image. --all-packages installs every workspace member as
# an editable install (including chat-api), which is why its full source needs to be
# present, not just its manifest.
RUN uv sync --frozen --all-packages --no-dev

FROM python:3.14-slim AS runtime

# D-384: patch the base image's OS packages here, in the runtime stage. This replaces a
# comment that ended "rebuild once Debian/the upstream image ships fixes" - that is exactly
# what happened, and it turned the CI gate red rather than green, because
# `.github/workflows/security-scan.yml` fires on *fixable* CRITICAL/HIGH: on 2026-08-17
# Debian published `util-linux 2.41.5-0+deb13u1`, which flipped CVE-2026-53615 from
# "ignored, no fix exists" to gating across the nine binary packages built from that one
# source (Trivy prints `Total: 9` because it counts rows, not CVEs).
#
# Measured before choosing this over the alternatives (OPEN_DECISIONS #11): `python:3.12-slim`
# still ships util-linux 2.41-5, so there was **no fixed base digest to pin to**, while the
# fix was already the archive Candidate - so pin-and-bump could not clear it today and this
# can. Verified in a throwaway container that `apt-get -y upgrade` moves all nine to
# 2.41.5-0+deb13u1 with exit 0 (on arm64; the amd64 archive carries the same source version).
#
# The cost, stated because it is what made this a decision rather than a fix: image contents
# now depend on *when* the build ran, so rebuilding the same commit is no longer
# byte-identical. Accepted - staying patched matters more than bit-reproducibility for an
# image whose provenance is already recorded per deploy (APP_BUILD_SHA + immutable ECR tags).
# `upgrade`, not `dist-upgrade`: it applies point-release security fixes and will not add or
# remove packages, so it cannot quietly change what is in the image beyond patch versions.
RUN apt-get update \
    && apt-get -y upgrade \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 appuser
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/packages /app/packages
COPY --from=builder /app/apps/learning-api /app/apps/learning-api
# AUD-F-25: this image is also the ops-task image, on the stated grounds that it "already
# has every workspace package installed" - and it did not. The builder above copies
# `apps/chat-api/` so `uv sync` installs it, but this stage never copied the source, so the
# venv carried a **dangling editable install**: metadata saying `chat_api` is present with
# nothing behind it. `python -c "import chat_api"` in the ops task returned
# `ModuleNotFoundError`, exit 1, which is why chat-web's welcome-card suggestions have never
# been seeded on staging (`/chat/meta` returned `"suggested_prompts":[]`).
#
# Source only - no separate `uv sync`, no second venv, no new dependency. The learning-api
# service itself never imports `chat_api`; this is here so the one image the ops task runs
# can execute either app's maintenance CLIs, which is what the ops task was always
# documented to be able to do.
COPY --from=builder /app/apps/chat-api /app/apps/chat-api
COPY --from=builder /app/curriculum /app/curriculum
COPY --from=builder /app/knowledge-content /app/knowledge-content

# D-088: PYTHONDONTWRITEBYTECODE - the ECS task definition now sets
# readonlyRootFilesystem=true (S33 Fargate hardening); Python would otherwise attempt
# (and harmlessly fail, but still attempt) to write .pyc caches under the read-only
# tree on every import.
# S43 (AUD-F-16): the image's own git SHA - see the matching comment in
# apps/chat-api/Dockerfile for why it sits here rather than in the builder stage.
ARG APP_BUILD_SHA=""

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_BUILD_SHA=${APP_BUILD_SHA}

USER appuser
EXPOSE 8001

# No curl in the slim image - a plain urllib call is enough for a liveness/readiness
# check without adding a package just for this.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/healthz', timeout=3)" || exit 1

# D-087: --proxy-headers makes Uvicorn trust X-Forwarded-For/X-Forwarded-Proto so
# `Request.client.host` reflects the real caller, not the ALB's own address - without
# this, every real request collapses onto one IP, making the new global rate limiter
# (and the admin-escalation one in chat-api) useless in the real deployment.
# --forwarded-allow-ips="*" trusts every direct connection's forwarded headers - safe
# here specifically because this container is never reachable except from the ALB (the
# ECS task security group only allows inbound from the ALB's security group, S32/D-084);
# there is no other path a spoofed header could arrive by.
# **`--timeout-keep-alive` above the ALB's idle timeout** (D-364). uvicorn defaults to 5s;
# the ALB is configured for 120s. So the ALB keeps a pooled backend connection for up to two
# minutes while uvicorn closes it after five seconds of idle, and a request sent on a
# connection the backend has just closed becomes a **502 the application never sees** - no
# access log, no error, nothing to find. Measured on staging: exactly one ALB-generated 5xx in
# three hours of load, on a fire-and-forget `POST /exam/viewed`, with zero task restarts and a
# clean application log. 125 > 120 makes the backend outlive the reuse window, so the ALB is
# always the side that closes.
CMD ["uvicorn", "learning_api.main:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers", "--forwarded-allow-ips=*", "--timeout-keep-alive", "125"]
