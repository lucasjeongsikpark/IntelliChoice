"""SPEC §5.11.6/§5.18.3 video option - S15 replaced the S10 hardcoded stub map with a
real Postgres catalog (`youtube_videos`) queried through the `youtube_catalog.search`
MCP tool. Real Postgres via the same rollback-session pattern as `packages/knowledge/
tests/test_ingest.py` (D-013). Skips cleanly when Postgres is unreachable (D-008).
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_db.engine import create_engine
from intellichoice_db.models.mcp import McpToolCall
from intellichoice_db.models.youtube import YoutubeVideo
from intellichoice_db.repositories.mcp import McpToolCallRepository
from intellichoice_db.repositories.youtube import YoutubeRepository
from intellichoice_shared.bedrock import BedrockGenerationResult, BedrockTask
from learning_api.services import video_catalog
from pydantic import BaseModel
from sqlalchemy import select, text
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
        model_registry={BedrockTask.EMBEDDING: "amazon.titan-embed-text-v2:0"},
    )


def test_search_video_returns_a_seeded_catalog_match() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            repo = YoutubeRepository(session)
            gateway = _gateway()
            await repo.upsert_video(
                YoutubeVideo(
                    youtube_video_id="zqxvvc-one-step",
                    channel_id="zqxvvc-channel",
                    channel_title="Khan Academy",
                    video_url="https://example.test/one-step",
                    title="Solve one-step linear equations",
                    description="An intro video.",
                    playlist_ids=[],
                    duration="PT5M",
                    published_at=datetime(2024, 1, 1, tzinfo=UTC),
                    thumbnail_url="https://example.test/thumb.jpg",
                    language="en",
                    topic_ids=["linear_equations"],
                    skill_ids=["zqxvvc_one_step"],
                    grade_band="3-5",
                    difficulty_min=1,
                    difficulty_max=3,
                    embedding=(await gateway.create_embedding(
                        texts=["Solve one-step linear equations"], session_spend_cents=0.0
                    )).vectors[0],
                    last_synced_at=datetime.now(UTC),
                )
            )

            video, cost = await video_catalog.search_video(
                repo=repo,
                gateway=gateway,
                mcp_call_repo=McpToolCallRepository(session),
                caller_external_id="zqxvvc-caller-1",
                skill_id="zqxvvc_one_step",
                skill_name="Solve one-step linear equations",
                difficulty=2,
                session_spend_cents=0.0,
            )
            assert video is not None
            assert video.video_id == "zqxvvc-one-step"
            assert video.source == "Khan Academy"
            assert cost > 0.0

            # Filtered on a nonsense marker caller id (D-018's pattern), not just the
            # real tool name - other tests' real, committed `TestClient(app)` HTTP
            # calls (unlike this rollback-isolated session) also legitimately call
            # `youtube_catalog.search` for real fixture students, so an exact global
            # count against the tool name alone would be environment-dependent.
            audit_rows = await session.execute(
                select(McpToolCall).where(
                    McpToolCall.tool_name == "youtube_catalog.search",
                    McpToolCall.caller_external_id == "zqxvvc-caller-1",
                )
            )
            rows = list(audit_rows.scalars().all())
            assert len(rows) == 1
            assert rows[0].success is True

    asyncio.run(run())


def test_search_video_falls_back_when_no_catalog_match() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            repo = YoutubeRepository(session)
            gateway = _gateway()

            video, cost = await video_catalog.search_video(
                repo=repo,
                gateway=gateway,
                mcp_call_repo=McpToolCallRepository(session),
                caller_external_id="zqxvvc-caller-1",
                skill_id="zqxvvc_no_such_skill",
                skill_name="Some skill with no seeded video",
                difficulty=1,
                session_spend_cents=0.0,
            )
            assert video is None
            # D-305: `>= 0.0` was vacuous - it holds for a free call and a paid one alike.
            # A skill with no video is a foregone conclusion, so it must cost nothing.
            assert cost == 0.0
            assert "not currently available" in video_catalog.FALLBACK_MESSAGE

    asyncio.run(run())


def test_an_empty_catalog_falls_back_without_paying_for_an_embedding() -> None:
    """D-207: the §5.11.6 outcome is already decided when nothing is servable, so the
    embedding call must not happen at all.

    This is not hypothetical tidying. Staging's `youtube_videos` has been empty since the
    environment was built - the sync worker has never been part of a deploy - so *every*
    "Watch a video" a student clicked bought a Titan embedding and then returned the
    fallback message anyway. Measured live at 2026-08-06T20:13:51Z: one
    `bedrock_embedding_call`, 144.73 ms, for a foregone conclusion.

    `_CountingGateway` rather than an assertion on cost alone: a zero cost could also mean
    "the embedding was free", which would let a regression through. Counting the calls says
    the thing the test is actually about.
    """

    class _CountingGateway:
        def __init__(self) -> None:
            self.embed_calls = 0

        async def create_embedding(self, *, texts: list[str], session_spend_cents: float):
            self.embed_calls += 1
            raise AssertionError("an empty catalog must not reach the embedding provider")

    async def run() -> None:
        async with _rollback_session() as session:
            # Inside the rollback transaction, so this empties the catalog for this test
            # only - the seeded rows other tests in this file rely on are restored when
            # the transaction rolls back.
            await session.execute(text("DELETE FROM youtube_videos"))
            gateway = _CountingGateway()

            video, cost = await video_catalog.search_video(
                repo=YoutubeRepository(session),
                gateway=gateway,  # type: ignore[arg-type]
                mcp_call_repo=McpToolCallRepository(session),
                caller_external_id="zqxvvc-caller-1",
                skill_id="linear_one_step",
                skill_name="Solve one-step linear equations",
                difficulty=1,
                session_spend_cents=0.0,
            )
            assert video is None
            assert cost == 0.0
            assert gateway.embed_calls == 0

    asyncio.run(run())


class _CapturingGateway:
    """S27 query-enrichment proof: records the exact text handed to `create_embedding`
    (delegating the real work to the wrapped gateway) so a test can assert the
    misconception/grade-band/mastery-state enrichment actually reaches the embedding
    call - not just that `search_video` accepts the new parameters. Mirrors
    `test_tutor_service.py`'s own `_CapturingGateway` pattern.
    """

    def __init__(self, inner: ResilientBedrockGateway) -> None:
        self._inner = inner
        self.embed_texts: list[list[str]] = []

    async def generate_structured[T: BaseModel](
        self,
        *,
        task: BedrockTask,
        system_prompt: str,
        payload: BaseModel,
        response_model: type[T],
        max_output_tokens: int,
        session_spend_cents: float,
    ) -> BedrockGenerationResult[T]:
        raise NotImplementedError

    async def create_embedding(self, *, texts: list[str], session_spend_cents: float):
        self.embed_texts.append(list(texts))
        return await self._inner.create_embedding(
            texts=texts, session_spend_cents=session_spend_cents
        )


def test_search_video_enriches_the_embedding_query_with_available_context() -> None:
    """S27 (SPEC §5.18.3 query enrichment): misconception tag/grade band/mastery state
    widen the embedding query text only - `skill_id`/`difficulty` stay the only hard
    filters, so the enriched query still costs exactly one embedding call and still
    finds the same catalog match.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            repo = YoutubeRepository(session)
            gateway = _CapturingGateway(_gateway())
            await repo.upsert_video(
                YoutubeVideo(
                    youtube_video_id="zqxvvc-enriched",
                    channel_id="zqxvvc-channel",
                    channel_title="Khan Academy",
                    video_url="https://example.test/enriched",
                    title="Solve two-step linear equations",
                    description="A follow-up video.",
                    playlist_ids=[],
                    duration="PT5M",
                    published_at=datetime(2024, 1, 1, tzinfo=UTC),
                    thumbnail_url="https://example.test/thumb.jpg",
                    language="en",
                    topic_ids=["linear_equations"],
                    skill_ids=["zqxvvc_two_step"],
                    grade_band="6-7",
                    difficulty_min=1,
                    difficulty_max=3,
                    embedding=(
                        await gateway.create_embedding(
                            texts=["Solve two-step linear equations"],
                            session_spend_cents=0.0,
                        )
                    ).vectors[0],
                    last_synced_at=datetime.now(UTC),
                )
            )
            gateway.embed_texts.clear()  # only the search call below matters

            video, cost = await video_catalog.search_video(
                repo=repo,
                gateway=gateway,
                mcp_call_repo=McpToolCallRepository(session),
                caller_external_id="zqxvvc-caller-2",
                skill_id="zqxvvc_two_step",
                skill_name="Solve two-step linear equations",
                difficulty=2,
                session_spend_cents=0.0,
                misconception_tag="sign_error",
                grade_band="6-7",
                mastery_state="weak_skill",
            )
            assert video is not None
            assert video.video_id == "zqxvvc-enriched"
            assert cost > 0.0

            assert len(gateway.embed_texts) == 1
            enriched_query = gateway.embed_texts[0][0]
            assert "Solve two-step linear equations" in enriched_query
            assert "sign_error" in enriched_query
            assert "6-7" in enriched_query
            assert "weak_skill" in enriched_query

    asyncio.run(run())


def test_a_skill_with_no_video_pays_nothing_even_when_the_catalog_is_not_empty() -> None:
    """D-305: the case D-207's guard was scoped to miss, and D-302 made it the common path.

    D-207 short-circuited the embedding when the catalog was **empty**, and said the skill
    filter belonged only in `search_catalog` because "a semantic rank is the thing deciding
    that". It is not: `search_catalog` applies `skill_id in v.skill_ids` as a hard filter
    *before* it ranks, so a skill with no video cannot match however good the embedding is.

    That scoping was right while staging held zero rows - "the catalog is empty" and "this
    skill has nothing" were then the same question. A sparse catalog separates them: dev holds
    4 videos covering 4 of 112 skills, so 108 skills would each buy a Titan embedding per
    "Watch a video" to reach a conclusion one indexed read already knows. D-302 opened all 33
    topics, and only one of them has any video at all.

    Counts calls rather than trusting cost, for the reason the empty-catalog test gives: a
    zero cost could also mean the embedding happened to be free.
    """

    class _CountingGateway:
        def __init__(self) -> None:
            self.embed_calls = 0

        async def create_embedding(self, *, texts: list[str], session_spend_cents: float):
            self.embed_calls += 1
            raise AssertionError("a skill with no servable video must not reach the provider")

    async def run() -> None:
        async with _rollback_session() as session:
            repo = YoutubeRepository(session)
            # The catalog is NOT empty - this is the whole point. The seeded rows cover
            # `linear_*` skills, so the guard cannot short-circuit on emptiness.
            assert await repo.has_servable_video() is True
            assert await repo.has_servable_video("zqxvvc_no_such_skill") is False

            gateway = _CountingGateway()
            video, cost = await video_catalog.search_video(
                repo=repo,
                gateway=gateway,  # type: ignore[arg-type]
                mcp_call_repo=McpToolCallRepository(session),
                caller_external_id="zqxvvc-caller-1",
                skill_id="zqxvvc_no_such_skill",
                skill_name="Some skill with no seeded video",
                difficulty=1,
                session_spend_cents=0.0,
            )
            assert video is None
            assert cost == 0.0
            assert gateway.embed_calls == 0

    asyncio.run(run())


def test_a_skill_that_does_have_a_video_still_reaches_the_ranker() -> None:
    """The recall half: the guard must not turn into a blanket refusal.

    Without this, scoping the existence check by skill would pass its own test by never
    serving a video at all - the same shape as the vacuous `cost >= 0.0` above.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            repo = YoutubeRepository(session)
            assert await repo.has_servable_video("linear_one_step") is True

            video, _cost = await video_catalog.search_video(
                repo=repo,
                gateway=_gateway(),
                mcp_call_repo=McpToolCallRepository(session),
                caller_external_id="zqxvvc-caller-1",
                skill_id="linear_one_step",
                skill_name="Solve one-step linear equations",
                # The seeded `ka-one-step-eq` fixture spans difficulty 2-4. Asking for 1
                # returned None and my first version of this test read that as the guard
                # over-refusing - it was the difficulty filter doing its job.
                difficulty=2,
                session_spend_cents=0.0,
            )
            assert video is not None, "a skill with a seeded video must still be served one"

    asyncio.run(run())
