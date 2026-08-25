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

    # D-348: the client's own id for the turn that produced this state, echoed back on every
    # response and on `/stream`'s initial snapshot so a browser can tell *which* turn a
    # snapshot describes. Checkpointed rather than request-scoped precisely because the
    # reconnect case is the one that needs it: after a reload the client rebuilds its
    # transcript from storage and the only thing that can match a snapshot to a bubble is an
    # id that survived in the checkpoint.
    #
    # Not the query text, which was the obvious alternative: `post_message` redacts free text
    # (AUD-C-24) before it reaches this state, so a question containing an email address would
    # arrive back differing from what the client typed and match nothing. A uuid carries no PII
    # and cannot be altered in transit.
    client_turn_id: str | None = None

    scope: str | None = None
    intent: str | None = None

    # D-351: why this turn ended the way it did, as a `TurnReason` value. Set by whichever
    # node produced `answer`, cleared with the rest of the last turn's result by
    # `resolve_role`. This is the field a client branches on; `answer` is the words.
    reason: str | None = None

    # AUD-C-07/AUD-C-08: set by any node that hit a `BedrockGatewayError` it had no
    # fallback for, and read only by that node's own router, which sends the turn to
    # `service_unavailable`. Per-turn, not sticky - `resolve_role` clears it alongside
    # the other last-turn fields, or an outage would outlive itself on every thread it
    # touched. Deliberately NOT surfaced on the API response: the user-visible signal is
    # the message text, and widening the response shape would break the e2e drift
    # control for a field no client needs to branch on.
    service_degraded: bool = False

    # External chunk ids only, not full chunk bodies - the citations below already carry
    # every field a caller needs to display (SPEC §5.21.8's `Citation` schema). D-423
    # constraint 2 turns on this: retrieval now runs a superstep earlier than synthesis, and
    # the whole point of re-fetching bodies by id in `synthesize_answer` is that moving
    # retrieval earlier must not buy latency by putting chunk text into the checkpoint.
    retrieved_chunk_ids: list[str] | None = None

    # D-423/WORK-01: what retrieval's Bedrock calls cost, in its own channel rather than
    # added straight into `bedrock_spend_cents`. `scope_guard` and `retrieve_context` run in
    # the *same* superstep now, and every node here writes the spend field as an absolute
    # running total - so two writers in one step is a LangGraph `InvalidUpdateError`
    # (measured, not assumed: `LastValue.update` raises "can receive only one value per
    # step"), and an additive reducer would be the wrong fix because it would sum two
    # totals rather than two deltas. `join_scope_and_retrieval` folds this into the running
    # total one superstep later, where it is again the only writer, and zeroes it.
    retrieval_spend_cents: float = 0.0

    # D-423/WORK-01: the concurrent retrieval failed. Deliberately NOT `service_degraded`:
    # only a `document_qa` turn is waiting on that result, and the verdict that decides it is
    # produced by `scope_guard` in the same superstep, so the failure cannot be interpreted
    # until both halves have finished. `join_scope_and_retrieval` promotes it to
    # `service_degraded` on a `document_qa` turn (unchanged fail-closed behaviour) and drops
    # it with a log line on every other intent - fail closed for the work the turn needed,
    # fail quiet for the work nothing was waiting on. Per-turn; cleared by `resolve_role`.
    retrieval_failed: bool = False

    # D-423/WORK-01: the exception *class name* when that failure was not a
    # `BedrockGatewayError` - a statement timeout or a dropped Postgres connection, say,
    # which the sequential graph never had to consider on a calendar or admin-contact turn
    # because retrieval did not run there. The class name only, never the message: this field
    # is checkpointed and a DB error's message can quote the statement's parameters, which
    # include the caller's own question (SPEC §5.30). `join_scope_and_retrieval` re-raises on
    # a `document_qa` turn - an unexpected error is still a 500, exactly as today - and
    # logs-and-drops it on every other intent.
    retrieval_unexpected_error: str | None = None

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

    # D-164: the caller is forwarding an already-asked question to a human rather than
    # asking a new one (chat-web's "Ask an administrator" button on a no-source refusal).
    # Comes in on `AskInput` every turn rather than being written by a node, which is what
    # makes it safe against staleness: `resolve_role` deliberately does NOT clear it,
    # because the router that reads it runs immediately after and would see the cleared
    # value instead of this turn's.
    escalate: bool = False

    # AUD-C-06 (D-164): set by `synthesize_answer` when synthesis ended in the no-source
    # refusal, and read only by that node's own router, which then runs the SPEC §18-C3
    # access probe (`explain_access`). Same shape and same reasons as `service_degraded`
    # above: per-turn (cleared by `resolve_role`, or a refusal would keep re-probing on
    # every later turn of the thread), a stored flag rather than something the router
    # re-derives from `answer` (the router must tell this refusal apart from the
    # *conflict* and *service-unavailable* ones, and that comparison belongs to
    # `services.qa.is_no_source_refusal`, which owns the message it compares against),
    # and deliberately absent from the API response - no client needs to branch on it,
    # and the e2e drift control exists to keep the response shape from growing fields
    # nobody reads.
    no_source_refusal: bool = False
