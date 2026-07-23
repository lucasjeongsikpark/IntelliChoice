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
from intellichoice_curriculum.content import load_curriculum
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.repositories.youtube import YoutubeRepository
from intellichoice_shared.bedrock import BedrockTask
from intellichoice_shared.youtube import YoutubeProvider

from intellichoice_youtube.catalog_sync import YoutubeSyncError, sync_channel
from intellichoice_youtube.settings import YoutubeSyncSettings, get_sync_settings


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


def _build_provider(settings: YoutubeSyncSettings) -> YoutubeProvider:
    if settings.youtube_provider == "youtube":
        # Real YouTube Data API credentials don't exist yet (D-002's posture, same
        # footing as Gmail/Calendar/Maps) - unexercised until a real `youtube_api_key`
        # is configured; `fake` stays the dev default.
        return YoutubeDataApiProvider(api_key=settings.youtube_api_key)
    return FakeYoutubeProvider()


async def main() -> None:
    settings = get_sync_settings()
    gateway = _build_gateway(settings)
    provider = _build_provider(settings)
    curriculum = load_curriculum()
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            repo = YoutubeRepository(session)
            try:
                summary = await sync_channel(
                    repo,
                    provider=provider,
                    gateway=gateway,
                    curriculum=curriculum,
                    channel_id=settings.channel_id,
                    run_budget_cents=settings.bedrock_run_budget_cents,
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
