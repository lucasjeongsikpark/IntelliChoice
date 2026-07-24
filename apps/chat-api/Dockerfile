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

# Known base-image gap, not fixed here: see the matching, more detailed comment in
# apps/learning-api/Dockerfile (identical base image, identical finding, S33/D-089).

RUN useradd --create-home --uid 10001 appuser
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/packages /app/packages
COPY --from=builder /app/apps/chat-api /app/apps/chat-api
COPY --from=builder /app/curriculum /app/curriculum
COPY --from=builder /app/knowledge-content /app/knowledge-content

# D-088: see the matching comment in apps/learning-api/Dockerfile.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser
EXPOSE 8002

# No curl in the slim image - a plain urllib call is enough for a liveness/readiness
# check without adding a package just for this.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/healthz', timeout=3)" || exit 1

# D-087: see the matching comment in apps/learning-api/Dockerfile - same rationale,
# and this app's own existing admin-escalation rate limiter (SPEC §5.24.2) needed this
# fix even more directly, since it's specifically meant to be per-caller.
CMD ["uvicorn", "chat_api.main:app", "--host", "0.0.0.0", "--port", "8002", "--proxy-headers", "--forwarded-allow-ips=*"]
