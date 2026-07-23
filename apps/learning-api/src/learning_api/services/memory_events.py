"""S25 episodic event emission (SPEC §5.15.2, plan §9) - the six trigger points named
in ROADMAP S25: answer submitted, intervention chosen (+hint level), retry-ladder
outcome, chat turn (intent + resolution only), exam finalized, gain computed. Called
directly from `graph/nodes.py` (the same place `HintEventRepository`/
`TutorChatMessageRepository` writes already happen, not from `services/flow.py` - `flow`
deliberately owns no repository for the session object itself, see its own docstring).

Every `structured_payload` shape here must match what
`intellichoice_memory.events.render_event_summary` expects - see that module's
docstring for the shared contract. Never write raw chat text into a payload here (D-072/
plan §9's "not the message text" rule) - only a `tutor_chat_message_id` reference, which
the consolidation worker resolves separately and only for that one Bedrock call.
"""

from intellichoice_db.models.memory import LearningEvent
from intellichoice_db.repositories.memory import MemoryRepository
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_memory.events import (
    ANSWER_SUBMITTED,
    CHAT_TURN,
    EXAM_FINALIZED,
    INTERVENTION_CHOSEN,
    LEARNING_GAIN_COMPUTED,
    STUDY_OUTCOME,
)


async def _topic_skill_for_variant(
    question_repo: QuestionRepository, question_variant_id: str
) -> tuple[str | None, str | None]:
    variant = await question_repo.get_variant(question_variant_id)
    if variant is None:
        return None, None
    template = await question_repo.get_template(variant.question_template_id)
    if template is None:
        return None, None
    return template.topic_id, template.skill_id


async def emit_answer_submitted(
    memory_repo: MemoryRepository,
    question_repo: QuestionRepository,
    *,
    student_external_id: str,
    session_id: str,
    question_variant_id: str,
    is_correct: bool,
    response_time_ms: int,
    phase: str,
) -> None:
    topic_id, skill_id = await _topic_skill_for_variant(question_repo, question_variant_id)
    await memory_repo.record_event(
        LearningEvent(
            student_external_id=student_external_id,
            session_id=session_id,
            event_type=ANSWER_SUBMITTED,
            topic_id=topic_id,
            skill_id=skill_id,
            question_variant_id=question_variant_id,
            structured_payload={
                "is_correct": is_correct,
                "response_time_ms": response_time_ms,
                "phase": phase,
            },
        )
    )


async def emit_intervention_chosen(
    memory_repo: MemoryRepository,
    question_repo: QuestionRepository,
    *,
    student_external_id: str,
    session_id: str,
    question_variant_id: str,
    choice: str,
    hint_level: int | None,
) -> None:
    topic_id, skill_id = await _topic_skill_for_variant(question_repo, question_variant_id)
    await memory_repo.record_event(
        LearningEvent(
            student_external_id=student_external_id,
            session_id=session_id,
            event_type=INTERVENTION_CHOSEN,
            topic_id=topic_id,
            skill_id=skill_id,
            question_variant_id=question_variant_id,
            structured_payload={"choice": choice, "hint_level": hint_level},
        )
    )


async def emit_study_outcome(
    memory_repo: MemoryRepository,
    question_repo: QuestionRepository,
    *,
    student_external_id: str,
    session_id: str,
    question_variant_id: str,
    target_skill_id: str,
    outcome_label: str,
) -> None:
    topic_id, _ = await _topic_skill_for_variant(question_repo, question_variant_id)
    await memory_repo.record_event(
        LearningEvent(
            student_external_id=student_external_id,
            session_id=session_id,
            event_type=STUDY_OUTCOME,
            topic_id=topic_id,
            # The skill line's base skill (not a prerequisite remediation item's own
            # skill) - matches what a `weak_skill`/`strength` fact should be about.
            skill_id=target_skill_id,
            question_variant_id=question_variant_id,
            structured_payload={
                "outcome_label": outcome_label,
                "target_skill_id": target_skill_id,
            },
        )
    )


async def emit_chat_turn(
    memory_repo: MemoryRepository,
    question_repo: QuestionRepository,
    *,
    student_external_id: str,
    session_id: str,
    question_variant_id: str | None,
    intent: str,
    resolved: bool,
    tutor_chat_message_id: str,
) -> None:
    topic_id: str | None = None
    skill_id: str | None = None
    if question_variant_id is not None:
        topic_id, skill_id = await _topic_skill_for_variant(question_repo, question_variant_id)
    await memory_repo.record_event(
        LearningEvent(
            student_external_id=student_external_id,
            session_id=session_id,
            event_type=CHAT_TURN,
            topic_id=topic_id,
            skill_id=skill_id,
            question_variant_id=question_variant_id,
            structured_payload={
                "intent": intent,
                "resolved": resolved,
                "tutor_chat_message_id": tutor_chat_message_id,
            },
        )
    )


async def emit_exam_finalized(
    memory_repo: MemoryRepository,
    *,
    student_external_id: str,
    session_id: str,
    topic_id: str | None,
    session_type: str,
    raw_score: float | None,
) -> None:
    await memory_repo.record_event(
        LearningEvent(
            student_external_id=student_external_id,
            session_id=session_id,
            event_type=EXAM_FINALIZED,
            topic_id=topic_id,
            structured_payload={"session_type": session_type, "raw_score": raw_score},
        )
    )


async def emit_learning_gain_computed(
    memory_repo: MemoryRepository,
    *,
    student_external_id: str,
    session_id: str,
    topic_id: str | None,
    weighted_gain: float,
    unresolved_skills: list[str],
) -> None:
    await memory_repo.record_event(
        LearningEvent(
            student_external_id=student_external_id,
            session_id=session_id,
            event_type=LEARNING_GAIN_COMPUTED,
            topic_id=topic_id,
            structured_payload={
                "weighted_gain": weighted_gain,
                "unresolved_skills": unresolved_skills,
            },
        )
    )
