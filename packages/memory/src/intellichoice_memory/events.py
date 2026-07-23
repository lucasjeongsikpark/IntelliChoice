"""Shared vocabulary for `learning_events.event_type`/`structured_payload` (SPEC
§5.15.2) - the one place the emitter (`learning_api.services.memory_events`) and the
consolidation renderer below agree on field names, so the two can't silently drift
apart. `learning_api` depends on this package (D-009's "apps depend on packages, not
the reverse") purely for these constants; the renderer itself is only ever called from
`consolidation.py`.

Six emission points (plan §9): answer submitted, intervention chosen (hint level/
choice), retry-ladder outcome label, chat turn (intent + resolution only - never the
message text, see `chat_turn`'s own note below), exam finalized, gain computed.
"""

ANSWER_SUBMITTED = "answer_submitted"
INTERVENTION_CHOSEN = "intervention_chosen"
STUDY_OUTCOME = "study_outcome"
CHAT_TURN = "chat_turn"
EXAM_FINALIZED = "exam_finalized"
LEARNING_GAIN_COMPUTED = "learning_gain_computed"


def render_event_summary(event_type: str, payload: dict, *, chat_text: str | None = None) -> str:
    """Code-owned, deterministic one-line rendering of a `LearningEvent` for the
    `MEMORY_CONSOLIDATION` payload - never a raw JSON dump, so the model has readable
    prose to reason over and cite (`MemoryEventSummary.summary`). `chat_text` is looked
    up by the caller from `tutor_chat_messages` via the event's own
    `tutor_chat_message_id` (D-074) - the raw message text never lives in
    `learning_events.structured_payload` itself, only this rendering ever combines the
    two, and only for this one Bedrock call.
    """
    if event_type == ANSWER_SUBMITTED:
        outcome = "correctly" if payload.get("is_correct") else "incorrectly"
        phase = payload.get("phase", "a")
        response_ms = payload.get("response_time_ms")
        return f"Answered a {phase} question {outcome} in {response_ms}ms."

    if event_type == INTERVENTION_CHOSEN:
        choice = payload.get("choice", "no")
        level = payload.get("hint_level")
        level_text = f" (level {level})" if level else ""
        return f"Chose {choice}{level_text} support after an incorrect study answer."

    if event_type == STUDY_OUTCOME:
        return (
            f"Study line for skill {payload.get('target_skill_id')} resolved as "
            f"{payload.get('outcome_label')}."
        )

    if event_type == CHAT_TURN:
        resolved = "resolved" if payload.get("resolved") else "not resolved"
        text = f"Chat turn, intent={payload.get('intent')} ({resolved})."
        if chat_text:
            text += f" Student message: {chat_text}"
        return text

    if event_type == EXAM_FINALIZED:
        return (
            f"Finalized a {payload.get('session_type')} with raw score "
            f"{payload.get('raw_score')}."
        )

    if event_type == LEARNING_GAIN_COMPUTED:
        return (
            f"Learning gain computed: weighted_gain={payload.get('weighted_gain')}, "
            f"unresolved_skills={payload.get('unresolved_skills')}."
        )

    return event_type
