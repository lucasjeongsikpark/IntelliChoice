"""CLI entrypoint for the S12 RAG ingestion pipeline (SPEC §5.21.1).

Run with: uv run python -m intellichoice_knowledge.ingest_cli

Mirrors `intellichoice_curriculum.pipeline_cli`'s shape (own engine, own session,
`make` target, provider selection off a `bedrock_provider` setting). Safe to re-run -
`ingest_entry`'s `source_sha256` check means an unchanged document is a no-op, not a
duplicate insert (SPEC §5.20's idempotent-ingestion "Done when" criterion).
"""

import asyncio

from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_adapters.bedrock.titan_embedding_provider import TitanEmbeddingProvider
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_shared.bedrock import BedrockTask, CostBudgetExceededError

from intellichoice_knowledge.content_store import LocalFilesystemContentStore
from intellichoice_knowledge.ingest import run_ingestion
from intellichoice_knowledge.settings import KnowledgeIngestSettings, get_ingest_settings


def _build_gateway(settings: KnowledgeIngestSettings) -> ResilientBedrockGateway:
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
        model_registry={BedrockTask.EMBEDDING: settings.bedrock_embedding_model_id},
        call_timeout_s=settings.bedrock_call_timeout_s,
        max_retries=settings.bedrock_max_retries,
        circuit_failure_threshold=settings.bedrock_circuit_failure_threshold,
        circuit_cooldown_s=settings.bedrock_circuit_cooldown_s,
        session_budget_cents=settings.bedrock_run_budget_cents,
    )


async def main() -> None:
    settings = get_ingest_settings()
    gateway = _build_gateway(settings)
    content_store = LocalFilesystemContentStore()
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            try:
                summary = await run_ingestion(
                    session,
                    content_store=content_store,
                    gateway=gateway,
                    run_budget_cents=settings.bedrock_run_budget_cents,
                    embedding_provider=settings.bedrock_provider,
                )
            except CostBudgetExceededError as exc:
                print(f"run budget exceeded: {exc}")
                raise
            await session.commit()
        print(
            f"Ingestion complete: {summary.documents_created} created, "
            f"{summary.documents_updated} updated, {summary.documents_unchanged} "
            f"unchanged, {summary.chunks_created} chunks written, "
            f"{summary.total_cost_cents:.4f} cents spent."
        )
        for document_id, outcome in summary.entries:
            print(f"  {outcome}: {document_id}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
