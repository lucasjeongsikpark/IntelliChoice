"""LearningState (SPEC §5.5.3), checkpointed via LangGraph's `PostgresSaver` (§5.16).

Only the fields exercised by phases built so far (S5's flow, S6's routing) are present.
Fields for later sessions (`intervention_choice`, `hint_count`, `estimated_theta`,
`pending_interrupt`, ...) are added when the node logic that sets them exists (S7/S8/S10),
not stubbed ahead of time. No names or email addresses are stored here (SPEC §5.5.3) - only
external ids, mirroring the Postgres PII rule (SPEC §5.30).
"""

from pydantic import BaseModel


class LearningState(BaseModel):
    session_id: str

    user_external_id: str | None = None
    user_role: str | None = None
    student_external_id: str | None = None
    parent_external_id: str | None = None

    week_id: str | None = None
    attendance_status: str | None = None

    # Named `topic_id`/`phase` (not `current_topic_id`/`current_phase`) so `flow.py`'s S5
    # node bodies - written to accept any object with these attributes - work on this
    # state unmodified (see `flow.py`'s own docstring: "so S6 can lift this logic into
    # LangGraph nodes without a rewrite").
    topic_id: str | None = None
    phase: str = "created"

    # Domain-table linkage (not in SPEC's exact §5.5.3 list, needed to resume mid-phase -
    # same extension pattern D-012 used for other tables without an exact spec schema).
    pre_assessment_session_id: str | None = None
    study_session_id: str | None = None
    post_assessment_session_id: str | None = None
    blocked_session_id: str | None = None

    # Candidate children ids when a parent must disambiguate (SPEC §5.6.1's "Multiple
    # children -> Child Selection interrupt()" branch). Set right before `resolve_student`
    # calls `interrupt()`, external ids only - the checkpointer persists this in Postgres,
    # so no MySQL-sourced display data (name/grade/branch) ever belongs here (D-020); the
    # router re-derives a human-readable preview per request from a live MySQL lookup.
    candidate_children: list[str] | None = None

    # SPEC §5.6.5: how a blocked attendance session was resolved, set by `resolve_attendance`.
    attendance_resolution: str | None = None

    # Bridges `submit_answer` (which records the misconception attempt) to the
    # `intervention_choice` node (which pauses via `interrupt()` for hint/solution/video
    # and then updates that same attempt row) - the two run as separate graph supersteps,
    # so this transient id is how the second node finds the row the first one wrote.
    last_study_attempt_id: str | None = None

    # Transient response payload from the most recent graph turn, re-served verbatim by
    # `/resume` after a restart so the caller sees the same pending question.
    last_message: str | None = None
    last_is_correct: bool | None = None
    last_items: list[dict[str, str | int]] | None = None
    last_learning_gain: dict | None = None
    last_error: str | None = None
    # Generated hint/solution/video content from `intervention_choice` (SPEC §5.11.3-
    # §5.11.6, S8) - a plain dict so the checkpointer doesn't need a schema per
    # intervention type; `routers/sessions.py` shapes it into a typed response.
    last_intervention: dict | None = None
    # S26 (SPEC §5.10.3/§5.13.3, plan §18-L7): the most recently generated stage
    # narrative (`pre_outro`/`study_step`/`study_outro`/`post_outro` - `pre_intro` fires
    # from the SSE connect path, outside a graph turn, so it's never written here; see
    # `routers/sessions.py`'s `_initial_snapshot`). Re-served verbatim on `/resume` like
    # `last_message`, and overwritten by the next narrative-firing turn.
    stage_narrative: str | None = None
    # S26: plain-language "How we personalized this" lines accompanying `stage_narrative`
    # (see `services/stage_narrative.py::_evidence_summary`) - always set together with
    # `stage_narrative`, never independently.
    stage_narrative_evidence: list[str] | None = None

    # Running total of Bedrock spend for this session (SPEC §5.25.1 "per-session cost
    # budget") - persisted so the budget survives a process restart, unlike the gateway's
    # own in-memory circuit-breaker state.
    bedrock_spend_cents: float = 0.0

    # S21 within-question hint ladder: current hint level already served per
    # `question_variant_id`, so a checkpoint restart mid-ladder resumes at the right
    # level instead of restarting from level 1. Keyed by variant (not attempt id) to
    # match `HintEvent`'s own keying and because the attempt id isn't guaranteed set on
    # every turn that might read this.
    assistance_level_by_variant: dict[str, int] = {}
    # Transient routing signal only, read once by `graph/build.py`'s
    # `_route_after_intervention_choice` immediately after this turn - True means the
    # node looped back to its own `interrupt()` for another round (more hints
    # available) instead of calling `flow.advance_study`; not meaningful afterward.
    hint_ladder_awaiting_choice: bool = False

    # Set on every `ainvoke` input to pick this turn's entry node (`graph/build.py`'s
    # `_route_entry`); overwritten every call, not meaningful once a turn completes.
    entry_action: str | None = None

    # D-217: an ids-only marker left by `submit_answer`/`intervention_choice` when a
    # `study_step`/`study_outro` narrative should fire but its Bedrock call was deferred
    # off the answer's critical path (real-Bedrock only; see
    # `services/stage_narrative_scheduler.py`). The route reads it, hands it to the
    # background scheduler, and the narrative arrives in a later SSE snapshot. Never a
    # name or grade - the background task re-derives those from its own session, keeping
    # the PII rule (SPEC §5.30) intact. `None` on every inline (mock-provider) turn.
    pending_study_narrative: dict | None = None
    # D-272: the same shape as `pending_study_narrative`, for the hint that has been served
    # canonically and is still waiting to be personalized. Ids only, never text - the
    # background task re-reads everything it needs, so nothing here can go stale against the
    # rows (SPEC §5.5.3).
    pending_hint_personalization: dict | None = None
