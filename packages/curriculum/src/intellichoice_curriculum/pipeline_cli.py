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
from collections.abc import Sequence
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
    TOPIC_DIFFICULTY_SKILLS,
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
    # D-194: two independent readings of how hard the item is, disagreeing by 2 or
    # more. Its own bucket because it is not the same finding as a judge rejection -
    # the question may be perfectly good and still land here.
    rejected_difficulty: int = 0
    # D-198. Two separate facts, because one number would hide the thing worth knowing:
    # how many Generator calls the run actually paid for, and how many candidates only
    # became publishable *because* a repair ran. A repair loop that fixes nothing still
    # spends, and `generator_calls` is what makes that visible.
    generator_calls: int = 0
    repaired_to_pending: int = 0
    repaired_still_rejected: int = 0
    skipped_circuit_open: int = 0
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
            + self.rejected_difficulty
        )

    def record(self, outcome: "PipelineOutcome") -> None:
        self.total_cost_cents += outcome.cost_cents
        # D-198: attempts, not candidates. A slot that repaired twice paid for three
        # Generator calls, and a run whose yield looks fine while this number is triple the
        # candidate count is not the same run as one that got there first time.
        self.generator_calls += outcome.attempts
        if outcome.status == "pending":
            self.processed += 1
            self.pending += 1
            if outcome.attempts > 1:
                self.repaired_to_pending += 1
            return
        if outcome.rejected_at == "budget":
            self.skipped_budget += 1
            return
        if outcome.rejected_at == "circuit_open":
            # Never reached a model, so it is not part of the quality denominator (D-199).
            self.skipped_circuit_open += 1
            return
        self.processed += 1
        if outcome.attempts > 1:
            # Repaired and still rejected: the money that bought nothing. Counted
            # separately because "repair helps" and "repair is affordable" are different
            # claims and this is the one that tests the second.
            self.repaired_still_rejected += 1
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
            f"solver={self.rejected_solver} judge={self.rejected_judge} "
            f"difficulty={self.rejected_difficulty}\n"
            f"  repair: generator_calls={self.generator_calls} "
            f"fixed={self.repaired_to_pending} still_rejected={self.repaired_still_rejected}\n"
            f"  skipped: budget={self.skipped_budget} circuit_open={self.skipped_circuit_open} "
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


@dataclass(frozen=True)
class GenerationSlot:
    """One candidate a run intends to produce. `question_template_id` is what the pipeline
    will actually write, computed here so preflight and the runner cannot disagree about
    which rows a run claims.
    """

    topic_id: str
    skill_id: str
    difficulty_label: int
    index: int
    seed: int
    question_template_id: str


class PlanError(Exception):
    """The requested run cannot be built - an unknown topic, a skill that is not in it, a
    difficulty outside 1-5, or a filter that leaves nothing to generate. Raised while
    planning, which is before anything has been called or written.
    """


@dataclass(frozen=True)
class GenerationPlan:
    mode: str
    slots: tuple[GenerationSlot, ...]
    candidates_per_slot: int
    seed_offset: int
    run_budget_cents: float
    # What was asked for, kept for the preflight report - "selected skills: all 5" and
    # "selected skills: linear_both_sides" are different runs and the report should say so.
    topic_ids: tuple[str, ...]
    skill_ids: tuple[str, ...]
    difficulties: tuple[int, ...]
    # D-198. Defaulted, and last, so every existing construction site keeps one-shot
    # behaviour without naming it.
    max_repair_attempts: int = 0

    @property
    def template_ids(self) -> tuple[str, ...]:
        return tuple(slot.question_template_id for slot in self.slots)


VALID_DIFFICULTIES = range(1, 6)
# Per candidate: generator, solver A, solver B, judge, plus one embedding for the dedup
# check. Used only to turn a plan into an upper bound on calls - it is the shape of the
# pipeline, so it changes when a stage is added and the estimate should be re-derived here
# rather than in the report.
_MODEL_CALLS_PER_AUTHORED_CANDIDATE = 5


def build_plan(
    mode: str,
    *,
    topic_id: str | None = None,
    skill_ids: Sequence[str] | None = None,
    difficulties: Sequence[int] | None = None,
    candidates_per_slot: int = 2,
    seed_offset: int = DEFAULT_SEED_OFFSET,
    run_budget_cents: float = 1000.0,
    max_repair_attempts: int = 0,
) -> GenerationPlan:
    """Turn CLI arguments into the exact list of candidates a run would attempt.

    One structure drives both the runner and `preflight`, which is the property that makes
    the preflight worth trusting: a filter that the report understands but the loop does
    not would be worse than no filter. The runner iterating `plan.slots` rather than
    re-deriving them is what forecloses that.

    This is also where presets would attach later - a YAML file would be parsed into these
    same arguments, so nothing below the plan needs to know they exist (deliberately not
    built now; there is one topic).

    Validation is fail-closed and happens here, before any provider is constructed: an
    unknown topic, a skill outside the topic, a difficulty off the 1-5 scale, or a filter
    combination with no planned (skill, tier) pairs all raise rather than quietly
    generating something adjacent to what was asked for.
    """
    requested_difficulties = tuple(difficulties or ())
    for difficulty in requested_difficulties:
        if difficulty not in VALID_DIFFICULTIES:
            raise PlanError(
                f"difficulty {difficulty} is outside the 1-5 scale the whole system uses"
            )

    plan_by_topic: dict[str, dict[str, list[int]]]
    if mode == "authored":
        plan_by_topic = {t: dict(s) for t, s in TOPIC_SKILL_DIFFICULTIES.items()}
    else:
        # The shape pipeline has no skill dimension of its own - its skill follows from the
        # tier (D-186's "native ladder"). Expressed in the same shape so one planner covers
        # both modes instead of two loops drifting apart.
        plan_by_topic = {}
        for topic, tiers in DIFFICULTY_SHAPES.items():
            by_skill: dict[str, list[int]] = {}
            for tier in sorted(tiers):
                skill = TOPIC_DIFFICULTY_SKILLS.get(topic, {}).get(tier)
                if skill is not None:
                    by_skill.setdefault(skill, []).append(tier)
            plan_by_topic[topic] = by_skill

    if topic_id is not None:
        if topic_id not in plan_by_topic:
            raise PlanError(
                f"topic {topic_id!r} has no registered generation plan "
                f"(known: {', '.join(sorted(plan_by_topic))})"
            )
        plan_by_topic = {topic_id: plan_by_topic[topic_id]}

    requested_skills = tuple(skill_ids or ())
    if requested_skills:
        if mode != "authored":
            raise PlanError("--skill-id applies to authored mode only; shape mode plans by tier")
        known = {skill for skills in plan_by_topic.values() for skill in skills}
        for skill in requested_skills:
            if skill not in known:
                raise PlanError(
                    f"skill {skill!r} is not in the selected topic "
                    f"(known: {', '.join(sorted(known))})"
                )

    slots: list[GenerationSlot] = []
    for topic, skill_difficulties in sorted(plan_by_topic.items()):
        # The skill index is enumerated over the *whole* topic, not the filtered subset,
        # so `--skill-id linear_both_sides` proposes the same seeds it would have as part
        # of a full run. A filter that shifted the seeds would make two runs collide by
        # having narrowed one of them, which is the opposite of what filtering is for.
        for skill_index, (skill_id, _tiers) in enumerate(
            sorted(TOPIC_SKILL_DIFFICULTIES.get(topic, skill_difficulties).items())
        ):
            if skill_id not in skill_difficulties:
                continue
            if requested_skills and skill_id not in requested_skills:
                continue
            for difficulty_label in sorted(skill_difficulties[skill_id]):
                if requested_difficulties and difficulty_label not in requested_difficulties:
                    continue
                for index in range(candidates_per_slot):
                    if mode == "authored":
                        seed = authored_seed(
                            skill_index=skill_index,
                            difficulty_label=difficulty_label,
                            index=index,
                            seed_offset=seed_offset,
                        )
                        template_id = f"authored-{topic}-d{difficulty_label}-{seed}"
                    else:
                        seed = _SEED_BASE + seed_offset + difficulty_label * 100 + index
                        template_id = f"ai-{topic}-d{difficulty_label}-{seed}"
                    slots.append(
                        GenerationSlot(
                            topic_id=topic,
                            skill_id=skill_id,
                            difficulty_label=difficulty_label,
                            index=index,
                            seed=seed,
                            question_template_id=template_id,
                        )
                    )

    if not slots:
        raise PlanError(
            "no generation slots match this request - the skill/difficulty combination is "
            "not in the authoring plan"
        )
    return GenerationPlan(
        mode=mode,
        slots=tuple(slots),
        candidates_per_slot=candidates_per_slot,
        max_repair_attempts=max_repair_attempts,
        seed_offset=seed_offset,
        run_budget_cents=run_budget_cents,
        topic_ids=tuple(sorted(plan_by_topic)),
        skill_ids=tuple(sorted({slot.skill_id for slot in slots})),
        difficulties=tuple(sorted({slot.difficulty_label for slot in slots})),
    )


async def run_plan(
    session: AsyncSession,
    gateway: BedrockGateway,
    plan: GenerationPlan,
) -> RunSummary:
    """Execute a plan, one committed candidate at a time.

    Both modes share this loop now; the only difference is which candidate function runs,
    because everything that used to differ - which (skill, tier) pairs to visit, what seed
    each gets, what id it claims - is decided by `build_plan` and identical in structure.
    """
    curriculum = load_curriculum()
    summary = RunSummary()
    summary.scheduled = len(plan.slots)
    spend = 0.0

    for slot in plan.slots:
        if spend >= plan.run_budget_cents:
            print(f"run budget of {plan.run_budget_cents} cents reached - stopping early")
            return summary
        try:
            if plan.mode == "authored":
                outcome: PipelineOutcome = await generate_authored_candidate(
                    session=session,
                    gateway=gateway,
                    curriculum=curriculum,
                    topic_id=slot.topic_id,
                    difficulty_label=slot.difficulty_label,
                    seed=slot.seed,
                    session_spend_cents=spend,
                    skill_id=slot.skill_id,
                    max_repair_attempts=plan.max_repair_attempts,
                    # The slot may not spend past the run's own ceiling; without this the
                    # between-slot check only notices after the money is gone.
                    budget_ceiling_cents=plan.run_budget_cents,
                )
            else:
                outcome = await generate_candidate(
                    session=session,
                    gateway=gateway,
                    curriculum=curriculum,
                    topic_id=slot.topic_id,
                    difficulty_label=slot.difficulty_label,
                    seed=slot.seed,
                    session_spend_cents=spend,
                )
        except IntegrityError as exc:
            # The collision surfaces HERE, not at commit: `QuestionRepository.create_template`
            # flushes, so the unique-violation is raised while the candidate is still being
            # built. D-193 put this catch in `_settle`, which is one statement too late -
            # measured by `test_per_candidate_settlement_survives_a_duplicate_id`, which
            # failed against that version. `_settle` keeps its own catch for the same error
            # arriving at commit time, since either is possible and both cost one candidate.
            await session.rollback()
            summary.skipped_duplicate_id += 1
            summary.rejections.append(
                (
                    slot.topic_id,
                    slot.difficulty_label,
                    [f"template id {slot.question_template_id} already exists: {exc}"],
                )
            )
            continue
        spend += outcome.cost_cents
        await _settle(
            session,
            summary,
            outcome,
            topic_id=slot.topic_id,
            difficulty_label=slot.difficulty_label,
        )
    return summary


# Bedrock's cross-region inference profiles are routing aliases, not models: `us.`,
# `global.` and the bare id all reach the same weights. Stripped before the solver-diversity
# comparison because otherwise that check reads two spellings of one model as two models -
# measured, not theorised, while preparing a pilot in an account with only two accessible
# Anthropic models, where reaching for an alias is the obvious move.
_INFERENCE_PROFILE_PREFIXES = ("us-gov.", "global.", "apac.", "us.", "eu.")


def underlying_model(model_id: str) -> str:
    """The model an id actually reaches, with any inference-profile prefix removed.

    A string comparison is the wrong test for "are these two different models", and it
    fails in the permissive direction: `us.anthropic.claude-haiku-4-5-20251001-v1:0` and
    `global.anthropic.claude-haiku-4-5-20251001-v1:0` are different strings and one model,
    so two solvers configured that way would agree by construction and the check that
    exists to catch exactly that would report PASS.
    """
    for prefix in _INFERENCE_PROFILE_PREFIXES:
        if model_id.startswith(prefix):
            return model_id[len(prefix) :]
    return model_id


@dataclass(frozen=True)
class PreflightReport:
    text: str
    ok: bool
    failures: tuple[str, ...]


def _repair_cost_note(plan: GenerationPlan) -> str:
    """How much a repair setting could cost, in the units the reader is deciding in.

    Preflight exists so nobody learns a run's shape by paying for it, and repair is the one
    setting whose worst case is a multiple of the visible candidate count rather than equal
    to it (D-198).
    """
    if not plan.max_repair_attempts:
        return " (off - a rejected candidate is not retried)"
    extra = len(plan.slots) * plan.max_repair_attempts
    return f" (worst case {extra} extra Generator calls across {len(plan.slots)} slots)"


async def preflight(
    session: AsyncSession,
    settings: CurriculumPipelineSettings,
    plan: GenerationPlan,
) -> PreflightReport:
    """What the run would do, before it costs anything. Makes no model or embedding call.

    Exists because the ways a paid run has actually been wasted here are all knowable up
    front. Seeds are deterministic, so id collisions are predictable rather than discovered
    at commit. Solver A/B share their model slots with the generator and reviewer, which
    default to the *same* model id - two solvers that are one model agreeing is one opinion
    counted twice, and every "independent solver agreement" recorded before this check was
    exactly that. Neither check costs anything, so declining to run it is the only
    expensive option.
    """
    taken = (
        (
            await session.execute(
                select(QuestionTemplate.question_template_id).where(
                    QuestionTemplate.question_template_id.in_(plan.template_ids)
                )
            )
        )
        .scalars()
        .all()
    )
    generator_model = (
        settings.bedrock_authored_generation_model_id
        if plan.mode == "authored"
        else settings.bedrock_generation_model_id
    )
    solver_a = settings.bedrock_generation_model_id
    solver_b = settings.bedrock_review_model_id
    solvers_differ = underlying_model(solver_a) != underlying_model(solver_b)
    max_calls = len(plan.slots) * _MODEL_CALLS_PER_AUTHORED_CANDIDATE

    failures: list[str] = []
    if not solvers_differ:
        detail = (
            f"both resolve to {solver_a!r}"
            if solver_a == solver_b
            else f"{solver_a!r} and {solver_b!r} are two inference profiles for one model"
        )
        failures.append(
            f"Solver A and Solver B {detail} - their agreement would be one opinion counted twice"
        )
    if taken:
        failures.append(
            f"{len(taken)} of {len(plan.slots)} planned template ids already exist - "
            f"pick a fresh --seed-offset"
        )
    if plan.run_budget_cents > settings.bedrock_run_budget_cents:
        failures.append(
            f"requested budget {plan.run_budget_cents:.0f}c exceeds the configured hard "
            f"ceiling of {settings.bedrock_run_budget_cents:.0f}c"
        )

    lines = [
        f"mode:                  {plan.mode}",
        f"provider:              {settings.bedrock_provider}",
        f"generator model:       {generator_model}",
        f"solver A model:        {solver_a}",
        f"solver B model:        {solver_b}",
        f"judge model:           {settings.bedrock_judge_model_id}",
        f"embedding model:       {settings.bedrock_embedding_model_id}",
        f"topic:                 {', '.join(plan.topic_ids)}",
        f"skills:                {', '.join(plan.skill_ids)}",
        f"difficulties:          {', '.join(str(d) for d in plan.difficulties)}",
        f"candidates per slot:   {plan.candidates_per_slot}",
        f"max repair attempts:   {plan.max_repair_attempts}{_repair_cost_note(plan)}",
        f"scheduled candidates:  {len(plan.slots)}",
        f"seed offset:           {plan.seed_offset}",
        f"planned template ids:  {len(plan.template_ids)} "
        f"({plan.template_ids[0]} .. {plan.template_ids[-1]})",
        f"already-used ids:      {len(taken)}"
        + (f" ({', '.join(sorted(taken)[:5])}{' ...' if len(taken) > 5 else ''})" if taken else ""),
        f"run budget ceiling:    {plan.run_budget_cents:.0f} cents "
        f"(configured hard cap {settings.bedrock_run_budget_cents:.0f})",
        f"estimated max calls:   {max_calls} ({_MODEL_CALLS_PER_AUTHORED_CANDIDATE} per candidate)",
        # Deliberately not a number. Per-call cost depends on the model ids above and on
        # output length, and this project has one measurement (Haiku, ~0.29c per call) that
        # says nothing about a premium generator. A budget ceiling the gateway enforces is
        # a real bound; an invented average would read like one and not be.
        "estimated max spend:   not calculable - no per-token price table is configured; "
        "the run budget ceiling above is the enforced bound",
        f"solver diversity:      {'PASS' if solvers_differ else 'FAIL'}",
        f"id availability:       {'PASS' if not taken else 'FAIL'}",
    ]
    for failure in failures:
        lines.append(f"  ! {failure}")
    return PreflightReport(text="\n".join(lines), ok=not failures, failures=tuple(failures))


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


def build_parser() -> argparse.ArgumentParser:
    """Separate from `main` so the argument surface is testable without a database.

    Deliberately still `argparse` (D-194). A framework migration would be the largest
    change in this area and would buy nothing the flags below do not already do; the
    thing worth having later is presets, and presets attach to `build_plan`, not to the
    parser.
    """
    parser = argparse.ArgumentParser(description="Run the AI question-generation pipeline")
    parser.add_argument(
        "--mode",
        choices=["shape", "authored"],
        default="shape",
        help="'shape' (S9, parameterized templates) or 'authored' (S20, the model "
        "writes the whole item) - default: shape",
    )
    parser.add_argument(
        "--topic-id",
        default=None,
        help="Restrict generation to one topic (default: every topic with a plan)",
    )
    parser.add_argument(
        "--skill-id",
        action="append",
        default=None,
        metavar="SKILL_ID",
        help="Restrict to this skill; repeat the flag to name several. Authored mode only "
        "(shape mode's skill follows from the tier). Default: every skill in the topic",
    )
    parser.add_argument(
        "--difficulty",
        action="append",
        type=int,
        default=None,
        metavar="1-5",
        help="Restrict to this difficulty tier; repeat the flag for several. Default: the "
        "tiers the authoring plan lists for each selected skill",
    )
    parser.add_argument(
        "--candidates-per-slot",
        type=int,
        default=None,
        help="Candidates to attempt per (skill, tier) slot (default: 2)",
    )
    parser.add_argument(
        # The old name, kept working rather than broken: it is in the Makefile's history,
        # in DECISIONS.md and in at least one shell someone has open. Same meaning.
        "--candidates-per-difficulty",
        type=int,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--max-repair-attempts",
        type=int,
        default=0,
        help="After a rejection a rewrite could fix, tell the Generator what was wrong and "
        "try again, up to this many extra times per slot (default: 0, off). Each attempt is "
        "a paid Generator call and is fully re-gated. Difficulty disagreements are never "
        "repaired - the only useful feedback would be the judge's tier, and handing that "
        "back is relabeling, not repair",
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
        "--run-budget-cents",
        type=float,
        default=None,
        help="Spend ceiling for this run. Cannot exceed the configured hard cap "
        "(CURRICULUM_BEDROCK_RUN_BUDGET_CENTS), which it defaults to",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Print what this run would do - resolved model ids, the selected slots, the "
        "ids it claims, the spend ceiling - then exit. Makes no model or embedding call "
        "and writes nothing. Free; run it before every paid batch",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Like --preflight, plus every planned slot listed individually. Also calls "
        "nothing and writes nothing",
    )
    parser.add_argument(
        "--allow-preflight-failure",
        action="store_true",
        help="Run even though preflight failed. Intended for mock-provider smoke tests, "
        "where a single-model solver pair is the correct configuration; a paid run refuses "
        "without it",
    )
    return parser


async def main() -> None:
    args = build_parser().parse_args()
    settings = get_pipeline_settings()

    candidates_per_slot = (
        args.candidates_per_slot
        if args.candidates_per_slot is not None
        else args.candidates_per_difficulty
        if args.candidates_per_difficulty is not None
        else 2
    )
    try:
        plan = build_plan(
            args.mode,
            topic_id=args.topic_id,
            skill_ids=args.skill_id,
            difficulties=args.difficulty,
            candidates_per_slot=candidates_per_slot,
            max_repair_attempts=args.max_repair_attempts,
            seed_offset=args.seed_offset,
            run_budget_cents=(
                args.run_budget_cents
                if args.run_budget_cents is not None
                else settings.bedrock_run_budget_cents
            ),
        )
    except PlanError as exc:
        # Before the engine, before the provider, before anything is written.
        raise SystemExit(f"cannot plan this run: {exc}") from exc

    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            report = await preflight(session, settings, plan)
            print(report.text)
            if args.dry_run:
                print("\nplanned slots:")
                for slot in plan.slots:
                    print(
                        f"  {slot.question_template_id}  skill={slot.skill_id} "
                        f"d={slot.difficulty_label} seed={slot.seed}"
                    )
            if args.preflight or args.dry_run:
                return
            if not report.ok:
                # Fail-closed for anything that spends money. A mock run is the documented
                # exception and still has to say so with the flag - the failure mode this
                # guards against is a paid batch that quietly proceeds past a warning
                # nobody was watching for.
                paid = settings.bedrock_provider == "bedrock"
                if paid and not args.allow_preflight_failure:
                    raise SystemExit(
                        "preflight failed and this run would call a paid provider - "
                        "fix the problems above, or pass --allow-preflight-failure if "
                        "you have decided they are acceptable"
                    )
                print("preflight failed - continuing because this run is not paid")
            gateway = _build_gateway(settings)
            try:
                summary = await run_plan(session, gateway, plan)
            except CostBudgetExceededError as exc:
                print(f"run budget exceeded: {exc}")
                raise
            # Every candidate has already committed itself (`_settle`); this only flushes
            # anything the runner left uncommitted on an early return.
            await session.commit()
        print(summary.format(args.mode))
        for topic_id, difficulty_label, reasons in summary.rejections:
            print(f"  rejected {topic_id} d{difficulty_label}: {reasons}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
