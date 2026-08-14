"""Standalone Bedrock + sync config for the offline YouTube catalog sync worker (S15),
mirroring `intellichoice_knowledge.settings.KnowledgeIngestSettings`'s shape (D-014's
pattern applied to this pipeline) - own env prefix, no `learning_api`/`chat_api` import.
"""

import re
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class YoutubeSyncSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="YOUTUBE_", env_file=".env", extra="ignore")

    bedrock_provider: str = "mock"
    bedrock_aws_region: str = "us-east-1"
    # D-211: a model this account can actually invoke. `anthropic.claude-sonnet-5` is
    # listed by `list-foundation-models` but has no agreement here - invoking it returns
    # `AccessDeniedException: not available for this account`, which reached the sync only
    # as a tripped circuit breaker. Video classification is a short label-picking call, so
    # Haiku is a fit rather than a compromise; the authoring pipeline is the place where
    # the model choice genuinely matters (D-204).
    bedrock_classification_model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    bedrock_call_timeout_s: float = 20.0
    bedrock_max_retries: int = 2
    bedrock_circuit_failure_threshold: int = 5
    bedrock_circuit_cooldown_s: float = 30.0
    # One classification + one embedding call per video; a small catalog per channel.
    bedrock_run_budget_cents: float = 200.0
    # SPEC §5.18.1's single hardcoded source channel for this session - a real deployment
    # would sync several; adding more is a config change, not a pipeline change. This is
    # also the S27 channel pin `sync_channel` re-validates every fetched item against.
    #
    # The default is `FakeYoutubeProvider`'s own id and is **not** a YouTube channel id.
    # The real Data API resolves channels by their `UC...` id only, so a real run must
    # override this - see `check_real_sync_preflight`, which refuses rather than letting
    # the run die inside `_uploads_playlist_id` with "channel not found".
    channel_id: str = "khan-academy-math"
    # "fake" (default, D-002) or "youtube" - mirrors `bedrock_provider`'s env-selection
    # pattern. `youtube_api_key` is required only when `youtube_provider="youtube"`.
    youtube_provider: str = "fake"
    youtube_api_key: str = ""
    # D-207: a first real run's blast radius. `sync_channel` already caps *Bedrock* spend
    # at `bedrock_run_budget_cents`, but nothing capped how many videos the fetch walked -
    # a large channel's uploads playlist is thousands of items, paginated 50 at a time,
    # every one of them fetched before the budget check ever runs. This bounds the fetch
    # itself so a first run against a real channel is predictable in time and in API quota.
    max_videos: int = 200
    # D-209: results kept per skill-name search. Started at 5 (a deliberately small catalog).
    # D-217: raised to 8 - the user asked for more videos, and a wider net per skill gives
    # the serving path's single-best-match pick more to choose from. Still bounded: each
    # kept video costs one classification + one embedding call, and `search.list` is a flat
    # 100 quota units per skill-term regardless of how many results it returns, so this
    # widens coverage without widening the quota cost. `max_videos` and
    # `bedrock_run_budget_cents` remain the hard ceilings on a run.
    search_results_per_skill: int = 8

    # D-326: the quota ceiling, declared rather than discovered mid-run.
    #
    # `search.list` costs a flat 100 units per term against a 10,000/day default, and the
    # search terms are the curriculum's own skill names. That was written when the taxonomy
    # had **5** authorable skills - "Five terms is 500 units", as
    # `YoutubeDataApiProvider.list_uploaded_videos` still says. The taxonomy is now **112**,
    # so a full run costs **11,200 units** and dies about 89% of the way through with a 403
    # that reads like an auth problem. Nothing noticed, because the cost scales with content
    # and the affordability argument was made once, in a docstring, against a number that
    # then moved.
    #
    # Both values are settings rather than constants because neither is ours to assert: the
    # per-term cost is Google's, and the daily allowance is per-project and can be raised.
    daily_quota_units: int = 10_000
    search_unit_cost: int = 100
    # 0 means "every skill", which is correct once the quota allows it. Set it to fit a day's
    # allowance and the run covers the skills that have no video yet, so successive days
    # advance through the remainder instead of redoing the same prefix.
    max_search_terms: int = 0


# A YouTube channel id: literal "UC" plus 22 characters of base64url. Checked by shape
# only - whether the channel *exists* is the API's answer to give, not ours to guess.
_CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")


class YoutubeSyncConfigError(Exception):
    """The real-sync configuration cannot work as given - raised before any network or
    paid call, so a misconfigured run costs nothing.
    """


def check_real_sync_preflight(settings: YoutubeSyncSettings) -> None:
    """Refuse a real-provider run that is configured to fail (D-207).

    Only two things can be wrong before the first request, and both produce errors that
    do not say what to fix: a missing key surfaces as an HTTP 403 from `_get`, and the
    default `channel_id` surfaces as `channel 'khan-academy-math' not found` - which reads
    like the channel was deleted rather than like the id is the wrong *kind* of value.

    Deliberately shape-only on the channel id. Hard-coding a specific channel's `UC...`
    id here would be asserting a fact this codebase cannot verify, and a wrong one sends
    a K-12 student to someone else's videos.
    """
    if settings.youtube_provider != "youtube":
        return
    if not settings.youtube_api_key:
        raise YoutubeSyncConfigError(
            "YOUTUBE_YOUTUBE_PROVIDER=youtube needs YOUTUBE_YOUTUBE_API_KEY set "
            "(a YouTube Data API v3 key). Never commit it - pass it via the environment."
        )
    if not _CHANNEL_ID_RE.match(settings.channel_id):
        raise YoutubeSyncConfigError(
            f"YOUTUBE_CHANNEL_ID={settings.channel_id!r} is not a YouTube channel id. "
            "The Data API resolves channels by their 'UC...' id (literal 'UC' plus 22 "
            "characters); the default here is the dev fake's own id and only works with "
            "YOUTUBE_YOUTUBE_PROVIDER=fake."
        )


def check_search_quota(settings: YoutubeSyncSettings, term_count: int) -> None:
    """Refuse a run whose searches cannot fit the day's quota (D-326).

    The same discipline the key and channel-id checks already apply, extended to the one
    failure that is arithmetic rather than configuration. Without it the run spends ~9,900
    units, dies on a 403 that reads like an auth failure, and leaves a partially-synced
    catalog behind - the worst of the three outcomes, because it looks like a credentials
    problem and is not.

    Raised with the numbers and the knob, because "quota exceeded" without them sends the
    reader to the Google console rather than to `YOUTUBE_MAX_SEARCH_TERMS`.
    """
    if settings.youtube_provider != "youtube":
        return
    cost = term_count * settings.search_unit_cost
    if cost > settings.daily_quota_units:
        raise YoutubeSyncConfigError(
            f"{term_count} search terms x {settings.search_unit_cost} units = {cost:,} "
            f"quota units, over the {settings.daily_quota_units:,} this run is allowed. "
            f"Set YOUTUBE_MAX_SEARCH_TERMS to at most "
            f"{settings.daily_quota_units // settings.search_unit_cost} and run again on a "
            "later day for the rest - each run covers the skills that have no video yet, so "
            "successive runs advance rather than repeat. Raise YOUTUBE_DAILY_QUOTA_UNITS "
            "only if this project's real allowance has been raised."
        )


@lru_cache
def get_sync_settings() -> YoutubeSyncSettings:
    return YoutubeSyncSettings()
