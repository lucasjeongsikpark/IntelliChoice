"""CLI loader: curriculum/internal_math YAML + hand-authored templates -> Postgres.

Run with: uv run python -m intellichoice_curriculum.loader

Idempotent — safe to re-run (mirrors the MySQL seed fixtures' upsert-by-natural-key
pattern, D-002). Topics/skills use the YAML-defined ids as their primary key; each
template gets a deterministic id (`<topic_id>-d<difficulty>-<index>`) so a second run
recognizes and skips what already exists instead of inserting duplicates. A template
that fails the §5.8.5 validation suite is never inserted — the whole run aborts.
"""

import asyncio
from dataclasses import dataclass

from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.curriculum import Skill, Topic
from intellichoice_db.models.questions import (
    VARIANT_ORIGIN_CANONICAL,
    QuestionTemplate,
    QuestionVariant,
)
from intellichoice_db.repositories.curriculum import CurriculumRepository
from intellichoice_db.repositories.questions import QuestionRepository
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_curriculum.content import CurriculumContent, load_curriculum
from intellichoice_curriculum.generation import generate_variant
from intellichoice_curriculum.templates.linear_equations import LINEAR_EQUATIONS_TEMPLATES
from intellichoice_curriculum.templates.model import QuestionTemplateDef
from intellichoice_curriculum.validation import validate_variant

# topic_id -> hand-authored templates for that topic. Only linear_equations has a
# seed bank so far (D-003); fraction_operations/place_value are filled by S9.
TEMPLATE_BANKS: dict[str, list[QuestionTemplateDef]] = {
    "linear_equations": LINEAR_EQUATIONS_TEMPLATES,
}


class CurriculumLoadError(Exception):
    """A hand-authored template failed the §5.8.5 validation suite - never inserted."""


@dataclass
class LoadSummary:
    topics_created: int = 0
    skills_created: int = 0
    templates_created: int = 0
    templates_skipped_existing: int = 0
    variants_created: int = 0


async def _load_taxonomy(
    session: AsyncSession, curriculum: CurriculumContent, summary: LoadSummary
) -> None:
    repo = CurriculumRepository(session)

    for topic_def in curriculum.topics:
        if await repo.get_topic(topic_def.topic_id) is not None:
            continue
        await repo.create_topic(
            Topic(
                topic_id=topic_def.topic_id,
                curriculum_version=curriculum.curriculum_version,
                name=topic_def.name,
                grade_band=topic_def.grade_band,
            )
        )
        summary.topics_created += 1

    for skill_def in curriculum.skills:
        if await repo.get_skill(skill_def.skill_id) is not None:
            continue
        await repo.create_skill(
            Skill(skill_id=skill_def.skill_id, topic_id=skill_def.topic_id, name=skill_def.name)
        )
        summary.skills_created += 1


def _template_id(topic_id: str, index: int, template: QuestionTemplateDef) -> str:
    return f"{topic_id}-d{template.difficulty_label}-{index:02d}"


async def _load_templates(
    session: AsyncSession,
    curriculum: CurriculumContent,
    topic_id: str,
    templates: list[QuestionTemplateDef],
    summary: LoadSummary,
) -> None:
    repo = QuestionRepository(session)
    seen_questions: set[str] = set()

    for index, template_def in enumerate(templates):
        template_id = _template_id(topic_id, index, template_def)
        if await repo.get_template(template_id) is not None:
            summary.templates_skipped_existing += 1
            continue

        variant = generate_variant(
            shape_key=template_def.solution_function,
            parameter_schema=template_def.parameter_schema,
            correct_option_generator=template_def.correct_option_generator,
            distractor_generator_keys=template_def.distractor_generators,
            seed=index,
        )
        result = validate_variant(template_def, variant, curriculum, seen_questions)
        seen_questions.add(variant.rendered_question)
        if not result.passed:
            raise CurriculumLoadError(
                f"template {template_id} failed validation: {result.failures}"
            )

        template = await repo.create_template(
            QuestionTemplate(
                question_template_id=template_id,
                curriculum_version=curriculum.curriculum_version,
                topic_id=template_def.topic_id,
                skill_id=template_def.skill_id,
                grade_band=template_def.grade_band,
                difficulty_label=template_def.difficulty_label,
                difficulty_confidence=template_def.difficulty_confidence,
                question_type=template_def.question_type,
                parameter_schema=template_def.parameter_schema,
                generation_constraints=template_def.generation_constraints,
                solution_function=template_def.solution_function,
                correct_option_generator=template_def.correct_option_generator,
                distractor_generators=template_def.distractor_generators,
                common_error_tags=template_def.common_error_tags,
                estimated_time_seconds=template_def.estimated_time_seconds,
                generator_model=template_def.generator_model,
                review_model_versions=template_def.review_model_versions,
                validation_status="approved",
                active_status="active",
            )
        )
        summary.templates_created += 1

        await repo.create_variant(
            QuestionVariant(
                # The seed bank's one defining rendering per template (D-106).
                origin=VARIANT_ORIGIN_CANONICAL,
                question_template_id=template.question_template_id,
                random_seed=variant.random_seed,
                rendered_question=variant.rendered_question,
                option_a=variant.option_a,
                option_b=variant.option_b,
                option_c=variant.option_c,
                option_d=variant.option_d,
                correct_option=variant.correct_option,
                parameter_values=variant.parameter_values,
            )
        )
        summary.variants_created += 1


async def load_curriculum_and_templates(session: AsyncSession) -> LoadSummary:
    curriculum = load_curriculum()
    summary = LoadSummary()
    await _load_taxonomy(session, curriculum, summary)
    for topic_id, templates in TEMPLATE_BANKS.items():
        await _load_templates(session, curriculum, topic_id, templates, summary)
    return summary


async def main() -> None:
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            summary = await load_curriculum_and_templates(session)
            await session.commit()
        print(
            f"Loaded curriculum: {summary.topics_created} topics, {summary.skills_created} "
            f"skills, {summary.templates_created} templates created "
            f"({summary.templates_skipped_existing} already existed), "
            f"{summary.variants_created} sample variants."
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
