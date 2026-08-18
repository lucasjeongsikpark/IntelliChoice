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
  access_hint?: { message: string } | null;
  suggested_followups: string[];
  ics_content?: string | null;
  pending_interrupt?: Record<string, unknown> | null;
  // D-348: echoed back so a client can tell which of its turns a payload describes.
  client_turn_id?: string | null;
  // D-351: the closed reason code the client branches on.
  reason?: string | null;
}

// Kept in step with `chat_api.services.outcomes.ACCESS_REQUIRED_MESSAGE` by
// `test_turn_reasons.py`'s copy assertions on the server side; duplicated here because the
// e2e fixtures deliberately do not import from the Python app.
const ACCESS_REQUIRED_MESSAGE =
  "I can't answer that from the sources available to you. Some information is only " +
  "available once you sign in, so signing in may help.";

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
  client_turn_id: null,
  reason: "answer",
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

  // AUD-C-11: the refusal the API used to return *with* citations attached. Fixed in the
  // backend by D-164, so this shape is no longer reachable from a real turn - kept as the
  // record of how it rendered, not as evidence about current behaviour. See the comment on
  // its test in `response-shapes.spec.ts` for why that distinction is load-bearing.
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

  // D-220: `answer` and `access_hint.message` are the SAME string, because that is what
  // `chat_api.graph.nodes.explain_access` returns - it sets `answer = hint.message`. This
  // fixture used to give them two different sentences, which is a shape production never
  // emits, and that is precisely why the duplicate-render defect survived a green e2e run
  // and was found by walking the deployed build instead. Keep them equal: with the two
  // different, the `renders:` assertions below cannot see the duplication at all.
  // D-351: the copy is now generic and names no tier, and the fixture uses the real string
  // rather than a paraphrase - `ChatScreen`'s D-220 de-duplication compares `answer` against
  // `access_hint.message` exactly, so a fixture that only *looks* like the real pair would
  // exercise the opposite branch of the very check this shape exists to cover.
  "access hint": {
    ...base,
    answer: ACCESS_REQUIRED_MESSAGE,
    citations: [],
    reason: "access_required",
    access_hint: { message: ACCESS_REQUIRED_MESSAGE },
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

  /** The `cancel` branch of the calendar interrupt. `answer` is `nodes.py`'s
   *  `CALENDAR_CANCELLED_MESSAGE`, quoted rather than paraphrased. */
  "calendar cancelled": {
    ...base,
    intent: "calendar_action",
    answer: "Okay, nothing was added to your calendar.",
    citations: [],
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

  // D-221: subject and body are the *real* output of
  // `chat_api.services.admin_escalation.build_escalation_draft` for the escalate path -
  // generated from it, not written here - for the same reason D-220 made `answer` and
  // `access_hint.message` equal: this file's header says the Pydantic model is the
  // authority, but `pending_interrupt` is typed `Record<string, unknown>`, so the one thing
  // the modal actually shows a human was the one thing nothing checked. Both fields used to
  // be invented prose about a student and Saturday hours, which no code path can emit.
  //
  // Worth keeping honest specifically here: the opening line is the administrator's only
  // statement of *why* this arrived, and D-219 shipped a version of it that was unreachable
  // in the graph while three unit tests passed. A fixture that paraphrases the template
  // cannot show that, and a person reading the modal in a trace is the last check left.
  "email_approval interrupt": {
    ...base,
    intent: "escalation",
    answer: null,
    pending_interrupt: {
      interrupt_type: "email_approval",
      email_subject: `IntelliChoice Q&A escalation - session ${SESSION_ID}`,
      email_body:
        "A user (role: public) asked a question the assistant could not answer:\n\n" +
        "Question: Do you offer transport from the middle school to the Dallas branch?\n" +
        "Missing information: No effective, approved document covers this topic.\n\n" +
        `Chat session: ${SESSION_ID}`,
    },
  },

  "calendar_action interrupt": {
    ...base,
    intent: "calendar_action",
    answer: null,
    pending_interrupt: {
      interrupt_type: "calendar_action",
      // D-352: these were `summary` / `start_time`, which no version of the backend has
      // ever emitted - the real `intellichoice_shared.calendar.CalendarEvent` uses
      // `title` / `start_datetime` / `end_datetime` / `timezone`. `CalendarActionModal`
      // reads the real names, so the drifted fixture rendered a title of literally
      // "Event" and an empty " – " date range, and the shape test passed anyway because
      // it only asserted that *a modal appeared*. The drift control at the top of
      // `response-shapes.spec.ts` could not see it either: it compares top-level
      // `/messages` keys, and `pending_interrupt` is `Record<string, unknown>`.
      calendar_event: {
        title: "Baton Rouge parent session",
        start_datetime: "2026-08-08T14:00:00Z",
        end_datetime: "2026-08-08T15:00:00Z",
        timezone: "America/Chicago",
        location: "Baton Rouge branch",
        description: "Termly parent update.",
        source_document_id: "doc-branch-directory",
        source_page: 4,
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
