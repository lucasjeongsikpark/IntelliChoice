/**
 * The response shapes `POST /chat/sessions/{id}/messages` can emit, as concrete
 * payloads, so each one can be *rendered* in a browser rather than reasoned about.
 *
 * S37 enumerated all fourteen against `ChatScreen`/`App` by reading the render code and
 * concluded twelve render correctly (AUDIT_FINDINGS.md, S37 negative results). Reading
 * is not rendering, which is why that sub-item kept S37 at ⏸. These fixtures close it.
 *
 * Every field here comes from `chat_api.routers.sessions.MessageResponse` - the
 * authority is the Pydantic model, not this file. `tests/chat/response-shapes.spec.ts`
 * guards against drift with a control that runs one *real* turn and asserts the live
 * response's field set matches these fixtures': a stub that has drifted from the
 * backend audits fiction, and would do so silently.
 */

export interface ShapeCitation {
  document_title: string;
  document_version: number;
  page_number: number | null;
  section_title: string | null;
  source_reference: string;
  supporting_quote_hash: string;
}

export interface Shape {
  chat_session_id: string;
  scope?: string | null;
  intent?: string | null;
  answer?: string | null;
  citations: ShapeCitation[];
  confidence?: number | null;
  missing_information?: string | null;
  escalation_recommended: boolean;
  access_hint?: { required_role: string; message: string } | null;
  suggested_followups: string[];
  ics_content?: string | null;
  pending_interrupt?: Record<string, unknown> | null;
}

export const SESSION_ID = "00000000-0000-4000-8000-00000000f39a";

const base: Shape = {
  chat_session_id: SESSION_ID,
  scope: "in_scope",
  intent: "org_question",
  answer: null,
  citations: [],
  confidence: null,
  missing_information: null,
  escalation_recommended: false,
  access_hint: null,
  suggested_followups: [],
  ics_content: null,
  pending_interrupt: null,
};

const citation: ShapeCitation = {
  document_title: "Branch Handbook",
  document_version: 3,
  page_number: 12,
  section_title: "Saturday hours",
  source_reference: "branch-handbook-v3#saturday-hours",
  supporting_quote_hash: "sha256:0f1e2d3c",
};

/**
 * Keyed by the name S37's enumeration used, so a finding can be traced from that list
 * to the rendered evidence without a translation step.
 */
export const SHAPES: Record<string, Shape> = {
  "grounded answer": {
    ...base,
    answer: "The Baton Rouge branch is open 9am to 1pm on Saturdays.",
    citations: [citation],
    confidence: 0.91,
    suggested_followups: ["What about Sunday?", "Where is the Baton Rouge branch?"],
  },

  "no-source refusal": {
    ...base,
    answer:
      "I don't have an approved source that answers that, so I'd rather not guess. An administrator can help.",
    citations: [],
    confidence: 0.2,
    missing_information: "No effective, approved document covers this topic.",
    escalation_recommended: true,
  },

  // AUD-C-11: the same refusal the API actually returns *with* citations attached.
  "no-source refusal with citations (AUD-C-11)": {
    ...base,
    answer: "I don't have an approved source that answers that, so I'd rather not guess.",
    citations: [citation],
    confidence: 0.31,
    escalation_recommended: true,
  },

  "conflict message": {
    ...base,
    answer:
      "Two approved documents disagree about this, so I've asked an administrator to confirm before I answer.",
    citations: [citation, { ...citation, document_version: 4, section_title: "Revised hours" }],
    confidence: 0.44,
    missing_information: "Conflicting effective sources.",
    escalation_recommended: true,
  },

  "out-of-scope refusal": {
    ...base,
    scope: "out_of_scope",
    intent: null,
    answer:
      "I can only help with IntelliChoice topics — branches, schedules, volunteering, and your learning here.",
    citations: [],
  },

  clarification: {
    ...base,
    answer: "Which branch did you mean? I can check hours for Baton Rouge or for the online program.",
    citations: [],
    confidence: 0.5,
    missing_information: "Branch not specified.",
    suggested_followups: ["Baton Rouge", "Online program"],
  },

  "access hint": {
    ...base,
    answer: "That information is available to tutors and branch managers.",
    citations: [],
    access_hint: {
      required_role: "tutor",
      message: "Sign in as a tutor to see branch procedures.",
    },
  },

  "event listing": {
    ...base,
    intent: "calendar_question",
    answer: "There are two sessions at Baton Rouge this week: Tuesday 4pm and Saturday 10am.",
    citations: [citation],
    confidence: 0.88,
    suggested_followups: ["Add Saturday to my calendar"],
  },

  ".ics result": {
    ...base,
    intent: "calendar_action",
    answer: "Here's a calendar file for Saturday's session.",
    citations: [citation],
    // Deliberately a real minimal VCALENDAR - `downloadIcs` builds a Blob from it.
    ics_content:
      "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//IntelliChoice//EN\r\nBEGIN:VEVENT\r\nUID:e39a\r\nDTSTAMP:20260801T090000Z\r\nDTSTART:20260808T140000Z\r\nSUMMARY:Baton Rouge session\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n",
  },

  "rate-limited escalation": {
    ...base,
    answer: "I'm getting more questions than I can answer right now. An administrator can help.",
    citations: [],
    escalation_recommended: true,
    missing_information: "Rate limited.",
  },

  "email sent": {
    ...base,
    intent: "escalation",
    answer: "I've sent your question to an administrator. They'll follow up with you.",
    citations: [],
  },

  "email declined": {
    ...base,
    intent: "escalation",
    answer: "No problem — I didn't send anything.",
    citations: [],
  },

  "email failed": {
    ...base,
    intent: "escalation",
    answer: "I couldn't send that message. Please try again, or contact your branch directly.",
    citations: [],
    escalation_recommended: true,
  },

  "location declined": {
    ...base,
    intent: "branch_locator",
    answer: "That's fine — tell me a city or ZIP code and I'll find the nearest branch.",
    citations: [],
  },

  "location missing": {
    ...base,
    intent: "branch_locator",
    answer: "I need a ZIP code or city to find the nearest branch.",
    citations: [],
    missing_information: "No location provided.",
  },

  "email_approval interrupt": {
    ...base,
    intent: "escalation",
    answer: null,
    pending_interrupt: {
      interrupt_type: "email_approval",
      email_subject: "Question from a student about Saturday hours",
      email_body: "A student asked about Saturday hours at Baton Rouge and I could not answer it.",
    },
  },

  "calendar_action interrupt": {
    ...base,
    intent: "calendar_action",
    answer: null,
    pending_interrupt: {
      interrupt_type: "calendar_action",
      calendar_event: {
        summary: "Baton Rouge session",
        start_time: "2026-08-08T14:00:00Z",
        location: "Baton Rouge branch",
      },
    },
  },

  "location_consent interrupt": {
    ...base,
    intent: "branch_locator",
    answer: null,
    pending_interrupt: {
      interrupt_type: "location_consent",
      notice:
        "To find the branch nearest you I'll use the location you share for this answer only. It is not stored.",
    },
  },
};

/** The eleven answer shapes plus the three interrupts = S37's fourteen. */
export const SHAPE_NAMES = Object.keys(SHAPES);
