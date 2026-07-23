"""CLI entrypoint for the S25 weekly memory consolidation worker (SPEC §5.15.4).

Run with: uv run python -m intellichoice_memory.consolidate_cli

Mirrors `intellichoice_youtube.sync_cli`'s shape (own engine, own session, `make`
target, provider selection off a `bedrock_provider` setting). Manual trigger only this
session - a real EventBridge Sunday schedule is later infra work (same "schedule later"
posture as `youtube-sync`/`webcontent-sync`). Idempotent per (student, week) - see
`consolidation.consolidate_student_window`'s own docstring.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.repositories.memory import MemoryRepository
from intellichoice_db.repositories.tutor_chat import TutorChatMessageRepository
from intellichoice_shared.bedrock import BedrockTask

from intellichoice_memory.consolidation import consolidate_student_window
from intellichoice_memory.settings import MemoryConsolidationSettings, get_consolidation_settings


def _build_gateway(settings: MemoryConsolidationSettings) -> ResilientBedrockGateway:
    if settings.bedrock_provider == "bedrock":
        provider = AnthropicBedrockProvider(aws_region=settings.bedrock_aws_region)
    else:
        provider = MockBedrockProvider()
    return ResilientBedrockGateway(
        provider=provider,
        model_registry={
            BedrockTask.MEMORY_CONSOLIDATION: settings.bedrock_consolidation_model_id,
        },
        call_timeout_s=settings.bedrock_call_timeout_s,
        max_retries=settings.bedrock_max_retries,
        circuit_failure_threshold=settings.bedrock_circuit_failure_threshold,
        circuit_cooldown_s=settings.bedrock_circuit_cooldown_s,
        session_budget_cents=settings.bedrock_run_budget_cents,
    )


async def main() -> None:
    settings = get_consolidation_settings()
    gateway = _build_gateway(settings)
    window_end = datetime.now(UTC)
    window_start = window_end - timedelta(days=settings.window_days)

    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            student_ids = await memory_repo.list_students_with_events_in_window(
                window_start, window_end
            )
            spend = 0.0
            total_added = total_updated = total_contested = total_expired = 0
            for student_id in student_ids:
                if spend >= settings.bedrock_run_budget_cents:
                    print(
                        f"run budget of {settings.bedrock_run_budget_cents} cents "
                        "reached - stopping early"
                    )
                    break
                result = await consolidate_student_window(
                    memory_repo=memory_repo,
                    tutor_chat_repo=tutor_chat_repo,
                    gateway=gateway,
                    student_external_id=student_id,
                    window_start=window_start,
                    window_end=window_end,
                    session_spend_cents=spend,
                )
                spend += result.cost_cents
                total_added += result.added
                total_updated += result.updated
                total_contested += result.contested
                total_expired += result.expired
                print(
                    f"  {student_id}: +{result.added} facts, {result.updated} "
                    f"reconfirmed, {result.contested} contested, {result.expired} "
                    f"expired ({result.cost_cents:.4f} cents)"
                )
            await session.commit()
        print(
            f"Consolidation run complete: {len(student_ids)} student(s), "
            f"{total_added} added, {total_updated} reconfirmed, {total_contested} "
            f"contested, {total_expired} expired, {spend:.2f} cents spent."
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
