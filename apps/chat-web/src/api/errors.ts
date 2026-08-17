import { ApiError } from "./client";

/**
 * Turns a backend failure into something a visitor can read (D-347).
 *
 * A port of `apps/learning-web/src/api/errors.ts`, and the reason it is a port rather than a
 * shared module is that the *rules* are per-app: learning maps five distinct 409s from
 * `/answers`, and none of them exist here. What is shared is the shape - status plus a
 * substring of the detail, first match wins, unrecognised failures fall through to one
 * generic line rather than to the API's wire text.
 *
 * chat-web had none of this. `useChatSession` surfaced `String(err.detail)` in two places
 * and `App.tsx` in a third, so a 409 read *"That message couldn't be sent. a pending
 * interrupt must be resolved via /respond before continuing"* - an endpoint path, shown to
 * a parent asking about branch hours.
 *
 * The raw detail is not discarded: `logDetail` puts it on the console with `console.warn`,
 * not `console.error`, because §2.6 criterion 3 counts console errors and a failure the user
 * was told about in plain language is handled.
 */

const GENERIC = "Something didn't go through. Give it another try in a moment.";

// Mirrors `ChatMessageRequest.query`'s `max_length` in chat-api (D-378). Stated as a
// number the visitor can act on rather than as "too long".
export const MAX_QUERY_CHARS = 2000;

const OFFLINE = "We can't reach the server right now. Check your connection and try again.";

/** Exported so the 401 branch in `useChatSession` can act on the same classification the
 *  message comes from, rather than re-testing the status somewhere else and drifting. */
export function isSignedOut(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

interface Rule {
  status: number;
  // `null` matches any detail for that status; otherwise lowercase substrings, any of which
  // matches.
  detail: string[] | null;
  message: string;
}

// Order matters: specific rules for a status precede its catch-all.
//
// The substrings are quoted from the raisers in `chat_api.routers.sessions`, not guessed -
// learning-web's version of this file shipped with a fragment that was not actually a
// substring of the message it targeted, and a duplicate submission fell through to the
// generic line until a Playwright screenshot showed it.
const RULES: Rule[] = [
  {
    // D-378: there was no 422 rule at all, so an over-length question fell to GENERIC -
    // "Something didn't go through. Give it another try in a moment." That says nothing
    // about length, and "try again" re-sends the identical text and fails identically,
    // forever. A parent describing a situation before escalating is the realistic case.
    //
    // Matched on the field name rather than on Pydantic's wording, which is a library
    // detail. The field name is only in the entry's `loc`, never in its `msg` - which is
    // why the rules match against `matchText` and not `detailText`. See both functions.
    status: 422,
    detail: ["query"],
    message: `That question is too long. Please shorten it to under ${MAX_QUERY_CHARS} characters and send it again.`,
  },
  {
    // D-346's advisory lock. Genuinely transient and genuinely the user's own doing, so it
    // says what to do rather than what happened.
    status: 409,
    detail: ["already working on a question"],
    message: "Still working on your last question. It'll be ready in a moment.",
  },
  {
    status: 409,
    detail: ["pending interrupt"],
    message: "Answer the prompt above first, then you can carry on.",
  },
  { status: 409, detail: null, message: "That didn't fit where this conversation is right now." },
  {
    status: 401,
    detail: null,
    message: "You've been signed out. Sign in again, or keep going as a guest.",
  },
  {
    status: 403,
    detail: null,
    message: "This conversation belongs to a different account. Start a new chat to continue.",
  },
  {
    // D-346. The server already writes a visitor-facing sentence for this one, but the
    // status is mapped anyway so a future 504 from anywhere else is not raw.
    status: 504,
    detail: null,
    message: "That took too long to answer. Try asking it again, or more simply.",
  },
  {
    status: 429,
    detail: null,
    message: "That was a lot of questions at once — wait a moment and try again.",
  },
];

export function friendlyError(error: unknown): string {
  // D-374: D-352 added `REQUEST_TIMEOUT_MS` and never taught this function about it. The
  // deadline aborts with a `DOMException`, not an `ApiError`, so a timed-out turn read as
  // "You appear to be offline" — wrong and unactionable when the network is fine and the
  // server is merely slow. A caller-initiated `AbortError` is deliberately *not* handled
  // here: `useChatSession` marks that turn `cancelled` and renders "You stopped this
  // question", which is a truer sentence than any error string.
  if (error instanceof DOMException && error.name === "TimeoutError") {
    return "That question took too long to answer. Try asking it again, or more simply.";
  }
  if (!(error instanceof ApiError)) {
    // A thrown `TypeError: Failed to fetch` is what a dropped connection looks like here.
    return OFFLINE;
  }
  logDetail(error);

  // D-345's daily ceiling and the graph's own outage message both arrive as 503 with a
  // sentence already written for a visitor, so those are passed through rather than
  // replaced - unlike learning-web, which has no server-authored 5xx text to preserve.
  if (error.status === 503) {
    const detail = detailText(error);
    if (detail) return detail;
  }
  if (error.status >= 500) {
    return "Something broke on our side. It's not you — try again in a moment.";
  }

  const detail = matchText(error).toLowerCase();
  for (const rule of RULES) {
    if (rule.status !== error.status) continue;
    if (rule.detail === null || rule.detail.some((fragment) => detail.includes(fragment))) {
      return rule.message;
    }
  }
  return GENERIC;
}

/**
 * The haystack the `RULES` substrings are searched in. Differs from `detailText` in exactly
 * one way: it keeps each validation entry's `loc` path.
 *
 * **This function exists because D-378 shipped a rule that could never match.** The rule
 * targets `"query"`, the field name — and Pydantic v2 puts the field name *only* in
 * `loc: ["body", "query"]`. Its `msg` is the library's wording, `"String should have at most
 * 2000 characters"`, which names no field. `detailText` drops `loc`, so the 422 rule was dead
 * on arrival and an over-length question fell through to GENERIC — the exact outcome D-378
 * was written to prevent. Found in the deployed bundle by a live browser audit on 2026-08-16,
 * not by a test, because there was no test.
 *
 * Kept separate from `detailText` rather than folded into it: the 503 branch of
 * `friendlyError` returns `detailText` **to the visitor**, so teaching that function to emit
 * `body.query: …` would put a JSON path on a parent's screen. Matching wants a wide haystack;
 * display wants a sentence. They are different jobs.
 */
function matchText(error: ApiError): string {
  const { detail } = error;
  if (!Array.isArray(detail)) return detailText(error);
  return detail
    .map((entry) => {
      if (entry === null || typeof entry !== "object") return String(entry);
      const { msg, loc } = entry as { msg?: unknown; loc?: unknown };
      const path = Array.isArray(loc) ? loc.join(".") : "";
      return path === "" ? String(msg) : `${path}: ${String(msg)}`;
    })
    .join("; ");
}

/**
 * `ApiError.detail` is already unwrapped from FastAPI's `{"detail": ...}` envelope
 * (`client.ts`), but a 422 carries an *array* of validation errors, and `String(...)` on that
 * yields `[object Object]` - which is how this class of bug showed up in the learning app.
 *
 * Deliberately still drops `loc`: this is the **display** path (the 503 pass-through), and a
 * validation path is not a sentence. `matchText` above is the matching path.
 */
function detailText(error: ApiError): string {
  const { detail } = error;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((entry) =>
        entry !== null && typeof entry === "object" && "msg" in entry
          ? String((entry as { msg: unknown }).msg)
          : String(entry),
      )
      .join("; ");
  }
  return detail === null || detail === undefined ? "" : JSON.stringify(detail);
}

function logDetail(error: ApiError): void {
  console.warn(`[api] ${error.status}`, error.detail);
}
