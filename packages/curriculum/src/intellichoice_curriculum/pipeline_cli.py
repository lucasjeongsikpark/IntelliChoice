"""CLI entrypoint for the S9 AI question-generation pipeline (SPEC §5.8.3).

Run with: uv run python -m intellichoice_curriculum.pipeline_cli

Mirrors `loader.py`'s standalone-script shape (own engine, own session, `make`
target) but is NOT idempotent the way the hand-authored loader is - every run
proposes fresh candidates (new seeds), since the whole point is generating volume
beyond the S4 seed bank. Re-running is safe: `generate_candidate`'s dedup check
means a re-proposed duplicate question is rejected, not double-inserted.

Every candidate that passes the full pipeline lands at `validation_status="pending"`,
never auto-activated by this script (see `ai_pipeline`'s module docstring and D-026) -
review and activate deliberately, e.g. via a REPL call to
`QuestionRepository.activate_template` after spot-checking `--dry-run`'s output, or a
future admin tool. This is intentionally conservative for content served to K-12
students.
"""

import argparse
import asyncio
from dataclasses import dataclass, field

from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_adapters.bedrock.titan_embedding_provider import TitanEmbeddingProvider
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_shared.bedrock import BedrockGateway, BedrockTask, CostBudgetExceededError
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_curriculum.ai_pipeline import (
    DIFFICULTY_SHAPES,
    TOPIC_DIFFICULTY_SKILLS,
    PipelineOutcome,
    generate_authored_candidate,
    generate_candidate,
)
from intellichoice_curriculum.content import load_curriculum
from intellichoice_curriculum.settings import CurriculumPipelineSettings, get_pipeline_settings

_SEED_BASE = 1000  # Well clear of the S4 hand-authored bank's seeds (0-9 per difficulty).
# S20 authored mode uses its own seed range so a shape-pipeline run and an authored-
# pipeline run against the same topic/difficulty never propose colliding template ids.
_AUTHORED_SEED_BASE = 5000


@dataclass
class RunSummary:
    pending: int = 0
    rejected: int = 0
    total_cost_cents: float = 0.0
    rejections: list[tuple[str, int, list[str]]] = field(default_factory=list)


async def run_pipeline(
    session: AsyncSession,
    gateway: BedrockGateway,
    *,
    candidates_per_difficulty: int = 2,
    run_budget_cents: float = 1000.0,
) -> RunSummary:
    curriculum = load_curriculum()
    summary = RunSummary()
    spend = 0.0

    for topic_id, difficulty_shapes in sorted(DIFFICULTY_SHAPES.items()):
        for difficulty_label in sorted(difficulty_shapes):
            for i in range(candidates_per_difficulty):
                if spend >= run_budget_cents:
                    print(f"run budget of {run_budget_cents} cents reached - stopping early")
                    return summary
                seed = _SEED_BASE + difficulty_label * 100 + i
                outcome: PipelineOutcome = await generate_candidate(
                    session=session,
                    gateway=gateway,
                    curriculum=curriculum,
                    topic_id=topic_id,
                    difficulty_label=difficulty_label,
                    seed=seed,
                    session_spend_cents=spend,
                )
                spend += outcome.cost_cents
                summary.total_cost_cents += outcome.cost_cents
                if outcome.status == "pending":
                    summary.pending += 1
                else:
                    summary.rejected += 1
                    summary.rejections.append((topic_id, difficulty_label, outcome.reasons))
    return summary


async def run_authored_pipeline(
    session: AsyncSession,
    gateway: BedrockGateway,
    *,
    candidates_per_difficulty: int = 2,
    run_budget_cents: float = 1000.0,
) -> RunSummary:
    """S20 (plan §7) counterpart to `run_pipeline` above, driving
    `generate_authored_candidate` over the same `TOPIC_DIFFICULTY_SKILLS` map instead of
    `DIFFICULTY_SHAPES` - authored mode has no shape allowlist to iterate.
    """
    curriculum = load_curriculum()
    summary = RunSummary()
    spend = 0.0

    for topic_id, difficulty_skills in sorted(TOPIC_DIFFICULTY_SKILLS.items()):
        for difficulty_label in sorted(difficulty_skills):
            for i in range(candidates_per_difficulty):
                if spend >= run_budget_cents:
                    print(f"run budget of {run_budget_cents} cents reached - stopping early")
                    return summary
                seed = _AUTHORED_SEED_BASE + difficulty_label * 100 + i
                outcome: PipelineOutcome = await generate_authored_candidate(
                    session=session,
                    gateway=gateway,
                    curriculum=curriculum,
                    topic_id=topic_id,
                    difficulty_label=difficulty_label,
                    seed=seed,
                    session_spend_cents=spend,
                )
                spend += outcome.cost_cents
                summary.total_cost_cents += outcome.cost_cents
                if outcome.status == "pending":
                    summary.pending += 1
                else:
                    summary.rejected += 1
                    summary.rejections.append((topic_id, difficulty_label, outcome.reasons))
    return summary


def _build_gateway(settings: CurriculumPipelineSettings) -> ResilientBedrockGateway:
    if settings.bedrock_provider == "bedrock":
        provider = AnthropicBedrockProvider(aws_region=settings.bedrock_aws_region)
        embedding_provider = TitanEmbeddingProvider(aws_region=settings.bedrock_aws_region)
    else:
        mock = MockBedrockProvider()
        provider = mock
        embedding_provider = mock
    return ResilientBedrockGateway(
        provider=provider,
        embedding_provider=embedding_provider,
        model_registry={
            BedrockTask.QUESTION_GENERATION: settings.bedrock_generation_model_id,
            BedrockTask.QUESTION_REVIEW: settings.bedrock_review_model_id,
            BedrockTask.AUTHORED_QUESTION_GENERATION: settings.bedrock_authored_generation_model_id,
            BedrockTask.QUESTION_JUDGE: settings.bedrock_judge_model_id,
            BedrockTask.EMBEDDING: settings.bedrock_embedding_model_id,
        },
        call_timeout_s=settings.bedrock_call_timeout_s,
        max_retries=settings.bedrock_max_retries,
        circuit_failure_threshold=settings.bedrock_circuit_failure_threshold,
        circuit_cooldown_s=settings.bedrock_circuit_cooldown_s,
        session_budget_cents=settings.bedrock_run_budget_cents,
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AI question-generation pipeline")
    parser.add_argument(
        "--mode",
        choices=["shape", "authored"],
        default="shape",
        help="'shape' (S9, parameterized templates) or 'authored' (S20, hand-quality "
        "items) - default: shape",
    )
    parser.add_argument(
        "--candidates-per-difficulty",
        type=int,
        default=2,
        help="Candidates to attempt per topic/difficulty pair (default: 2)",
    )
    args = parser.parse_args()

    settings = get_pipeline_settings()
    gateway = _build_gateway(settings)
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            try:
                run = run_authored_pipeline if args.mode == "authored" else run_pipeline
                summary = await run(
                    session,
                    gateway,
                    candidates_per_difficulty=args.candidates_per_difficulty,
                    run_budget_cents=settings.bedrock_run_budget_cents,
                )
            except CostBudgetExceededError as exc:
                print(f"run budget exceeded: {exc}")
                raise
            await session.commit()
        print(
            f"Pipeline run complete ({args.mode}): {summary.pending} pending, "
            f"{summary.rejected} rejected, {summary.total_cost_cents:.2f} cents spent."
        )
        for topic_id, difficulty_label, reasons in summary.rejections:
            print(f"  rejected {topic_id} d{difficulty_label}: {reasons}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
