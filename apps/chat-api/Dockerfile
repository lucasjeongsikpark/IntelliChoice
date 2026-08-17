# Build context must be the repo ROOT, not this directory - this is a uv workspace
# monorepo (apps/chat-api depends on packages/{shared,adapters,db,knowledge,
# observability} via `{workspace = true}`), so the whole workspace needs to be
# present for `uv sync` to resolve it the same way `make test`/CI already do.
#   docker build -f apps/chat-api/Dockerfile -t chat-api .

FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir "uv>=0.9"

WORKDIR /app

# Copy the whole workspace (all apps/ + packages/, not just this app) - `uv sync
# --all-packages` installs every workspace member as an editable install (including
# learning-api), so its full source needs to be present too, not just its manifest.
COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY apps/chat-api/ apps/chat-api/
COPY apps/learning-api/ apps/learning-api/
# Static content the loader/ingest CLIs read from disk at runtime - see the matching
# comment in apps/learning-api/Dockerfile for why both are copied into both images.
COPY curriculum/ curriculum/
COPY knowledge-content/ knowledge-content/

# --frozen: fail rather than silently re-resolve if uv.lock is out of date (same
# guarantee `make lint`/`test`/CI already rely on). --no-dev: uv treats a group literally
# named "dev" as auto-included by default (confirmed empirically - ruff/pyright/pytest/
# httpx2 showed up in the image without --all-groups); --no-dev is required to actually
# keep them out of the runtime image. --all-packages installs every workspace member as
# an editable install (including learning-api), which is why its full source needs to be
# present, not just its manifest.
RUN uv sync --frozen --all-packages --no-dev

FROM python:3.12-slim AS runtime

# D-384: patch the base image's OS packages - see the matching, more detailed comment in
# apps/learning-api/Dockerfile for the measurement and the reproducibility cost. Identical
# base image, identical finding, and both scans failed together.
RUN apt-get update \
    && apt-get -y upgrade \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 appuser
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/packages /app/packages
COPY --from=builder /app/apps/chat-api /app/apps/chat-api
COPY --from=builder /app/curriculum /app/curriculum
COPY --from=builder /app/knowledge-content /app/knowledge-content

# S43 (AUD-F-16): the image's own git SHA, so `/healthz` can say what version is running
# and a test run can record what it tested. Last, and in the runtime stage only, so it
# cannot invalidate the builder layers - a new SHA on every commit would otherwise mean a
# full `uv sync` on every build. Empty in a plain `docker build`, which reports "unknown".
ARG APP_BUILD_SHA=""

# D-088: see the matching comment in apps/learning-api/Dockerfile.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_BUILD_SHA=${APP_BUILD_SHA}

USER appuser
EXPOSE 8002

# No curl in the slim image - a plain urllib call is enough for a liveness/readiness
# check without adding a package just for this.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/healthz', timeout=3)" || exit 1

# D-087: see the matching comment in apps/learning-api/Dockerfile - same rationale,
# and this app's own existing admin-escalation rate limiter (SPEC §5.24.2) needed this
# fix even more directly, since it's specifically meant to be per-caller.
# **`--timeout-keep-alive` above the ALB's idle timeout** (D-364). uvicorn defaults to 5s;
# the ALB is configured for 120s. So the ALB keeps a pooled backend connection for up to two
# minutes while uvicorn closes it after five seconds of idle, and a request sent on a
# connection the backend has just closed becomes a **502 the application never sees** - no
# access log, no error, nothing to find. Measured on staging: exactly one ALB-generated 5xx in
# three hours of load, on a fire-and-forget `POST /exam/viewed`, with zero task restarts and a
# clean application log. 125 > 120 makes the backend outlive the reuse window, so the ALB is
# always the side that closes.
CMD ["uvicorn", "chat_api.main:app", "--host", "0.0.0.0", "--port", "8002", "--proxy-headers", "--forwarded-allow-ips=*", "--timeout-keep-alive", "125"]
