"""CLI entrypoint for the S25 weekly memory consolidation worker (SPEC §5.15.4).

Run with: uv run python -m intellichoice_memory.consolidate_cli

Mirrors `intellichoice_youtube.sync_cli`'s shape (own engine, own session, `make`
target, provider selection off a `bedrock_provider` setting). Manual trigger only this
session - a real EventBridge Sunday schedule is later infra work (same "schedule later"
posture as `youtube-sync`/`webcontent-sync`). Idempotent per (student, *window*) - the
window is the rolling `[now - window_days, now)` computed below, deliberately not
snapped to a calendar week (see `settings.window_days`), so two runs on the same day
see different windows. The looser "per (student, week)" wording this replaces was read
as an ISO-week bucket during D-149 and is not one.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.repositories.mastery import MasteryRepository
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


async def main() -> int:
    """Returns a process exit code.

    **Non-zero when every model call in the run failed (AUD-F-34, D-141).** That is not
    defensive coding, it is the difference between this job being findable and not: the ECS
    failure rule that watches these runs matches `containers.exitCode: [{"anything-but": [0]}]`,
    so a run that catches its own errors and returns 0 is invisible in every console - which is
    how a job that had never once succeeded went unnoticed until it was run by hand.

    Partial failure deliberately stays exit 0 and is reported in the summary line instead: the
    gateway already retries, one student's bad batch should not page anyone, and a rule that
    fires on any failure would be turned off within a month. `run budget reached` is not a
    failure at all and is counted separately.
    """
    settings = get_consolidation_settings()
    gateway = _build_gateway(settings)
    window_end = datetime.now(UTC)
    window_start = window_end - timedelta(days=settings.window_days)

    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            memory_repo = MemoryRepository(session)
            mastery_repo = MasteryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            student_ids = await memory_repo.list_students_with_events_in_window(
                window_start, window_end
            )
            spend = 0.0
            total_added = total_updated = total_contested = total_expired = 0
            # AUD-L-13 (D-156): ability facts refused for contradicting the measured
            # mastery score. Surfaced per-student and in the run summary because the rate
            # is the signal - a spike means the prompt drifted or mastery went stale, and
            # neither is visible from `added` alone.
            total_mastery_conflicts = 0
            total_attempted = total_failed = total_dropped = 0
            students_processed = 0
            students_skipped = 0
            for index, student_id in enumerate(student_ids):
                if spend >= settings.bedrock_run_budget_cents:
                    # D-153: name the students who were NOT consolidated. The summary line
                    # below used to report `len(student_ids)`, so a run that stopped at 700
                    # of 1,000 announced "1000 student(s)" and the 300 who were skipped were
                    # invisible - `0 added` for a student who was never attempted reads
                    # exactly like `0 added` for a student with nothing to consolidate.
                    students_skipped = len(student_ids) - index
                    print(
                        f"run budget of {settings.bedrock_run_budget_cents} cents reached - "
                        f"stopping early. {students_skipped} student(s) NOT consolidated this "
                        "run; they are not queued anywhere and the next run re-derives its own "
                        "list, so a persistently over-budget run silently starves the tail."
                    )
                    break
                students_processed += 1
                result = await consolidate_student_window(
                    memory_repo=memory_repo,
                    mastery_repo=mastery_repo,
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
                total_attempted += result.calls_attempted
                total_failed += result.calls_failed
                total_dropped += result.events_dropped
                total_mastery_conflicts += result.mastery_conflicts
                detail = (
                    f" [{result.calls_failed}/{result.calls_attempted} call(s) FAILED]"
                    if result.calls_failed
                    else ""
                )
                if result.events_dropped:
                    detail += f" [{result.events_dropped} event(s) dropped over the call cap]"
                if result.mastery_conflicts:
                    detail += (
                        f" [{result.mastery_conflicts} fact(s) refused: contradicted "
                        "measured mastery]"
                    )
                print(
                    f"  {student_id}: +{result.added} facts, {result.updated} "
                    f"reconfirmed, {result.contested} contested, {result.expired} "
                    f"expired ({result.cost_cents:.4f} cents){detail}"
                )
            await session.commit()
        # The counts go in the summary line unconditionally, including the zeros. The old line
        # said "complete" and nothing else, so a run in which nothing worked read exactly like a
        # run with nothing to do - and `0 added` is the correct output for both.
        skipped_note = f", {students_skipped} SKIPPED (over budget)" if students_skipped else ""
        print(
            f"Consolidation run complete: {students_processed} of {len(student_ids)} "
            f"student(s){skipped_note}, "
            f"{total_added} added, {total_updated} reconfirmed, {total_contested} "
            f"contested, {total_expired} expired, {spend:.2f} cents spent; "
            f"{total_attempted} model call(s), {total_failed} failed, "
            f"{total_dropped} event(s) dropped, "
            f"{total_mastery_conflicts} refused (contradicted mastery)."
        )
        if total_attempted and total_failed == total_attempted:
            print(
                f"FAILED: all {total_attempted} model call(s) failed and no fact changed. "
                "Exiting non-zero so the ops-task failure alarm fires (AUD-F-34)."
            )
            return 1
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
