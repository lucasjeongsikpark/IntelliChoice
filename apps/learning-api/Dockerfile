# Build context must be the repo ROOT, not this directory - this is a uv workspace
# monorepo (apps/learning-api depends on packages/{shared,adapters,db,curriculum,
# memory,observability} via `{workspace = true}`), so the whole workspace needs to be
# present for `uv sync` to resolve it the same way `make test`/CI already do.
#   docker build -f apps/learning-api/Dockerfile -t learning-api .

FROM python:3.12-slim AS builder

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

FROM python:3.12-slim AS runtime

# Known base-image gap, not fixed here: python:3.12-slim's perl-base package carries
# CVE-2026-12087 (critical) + CVE-2026-48959/48962 (high), no upstream fix published yet
# (confirmed via `docker scout cves`). Tried removing it - apt refuses (`perl-base` is
# marked Essential; forcing removal risks destabilizing the base image for a CVE this
# app's own code never exercises, since nothing here invokes perl). Tracked via ECR's
# scan-on-push (S32/D-084); rebuild once Debian/the upstream image ships a fix.

RUN useradd --create-home --uid 10001 appuser
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/packages /app/packages
COPY --from=builder /app/apps/learning-api /app/apps/learning-api
COPY --from=builder /app/curriculum /app/curriculum
COPY --from=builder /app/knowledge-content /app/knowledge-content

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER appuser
EXPOSE 8001

# No curl in the slim image - a plain urllib call is enough for a liveness/readiness
# check without adding a package just for this.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/healthz', timeout=3)" || exit 1

CMD ["uvicorn", "learning_api.main:app", "--host", "0.0.0.0", "--port", "8001"]
