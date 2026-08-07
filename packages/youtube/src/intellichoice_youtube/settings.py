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
    bedrock_classification_model_id: str = "anthropic.claude-sonnet-5"
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


@lru_cache
def get_sync_settings() -> YoutubeSyncSettings:
    return YoutubeSyncSettings()
