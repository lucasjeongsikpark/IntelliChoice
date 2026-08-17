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
    // D-381: a 404 fell through to GENERIC — "Something didn't go through. Give it another
    // try in a moment." A dead `/results/<id>` link is the case that reaches this, and it is
    // the one failure in the app that **retrying can never fix**: the session does not exist,
    // is not this student's, or predates the results endpoint. The old line advised an action
    // that was guaranteed useless and named no alternative, while the screen's own buttons
    // ("Back to start", "View progress dashboard") went unmentioned. Says what is true and
    // points at what is on screen.
    status: 404,
    detail: null,
    message: "We couldn't find this. It may have been from a different account, or it may not exist any more.",
  },
  // **A `{status: 400, detail: ["attendance"]}` rule used to sit here and could never fire**
  // (V3, 2026-08-17). No `HTTPException` in learning-api has ever carried the word "attendance"
  // in a detail, because the gate is not an error: `check_attendance_gate` answers **200** with
  // `phase: "blocked"` and `attendance.UNKNOWN_MESSAGE`/`BLOCKED_MESSAGE`, which
  // `AttendanceScreen` renders directly. So the sentence "Attendance for this week hasn't been
  // confirmed yet." was unreachable, and the 400s this API does return ("unknown topic …",
  // "unknown question variant …") fell to GENERIC either way.
  //
  // Same class as D-378 and found the same way its fix should have been checked: by asking what
  // the server actually sends. Every remaining substring rule above is now pinned by a driven
  // request in `apps/learning-api/tests/test_error_detail_contract.py`, including a test that
  // asserts no 400 mentions attendance - **add a case there when you add a rule here.**
  { status: 429, detail: null, message: "That was a lot at once — wait a moment and try again." },
];

function isServerError(status: number): boolean {
  return status >= 500;
}

/** Exported so the 401 branch in `useLearningSession` acts on the same classification the
 *  message comes from, rather than re-testing the status somewhere else and drifting (D-375,
 *  mirroring chat-web's `isSignedOut`). */
export function isSignedOut(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

export function friendlyError(error: unknown): string {
  // D-374: the request deadline aborts with a `DOMException`, not an `ApiError`, so without
  // this it falls to `OFFLINE` — "You appear to be offline", which is wrong and unactionable
  // when the network is fine and the server is merely slow. `TimeoutError` is what
  // `AbortSignal.timeout` raises; `AbortError` is a caller-initiated cancel.
  if (error instanceof DOMException && error.name === "TimeoutError") {
    // **No claim about saved state.** This sentence read "Your progress is saved — try again
    // in a moment" until a live audit measured what a timed-out `POST /answers` actually
    // does: D-378 *rolls the answer back*, so the reassurance was false at exactly the moment
    // it mattered, and the accurate sentence D-378 writes was `sr-only`. `REQUEST_TIMEOUT_MS`
    // applies to every request, reads and writes alike, so this string cannot know whether
    // anything was saved — the caller can, and `ExamScreen` now says so visibly.
    // chat-web's sibling line never made the claim; this was learning-web's own divergence.
    return "That took too long to answer. Try again in a moment.";
  }
  if (!(error instanceof ApiError)) {
    // A thrown `TypeError: Failed to fetch` is what a dropped connection looks like here.
    return OFFLINE;
  }
  logDetail(error);

  if (isServerError(error.status)) {
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
 * The haystack the `RULES` substrings are searched in — `detailText` plus each validation
 * entry's `loc` path.
 *
 * **Ported from chat-web, where the missing `loc` made a shipped rule unmatchable** (D-378,
 * found live 2026-08-16). There is no 422 rule in this file *yet*, so today this behaves
 * identically to `detailText` for every detail these routes actually return. It is here
 * because the trap is invisible until someone writes that rule: Pydantic puts the field name
 * only in `loc`, so a rule matching on a field name silently never fires. This file is where
 * chat-web's `detailText` was copied from in the first place, which is how the defect
 * travelled; keeping the two structurally identical is what stops the next copy repeating it.
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
 * (`client.ts`), but a 422 carries an *array* of validation errors rather than a string,
 * and `String(...)` on that yields `[object Object]` - which is how this class of bug
 * showed up before. Flattening here keeps the substring rules above honest.
 *
 * Deliberately drops `loc`: this is the display shape. `matchText` is the matching shape.
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
