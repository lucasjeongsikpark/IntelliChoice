"""Topic Resolver (ROADMAP S8 build item; SPEC §5.11.4's TutorContext assembly).

This is a deterministic (non-LLM) resolver: it builds a `TutorContext` from ids already
known from graph state (`question_variant_id`, `selected_option`), never from free
text - nothing in this session's endpoints accepts a free-text topic/skill reference.
SPEC §5.25.2's "Topic mapping | Reliable structured output" row implies an eventual
LLM-based resolver for free-text input (e.g. a Tutor Agent follow-up question), but that
has no caller until a free-text endpoint exists (most likely S13's Intent Router) - per
this project's "don't stub ahead of time" convention, that variant isn't built until then.
"""

from intellichoice_db.models.mastery import Mastery
from intellichoice_db.models.questions import QuestionTemplate, QuestionVariant
from intellichoice_db.repositories.curriculum import CurriculumRepository
from intellichoice_db.repositories.mastery import MasteryRepository
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_shared.bedrock import TutorContext
from intellichoice_shared.profiles import ProfileAdapter

from learning_api.services.mastery_bootstrap import WEAK_SKILL_THRESHOLD

_OPTION_LABELS = ("a", "b", "c", "d")


class TopicResolutionError(Exception):
    """A referenced template/topic/skill/variant/profile no longer exists."""


def resolve_misconception_tag(
    template: QuestionTemplate, variant: QuestionVariant, selected_option: str
) -> str | None:
    """S21: maps the student's actual wrong option to a `common_error_tags` entry by
    its ordinal rank among the three non-correct options (alphabetical a/b/c/d order,
    excluding the correct one). Deterministic and testable, and works uniformly for
    shape and authored templates (both store `common_error_tags` as a flat list) - but
    it's a coarse mapping, not a true per-distractor-generator trace back to which
    specific error produced that option (that would need to replay `generation.py`'s
    seeded RNG; future work if hint personalization quality demands it, not built this
    session - see PROGRESS.md carry-over).
    """
    if not template.common_error_tags:
        return None
    wrong_option_labels = [label for label in _OPTION_LABELS if label != variant.correct_option]
    try:
        rank = wrong_option_labels.index(selected_option)
    except ValueError:
        return None
    if rank >= len(template.common_error_tags):
        return None
    return template.common_error_tags[rank]


def resolve_mastery_state(mastery: Mastery | None) -> str:
    """S27 (SPEC §5.18.3 video query enrichment): a coarse, deterministic label reusing
    the same `WEAK_SKILL_THRESHOLD` the study plan's own weak-skill classification
    already relies on - not a new threshold invented for this one caller.
    """
    if mastery is None:
        return "unassessed"
    return "weak_skill" if mastery.weighted_score < WEAK_SKILL_THRESHOLD else "proficient"


async def resolve_tutor_context(
    *,
    profile_adapter: ProfileAdapter,
    question_repo: QuestionRepository,
    curriculum_repo: CurriculumRepository,
    mastery_repo: MasteryRepository,
    student_external_id: str,
    question_variant_id: str,
    selected_option: str,
) -> TutorContext:
    profile = await profile_adapter.get_student_profile(student_external_id)
    if profile is None:
        raise TopicResolutionError(f"unknown student {student_external_id!r}")

    variant = await question_repo.get_variant(question_variant_id)
    if variant is None:
        raise TopicResolutionError(f"unknown question variant {question_variant_id!r}")
    template = await question_repo.get_template(variant.question_template_id)
    if template is None:
        raise TopicResolutionError(f"unknown question template {variant.question_template_id!r}")

    topic = await curriculum_repo.get_topic(template.topic_id)
    skill = await curriculum_repo.get_skill(template.skill_id)
    if topic is None or skill is None:
        raise TopicResolutionError(
            f"unknown topic/skill for template {template.question_template_id!r}"
        )

    mastery = await mastery_repo.get_mastery(student_external_id, template.skill_id)
    estimated_level = (
        f"{mastery.weighted_score:.2f}"
        if mastery is not None
        else f"difficulty {template.difficulty_label}"
    )

    selected_option_text = {
        "a": variant.option_a,
        "b": variant.option_b,
        "c": variant.option_c,
        "d": variant.option_d,
    }.get(selected_option, selected_option)

    return TutorContext(
        grade=profile.grade,
        estimated_level=estimated_level,
        topic=topic.name,
        skill=skill.name,
        question=variant.rendered_question,
        selected_wrong_answer=selected_option_text,
        common_error_tag=resolve_misconception_tag(template, variant, selected_option),
        # `TutorContext.previous_hints` stays unused/empty - S21's within-question hint
        # ladder sources its own history from `HintEventRepository`, not this field
        # (D-023: this field never crosses the gateway anyway, only
        # `HintPersonalizationPayload.previous_hint_summaries` does).
        previous_hints=[],
    )


async def resolve_correct_answer_text(
    *, question_repo: QuestionRepository, question_variant_id: str
) -> str:
    """The ground-truth answer text for `tutor.generate_solution`'s SPEC §5.12.2
    verification step - never derived from an LLM.
    """
    variant = await question_repo.get_variant(question_variant_id)
    if variant is None:
        raise TopicResolutionError(f"unknown question variant {question_variant_id!r}")
    return {
        "a": variant.option_a,
        "b": variant.option_b,
        "c": variant.option_c,
        "d": variant.option_d,
    }[variant.correct_option]
