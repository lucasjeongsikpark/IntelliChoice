"""SPEC §5.30.1 "minimum necessary data" test - mirrors D-011's exact-match PII
denylist approach for Postgres columns, applied here to every payload type that ever
crosses the Bedrock gateway. `HintPersonalizationPayload` (S21) is a second, narrower
allowlist - see DECISIONS.md's D-023 follow-up entry for why it's a distinct model
rather than a widened `BedrockTutorPayload`. `LearningChatIntentPayload`/
`TutorChatPayload` (S24, D-072) are the first payloads carrying free text -
`redacted_message` is the one deliberate extension, and only ever holds text that has
already passed `intellichoice_shared.pii_redaction.redact_free_text`.
"""

import pytest
from intellichoice_shared.bedrock import (
    BedrockTutorPayload,
    HintPersonalizationPayload,
    LearningChatIntentPayload,
    ReportInterpretationPayload,
    StageNarrativePayload,
    TutorChatPayload,
)
from pydantic import ValidationError

_ALLOWED_FIELDS = {
    "grade",
    "current_topic",
    "skill",
    "estimated_level",
    "question",
    "selected_answer",
    "relevant_learning_fact",
}

_HINT_PERSONALIZATION_ALLOWED_FIELDS = {
    "grade",
    "skill",
    "question",
    "selected_answer",
    "canonical_hint_text",
    "misconception_tag",
    "attempt_count",
    "hint_level",
    "previous_hint_summaries",
    "relevant_learning_fact",
}

_LEARNING_CHAT_INTENT_ALLOWED_FIELDS = {"redacted_message"}

_TUTOR_CHAT_ALLOWED_FIELDS = {
    "grade",
    "current_topic",
    "skill",
    "question",
    "selected_answer",
    "relevant_learning_fact",
    "redacted_message",
}

_STAGE_NARRATIVE_ALLOWED_FIELDS = {
    "stage",
    "grade",
    "attendance_status",
    "weak_skill_names",
    "target_skill_name",
    "completed_skill_name",
    "pre_raw_score",
    "post_raw_score",
    "raw_gain",
    "normalized_gain",
    "hint_count",
    "solution_count",
    "video_count",
    "independent_correct_rate",
    "relevant_learning_facts",
}

_REPORT_INTERPRETATION_ALLOWED_FIELDS = {
    "audience",
    "grade",
    "date_range_label",
    "pre_raw_score",
    "post_raw_score",
    "raw_gain",
    "overall_accuracy",
    "mastery_by_skill",
    "weak_skill_names",
    "hint_count",
    "solution_count",
    "video_count",
    "independent_correct_rate",
    "attempts_count",
    "time_spent_minutes",
    "tutor_review_flagged",
    "relevant_learning_facts",
}

_PII_DENYLIST = {
    "full_name",
    "display_name",
    "name",
    "email",
    "phone",
    "home_address",
    "address",
    "precise_location",
    "location",
    "parent_contact",
    "branch_manager_email",
    "student_external_id",
    "parent_external_id",
    "raw_message",
    "message",
}


def test_payload_field_set_matches_spec_exactly() -> None:
    assert set(BedrockTutorPayload.model_fields) == _ALLOWED_FIELDS


def test_payload_has_no_denylisted_pii_field_names() -> None:
    assert set(BedrockTutorPayload.model_fields) & _PII_DENYLIST == set()


def test_payload_rejects_unknown_extra_fields() -> None:
    with pytest.raises(ValidationError):
        BedrockTutorPayload(
            grade="6",
            current_topic="Linear Equations",
            skill="Two-Step Equations",
            estimated_level="0.40",
            question="Solve for x: x + 3 = 7",
            selected_answer="3",
            parent_contact="parent@example.com",  # type: ignore[call-arg]
        )


def test_hint_personalization_payload_field_set_matches_allowlist_exactly() -> None:
    assert set(HintPersonalizationPayload.model_fields) == _HINT_PERSONALIZATION_ALLOWED_FIELDS


def test_hint_personalization_payload_has_no_denylisted_pii_field_names() -> None:
    assert set(HintPersonalizationPayload.model_fields) & _PII_DENYLIST == set()


def test_hint_personalization_payload_rejects_unknown_extra_fields() -> None:
    with pytest.raises(ValidationError):
        HintPersonalizationPayload(
            grade="6",
            skill="Two-Step Equations",
            question="Solve for x: x + 3 = 7",
            selected_answer="3",
            canonical_hint_text="Try the opposite operation on both sides.",
            attempt_count=1,
            hint_level=1,
            parent_contact="parent@example.com",  # type: ignore[call-arg]
        )


def test_learning_chat_intent_payload_field_set_matches_allowlist_exactly() -> None:
    assert set(LearningChatIntentPayload.model_fields) == _LEARNING_CHAT_INTENT_ALLOWED_FIELDS


def test_learning_chat_intent_payload_has_no_denylisted_pii_field_names() -> None:
    assert set(LearningChatIntentPayload.model_fields) & _PII_DENYLIST == set()


def test_learning_chat_intent_payload_rejects_unknown_extra_fields() -> None:
    with pytest.raises(ValidationError):
        LearningChatIntentPayload(
            redacted_message="can I get a hint?",
            parent_contact="parent@example.com",  # type: ignore[call-arg]
        )


def test_tutor_chat_payload_field_set_matches_allowlist_exactly() -> None:
    assert set(TutorChatPayload.model_fields) == _TUTOR_CHAT_ALLOWED_FIELDS


def test_tutor_chat_payload_has_no_denylisted_pii_field_names() -> None:
    assert set(TutorChatPayload.model_fields) & _PII_DENYLIST == set()


def test_tutor_chat_payload_rejects_unknown_extra_fields() -> None:
    with pytest.raises(ValidationError):
        TutorChatPayload(
            grade="6",
            current_topic="Linear Equations",
            skill="Two-Step Equations",
            question="Solve for x: x + 3 = 7",
            selected_answer="3",
            redacted_message="why is this wrong?",
            parent_contact="parent@example.com",  # type: ignore[call-arg]
        )


def test_stage_narrative_payload_field_set_matches_allowlist_exactly() -> None:
    assert set(StageNarrativePayload.model_fields) == _STAGE_NARRATIVE_ALLOWED_FIELDS


def test_stage_narrative_payload_has_no_denylisted_pii_field_names() -> None:
    assert set(StageNarrativePayload.model_fields) & _PII_DENYLIST == set()


def test_stage_narrative_payload_rejects_unknown_extra_fields() -> None:
    with pytest.raises(ValidationError):
        StageNarrativePayload(
            stage="pre_outro",
            grade="6",
            weak_skill_names=["Two-Step Equations"],
            parent_contact="parent@example.com",  # type: ignore[call-arg]
        )


def test_report_interpretation_payload_field_set_matches_allowlist_exactly() -> None:
    assert set(ReportInterpretationPayload.model_fields) == _REPORT_INTERPRETATION_ALLOWED_FIELDS


def test_report_interpretation_payload_has_no_denylisted_pii_field_names() -> None:
    assert set(ReportInterpretationPayload.model_fields) & _PII_DENYLIST == set()


def test_report_interpretation_payload_rejects_unknown_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ReportInterpretationPayload(
            audience="parent",
            grade="6",
            date_range_label="last 30 days",
            weak_skill_names=["Two-Step Equations"],
            parent_contact="parent@example.com",  # type: ignore[call-arg]
        )
