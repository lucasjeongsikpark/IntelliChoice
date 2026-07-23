"""QAState (SPEC §5.19.3), checkpointed via LangGraph's `AsyncPostgresSaver` (§5.16) -
same checkpointing approach as `learning_api.graph.state.LearningState`.

`location_consent`/`ephemeral_location` (branch-locator fields) are still not present -
S15 adds them alongside the Google Maps MCP tool, matching this project's existing
"don't stub ahead of time" convention (see `LearningState`'s own docstring). No names or
email addresses are stored here (SPEC §5.30) - `email_draft` is deliberately typed as
`EmailDraftState` (subject/body only, no recipient - see that model's own docstring),
never the full `EmailMessage`; `calendar_event` has no such concern since a
`CalendarEvent`'s fields come from public organizational documents, not a person.
`pending_interrupt` is NOT a stored field here - unlike this file's own request/response
DTOs, whether a turn is paused is read straight off `aget_state().tasks` per request
(mirrors `learning_api`'s own approach), so there's no risk of a denormalized copy
drifting from the real checkpoint.
"""

from intellichoice_shared.calendar import CalendarEvent
from pydantic import BaseModel

from chat_api.services.admin_escalation import EmailDraftState


class QAState(BaseModel):
    session_id: str

    user_external_id: str | None = None
    authenticated: bool = False
    user_role: str = "public"
    branch_external_id: str | None = None

    # `standalone_query` would be a conversation-history-aware rewrite of `query` (e.g.
    # resolving "when is it?" against a prior turn) - single-turn only this session, so
    # it's always identical to `query`; multi-turn contextualization is a later carry-over.
    query: str | None = None
    standalone_query: str | None = None

    scope: str | None = None
    intent: str | None = None

    # External chunk ids only, not full chunk bodies - the citations below already carry
    # every field a caller needs to display (SPEC §5.21.8's `Citation` schema).
    retrieved_chunk_ids: list[str] | None = None

    answer: str | None = None
    citations: list[dict] | None = None
    confidence: float | None = None
    missing_information: str | None = None
    escalation_recommended: bool = False
    # SPEC §18-C3: set only by `explain_access` when the metadata-only probe finds a
    # role- or branch-gated match behind an otherwise-empty role-filtered retrieval -
    # `None` on every other path, including a genuine no-answer.
    access_hint: dict | None = None

    # Running total of Bedrock spend for this session (SPEC §5.25.1 "per-session cost
    # budget") - persisted so the budget survives a process restart, mirroring
    # `LearningState.bedrock_spend_cents`.
    bedrock_spend_cents: float = 0.0

    # SPEC §5.19.3 - populated by `admin_escalation`/`calendar_action` right before
    # each pauses via `interrupt()`; read back by `/respond`'s pending-interrupt preview
    # and by the resuming node itself (a resumed node replays from the top, so this must
    # be re-readable from checkpointed state, not only the transient `interrupt()`
    # payload - mirrors D-021's "context needed before the pause" gotcha).
    email_draft: EmailDraftState | None = None
    calendar_event: CalendarEvent | None = None
    # S18: a deterministic "what's coming up" listing from `org_events` (title/
    # starts_at/location dicts) - populated only when no single event was matched and
    # at least one real event is upcoming; routed straight to an answer, no
    # `interrupt()` (SPEC §5.23.1's "information request", not an action).
    event_listing: list[dict] | None = None
    # Set only on the `calendar_action` "google" choice falling back to `.ics` (SPEC
    # §5.29 "Google Calendar failure -> Generate .ics") or the "ics" choice directly -
    # the generated RFC 5545 text, returned inline in the response (no download
    # endpoint exists yet - that's chat-web's job, S16).
    ics_content: str | None = None

    # Transient per-turn routing flag written by `prepare_admin_escalation` and read
    # only by that node's own conditional edge - split into its own field (not reused
    # from another field) so the rate-limit decision is unambiguous regardless of what
    # a prior turn on this same thread last set.
    rate_limited: bool = False
