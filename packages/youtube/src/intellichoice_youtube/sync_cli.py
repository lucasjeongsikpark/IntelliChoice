"""CLI entrypoint for the S15 YouTube catalog sync worker (SPEC §5.18.1).

Run with: uv run python -m intellichoice_youtube.sync_cli

Mirrors `intellichoice_knowledge.ingest_cli`'s shape (own engine, own session, `make`
target, provider selection off a `bedrock_provider` setting). Manual trigger only this
session - a real EventBridge-style weekly schedule is later infra work (same posture as
S12's `make knowledge-load`).
"""

import asyncio

from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_adapters.bedrock.titan_embedding_provider import TitanEmbeddingProvider
from intellichoice_adapters.fake_youtube import FakeYoutubeProvider
from intellichoice_adapters.youtube_data_api_provider import YoutubeDataApiProvider
from intellichoice_curriculum.content import CurriculumContent, load_curriculum
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.repositories.youtube import YoutubeRepository
from intellichoice_shared.bedrock import BedrockTask
from intellichoice_shared.youtube import YoutubeProvider

from intellichoice_youtube.catalog_sync import YoutubeSyncError, sync_channel
from intellichoice_youtube.settings import (
    YoutubeSyncSettings,
    check_real_sync_preflight,
    check_search_quota,
    get_sync_settings,
)


def _build_gateway(settings: YoutubeSyncSettings) -> ResilientBedrockGateway:
    if settings.bedrock_provider == "bedrock":
        chat_provider = AnthropicBedrockProvider(aws_region=settings.bedrock_aws_region)
        embedding_provider = TitanEmbeddingProvider(aws_region=settings.bedrock_aws_region)
    else:
        mock = MockBedrockProvider()
        chat_provider = mock
        embedding_provider = mock

    return ResilientBedrockGateway(
        provider=chat_provider,
        embedding_provider=embedding_provider,
        model_registry={
            BedrockTask.VIDEO_CLASSIFICATION: settings.bedrock_classification_model_id,
            BedrockTask.EMBEDDING: settings.bedrock_embedding_model_id,
        },
        call_timeout_s=settings.bedrock_call_timeout_s,
        max_retries=settings.bedrock_max_retries,
        circuit_failure_threshold=settings.bedrock_circuit_failure_threshold,
        circuit_cooldown_s=settings.bedrock_circuit_cooldown_s,
        session_budget_cents=settings.bedrock_run_budget_cents,
    )


def saw_whole_channel(covered: int, deferred: int) -> bool:
    """May this run deactivate catalog rows it did not encounter?

    Only if it searched **every** skill. Two independent reasons it might not have:

    - `deferred > 0` - the quota cap cut the term list (D-326 addendum's case).
    - `covered > 0` - the resumable selection deliberately skips skills that already have a
      servable video, so **their** videos are absent from `seen_ids` by construction.

    **The second reason was missed, and it did real damage.** D-326's addendum guarded only on
    `deferred == 0` while its own comment described the resumability case correctly. On staging
    2026-08-15 a run with `covered=72, deferred=0` evaluated this as "saw everything" and marked
    **182 videos inactive** - the entire previously-active catalog, found by earlier runs'
    searches. Net coverage still rose 72 -> 76 skills, which is precisely why it was easy to miss:
    the headline improved while the catalog was replaced underneath it.

    That is the same failure D-326's addendum was written to prevent, reproduced by an incomplete
    version of its own fix. Tested here rather than only through `sync_channel`, because the
    existing tests passed this flag *in* - they exercised its effect and never its computation.
    """
    return covered == 0 and deferred == 0


async def _pending_search_terms(
    repo: YoutubeRepository, settings: YoutubeSyncSettings, curriculum: CurriculumContent
) -> tuple[list[str], int, int]:
    """The skill names to search this run: uncovered skills first, capped to the quota.

    **Why the order matters (D-326).** A full run costs 112 x 100 = 11,200 quota units
    against a 10,000/day default, so the catalog has to be built over several days. Taking
    the first N skills each time would redo the same prefix every day and never reach the
    tail. Asking the catalog which skills already have a servable video makes each run pick
    up where the last one stopped, using the existence check `has_servable_video` already
    performs for the serving path.

    Returns `(terms, already_covered, skipped_for_quota)` so the caller can print what the
    run is *not* doing - a cap that silently drops work reads as a completed sync.

    One honest limitation: a skill whose search genuinely returns nothing stays "uncovered"
    and will be retried on every later run. That is the right default (content appears over
    time) but it means the pending list does not converge to empty on its own.
    """
    uncovered: list[str] = []
    covered = 0
    for skill in curriculum.skills:
        if await repo.has_servable_video(skill.skill_id):
            covered += 1
        else:
            uncovered.append(skill.name)
    if settings.max_search_terms > 0:
        selected = uncovered[: settings.max_search_terms]
    else:
        selected = uncovered
    return selected, covered, len(uncovered) - len(selected)


def _build_provider(
    settings: YoutubeSyncSettings, search_terms: list[str]
) -> YoutubeProvider:
    if settings.youtube_provider == "youtube":
        # `fake` stays the dev default (D-002's posture, same footing as Gmail/Calendar/
        # Maps). `check_real_sync_preflight` has already refused a run that cannot work,
        # so reaching here means key and channel id are both present and well-shaped.
        #
        # D-209: the search terms are **the curriculum's own skill names**, not a
        # hand-written list. That keeps the same "code decides what to ask for, the model
        # only judges what comes back" split the rest of this pipeline has, and it means
        # adding a skill automatically widens the catalog rather than silently leaving a
        # gap. Measured against Khan Academy: all five linear-equations skills returned
        # their intended videos.
        return YoutubeDataApiProvider(
            api_key=settings.youtube_api_key,
            max_videos=settings.max_videos,
            # D-326: the *pending* skills, not every skill - see `_pending_search_terms`.
            search_terms=search_terms,
            per_term=settings.search_results_per_skill,
        )
    return FakeYoutubeProvider()


async def main() -> None:
    settings = get_sync_settings()
    # D-207: before the engine, before the gateway, before anything billable.
    check_real_sync_preflight(settings)
    gateway = _build_gateway(settings)
    curriculum = load_curriculum()
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            repo = YoutubeRepository(session)
            # D-326: which terms this run owes depends on what the catalog already holds, so
            # the provider is built here rather than before the session opens.
            terms, covered, deferred = await _pending_search_terms(repo, settings, curriculum)
            check_search_quota(settings, len(terms))
            print(
                f"{covered} of {len(curriculum.skills)} skills already have a servable video; "
                f"searching {len(terms)} this run"
                + (f", deferring {deferred} to a later run (quota cap)" if deferred else "")
            )
            if not terms:
                print("nothing pending - every skill already has a servable video.")
                return
            provider = _build_provider(settings, terms)
            try:
                summary = await sync_channel(
                    repo,
                    provider=provider,
                    gateway=gateway,
                    curriculum=curriculum,
                    channel_id=settings.channel_id,
                    run_budget_cents=settings.bedrock_run_budget_cents,
                    saw_whole_channel=saw_whole_channel(covered, deferred),
                )
            except YoutubeSyncError as exc:
                print(f"sync failed, previous catalog left untouched: {exc}")
                raise
            await session.commit()
        print(
            f"Sync complete: {summary.videos_created} created, "
            f"{summary.videos_updated} updated, "
            f"{summary.videos_marked_inactive} marked inactive, "
            f"{summary.videos_rejected_off_channel} rejected (off-channel), "
            f"{summary.videos_failed_verification} failed verification, "
            f"{summary.total_cost_cents:.4f} cents spent."
        )
        for youtube_video_id, outcome in summary.entries:
            print(f"  {outcome}: {youtube_video_id}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
