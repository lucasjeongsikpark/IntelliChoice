"""S20 human-review CLI (plan §7 step 5, SPEC §5.8.3 "Activate or Quarantine").

Run with: uv run python -m intellichoice_curriculum.review_cli [--topic TOPIC_ID]

Lists `pending` authored templates (`review_priority="high"` first), renders each item
alongside its pipeline evidence (`question_validation_runs`), and asks for a decision.
D-026's rule is unchanged and structurally enforced here too: approval is the only path
to `validation_status="approved"`, and it's always `QuestionRepository.
activate_template` doing the flip - this CLI has no code path that marks a template
approved on its own.
"""

import argparse
import asyncio

from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.questions import (
    QuestionTemplate,
    QuestionValidationRun,
    QuestionVariant,
)
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_shared.bedrock import (
    BedrockGateway,
    BedrockGatewayError,
    CostBudgetExceededError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_curriculum.ai_pipeline import (
    _HINT_QUALITY_BORDERLINE_AT,
    PipelineConfigError,
    generate_authored_candidate,
)
from intellichoice_curriculum.content import load_curriculum
from intellichoice_curriculum.pipeline_cli import _build_gateway
from intellichoice_curriculum.settings import get_pipeline_settings

_RERUN_SEED_STEP = 1  # bumped past the original seed each edit-and-rerun, stays unique.


def render_item(
    template: QuestionTemplate,
    variant: QuestionVariant | None,
    validation_run: QuestionValidationRun | None,
) -> str:
    """Pure rendering, no I/O - kept separate from `main`'s `input()` loop so it's
    directly unit-testable.
    """
    lines = [
        f"--- {template.question_template_id} "
        f"(topic={template.topic_id} skill={template.skill_id} "
        f"difficulty={template.difficulty_label} priority={template.review_priority} "
        f"version={template.version}) ---",
        f"stem: {template.stem}",
    ]
    if template.context_block:
        lines.append(f"context: {template.context_block}")
    if variant is not None:
        options = {
            "a": variant.option_a,
            "b": variant.option_b,
            "c": variant.option_c,
            "d": variant.option_d,
        }
        for label, text in options.items():
            marker = "*" if label == variant.correct_option else " "
            lines.append(f"  {marker} {label}) {text}")
    if template.hint_ladder:
        for i, level in enumerate(template.hint_ladder, start=1):
            lines.append(f"hint {i}: {level}")
    if template.canonical_solution:
        lines.append(f"solution final_answer: {template.canonical_solution.get('final_answer')}")
    if validation_run is not None:
        # D-247: the reasons in prose, above the raw evidence rather than inside it.
        #
        # Measured need, not a nicety. D-246 downgraded `hint_reveals_answer` from a
        # rejection to a review signal on the argument that "the judge's reason travels with
        # the candidate" - and it does, inside the dict printed on the next line. The first
        # paid run afterwards showed what that is worth: **26 of 29 pending candidates carry
        # `review_priority="high"`**, so the field meant to draw the eye fires on 90% of
        # items and directs attention nowhere, while the actual reason is one key inside a
        # large JSON blob. Present, and read by nobody - the same shape as D-244's twenty
        # uncollected metrics.
        #
        # This summarises; it never replaces. The raw `stage_results` still prints below,
        # because a summary that becomes the only record is how evidence quietly narrows.
        for flag in _review_flags(validation_run.stage_results):
            lines.append(f"review flags: {flag}")
        lines.append(f"pipeline evidence: {validation_run.stage_results}")
    return "\n".join(lines)


def _review_flags(stage_results: dict) -> list[str]:
    """Why this candidate wants a human, in the reviewer's language.

    Reads the same keys the pipeline wrote, so a flag cannot appear here that the evidence
    below does not support - and an empty list prints nothing at all, because a heading with
    nothing under it trains a reader to skip the line on every item including the ones that
    have something.
    """
    judge = stage_results.get("judge") or {}
    difficulty = stage_results.get("difficulty") or {}
    flags: list[str] = []
    if judge.get("hint_reveals_answer"):
        reason = judge.get("hint_reveals_answer_reason") or "no reason given"
        # D-245/D-246 measured this flag at ~50% false positives on content a human had
        # already approved, so the wording is deliberately "may": it is a prompt to look,
        # not a verdict to act on.
        flags.append(f"hint may give the answer away - {reason}")
    score = judge.get("hint_quality_score")
    if isinstance(score, int) and score <= _HINT_QUALITY_BORDERLINE_AT:
        flags.append(f"hint quality {score}, at or below the borderline")
    if difficulty.get("decision") in ("flagged", "retiered"):
        stored = difficulty.get("stored_at_difficulty")
        flags.append(
            f"difficulty {difficulty['decision']} - two readings disagreed, stored at {stored}"
        )
    return flags


def render_rejected_run(run: QuestionValidationRun) -> str:
    """Render one rejected candidate from its validation-run evidence alone (D-195).

    Separate from `render_item` because it has a different source: `render_item` reads a
    `QuestionTemplate` row, and a rejected candidate never becomes one. Everything here
    comes out of `stage_results["candidate_snapshot"]`, which is why that snapshot exists -
    the first four-candidate pilot rejected all four, and afterwards no stem, option or
    hint could be read back at all.

    Pure rendering, and that is the whole safety argument for this path: it has no session,
    no repository, and no decision prompt, so there is no code here that could approve
    anything. A rejected candidate is evidence for rewriting the Generator, not an item
    awaiting a second opinion.
    """
    stages = run.stage_results or {}
    snapshot = stages.get("candidate_snapshot")
    request = stages.get("generator_request")
    if snapshot:
        header = snapshot.get("planned_template_id", "?")
    elif request:
        header = request.get("planned_template_id", "?")
    else:
        header = "(content not retained)"
    lines = [f"--- REJECTED {header} (run={run.question_validation_run_id}) ---"]

    if snapshot is None and request is not None:
        # A Generator-stage failure: there is no item, and none is invented. What the
        # pipeline could record is the request and the provider's exact words.
        lines.append("no candidate was generated - the Generator call itself failed")
        for key, value in request.items():
            lines.append(f"  {key}: {value}")
    elif snapshot is None:
        # A run from before D-195. The candidate *was* generated - the stage evidence
        # below proves it, since a deterministic gate or a solver had something to read -
        # but the content was discarded. Saying "no candidate was generated" here would be
        # a false report of what happened, and these rows are exactly the ones a reviewer
        # is most likely to open first.
        lines.append(
            "content not retained - this run predates D-195, which is why the snapshot "
            "exists; the evidence below is all that was kept"
        )
    else:
        lines.extend(
            [
                f"topic={snapshot.get('topic_id')} skill={snapshot.get('skill_id')} "
                f"requested_difficulty={snapshot.get('requested_difficulty')} "
                f"seed={snapshot.get('seed')}",
                f"generator model: {snapshot.get('generator_model_id') or 'unknown'}",
                f"stem: {snapshot.get('stem')}",
            ]
        )
        if snapshot.get("context_block"):
            lines.append(f"context: {snapshot['context_block']}")
        for label in ("a", "b", "c", "d"):
            marker = "*" if label == snapshot.get("correct_option") else " "
            lines.append(f"  {marker} {label}) {snapshot.get(f'option_{label}')}")
        for i, level in enumerate(snapshot.get("hint_ladder") or [], start=1):
            lines.append(f"hint {i}: {level}")
        solution = snapshot.get("canonical_solution") or {}
        lines.append(f"equation: {snapshot.get('equation')}")
        lines.append(f"solution final_answer: {solution.get('final_answer')}")
        lines.append(
            f"proposed_difficulty: {snapshot.get('proposed_difficulty')} - "
            f"{snapshot.get('difficulty_rationale')}"
        )
        lines.append(f"prerequisites: {snapshot.get('required_prerequisites')}")
        lines.append(f"misconception_tags: {snapshot.get('misconception_tags')}")
        lines.append(f"estimated_time_seconds: {snapshot.get('estimated_time_seconds')}")

    for stage in (
        "deterministic_gate",
        "deduplication",
        "solver_a",
        "solver_b",
        "judge",
        "difficulty",
    ):
        if stage in stages:
            lines.append(f"{stage}: {stages[stage]}")
    lines.append(f"rejection reasons: {run.reasons}")
    lines.append(f"cost_cents: {run.cost_cents}")
    return "\n".join(lines)


async def show_rejected(session: AsyncSession, *, limit: int, planned_id: str | None) -> str:
    """Read-only: fetches rejected runs and renders them. No write of any kind."""
    repo = QuestionRepository(session)
    runs = await repo.list_rejected_validation_runs(limit=limit)
    if planned_id is not None:
        runs = [
            run
            for run in runs
            if (run.stage_results or {}).get("candidate_snapshot", {}).get("planned_template_id")
            == planned_id
        ]
    if not runs:
        return "No rejected candidates found."
    return "\n\n".join(render_rejected_run(run) for run in runs)


class UnservableTemplateError(Exception):
    """Approving this template would put content in the active bank that the runtime
    cannot render - see `approve`.
    """


async def approve(session: AsyncSession, question_template_id: str) -> str:
    """Approval is a human action (D-026) and this is the documented way in, so it is
    also where "would this content actually serve?" has to be answered.

    D-188 measured what happens without this, by approving five authored templates and
    running the suite: 34 tests failed because every served question was rendered from a
    parameterized shape and an authored template has none. D-189 built the serving path,
    so the question became "is there anything to serve?" rather than "does this render?".

    D-226 removed the shapes entirely, which makes the check *unconditional* rather than
    weaker: every servable template is now served from its canonical variant, so a template
    without one is unservable, full stop. There is no longer a second kind of template for
    which the missing variant would have been fine.

    Refusing here is the fail-closed direction (CLAUDE.md rule 5): a reviewer working
    through `make question-review` cannot silently brick exam building for real students.
    """
    repo = QuestionRepository(session)
    template = await repo.get_template(question_template_id)
    if template is not None:
        canonical_variant = await repo.get_variant_for_template(question_template_id)
        if canonical_variant is None:
            raise UnservableTemplateError(
                f"{question_template_id} has no canonical variant to serve - every "
                f"servable template stores its content (D-226), so approving it would "
                f"make exam building raise for any student who draws it."
            )
    await repo.activate_template(question_template_id)
    await session.commit()
    return f"approved {question_template_id}"


async def reject(session: AsyncSession, question_template_id: str) -> str:
    repo = QuestionRepository(session)
    await repo.reject_template(question_template_id)
    await session.commit()
    return f"rejected {question_template_id}"


async def edit_and_rerun(
    session: AsyncSession, gateway: BedrockGateway, question_template_id: str
) -> str:
    """Plan §7 "Versioning/audit": marks the current template `superseded` (kept, never
    deleted) and immediately re-runs the pipeline for the same topic/skill/difficulty at
    `version + 1`, so a reviewer who wants a different take on the same slot doesn't have
    to separately track down a fresh seed.
    """
    repo = QuestionRepository(session)
    old = await repo.supersede_template(question_template_id)
    curriculum = load_curriculum()
    rerun_seed = _seed_from_template_id(question_template_id) + _RERUN_SEED_STEP
    try:
        outcome = await generate_authored_candidate(
            session=session,
            gateway=gateway,
            curriculum=curriculum,
            topic_id=old.topic_id,
            difficulty_label=old.difficulty_label,
            seed=rerun_seed,
            session_spend_cents=0.0,
            version=old.version + 1,
            # D-186: carried from the superseded row rather than re-derived from the tier.
            # The docstring above promises "the same topic/skill/difficulty", and once a
            # tier is shared by two skills, deriving from the tier silently returns the
            # other one - a re-run that quietly changes which skill the slot belongs to.
            skill_id=old.skill_id,
        )
    except (BedrockGatewayError, PipelineConfigError) as exc:
        await session.rollback()
        return f"edit-and-rerun for {question_template_id} failed: {exc}"
    await session.commit()
    if outcome.status == "retiered":
        # Worth saying out loud rather than folding into "new candidate": the reviewer
        # asked for a rerun at one tier and got a usable item at another (D-239).
        return (
            f"superseded {question_template_id} -> new candidate "
            f"{outcome.question_template_id}, re-tiered to the judge's reading"
        )
    if outcome.status == "pending":
        return f"superseded {question_template_id} -> new candidate {outcome.question_template_id}"
    return f"superseded {question_template_id} -> rerun rejected: {outcome.reasons}"


def _seed_from_template_id(question_template_id: str) -> int:
    # Template ids are "authored-{topic_id}-d{difficulty_label}-{seed}" (see
    # `ai_pipeline.generate_authored_candidate`) - the seed is always the last segment.
    return int(question_template_id.rsplit("-", 1)[-1])


async def main() -> None:
    parser = argparse.ArgumentParser(description="Review pending authored question-bank items")
    parser.add_argument("--topic", default=None, help="Restrict to one topic_id (default: all)")
    parser.add_argument(
        "--rejected",
        action="store_true",
        help="Read-only: print rejected candidates with their full content and evidence",
    )
    parser.add_argument(
        "--planned-id",
        default=None,
        help="With --rejected, show only the candidate planned for this template id",
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="With --rejected, how many runs to show"
    )
    args = parser.parse_args()

    if args.rejected:
        # Returns before a gateway is built, which is the point: inspecting a rejection
        # must not be able to spend money, and the only paid path in this CLI
        # (edit-and-rerun) needs the gateway that this branch never creates.
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                print(await show_rejected(session, limit=args.limit, planned_id=args.planned_id))
        finally:
            await engine.dispose()
        return

    settings = get_pipeline_settings()
    gateway = _build_gateway(settings)
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            repo = QuestionRepository(session)
            pending = await repo.get_pending_authored_by_priority(args.topic)
            if not pending:
                print("No pending authored items to review.")
                return
            print(f"{len(pending)} pending item(s) to review.\n")
            for template in pending:
                variant = await repo.get_variant_for_template(template.question_template_id)
                validation_run = await repo.get_latest_validation_run(template.question_template_id)
                print(render_item(template, variant, validation_run))
                choice = (
                    input("[a]pprove / [r]eject / [e]dit-and-rerun / [s]kip / [q]uit: ")
                    .strip()
                    .lower()
                )
                if choice == "q":
                    break
                if choice == "s":
                    print()
                    continue
                try:
                    if choice == "a":
                        print(await approve(session, template.question_template_id))
                    elif choice == "r":
                        print(await reject(session, template.question_template_id))
                    elif choice == "e":
                        print(await edit_and_rerun(session, gateway, template.question_template_id))
                    else:
                        print(f"unrecognized choice {choice!r}, skipping")
                except CostBudgetExceededError as exc:
                    print(f"budget exceeded during edit-and-rerun: {exc}")
                print()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
