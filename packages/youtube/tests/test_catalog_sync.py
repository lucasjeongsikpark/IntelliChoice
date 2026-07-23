"""SPEC §5.18/§6.17 catalog sync worker - real Postgres via the same rollback-session
pattern as `packages/knowledge/tests/test_ingest.py` (D-013). Skips cleanly when
Postgres is unreachable (D-008).
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_adapters.fake_youtube import CHANNEL_ID, DEFAULT_VIDEOS, FakeYoutubeProvider
from intellichoice_curriculum.content import load_curriculum
from intellichoice_db.engine import create_engine
from intellichoice_db.repositories.youtube import YoutubeRepository
from intellichoice_shared.bedrock import BedrockTask
from intellichoice_shared.youtube import RawVideoMetadata, VideoDetails
from intellichoice_youtube.catalog_sync import YoutubeSyncError, sync_channel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _postgres_skip_reason() -> str | None:
    async def check() -> str | None:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                try:
                    await conn.execute(text("SELECT 1 FROM youtube_videos LIMIT 1"))
                except Exception:
                    return "Postgres schema is not migrated (run `make up && make db-upgrade`)"
            return None
        except Exception:
            return "PostgreSQL is not reachable at localhost:5432 (run `make up`)"
        finally:
            await engine.dispose()

    return asyncio.run(check())


@asynccontextmanager
async def _rollback_session() -> AsyncIterator[AsyncSession]:
    engine = create_engine()
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
            try:
                yield session
            finally:
                await session.close()
                await trans.rollback()
    finally:
        await engine.dispose()


pytestmark = pytest.mark.skipif(
    (_reason := _postgres_skip_reason()) is not None, reason=_reason or ""
)


def _gateway() -> ResilientBedrockGateway:
    mock = MockBedrockProvider()
    return ResilientBedrockGateway(
        provider=mock,
        embedding_provider=mock,
        model_registry={
            BedrockTask.VIDEO_CLASSIFICATION: "test-model",
            BedrockTask.EMBEDDING: "amazon.titan-embed-text-v2:0",
        },
    )


def test_sync_creates_then_is_idempotent_and_classifies_known_skills() -> None:
    """Deliberately doesn't assume the table starts empty - a real `make youtube-sync`
    run against the shared dev Postgres (outside this test's rollback transaction) may
    already have synced these same fixture videos. What matters is that every fetched
    video ends up existing exactly once, and that a second identical run creates
    nothing new (mirrors `packages/knowledge/tests/test_ingest.py`'s same reasoning).
    """

    async def run() -> None:
        async with _rollback_session() as session:
            repo = YoutubeRepository(session)
            provider = FakeYoutubeProvider()
            curriculum = load_curriculum()

            first = await sync_channel(
                repo,
                provider=provider,
                gateway=_gateway(),
                curriculum=curriculum,
                channel_id=CHANNEL_ID,
                run_budget_cents=1000.0,
            )
            assert first.videos_created + first.videos_updated == len(DEFAULT_VIDEOS)

            one_step = await repo.get_video("ka-one-step-eq")
            assert one_step is not None
            assert one_step.active_status == "active"
            # The mock classifier keyword-matches the video's title/description
            # against the real curriculum registry (D-038-style re-validation) -
            # proves a real skill id landed, not an invented label.
            assert "linear_one_step" in one_step.skill_ids
            assert "linear_equations" in one_step.topic_ids
            assert one_step.embedding is not None

            # S27: prerequisite_skill_ids is derived deterministically (no LLM) from
            # the classified skill_ids via `prerequisites.yaml` - `linear_two_step`'s
            # own prerequisite is `linear_one_step`.
            two_step = await repo.get_video("ka-two-step-eq")
            assert two_step is not None
            assert "linear_two_step" in two_step.skill_ids
            assert two_step.prerequisite_skill_ids == ["linear_one_step"]

            second = await sync_channel(
                repo,
                provider=provider,
                gateway=_gateway(),
                curriculum=curriculum,
                channel_id=CHANNEL_ID,
                run_budget_cents=1000.0,
            )
            assert second.videos_created == 0
            assert second.videos_updated == len(DEFAULT_VIDEOS)
            assert second.videos_marked_inactive == 0

    asyncio.run(run())


def test_removed_video_is_marked_inactive_not_deleted() -> None:
    """SPEC §5.18.2 "Mark deleted or private videos as inactive"."""

    async def run() -> None:
        async with _rollback_session() as session:
            repo = YoutubeRepository(session)
            provider = FakeYoutubeProvider()
            curriculum = load_curriculum()

            await sync_channel(
                repo,
                provider=provider,
                gateway=_gateway(),
                curriculum=curriculum,
                channel_id=CHANNEL_ID,
                run_budget_cents=1000.0,
            )

            removed_id = provider.videos.pop().youtube_video_id
            summary = await sync_channel(
                repo,
                provider=provider,
                gateway=_gateway(),
                curriculum=curriculum,
                channel_id=CHANNEL_ID,
                run_budget_cents=1000.0,
            )
            assert summary.videos_marked_inactive == 1

            removed = await repo.get_video(removed_id)
            assert removed is not None  # never deleted
            assert removed.active_status == "inactive"

            # An inactive video never surfaces from a learning-time search.
            results = await repo.search_catalog(query_embedding=[0.0] * 1024, limit=10)
            assert removed_id not in [v.youtube_video_id for v in results]

    asyncio.run(run())


def test_fetch_failure_raises_and_leaves_existing_catalog_untouched() -> None:
    """SPEC §6.17 "Keeps the previous catalog on failure"."""

    async def run() -> None:
        async with _rollback_session() as session:
            repo = YoutubeRepository(session)
            provider = FakeYoutubeProvider()
            curriculum = load_curriculum()

            await sync_channel(
                repo,
                provider=provider,
                gateway=_gateway(),
                curriculum=curriculum,
                channel_id=CHANNEL_ID,
                run_budget_cents=1000.0,
            )
            before = await repo.get_video("ka-one-step-eq")
            assert before is not None

            provider.fail = True
            with pytest.raises(YoutubeSyncError):
                await sync_channel(
                    repo,
                    provider=provider,
                    gateway=_gateway(),
                    curriculum=curriculum,
                    channel_id=CHANNEL_ID,
                    run_budget_cents=1000.0,
                )

            after = await repo.get_video("ka-one-step-eq")
            assert after is not None
            assert after.active_status == "active"
            assert after.title == before.title

    asyncio.run(run())


def test_off_channel_video_is_rejected_at_sync_never_upserted() -> None:
    """S27 hardening: `sync_channel` re-checks each fetched item's own `channel_id`
    itself rather than trusting the provider to have already filtered correctly -
    `FakeYoutubeProvider.list_uploaded_videos` deliberately returns everything in
    `provider.videos` regardless of the requested channel, so this test only passes if
    the sync layer's own pin check is what's actually rejecting the off-channel item.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            repo = YoutubeRepository(session)
            curriculum = load_curriculum()

            off_channel = RawVideoMetadata(
                youtube_video_id="not-khan-academy-video",
                channel_id="some-other-channel",
                channel_title="Some Other Channel",
                video_url="https://example.test/not-khan-academy-video",
                title="Unrelated video",
                description="Not part of the pinned channel.",
                duration="PT3M",
                published_at=datetime(2024, 2, 1, tzinfo=UTC),
                thumbnail_url="https://example.test/thumb.jpg",
            )
            provider = FakeYoutubeProvider(videos=[*DEFAULT_VIDEOS, off_channel])

            summary = await sync_channel(
                repo,
                provider=provider,
                gateway=_gateway(),
                curriculum=curriculum,
                channel_id=CHANNEL_ID,
                run_budget_cents=1000.0,
            )

            assert summary.videos_rejected_off_channel == 1
            # Doesn't assume the table starts empty - a real `make youtube-sync` run
            # against the shared dev Postgres may already have synced these same
            # fixture videos (same reasoning as the idempotency test above).
            assert summary.videos_created + summary.videos_updated == len(DEFAULT_VIDEOS)
            rejected = await repo.get_video("not-khan-academy-video")
            assert rejected is None

    asyncio.run(run())


def test_verification_pass_marks_gone_video_inactive_and_reverses() -> None:
    """S27: `sync_channel` runs a `get_video_details` verification pass after upsert -
    an unavailable video is marked inactive with `verification_failures` incremented;
    a later sync where it verifies as available again resets the failure count
    (reversible, same posture as `mark_inactive_except`)."""

    async def run() -> None:
        async with _rollback_session() as session:
            repo = YoutubeRepository(session)
            provider = FakeYoutubeProvider()
            curriculum = load_curriculum()

            provider.details["ka-one-step-eq"] = VideoDetails(available=False)
            summary = await sync_channel(
                repo,
                provider=provider,
                gateway=_gateway(),
                curriculum=curriculum,
                channel_id=CHANNEL_ID,
                run_budget_cents=1000.0,
            )
            assert summary.videos_failed_verification == 1

            failed = await repo.get_video("ka-one-step-eq")
            assert failed is not None
            assert failed.active_status == "inactive"
            assert failed.verification_failures == 1
            assert failed.last_verified_at is not None

            # It never surfaces from a learning-time search while inactive.
            results = await repo.search_catalog(query_embedding=[0.0] * 1024, limit=10)
            assert "ka-one-step-eq" not in [v.youtube_video_id for v in results]

            provider.details["ka-one-step-eq"] = VideoDetails(
                available=True, transcript_available=True
            )
            second = await sync_channel(
                repo,
                provider=provider,
                gateway=_gateway(),
                curriculum=curriculum,
                channel_id=CHANNEL_ID,
                run_budget_cents=1000.0,
            )
            assert second.videos_failed_verification == 0

            recovered = await repo.get_video("ka-one-step-eq")
            assert recovered is not None
            # `upsert_video` (this re-sync fetched it again) already reset
            # active_status to "active"; verification then confirms it and zeroes the
            # failure count.
            assert recovered.active_status == "active"
            assert recovered.verification_failures == 0
            assert recovered.transcript_available is True
            assert recovered.transcript_language == recovered.language

    asyncio.run(run())
