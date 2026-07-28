"""CLI entrypoint for the AUD-C-16 re-embed path.

Run with: uv run python -m intellichoice_knowledge.reembed_cli
(or `make knowledge-reembed`)

Re-embeds every rag_chunks row whose embedding provenance does not match the configured
`KNOWLEDGE_BEDROCK_PROVIDER` + `KNOWLEDGE_BEDROCK_EMBEDDING_MODEL_ID`. Safe to re-run:
a corpus already embedded by the configured model is a no-op, so this runs on every
staging deploy (after migrations, before rollout - chat-api's /readyz fails closed on a
mismatched corpus, so the corpus must be fixed before the new tasks take traffic).
"""

import asyncio

from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_shared.bedrock import CostBudgetExceededError

from intellichoice_knowledge.ingest_cli import _build_gateway
from intellichoice_knowledge.reembed import run_reembed
from intellichoice_knowledge.settings import get_ingest_settings


async def main() -> None:
    settings = get_ingest_settings()
    gateway = _build_gateway(settings)
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            try:
                summary = await run_reembed(
                    session,
                    gateway=gateway,
                    embedding_provider=settings.bedrock_provider,
                    embedding_model_id=settings.bedrock_embedding_model_id,
                    run_budget_cents=settings.bedrock_run_budget_cents,
                )
            except CostBudgetExceededError as exc:
                print(f"run budget exceeded: {exc}")
                raise
            await session.commit()
        print(
            f"Reembed complete: {summary.chunks_reembedded} chunks reembedded across "
            f"{summary.documents_touched} documents, {summary.chunks_already_current} "
            f"already current, {summary.total_cost_cents:.4f} cents spent."
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
