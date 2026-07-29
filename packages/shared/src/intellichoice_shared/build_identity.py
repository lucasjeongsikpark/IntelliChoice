"""S43 (AUD-F-16): what version of the application is actually answering.

The finding: `playwright.config.ts` sets `reuseExistingServer: true`, and the two
`uvicorn` processes on 8001/8002 had been up since 2026-07-25 21:31 - started *before*
S40's four authorization fixes merged. Playwright starts and tears down the vite dev
servers on every run, so the frontends were always current while the APIs were frozen,
which is the worst version of this failure: nothing looks stale. Every S39 and S40 e2e
result against `local` is therefore of an unknown application version.

A run has to be able to say what it tested. Two identities, because the two environments
go stale in different ways:

- `build_sha` - the image's git SHA, injected at `docker build` time by
  `deploy-staging.yml` (`--build-arg APP_BUILD_SHA=$GITHUB_SHA`). This is the staging
  answer, and it is also what makes "the deployed code contains the fix" checkable
  instead of assumed - the open question behind the time-telemetry staging failure,
  where AUD-F-01's fix is in `main` and its signature is still on the screen.
- `started_at` - process boot time. This is the *local* answer, where there is no image
  and no SHA: a server booted before the source it is supposed to be running is stale,
  and comparing this timestamp to the newest source mtime is a check the harness can
  make on its own (see e2e/fixtures/build-identity.ts).

Deliberately on `/healthz`, which is dependency-free and unauthenticated: an identity you
need a token or a database to read is not available at the moment you most need it.
Neither field is PII and neither is a secret - a git SHA of a private repo names a commit
to someone who already has the repo, and the boot time of a process is visible in its
own logs.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime

# Captured at import, which is the closest thing to "when this process started" that does
# not require threading a lifespan value through every caller. Within a few milliseconds
# of the real boot, and the comparison it exists for is measured in minutes and days.
_STARTED_AT = datetime.now(UTC)
_STARTED_MONOTONIC = time.monotonic()

# Set by the Dockerfile's ARG/ENV pair. Absent in local dev and in the test suite, where
# `started_at` is the identity that matters and a fake SHA would be worse than none.
_BUILD_SHA = os.environ.get("APP_BUILD_SHA", "").strip() or "unknown"


def build_identity() -> dict[str, str | float]:
    """The identity block `/healthz` returns. Cheap enough to call per health check."""
    return {
        "build_sha": _BUILD_SHA,
        "started_at": _STARTED_AT.isoformat(),
        "uptime_seconds": round(time.monotonic() - _STARTED_MONOTONIC, 1),
    }
