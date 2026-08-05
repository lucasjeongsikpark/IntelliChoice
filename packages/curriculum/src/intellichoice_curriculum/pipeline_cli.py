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
    TOPIC_SKILL_DIFFICULTIES,
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

# Seeds are a pure function of (skill, tier, index), and a template id is a pure function
# of the seed - so a second run at the same settings re-proposes ids the first run's
# surviving candidates already hold. That is not merely wasteful: `main` commits once
# after the whole batch, so a single primary-key collision would discard every candidate
# in the run, including the ones that passed. `--seed-offset` is how a follow-up run
# claims a fresh id range; it is the caller's job to pick one, deliberately, rather than
# a timestamp, so runs stay reproducible (D-013's determinism posture).
DEFAULT_SEED_OFFSET = 0


def authored_seed(
    *, skill_index: int, difficulty_label: int, index: int, seed_offset: int
) -> int:
    """The (skill, tier, index) -> seed mapping, as a pure function so its one real
    invariant is testable without a gateway or a database: distinct inputs must produce
    distinct seeds, because a seed determines a template id and a duplicate id discards
    the entire batch at commit time.

    The skill term is what keeps seeds distinct now that a tier can be visited by more
    than one skill (D-186) - without it, two skills at tier 3 would propose the same seed
    and therefore the same template id.
    """
    return (
        _AUTHORED_SEED_BASE
        + seed_offset
        + skill_index * 1000
        + difficulty_label * 100
        + index
    )


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
    seed_offset: int = DEFAULT_SEED_OFFSET,
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
                seed = _SEED_BASE + seed_offset + difficulty_label * 100 + i
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
    seed_offset: int = DEFAULT_SEED_OFFSET,
) -> RunSummary:
    """S20 (plan §7) counterpart to `run_pipeline` above, driving
    `generate_authored_candidate` - authored mode has no shape allowlist to iterate.

    D-186: iterates **(skill, tier) pairs** from `TOPIC_SKILL_DIFFICULTIES` rather than
    tiers alone from `TOPIC_DIFFICULTY_SKILLS`, which is what makes multi-tier-per-skill
    content reachable at all. The old loop derived the skill *from* the tier, so it could
    only ever produce the 1:1 ladder no matter how many times it ran. `skill_id` is now
    passed explicitly for the same reason - once two skills share a tier, derivation has
    nothing to derive from.

    `candidates_per_difficulty` is now per (skill, tier) pair, so the same value asks for
    more items than it used to: `linear_equations` went from 5 pairs to 11.
    """
    curriculum = load_curriculum()
    summary = RunSummary()
    spend = 0.0

    for topic_id, skill_difficulties in sorted(TOPIC_SKILL_DIFFICULTIES.items()):
        for skill_index, (skill_id, difficulty_labels) in enumerate(
            sorted(skill_difficulties.items())
        ):
            for difficulty_label in sorted(difficulty_labels):
                for i in range(candidates_per_difficulty):
                    if spend >= run_budget_cents:
                        print(f"run budget of {run_budget_cents} cents reached - stopping early")
                        return summary
                    seed = authored_seed(
                        skill_index=skill_index,
                        difficulty_label=difficulty_label,
                        index=i,
                        seed_offset=seed_offset,
                    )
                    outcome: PipelineOutcome = await generate_authored_candidate(
                        session=session,
                        gateway=gateway,
                        curriculum=curriculum,
                        topic_id=topic_id,
                        difficulty_label=difficulty_label,
                        seed=seed,
                        session_spend_cents=spend,
                        skill_id=skill_id,
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
    parser.add_argument(
        "--seed-offset",
        type=int,
        default=DEFAULT_SEED_OFFSET,
        help="Shifts every seed, and therefore every proposed template id, by this much. "
        "A follow-up run against a topic that already has candidates needs a fresh offset "
        "- otherwise it re-proposes ids the earlier run's survivors hold, and the "
        "resulting collision discards the whole batch (default: 0)",
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
                    seed_offset=args.seed_offset,
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
