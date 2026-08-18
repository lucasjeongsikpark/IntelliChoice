// Mirrors the Pydantic response/request models in
// apps/chat-api/src/chat_api/routers/{sessions,stream}.py and main.py's
// DevTokenRequest/Response. Kept as plain hand-written types (no codegen) - the backend
// is the source of truth; update both sides together when a shape changes.

export type Role = "student" | "parent" | "tutor" | "branch_manager";

export interface Citation {
  document_title: string;
  document_version: number;
  page_number: number | null;
  section_title: string | null;
  source_reference: string;
  supporting_quote_hash: string;
}

export interface EmailApprovalInterrupt {
  interrupt_type: "email_approval";
  email_subject?: string | null;
  email_body?: string | null;
}

export interface CalendarActionInterrupt {
  interrupt_type: "calendar_action";
  calendar_event?: Record<string, unknown> | null;
}

export interface LocationConsentInterrupt {
  interrupt_type: "location_consent";
  notice?: string | null;
}

export type PendingInterrupt =
  | EmailApprovalInterrupt
  | CalendarActionInterrupt
  | LocationConsentInterrupt;

// SPEC §18-C3 (see `chat_api.services.role_access.AccessHint`'s own docstring).
export interface AccessHint {
  // D-351: `required_role` was removed from the API. The tier is still selected server-side
  // and logged, so the probe stays measurable, but naming it told an unauthenticated caller
  // which role holds a document matching their terms.
  message: string;
}

// The shape shared by `/messages`'s and `/respond`'s response and the SSE stream's
// initial snapshot (see `routers/sessions.py`'s `SessionSnapshotEvent`) - one turn's
// worth of state, not a conversation transcript (QAState carries only the current
// turn - see `graph/state.py`'s `QAState`).
export interface TurnSnapshot {
  event?: "session_update";
  chat_session_id: string;
  scope?: string | null;
  intent?: string | null;
  answer?: string | null;
  citations: Citation[];
  confidence?: number | null;
  missing_information?: string | null;
  escalation_recommended: boolean;
  access_hint?: AccessHint | null;
  suggested_followups: string[];
  ics_content?: string | null;
  pending_interrupt?: PendingInterrupt | null;
  // D-351: why the turn ended this way, as a closed server-side code (`TurnReason`). The
  // field to branch on - `answer` is the words. Optional because a session checkpointed
  // before this existed has no reason recorded.
  reason?: string | null;
  // D-348: the `turnId` this client sent with the question, echoed back on the response and
  // on every snapshot describing that turn. Optional because a session started before this
  // field existed still has checkpoints without it.
  client_turn_id?: string | null;
}

// `GET /chat/meta` (see `routers/meta.py`'s `ChatMetaResponse`) - anonymous-OK, no
// session/graph state, safe to call before a first message is ever sent.
export interface ChatMeta {
  welcome_text: string;
  suggested_prompts: string[];
}

// Client-only: the visible conversation, built up locally turn by turn (the backend
// never stores or replays a full transcript).
export interface ChatTurn {
  id: string;
  query: string;
  response: TurnSnapshot | null;
  // AUD-C-10: a turn has three states, not two. `response === null` alone meant "in
  // flight", so a failed request left the turn indistinguishable from a pending one and
  // `ChatScreen` rendered `Thinking…` forever. `error` is what makes the third state
  // representable; it is cleared whenever a real response arrives for this turn.
  error?: string | null;
  // D-352: a fourth state, and a distinct one. A turn the user *stopped* is not a turn that
  // failed - it needs no apology and no "couldn't be sent", just an offer to ask again. The
  // flag rather than a string comparison against the message, so the wording stays a
  // rendering concern.
  cancelled?: boolean;
  /**
   * D-413 (`AUD-CHAT-07`): a fifth state — the turn was replayed from storage after a reload
   * and no snapshot ever arrived to finish it.
   *
   * **It cannot reuse `error`, because that bubble says "That message couldn't be sent." and
   * here that is false.** A replayed turn shows `Thinking…` precisely *because* the question was
   * sent; what is unknown is what became of it. Telling a visitor their message never left is
   * the `AEL-01` defect — a failure path that states the opposite of what happened — so this gets
   * its own wording, exactly as `cancelled` did rather than being folded into `error`.
   *
   * Set only by the mount deadline in `useChatSession`, guarded by `isPendingTurn`, so it can
   * never land on a turn that already reached one of the other end states.
   */
  unresolved?: boolean;
  /**
   * Whether this turn was sent as an escalation (D-378).
   *
   * **`retryTurn` re-sent it as an ordinary question without this**, because it rebuilt the
   * request from `query` alone and `escalate` defaults to false. So a failed "Ask an
   * administrator" retried straight back through the scope guard, was refused again, and
   * offered the same button - a loop that never reaches a human.
   * `escalate-from-refusal.spec.ts` asserts the flag on the *first* send precisely because
   * "omitting it would send it back through the scope guard as a fresh question"; the retry
   * was outside that assertion's reach.
   */
  escalate?: boolean;
}
