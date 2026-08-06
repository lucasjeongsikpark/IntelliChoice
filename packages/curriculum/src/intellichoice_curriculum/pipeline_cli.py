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
from intellichoice_db.models.questions import QuestionTemplate
from intellichoice_shared.bedrock import BedrockGateway, BedrockTask, CostBudgetExceededError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_curriculum.ai_pipeline import (
    DIFFICULTY_SHAPES,
    TOPIC_SKILL_DIFFICULTIES,
    PipelineOutcome,
    generate_authored_candidate,
    generate_candidate,
)
from intellichoice_curriculum.ai_pipeline import (
    PipelineOutcome as _PipelineOutcome,  # noqa: F401  (RunSummary.record's annotation)
)
from intellichoice_curriculum.content import load_curriculum
from intellichoice_curriculum.settings import CurriculumPipelineSettings, get_pipeline_settings

_SEED_BASE = 1000  # Well clear of the S4 hand-authored bank's seeds (0-9 per difficulty).
# S20 authored mode uses its own seed range so a shape-pipeline run and an authored-
# pipeline run against the same topic/difficulty never propose colliding template ids.
_AUTHORED_SEED_BASE = 5000

# Seeds are a pure function of (skill, tier, index), and a template id is a pure function
# of the seed - so a second run at the same settings re-proposes ids the first run's
# surviving candidates already hold. `--seed-offset` is how a follow-up run claims a fresh
# id range; it is the caller's job to pick one, deliberately, rather than a timestamp, so
# runs stay reproducible (D-013's determinism posture). `--preflight` says in advance
# whether the offset is fresh, and `_settle` contains the damage if it is not.
DEFAULT_SEED_OFFSET = 0


def authored_seed(*, skill_index: int, difficulty_label: int, index: int, seed_offset: int) -> int:
    """The (skill, tier, index) -> seed mapping, as a pure function so its one real
    invariant is testable without a gateway or a database: distinct inputs must produce
    distinct seeds, because a seed determines a template id and a duplicate id costs a
    paid candidate.

    The skill term is what keeps seeds distinct now that a tier can be visited by more
    than one skill (D-186) - without it, two skills at tier 3 would propose the same seed
    and therefore the same template id.
    """
    return _AUTHORED_SEED_BASE + seed_offset + skill_index * 1000 + difficulty_label * 100 + index


@dataclass
class RunSummary:
    """Counts with separate denominators, because one number was hiding two (D-192).

    A 50-candidate run reported "8 of 50" and "stopped at 34 of 50" in the same
    breath: 16 candidates were never sent to a model at all - the gateway refused them on
    budget - yet they were counted as rejections. So the yield was quoted as 16% when the
    rate that actually says whether the mode works is 8/34, and neither number was
    labelled. `processed` is the honest denominator for quality; `scheduled` is the one for
    coverage.
    """

    scheduled: int = 0
    processed: int = 0
    pending: int = 0
    rejected_generator: int = 0
    rejected_validation: int = 0
    rejected_dedup: int = 0
    rejected_solver: int = 0
    rejected_judge: int = 0
    skipped_budget: int = 0
    # A candidate whose template id was already taken. Its own row is discarded and the
    # batch continues (D-193) - the money is still counted, because it was still spent.
    skipped_duplicate_id: int = 0
    total_cost_cents: float = 0.0
    rejections: list[tuple[str, int, list[str]]] = field(default_factory=list)

    @property
    def rejected(self) -> int:
        return (
            self.rejected_generator
            + self.rejected_validation
            + self.rejected_dedup
            + self.rejected_solver
            + self.rejected_judge
        )

    def record(self, outcome: "PipelineOutcome") -> None:
        self.total_cost_cents += outcome.cost_cents
        if outcome.status == "pending":
            self.processed += 1
            self.pending += 1
            return
        if outcome.rejected_at == "budget":
            self.skipped_budget += 1
            return
        self.processed += 1
        attribute = f"rejected_{outcome.rejected_at or 'generator'}"
        setattr(self, attribute, getattr(self, attribute) + 1)

    def format(self, mode: str) -> str:
        yield_rate = (self.pending / self.processed * 100) if self.processed else 0.0
        return (
            f"Pipeline run complete ({mode}): {self.pending} accepted of {self.processed} "
            f"processed ({yield_rate:.0f}%), {self.scheduled} scheduled, "
            f"{self.total_cost_cents:.2f} cents spent.\n"
            f"  rejected: generator={self.rejected_generator} "
            f"validation={self.rejected_validation} dedup={self.rejected_dedup} "
            f"solver={self.rejected_solver} judge={self.rejected_judge}\n"
            f"  skipped: budget={self.skipped_budget} "
            f"duplicate_id={self.skipped_duplicate_id}"
        )


async def _settle(
    session: AsyncSession,
    summary: RunSummary,
    outcome: "PipelineOutcome",
    *,
    topic_id: str,
    difficulty_label: int,
) -> None:
    """Commit this one candidate, so a failure costs one candidate rather than the run.

    Before D-193 the runners held every candidate in one transaction and `main` committed
    after the loop, which made a duplicate template id a *batch-wide* event: seeds are a
    pure function of (skill, tier, index), so a second run at the same settings re-proposes
    ids the first run's survivors already hold, and the resulting `IntegrityError` at commit
    discarded every candidate in the run - including the paid, passing ones. `--seed-offset`
    exists to avoid that collision; this makes not avoiding it survivable, which is the
    property that matters when a batch has already spent real money.

    A committed candidate is also a *resumable* one: an interrupted run leaves everything
    up to the interruption in the database rather than nothing.
    """
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        summary.total_cost_cents += outcome.cost_cents
        summary.skipped_duplicate_id += 1
        summary.rejections.append(
            (topic_id, difficulty_label, [f"template id already exists, candidate dropped: {exc}"])
        )
        return
    summary.record(outcome)
    if outcome.status != "pending":
        summary.rejections.append((topic_id, difficulty_label, outcome.reasons))


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
    summary.scheduled = candidates_per_difficulty * sum(
        len(shapes) for shapes in DIFFICULTY_SHAPES.values()
    )
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
                await _settle(
                    session,
                    summary,
                    outcome,
                    topic_id=topic_id,
                    difficulty_label=difficulty_label,
                )
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
    summary.scheduled = candidates_per_difficulty * sum(
        len(tiers) for plan in TOPIC_SKILL_DIFFICULTIES.values() for tiers in plan.values()
    )
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
                    await _settle(
                        session,
                        summary,
                        outcome,
                        topic_id=topic_id,
                        difficulty_label=difficulty_label,
                    )
    return summary


def planned_template_ids(
    mode: str, *, candidates_per_difficulty: int, seed_offset: int
) -> list[str]:
    """Every template id a run at these settings would try to claim, without calling
    anything. The runners derive ids from seeds and seeds from (skill, tier, index), so
    the whole plan is knowable in advance - which is what makes a no-cost preflight
    possible at all.

    Deliberately recomputed here from the same inputs rather than refactored out of the
    runners: a preflight that shares the runners' code would agree with them by
    construction and could not catch a divergence, but one that agrees by *test* can. See
    `test_preflight_predicts_the_ids_the_run_claims`.
    """
    ids: list[str] = []
    if mode == "authored":
        for topic_id, skill_difficulties in sorted(TOPIC_SKILL_DIFFICULTIES.items()):
            for skill_index, (_skill_id, difficulty_labels) in enumerate(
                sorted(skill_difficulties.items())
            ):
                for difficulty_label in sorted(difficulty_labels):
                    for i in range(candidates_per_difficulty):
                        seed = authored_seed(
                            skill_index=skill_index,
                            difficulty_label=difficulty_label,
                            index=i,
                            seed_offset=seed_offset,
                        )
                        ids.append(f"authored-{topic_id}-d{difficulty_label}-{seed}")
    else:
        for topic_id, difficulty_shapes in sorted(DIFFICULTY_SHAPES.items()):
            for difficulty_label in sorted(difficulty_shapes):
                for i in range(candidates_per_difficulty):
                    seed = _SEED_BASE + seed_offset + difficulty_label * 100 + i
                    ids.append(f"ai-{topic_id}-d{difficulty_label}-{seed}")
    return ids


async def preflight(
    session: AsyncSession,
    settings: CurriculumPipelineSettings,
    *,
    mode: str,
    candidates_per_difficulty: int,
    seed_offset: int,
) -> tuple[str, bool]:
    """What the run would do, before it costs anything. Returns (report, ok).

    Exists because the two ways a paid run has been wasted here are both knowable up
    front. Seeds are deterministic, so id collisions are predictable rather than
    discovered at commit; and Solver A/B share their model slots with the generator and
    reviewer, which default to the *same* model id - two solvers that are one model
    agreeing with each other is not independent verification, it is one opinion counted
    twice (§3.5). Neither check calls a model, so running it is free and refusing to run
    it is the only expensive option.
    """
    ids = planned_template_ids(
        mode, candidates_per_difficulty=candidates_per_difficulty, seed_offset=seed_offset
    )
    taken = (
        (
            await session.execute(
                select(QuestionTemplate.question_template_id).where(
                    QuestionTemplate.question_template_id.in_(ids)
                )
            )
        )
        .scalars()
        .all()
    )
    solver_a = settings.bedrock_generation_model_id
    solver_b = settings.bedrock_review_model_id
    solvers_differ = solver_a != solver_b
    # A ceiling, not an estimate: the gateway refuses the call that would cross it, so this
    # is the most the run can cost however the candidates go.
    lines = [
        f"mode:                {mode}",
        f"provider:            {settings.bedrock_provider}",
        f"candidates:          {len(ids)} "
        f"({candidates_per_difficulty} per slot, seed offset {seed_offset})",
        f"generator model:     {settings.bedrock_authored_generation_model_id}"
        if mode == "authored"
        else f"generator model:     {solver_a}",
        f"solver A model:      {solver_a}",
        f"solver B model:      {solver_b}",
        f"judge model:         {settings.bedrock_judge_model_id}",
        f"embedding model:     {settings.bedrock_embedding_model_id}",
        f"max spend:           {settings.bedrock_run_budget_cents:.0f} cents",
        f"solver diversity:    "
        f"{'PASS' if solvers_differ else 'FAIL - both solvers are one model'}",
        f"id availability:     "
        f"{'PASS' if not taken else f'FAIL - {len(taken)} of {len(ids)} taken'}",
    ]
    if taken:
        lines.append(
            f"  already taken:     {', '.join(sorted(taken)[:5])}{' ...' if len(taken) > 5 else ''}"
        )
        lines.append("  pick a fresh --seed-offset")
    return "\n".join(lines), solvers_differ and not taken


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
        help="'shape' (S9, parameterized templates) or 'authored' (S20, the model "
        "writes the whole item) - default: shape",
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
        "- otherwise it re-proposes ids the earlier run's survivors hold and those "
        "candidates are paid for and then dropped (default: 0)",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Print what this run would do - resolved model ids, whether the two solvers "
        "are actually two models, the id range it claims and the spend ceiling - then "
        "exit without calling anything. Free; run it before every paid batch.",
    )
    args = parser.parse_args()

    settings = get_pipeline_settings()
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            report, ok = await preflight(
                session,
                settings,
                mode=args.mode,
                candidates_per_difficulty=args.candidates_per_difficulty,
                seed_offset=args.seed_offset,
            )
            print(report)
            if args.preflight:
                return
            # Printed rather than enforced. A failing check is a warning here, not a
            # refusal: `--seed-offset 0` against an empty topic is a legitimate first run,
            # and a single-model solver pair is the right configuration for a mock-provider
            # smoke test. What the run must not do is spend money without saying which of
            # those it is doing.
            if not ok:
                print("preflight found problems above - continuing anyway")
            gateway = _build_gateway(settings)
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
            # Every candidate has already committed itself (`_settle`); this only flushes
            # anything a runner left uncommitted on an early return.
            await session.commit()
        print(summary.format(args.mode))
        for topic_id, difficulty_label, reasons in summary.rejections:
            print(f"  rejected {topic_id} d{difficulty_label}: {reasons}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
