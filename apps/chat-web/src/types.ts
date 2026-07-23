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
  required_role: Role;
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
}
