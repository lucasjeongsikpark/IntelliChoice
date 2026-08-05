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

from intellichoice_curriculum.ai_pipeline import PipelineConfigError, generate_authored_candidate
from intellichoice_curriculum.content import load_curriculum
from intellichoice_curriculum.generation import SHAPES
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
        lines.append(f"pipeline evidence: {validation_run.stage_results}")
    return "\n".join(lines)


class UnservableTemplateError(Exception):
    """Approving this template would put content in the active bank that the runtime
    cannot render - see `approve`.
    """


async def approve(session: AsyncSession, question_template_id: str) -> str:
    """Approval is a human action (D-026) and this is the documented way in, so it is
    also where "would this content actually serve?" has to be answered.

    D-188 measured what happens without this, by approving five authored templates and
    running the suite: 34 tests failed with `VariantGenerationError: unknown shape
    'authored'`, because every served question went through
    `generation.generate_variant(shape_key=template.solution_function)` and an authored
    template has no shape. D-189 built the serving path, so the question is no longer
    "does this render?" but "is there anything to serve?" - a template with no shape is
    served from its canonical variant, and one with neither is unservable.

    Refusing here is the fail-closed direction (CLAUDE.md rule 5): a reviewer working
    through `make question-review` cannot silently brick exam building for real students.
    It is deliberately not a repository-level guard - `intellichoice_db` importing
    `intellichoice_curriculum`'s shape registry would invert the dependency (curriculum
    already imports the repositories).
    """
    repo = QuestionRepository(session)
    template = await repo.get_template(question_template_id)
    if template is not None and template.solution_function not in SHAPES:
        canonical_variant = await repo.get_variant_for_template(question_template_id)
        if canonical_variant is None:
            raise UnservableTemplateError(
                f"{question_template_id} has solution_function="
                f"{template.solution_function!r}, which the runtime variant generator has "
                f"no shape for, and no canonical variant to serve instead - approving it "
                f"would make exam building raise for any student who draws it."
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
    args = parser.parse_args()

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
                validation_run = await repo.get_latest_validation_run(
                    template.question_template_id
                )
                print(render_item(template, variant, validation_run))
                choice = input(
                    "[a]pprove / [r]eject / [e]dit-and-rerun / [s]kip / [q]uit: "
                ).strip().lower()
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
                        print(
                            await edit_and_rerun(session, gateway, template.question_template_id)
                        )
                    else:
                        print(f"unrecognized choice {choice!r}, skipping")
                except CostBudgetExceededError as exc:
                    print(f"budget exceeded during edit-and-rerun: {exc}")
                print()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
