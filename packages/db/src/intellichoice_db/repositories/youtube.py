"""SPEC §5.18: catalog upsert/inactive-marking (the sync worker's write path,
`packages/youtube/catalog_sync.py`) and `search_catalog` (§5.18.3's learning-time read
path - metadata filter, then a semantic rank over the filtered set, never a live
YouTube call). The catalog is small (single-digit-to-low-hundreds of approved videos
per channel), so the semantic rank is a plain Python cosine sort over the metadata-
filtered rows rather than a SQL `ORDER BY` - avoids JSONB array-containment operators
for `topic_ids`/`skill_ids` (stored as plain `JSON`, not `JSONB`) without sacrificing
the "filter before rank" order SPEC §5.21.3 established for RAG chunks.
"""

import math
from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.youtube import YoutubeVideo


def _cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 1.0
    return 1.0 - dot / (norm_a * norm_b)


class YoutubeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_video(self, youtube_video_id: str) -> YoutubeVideo | None:
        return await self._session.get(YoutubeVideo, youtube_video_id)

    async def upsert_video(self, video: YoutubeVideo) -> YoutubeVideo:
        """Re-syncing an already-known video updates it in place (natural-key
        idempotency, D-016's pattern) and always resets `active_status` to "active" -
        a video that reappears in a fetch is proof it's live again.
        """
        existing = await self.get_video(video.youtube_video_id)
        if existing is None:
            self._session.add(video)
            await self._session.flush()
            return video

        existing.channel_id = video.channel_id
        existing.channel_title = video.channel_title
        existing.video_url = video.video_url
        existing.title = video.title
        existing.description = video.description
        existing.playlist_ids = video.playlist_ids
        existing.duration = video.duration
        existing.published_at = video.published_at
        existing.thumbnail_url = video.thumbnail_url
        existing.language = video.language
        existing.topic_ids = video.topic_ids
        existing.skill_ids = video.skill_ids
        existing.grade_band = video.grade_band
        existing.difficulty_min = video.difficulty_min
        existing.difficulty_max = video.difficulty_max
        existing.embedding = video.embedding
        existing.last_synced_at = video.last_synced_at
        existing.active_status = "active"
        # Re-derived from this sync's own classification (S27) - re-copied on every
        # re-sync in case a skill re-classification changes it. Deliberately excludes
        # `transcript_available`/`transcript_language`/`license`/`last_verified_at`/
        # `verification_failures` - those are the separate verification pass's fields
        # (`apply_verification` below), never touched by this classify/embed upsert.
        existing.prerequisite_skill_ids = video.prerequisite_skill_ids
        await self._session.flush()
        return existing

    async def apply_verification(
        self,
        youtube_video_id: str,
        *,
        available: bool,
        license_: str,
        transcript_available: bool,
        transcript_language: str | None,
        verified_at: datetime,
    ) -> None:
        """S27 verification pass write path - reversible, same "reappear -> active
        again" posture `upsert_video`/`mark_inactive_except` already have.
        `verification_failures` resets to 0 on a passing check and increments on a
        failing one, rather than being set to a fixed value, so a caller can see how
        many consecutive/total checks have failed over time.
        """
        video = await self.get_video(youtube_video_id)
        if video is None:
            return
        video.license = license_
        video.transcript_available = transcript_available
        video.transcript_language = transcript_language
        video.last_verified_at = verified_at
        if available:
            video.verification_failures = 0
        else:
            video.active_status = "inactive"
            video.verification_failures += 1
        await self._session.flush()

    async def mark_inactive_except(self, channel_id: str, seen_video_ids: list[str]) -> int:
        """SPEC §5.18.2 "Mark deleted or private videos as inactive" - anything last
        synced under this channel that didn't appear in the latest fetch. Never
        deletes a row (SPEC §5.18.1's diagram has no removal step, only "inactive").
        """
        stmt = (
            update(YoutubeVideo)
            .where(YoutubeVideo.channel_id == channel_id)
            .where(YoutubeVideo.active_status != "inactive")
        )
        if seen_video_ids:
            stmt = stmt.where(YoutubeVideo.youtube_video_id.notin_(seen_video_ids))
        stmt = stmt.values(active_status="inactive")
        result = cast(CursorResult, await self._session.execute(stmt))
        await self._session.flush()
        return result.rowcount or 0

    async def has_servable_video(self, skill_id: str | None = None) -> bool:
        """Is there any video `search_catalog` could possibly return?

        D-207: the same three unconditional gates `search_catalog` applies (active,
        approved suitability, embedded), asked as a cheap existence check *before* the
        caller pays for an embedding. Staging ran for weeks with `youtube_videos` empty -
        the sync worker has never been part of a deploy - so every "Watch a video" bought
        a Titan embedding and then hit the §5.11.6 fallback anyway, ~145 ms and a real
        (if tiny) charge for a foregone conclusion.

        **Now filtered by skill, and D-305 is a correction to this docstring's own
        reasoning.** It used to say the skill filter belonged only in `search_catalog`
        because "a semantic rank is the thing deciding that". It is not: `search_catalog`
        applies `skill_id in v.skill_ids` as a **hard filter before** the rank, so for a
        skill with no video the candidate list is empty and the outcome is foregone - which
        is precisely the condition this check exists to short-circuit.

        The original scope was right for the world it was written in: staging held **zero**
        rows, so "the catalog is empty" and "this skill has nothing" were the same question.
        A sparse catalog separates them. Measured in dev: 4 videos covering 4 of 112 skills,
        so **108 skills** would pay a Titan embedding per "Watch a video" to reach a
        conclusion one indexed read already knows - and D-302 opened all 33 topics, so that
        is now the common path rather than a corner.

        The objection the old note raised - two places to keep the filter in step - is real
        and is why this reads `skill_ids` rather than re-deriving anything: same column, same
        membership test as `search_catalog`, one query, still no paid call.
        """
        stmt = select(YoutubeVideo.skill_ids).where(
            YoutubeVideo.active_status == "active",
            YoutubeVideo.suitability_status == "approved",
            YoutubeVideo.embedding.is_not(None),
        )
        if skill_id is None:
            return (await self._session.execute(stmt.limit(1))).first() is not None
        rows = (await self._session.execute(stmt)).scalars().all()
        return any(skill_id in (skill_ids or []) for skill_ids in rows)

    async def search_catalog(
        self,
        *,
        skill_id: str | None = None,
        topic_id: str | None = None,
        difficulty: int | None = None,
        query_embedding: list[float],
        limit: int = 1,
    ) -> list[YoutubeVideo]:
        """SPEC §5.18.3: Postgres metadata filter (active + approved-suitability +
        skill/topic/difficulty), then a semantic rank over the filtered set - never a
        live YouTube call. `suitability_status` (S27) is an unconditional gate, not a
        caller-supplied arg - it's a content-policy floor, not a query parameter.
        """
        stmt = select(YoutubeVideo).where(
            YoutubeVideo.active_status == "active",
            YoutubeVideo.suitability_status == "approved",
            YoutubeVideo.embedding.is_not(None),
        )
        result = await self._session.execute(stmt)
        candidates = [v for v in result.scalars().all() if v.embedding is not None]

        if skill_id is not None:
            candidates = [v for v in candidates if skill_id in v.skill_ids]
        if topic_id is not None:
            candidates = [v for v in candidates if topic_id in v.topic_ids]
        if difficulty is not None:
            candidates = [
                v for v in candidates if v.difficulty_min <= difficulty <= v.difficulty_max
            ]

        def _distance(video: YoutubeVideo) -> float:
            assert video.embedding is not None
            return _cosine_distance(video.embedding, query_embedding)

        candidates.sort(key=_distance)
        return candidates[:limit]
