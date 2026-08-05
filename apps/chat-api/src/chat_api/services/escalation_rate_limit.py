"""The SPEC §5.24.2 escalation cap, enforced across tasks (AUD-C-27).

Composition only: `RateLimitRepository` does the counting and `hash_caller_key` does the
key derivation, and this class holds the policy that joins them. It lives in chat-api
rather than in `intellichoice_shared` because `intellichoice_shared` depends on nothing
but pydantic by design, and the repository is `intellichoice_db`'s.

Why there is no env flag selecting this over `InMemoryRateLimiter`: D-002's
"fake by default, real opt-in" pattern is for *external* dependencies, whose real client
costs money or needs credentials this repo does not hold. Postgres is this app's own
database, already required for the turn that reaches this code, so a flag would only
create the possibility of the deployed behaviour differing from the tested one - which is
the shape of the defect being fixed, not a safeguard against it. `InMemoryRateLimiter`
remains the `RateLimiter` fake for unit tests that inject a `TurnContext` directly.
"""

from datetime import timedelta

from intellichoice_db.models.rate_limit import SCOPE_ADMIN_ESCALATION
from intellichoice_db.repositories.rate_limit import RateLimitRepository
from intellichoice_shared.rate_limit import hash_caller_key


class PostgresRateLimiter:
    """`RateLimiter` over a shared counter. Structurally satisfies the Protocol; the
    caller (`nodes.prepare_admin_escalation`) cannot tell which implementation it holds.
    """

    def __init__(
        self,
        *,
        repository: RateLimitRepository,
        max_per_window: int,
        window_s: float,
        key_secret: str,
        scope: str = SCOPE_ADMIN_ESCALATION,
    ) -> None:
        self._repository = repository
        self._max_per_window = max_per_window
        self._window = timedelta(seconds=window_s)
        self._key_secret = key_secret
        self._scope = scope

    async def allow(self, key: str) -> bool:
        return await self._repository.try_consume(
            scope=self._scope,
            caller_key_hash=hash_caller_key(key, secret=self._key_secret),
            max_per_window=self._max_per_window,
            window=self._window,
        )
