import { ApiError } from "./client";

/**
 * Turns a backend failure into something a K-12 student can read.
 *
 * Every mutation in `useLearningSession` used to surface `String(err.detail)` directly,
 * which is the API's own wire text. Measured on staging at 2026-08-06T20:12:46Z, a
 * `POST /answers` took a 409 and the student's screen showed the raw detail - text like
 * `question variant 3f2a… is not an item of this session`. That is a debugging string; the
 * primary users of this app are minors, and a session id in an error message is both
 * frightening and useless to them.
 *
 * The mapping is keyed on **status plus a substring of the detail**, not on status alone,
 * because `/answers` alone returns 409 for five distinct situations (`sessions.py`), and
 * "you already answered this one" and "your time ran out" call for different words. An
 * unrecognised failure falls through to a single generic line rather than to the raw text:
 * a message nobody wrote is not a message worth showing a child.
 *
 * The raw detail is not discarded - `logDetail` puts it on the console, where it stays
 * available for exactly the person who wants it (us) and invisible to the person who
 * doesn't (them).
 */

const GENERIC = "Something didn't go through. Give it another try in a moment.";

const OFFLINE =
  "We can't reach the server right now. Check your connection and try again.";

interface Rule {
  status: number;
  // `null` matches any detail for that status; otherwise a list of lowercase substrings,
  // any one of which matches.
  detail: string[] | null;
  message: string;
}

// Order matters: the first match wins, so the specific rules for a status precede its
// catch-all.
//
// The substrings are quoted from the raisers, not guessed. `ItemAlreadyAnsweredError`
// formats `item {id} has already been answered` - the first draft of this file tested for
// "already answered", which is *not* a substring of that, so a duplicate submission fell
// through to the generic line. Caught by reading a Playwright failure screenshot rather
// than by reasoning about it, which is the argument for keeping these anchored to short,
// stable fragments.
const RULES: Rule[] = [
  {
    status: 409,
    detail: ["already been answered", "already answered"],
    message: "You've already answered this one — it's saved.",
  },
  {
    status: 409,
    detail: ["time limit"],
    message: "Your exam time is up. Submit your exam to finish.",
  },
  {
    status: 409,
    detail: ["not an item of this session"],
    message:
      "That question isn't part of this session any more. Refresh the page to pick up where you are now.",
  },
  {
    status: 409,
    detail: ["not accepting answers"],
    message: "This part of the session has moved on. Refresh the page to continue.",
  },
  {
    status: 409,
    detail: ["select a student"],
    message: "This session hasn't finished starting up. Go back and start it again.",
  },
  { status: 409, detail: null, message: "That didn't fit where the session is right now." },
  {
    status: 401,
    detail: null,
    message: "You've been signed out. Sign in again to keep going.",
  },
  {
    status: 403,
    detail: null,
    message: "This isn't available for your account.",
  },
  {
    status: 400,
    detail: ["attendance"],
    message: "Attendance for this week hasn't been confirmed yet.",
  },
  { status: 429, detail: null, message: "That was a lot at once — wait a moment and try again." },
];

function isServerError(status: number): boolean {
  return status >= 500;
}

export function friendlyError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    // A thrown `TypeError: Failed to fetch` is what a dropped connection looks like here.
    return OFFLINE;
  }
  logDetail(error);

  if (isServerError(error.status)) {
    return "Something broke on our side. It's not you — try again in a moment.";
  }

  const detail = detailText(error).toLowerCase();
  for (const rule of RULES) {
    if (rule.status !== error.status) continue;
    if (rule.detail === null || rule.detail.some((fragment) => detail.includes(fragment))) {
      return rule.message;
    }
  }
  return GENERIC;
}

/**
 * `ApiError.detail` is already unwrapped from FastAPI's `{"detail": ...}` envelope
 * (`client.ts`), but a 422 carries an *array* of validation errors rather than a string,
 * and `String(...)` on that yields `[object Object]` - which is how this class of bug
 * showed up before. Flattening here keeps the substring rules above honest.
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
  // Kept out of the UI, kept in the console. Not `console.error`: §2.6 criterion 3 counts
  // console errors, and a handled 409 that the student was told about in plain language is
  // not an unhandled error.
  console.warn(`[api] ${error.status}`, error.detail);
}
