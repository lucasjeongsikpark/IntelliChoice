"""YouTube Data API abstraction (SPEC §5.18.1). Real Google API credentials don't exist
yet (D-002's posture, same footing as Gmail/Calendar/Maps) - `FakeYoutubeProvider`
(`packages/adapters`) stays the dev/test default; `YoutubeDataApiProvider` (S27,
`packages/adapters`) is a real implementation behind this same `YoutubeProvider`
Protocol, unexercised until real credentials exist.
"""

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel


class RawVideoMetadata(BaseModel):
    """What the sync pipeline gets back per video, pre-classification/embedding - the
    SPEC §5.18.2 fields that come directly from the API, not the ones the pipeline
    itself derives (`topic_ids`/`skill_ids`/`grade_band`/`difficulty_min`/
    `difficulty_max`/`embedding`/`last_synced_at`/`active_status`).
    """

    youtube_video_id: str
    channel_id: str
    channel_title: str
    video_url: str
    title: str
    description: str
    playlist_ids: list[str] = []
    duration: str
    published_at: datetime
    thumbnail_url: str
    language: str = "en"


class VideoDetails(BaseModel):
    """S27 verification pass result for one video (SPEC §5.18 hardening) - a single
    `videos.list(part=status,contentDetails)`-shaped call gives liveness, license, and
    caption availability together, so no separate `captions.list` call is needed.
    `available=False` covers both "missing from the response entirely" (the real API
    simply omits deleted video ids) and an explicit private/rejected status.
    `transcript_language` isn't part of this - a real per-track language needs
    `captions.list` per video, one more real API call this session skips (unexercisable
    without real creds anyway); `catalog_sync` instead uses the video's own language
    (`RawVideoMetadata.language`) as the stored `transcript_language` whenever
    `transcript_available` is true.
    """

    available: bool
    license: str = "youtube"
    transcript_available: bool = False


class YoutubeProvider(Protocol):
    async def list_uploaded_videos(self, channel_id: str) -> list[RawVideoMetadata]: ...

    async def get_video_details(self, video_ids: list[str]) -> dict[str, VideoDetails]: ...


class YoutubeCatalogSearchArgs(BaseModel):
    """Args for the `youtube_catalog.search` internal MCP tool (SPEC §5.18.3) - the
    query embedding itself is computed by the caller (a Bedrock call, not a "tool
    argument"), so this is just the metadata filter half. S27's misconception-tag/
    grade-band/mastery-state enrichment happens one layer up, in the text handed to
    the embedding call (`video_catalog.search_video`) - it only ever *widens the
    embedding query text*, never becomes a hard filter here, so it costs zero extra
    external calls at learning time.
    """

    skill_id: str
    difficulty: int | None = None


class YoutubeCatalogSearchResult(BaseModel):
    video_id: str
    title: str
    url: str
    source: str
