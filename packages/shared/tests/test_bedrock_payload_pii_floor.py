"""SPEC §5.30.1 "minimum necessary data" test - mirrors D-011's exact-match PII
denylist approach for Postgres columns, applied here to every payload type that ever
crosses the Bedrock gateway. `HintPersonalizationPayload` (S21) is a second, narrower
allowlist - see DECISIONS.md's D-023 follow-up entry for why it's a distinct model
rather than a widened `BedrockTutorPayload`. `LearningChatIntentPayload`/
`TutorChatPayload` (S24, D-072) are the first payloads carrying free text -
`redacted_message` is the one deliberate extension, and only ever holds text that has
already passed `intellichoice_shared.pii_redaction.redact_free_text`.

**AUD-L-05 (D-175): "every payload type" was the claim and six of twenty was the fact.**
D-072's "How to apply" clause requires each new free-text payload to appear here, and the
clause was never enforced by anything but memory, so `MemoryConsolidationPayload` - the
payload closest to real student free text - was missing for a session, and the four chat
payloads and `VideoClassificationPayload` were never governed by this file or by
`test_generation_payload_schemas.py`. Two structural fixes, because adding seven rows
would leave the eighth to the same memory:

1. **The check recurses.** `MemoryConsolidationPayload`'s own three field names are
   `events`/`existing_facts`/`allowed_fact_types` - a shallow scan of *those* passes
   trivially while `MemoryEventSummary.summary` carries the student's chat text one level
   down. A field-name denylist that stops at the top level would have been decoration on
   exactly the payload the finding was filed about. Nested models are first-class rows in
   `_PII_ALLOWLISTS` and `test_every_nested_model_is_itself_governed` proves none is
   reachable without one.
2. **Governance is total and asserted.** Every `*Payload` in `intellichoice_shared.bedrock`
   must sit in exactly one of three regimes - this file's field allowlist, the generation
   payloads' `extra="forbid"`-only regime (`test_generation_payload_schemas.py`, whose
   narrower standard is deliberate and reasoned), or `_UNGOVERNED_WITH_REASON` with a
   written justification. `test_every_bedrock_payload_is_governed_by_one_regime` fails on
   a *new payload class*, not just on a new field, which is the level the original defect
   happened at.
"""

import typing

import pytest
from intellichoice_shared import bedrock
from intellichoice_shared.bedrock import (
    BedrockTutorPayload,
    CalendarContextChunk,
    CalendarExtractionPayload,
    HintPersonalizationPayload,
    LearningChatIntentPayload,
    LlmJudgePayload,
    MemoryConsolidationPayload,
    MemoryEventSummary,
    MemoryExistingFact,
    NarrativeDressingPayload,
    RagAnswerPayload,
    RagContextChunk,
    ReportInterpretationPayload,
    RerankCandidate,
    RerankPayload,
    ScopeAndIntentPayload,
    StageNarrativePayload,
    TutorChatPayload,
    VideoClassificationPayload,
)
from pydantic import BaseModel, ValidationError

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
    # AUD-L-15 (D-156). Both are fixed English strings built from module constants in
    # `services/report.py` - no student data reaches them, and neither is interpolated
    # from anything but `_REPORT_WEAK_SKILL_POST_ACCURACY`. They say which window a figure
    # came from, which the single `date_range_label` above used to misstate for two of
    # them.
    "mastery_window_label",
    "weak_skill_window_label",
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

# AUD-L-05 (D-175). The payload D-072's clause named, plus its two nested models - which
# are where the student text actually is. `MemoryEventSummary.summary` is a code-rendered
# one-line summary of a real `learning_events` row, and for a `chat_turn` event it may
# include the student's own already-`redact_free_text`-ed chat text (approved for this one
# task by D-074). `MemoryExistingFact.fact_text` is derived from that same text. Neither is
# raw student input, and both are named here so that a future field carrying something
# stronger has to pass this file.
_MEMORY_CONSOLIDATION_ALLOWED_FIELDS = {
    "events",
    "existing_facts",
    "allowed_fact_types",
}

_MEMORY_EVENT_SUMMARY_ALLOWED_FIELDS = {
    "event_id",
    "event_type",
    "topic_id",
    "skill_id",
    "summary",
}

_MEMORY_EXISTING_FACT_ALLOWED_FIELDS = {
    "semantic_memory_id",
    "fact_type",
    "skill_id",
    "fact_text",
    "status",
    "confidence",
}

# AUD-L-05 (D-175): the chat app's four payloads, governed here for the first time.
# `query`/`standalone_query` hold the user's typed question verbatim and `chunk_text` holds
# approved org document content; `user_role` is a role string, never an identifier. The
# field-name floor is what this file can enforce - **that the query text itself is not
# redacted before the wire is a separate, live finding (AUD-C-24), not something these
# allowlists assert.** Kept as an exact match anyway: it is the mechanism by which a future
# session adding, say, `student_external_id` for "personalized answers" trips a test.
_SCOPE_AND_INTENT_ALLOWED_FIELDS = {"standalone_query", "user_role"}

_RERANK_ALLOWED_FIELDS = {"query", "candidates"}

_RERANK_CANDIDATE_ALLOWED_FIELDS = {"candidate_index", "chunk_text"}

_RAG_ANSWER_ALLOWED_FIELDS = {"query", "user_role", "context_chunks"}

_RAG_CONTEXT_CHUNK_ALLOWED_FIELDS = {"context_index", "chunk_text"}

_CALENDAR_EXTRACTION_ALLOWED_FIELDS = {"query", "as_of_date", "context_chunks"}

_CALENDAR_CONTEXT_CHUNK_ALLOWED_FIELDS = {"chunk_id", "chunk_text"}

# AUD-L-05 (D-175). Org content, not student data: `title`/`description` are a fetched
# YouTube video's own metadata and the two lists are curriculum names. No student field has
# any business here, which is the whole point of pinning it.
_VIDEO_CLASSIFICATION_ALLOWED_FIELDS = {
    "title",
    "description",
    "known_topic_names",
    "known_skill_names",
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

# Regime 1: an exact field allowlist, enforced by the three parametrized tests below.
# Nested models are rows in their own right - see this module's docstring, point 1.
_PII_ALLOWLISTS: dict[type[BaseModel], set[str]] = {
    BedrockTutorPayload: _ALLOWED_FIELDS,
    HintPersonalizationPayload: _HINT_PERSONALIZATION_ALLOWED_FIELDS,
    LearningChatIntentPayload: _LEARNING_CHAT_INTENT_ALLOWED_FIELDS,
    TutorChatPayload: _TUTOR_CHAT_ALLOWED_FIELDS,
    StageNarrativePayload: _STAGE_NARRATIVE_ALLOWED_FIELDS,
    ReportInterpretationPayload: _REPORT_INTERPRETATION_ALLOWED_FIELDS,
    MemoryConsolidationPayload: _MEMORY_CONSOLIDATION_ALLOWED_FIELDS,
    MemoryEventSummary: _MEMORY_EVENT_SUMMARY_ALLOWED_FIELDS,
    MemoryExistingFact: _MEMORY_EXISTING_FACT_ALLOWED_FIELDS,
    ScopeAndIntentPayload: _SCOPE_AND_INTENT_ALLOWED_FIELDS,
    RerankPayload: _RERANK_ALLOWED_FIELDS,
    RerankCandidate: _RERANK_CANDIDATE_ALLOWED_FIELDS,
    RagAnswerPayload: _RAG_ANSWER_ALLOWED_FIELDS,
    RagContextChunk: _RAG_CONTEXT_CHUNK_ALLOWED_FIELDS,
    CalendarExtractionPayload: _CALENDAR_EXTRACTION_ALLOWED_FIELDS,
    CalendarContextChunk: _CALENDAR_CONTEXT_CHUNK_ALLOWED_FIELDS,
    VideoClassificationPayload: _VIDEO_CLASSIFICATION_ALLOWED_FIELDS,
}

# Regime 2: `extra="forbid"` only, no field allowlist - the S9/S20 question-generation
# payloads carry curriculum content rather than student data, and
# `test_generation_payload_schemas.py` owns them. Listed by name here so the completeness
# test below can see them; that file, not this one, asserts their properties.
_GENERATION_REGIME_PAYLOAD_NAMES = {
    "GeneratorPayload",
    "SolverPayload",
    "DifficultyReviewPayload",
    "AmbiguityReviewPayload",
    "AlignmentReviewPayload",
    "AuthoredGeneratorPayload",
    "QuestionJudgePayload",
}

# Regime 3: ungoverned on purpose, with the reason written down. An entry here is a claim
# that has to survive being read - not a place to park a payload nobody wants to allowlist.
_UNGOVERNED_WITH_REASON: dict[type[BaseModel], str] = {
    NarrativeDressingPayload: (
        "Every field is curriculum content the caller computed before the call: an equation "
        "from a registered shape, its answer, its four option values, and the topic/skill/"
        "grade-band names from the taxonomy (D-192). No student is involved - this is the "
        "offline authoring pipeline, so there is no request, no session and no learner "
        "whose data could reach it. Same regime as the other §5.8.3 generation payloads, "
        "which are bound by `extra=\"forbid\"` rather than by a §5.30.1 field list (D-026)."
    ),
    LlmJudgePayload: (
        "`content_to_judge`/`context` hold already-generated text (a hint, solution, chat "
        "reply, or RAG answer plus its grounding context) that passed the PII floor when it "
        "was first generated (D-023), not raw student fields. The exclusion and its "
        "reasoning are stated at the class's own definition site in bedrock.py, and this "
        "row is that comment made mechanical."
    ),
}


def _payload_classes_in_bedrock_module() -> set[type[BaseModel]]:
    """Every `*Payload` model the gateway module defines, discovered rather than listed.

    Discovery is the point: a hand-maintained list of payloads is the thing that fell out
    of date and produced AUD-L-05 in the first place.
    """
    found: set[type[BaseModel]] = set()
    for name in dir(bedrock):
        if not name.endswith("Payload"):
            continue
        candidate = getattr(bedrock, name)
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            found.add(candidate)
    return found


def _nested_models(model: type[BaseModel]) -> set[type[BaseModel]]:
    """The Pydantic models reachable one hop from `model`'s field annotations.

    Unwraps one level of generic args, which covers every shape this module actually uses
    (`list[RerankCandidate]`, `X | None`). A future deeper nesting would surface as a
    missing allowlist row rather than as silent non-coverage.
    """
    reachable: set[type[BaseModel]] = set()
    for field in model.model_fields.values():
        annotation = field.annotation
        for candidate in (annotation, *typing.get_args(annotation)):
            for inner in (candidate, *typing.get_args(candidate)):
                if isinstance(inner, type) and issubclass(inner, BaseModel):
                    reachable.add(inner)
    return reachable


def test_every_bedrock_payload_is_governed_by_one_regime() -> None:
    """AUD-L-05 (D-175): the test that fails on a new *payload*, not a new field.

    D-072's "add it to the allowlist" clause was enforced by memory alone, and memory
    missed `MemoryConsolidationPayload` plus the four chat payloads and
    `VideoClassificationPayload`. This is that clause turned into an assertion.
    """
    governed_names = (
        {cls.__name__ for cls in _PII_ALLOWLISTS}
        | _GENERATION_REGIME_PAYLOAD_NAMES
        | {cls.__name__ for cls in _UNGOVERNED_WITH_REASON}
    )
    discovered_names = {cls.__name__ for cls in _payload_classes_in_bedrock_module()}

    assert discovered_names - governed_names == set(), (
        "these Bedrock payloads are governed by no PII regime - add a field allowlist to "
        "_PII_ALLOWLISTS, or an entry to _UNGOVERNED_WITH_REASON with a written reason"
    )
    # And the reverse: a regime naming a payload that no longer exists is a stale claim.
    # Restricted to `*Payload` names, because `_PII_ALLOWLISTS` deliberately also holds
    # nested models (`RerankCandidate`, `MemoryEventSummary`, ...) that discovery does not
    # and should not return - `test_every_nested_model_is_itself_governed` owns those.
    stale = {name for name in governed_names if name.endswith("Payload")} - discovered_names
    assert stale == set(), f"regimes name payloads that no longer exist: {sorted(stale)}"


def test_every_nested_model_is_itself_governed() -> None:
    """The recursion AUD-L-05's own payload needed.

    `MemoryConsolidationPayload`'s field names are `events`/`existing_facts`/
    `allowed_fact_types`; the student text is in `MemoryEventSummary.summary`, one level
    down, where a top-level-only denylist scan cannot see it.
    """
    missing: list[str] = []
    for payload_cls in _PII_ALLOWLISTS:
        for nested in _nested_models(payload_cls):
            if nested not in _PII_ALLOWLISTS:
                missing.append(f"{payload_cls.__name__}.-> {nested.__name__}")

    assert missing == [], (
        f"nested models reachable from an allowlisted payload but not allowlisted "
        f"themselves: {missing}"
    )


@pytest.mark.parametrize(
    ("model_cls", "allowed_fields"),
    [pytest.param(k, v, id=k.__name__) for k, v in _PII_ALLOWLISTS.items()],
)
def test_payload_field_set_matches_allowlist_exactly(
    model_cls: type[BaseModel], allowed_fields: set[str]
) -> None:
    assert set(model_cls.model_fields) == allowed_fields


@pytest.mark.parametrize(
    "model_cls", [pytest.param(k, id=k.__name__) for k in _PII_ALLOWLISTS]
)
def test_payload_has_no_denylisted_pii_field_name(model_cls: type[BaseModel]) -> None:
    assert set(model_cls.model_fields) & _PII_DENYLIST == set()


@pytest.mark.parametrize(
    "model_cls", [pytest.param(k, id=k.__name__) for k in _PII_ALLOWLISTS]
)
def test_payload_forbids_extra_fields(model_cls: type[BaseModel]) -> None:
    """`extra="forbid"` is what makes the allowlist above binding at runtime rather than
    merely descriptive: without it an unexpected field is accepted and forwarded.
    """
    assert model_cls.model_config.get("extra") == "forbid"


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


# The six constructor tests below stay hand-written rather than parametrized: each one
# exercises real Pydantic validation with a plausible payload plus one denylisted field,
# which is stronger evidence than `model_config["extra"] == "forbid"` alone. The field-set
# and denylist assertions they used to carry are now the parametrized tests above, which
# cover all seventeen allowlisted models instead of these six.


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


def test_learning_chat_intent_payload_rejects_unknown_extra_fields() -> None:
    with pytest.raises(ValidationError):
        LearningChatIntentPayload(
            redacted_message="can I get a hint?",
            parent_contact="parent@example.com",  # type: ignore[call-arg]
        )


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


def test_stage_narrative_payload_rejects_unknown_extra_fields() -> None:
    with pytest.raises(ValidationError):
        StageNarrativePayload(
            stage="pre_outro",
            grade="6",
            weak_skill_names=["Two-Step Equations"],
            parent_contact="parent@example.com",  # type: ignore[call-arg]
        )


def test_report_interpretation_payload_rejects_unknown_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ReportInterpretationPayload(
            audience="parent",
            grade="6",
            date_range_label="last 30 days",
            weak_skill_names=["Two-Step Equations"],
            parent_contact="parent@example.com",  # type: ignore[call-arg]
        )
