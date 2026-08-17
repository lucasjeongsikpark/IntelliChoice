import type {
  ChildCandidate,
  DashboardData,
  ExamOverview,
  Role,
  SessionSnapshot,
  StudentHistory,
  StudentReport,
  TopicOption,
  SessionResults,
} from "../types";

export const API_BASE = (import.meta.env.VITE_LEARNING_API_URL as string | undefined) ??
  "http://localhost:8001";

/**
 * Every request carries a deadline (D-374, porting chat-web's D-352).
 *
 * **There was no timeout anywhere in this client** — no `AbortController`, no `AbortSignal`,
 * no `signal` on any fetch — and unlike chat-web, learning-web serialises the *whole UI*
 * behind one request. `useLearningSession`'s `busyRef` is set before the call and cleared in
 * a `finally` that never runs if the fetch never settles, so a stalled Submit left every
 * option, Submit, Skip, Flag and the question navigator disabled forever. The server-side
 * timer kept running and `submitBlocked` then refused "Submit exam" because items were
 * unanswered: **the student could neither answer nor submit**, which D-241 records as a state
 * that must never exist. Only a reload escaped, and nothing on screen suggested one.
 *
 * 55s is deliberately just above learning-api's own 50s turn deadline (D-374) and below
 * CloudFront's 60s origin read timeout, so the ordering is: the server stops the work and
 * answers with its own structured 504, *then* this fires only if even that never arrives —
 * which is the network-level stall a shared classroom tablet actually produces. A client
 * timeout below the server's would abandon turns the backend was about to complete and pay
 * for.
 */
export const REQUEST_TIMEOUT_MS = 55_000;

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(`API error ${status}: ${JSON.stringify(detail)}`);
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Fired once for any authenticated request that comes back 401. Registered by `App`.
 *
 * **Why this lives here and not at the call sites.** D-375 wired `handleSignedOut` into
 * `useLearningSession.run()` — the graph-mutation path — and that is *all* it covered. A live
 * audit on 2026-08-16 signed in, expired the token and opened `/dashboard`: the three GETs
 * behind that screen (`getStudentDashboard`, `getStudentHistory`, `getMyChildren`) each
 * rendered "You've been signed out. Sign in again to keep going." with a **Try again** button
 * that re-fired the same dead token forever. `localStorage` still held it, so a reload
 * skipped the login screen too. The message named the remedy and no screen offered it — the
 * same defect D-375 fixed, in the paths D-375 did not reach.
 *
 * A per-call-site fix would have needed the same three lines in five `catch` blocks and would
 * have been one `getStudentReport` away from the next gap. Here it is structurally
 * unmissable: every request in this module goes through `request()`.
 *
 * `token !== null` is the guard that matters. `devToken` deliberately passes `null`, so a
 * failed sign-in stays a login error rather than becoming a spurious sign-out of the session
 * the user does not yet have.
 */
let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

async function request<T>(path: string, token: string | null, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (init?.headers) Object.assign(headers, init.headers);
  if (token) headers.Authorization = `Bearer ${token}`;

  // A caller's own signal composes with the deadline, so whichever fires first aborts.
  // `AbortSignal.any` rather than one wrapping the other, because a cancelled request and a
  // timed-out one must both actually abort — chaining them by hand is how one ends up ignored.
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const signal = init?.signal ? AbortSignal.any([init.signal, timeout]) : timeout;

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers, signal });
  if (!res.ok) {
    // Before the body is read, because the handler only clears client state and the caller
    // still gets its `ApiError` to render. See `setUnauthorizedHandler`.
    if (res.status === 401 && token !== null) onUnauthorized?.();
    // A `Response` body can only be consumed once - `res.json()` still reads (and
    // locks) the stream even when it throws on invalid JSON, so a `res.text()`
    // fallback in the catch block throws "body stream already read" instead of
    // recovering. Read once as text, then attempt to parse that string - found live
    // when a non-JSON error body (an S3 XML 404, from a CloudFront routing gap) hit
    // this exact path.
    const raw = await res.text();
    let detail: unknown = raw;
    try {
      const parsed: unknown = JSON.parse(raw);
      // FastAPI/Starlette always wrap error bodies as `{"detail": ...}` - unwrap here
      // so `ApiError.detail` is always the actual message (or validation-error array),
      // not the wrapper object. Storing the wrapper itself meant every caller's
      // `String(err.detail)` rendered "[object Object]" instead of the real message -
      // found live via a real attendance-gate 400 during S32/D-084 holistic testing.
      detail =
        typeof parsed === "object" && parsed !== null && "detail" in parsed
          ? (parsed as { detail: unknown }).detail
          : parsed;
    } catch {
      // Not JSON - keep the raw text as the detail.
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/**
 * `stagingSecret` is the `X-Staging-Token-Secret` D-097 requires on a deployed
 * environment, where `/dev/token` 404s without it and the dev-login screen therefore
 * showed a bare "Not Found" - i.e. nobody could sign in to staging through the UI at all
 * (S42/AUD-F-18 found this for the e2e harness; a human hit the same wall).
 *
 * Sent only when non-empty. Locally the endpoint takes its `environment=="dev"` path and
 * ignores the header entirely, so passing it is always safe and there is no build-time
 * switch to get wrong - deliberately, because a switch that silently points at the wrong
 * thing is exactly what AUD-F-17 was.
 */
export function devToken(
  role: Role,
  sub: string,
  stagingSecret?: string,
): Promise<{ token: string }> {
  const headers: Record<string, string> = {};
  if (stagingSecret) headers["X-Staging-Token-Secret"] = stagingSecret;
  return request("/dev/token", null, {
    method: "POST",
    headers,
    body: JSON.stringify({ role, sub }),
  });
}

/**
 * AUD-F-22: the caller's linked children, resolvable *before* any learning session.
 * Parent-only on the backend (403 for every other role); the id comes from the verified
 * token, so there is nothing to pass.
 */
export function getMyChildren(token: string): Promise<ChildCandidate[]> {
  return request("/learning/parents/me/children", token);
}

export function createSession(token: string): Promise<SessionSnapshot> {
  return request("/learning/sessions", token, { method: "POST" });
}

export function selectStudent(
  token: string,
  sessionId: string,
  studentId?: string,
): Promise<SessionSnapshot> {
  return request(`/learning/sessions/${sessionId}/student`, token, {
    method: "POST",
    body: JSON.stringify({ student_id: studentId ?? null }),
  });
}

/**
 * D-187: the topic picker's contents, availability decided by the backend's template bank
 * rather than by a hard-coded list in this app. Session-scoped because the grade that
 * annotates it is profile data the server resolves from the session's bound student.
 */
export function getTopics(
  token: string,
  sessionId: string,
): Promise<{ learning_session_id: string; topics: TopicOption[] }> {
  return request(`/learning/sessions/${sessionId}/topics`, token);
}

export function selectTopic(
  token: string,
  sessionId: string,
  topicId: string,
): Promise<SessionSnapshot> {
  return request(`/learning/sessions/${sessionId}/topics`, token, {
    method: "POST",
    body: JSON.stringify({ topic_id: topicId }),
  });
}

export function resolveAttendance(
  token: string,
  sessionId: string,
  choice: "acknowledge" | "ask_branch_manager",
): Promise<SessionSnapshot> {
  return request(`/learning/sessions/${sessionId}/attendance-resolution`, token, {
    method: "POST",
    body: JSON.stringify({ choice }),
  });
}

export function submitAnswer(
  token: string,
  sessionId: string,
  questionVariantId: string,
  selectedOption: string,
  responseTimeMs: number,
): Promise<SessionSnapshot> {
  return request(`/learning/sessions/${sessionId}/answers`, token, {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify({
      question_variant_id: questionVariantId,
      selected_option: selectedOption,
      response_time_ms: responseTimeMs,
    }),
  });
}

export type RespondBody =
  | { interrupt_type: "child_selection"; student_id: string }
  | { interrupt_type: "email_approval"; approved: boolean }
  | { interrupt_type: "intervention_choice"; choice: "hint" | "solution" | "video" | "continue" };

export function respondToInterrupt(
  token: string,
  sessionId: string,
  body: RespondBody,
): Promise<SessionSnapshot> {
  return request(`/learning/sessions/${sessionId}/respond`, token, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getExamOverview(token: string, sessionId: string): Promise<ExamOverview> {
  return request(`/learning/sessions/${sessionId}/exam/overview`, token);
}

// D-218: reports that the exam is on screen with nothing over it, which is when its time
// limit starts counting. Idempotent server-side, and it returns the overview so the caller
// gets a `remaining_seconds` measured from the clock it just started.
export function markExamViewed(token: string, sessionId: string): Promise<ExamOverview> {
  return request(`/learning/sessions/${sessionId}/exam/viewed`, token, { method: "POST" });
}

export function skipExamItem(
  token: string,
  sessionId: string,
  assessmentItemId: string,
): Promise<void> {
  return request(`/learning/sessions/${sessionId}/exam/items/${assessmentItemId}/skip`, token, {
    method: "POST",
  });
}

export function flagExamItem(
  token: string,
  sessionId: string,
  assessmentItemId: string,
  flagged: boolean,
): Promise<void> {
  return request(`/learning/sessions/${sessionId}/exam/items/${assessmentItemId}/flag`, token, {
    method: "POST",
    body: JSON.stringify({ flagged }),
  });
}

export function recordItemTime(
  token: string,
  sessionId: string,
  assessmentItemId: string,
  elapsedMs: number,
): Promise<void> {
  return request(`/learning/sessions/${sessionId}/exam/items/${assessmentItemId}/time`, token, {
    method: "POST",
    body: JSON.stringify({ elapsed_ms: elapsedMs }),
  });
}

export function finalizeExam(
  token: string,
  sessionId: string,
  confirmUnanswered: boolean,
): Promise<SessionSnapshot> {
  return request(`/learning/sessions/${sessionId}/exam/finalize`, token, {
    method: "POST",
    body: JSON.stringify({ confirm_unanswered: confirmUnanswered }),
  });
}

export function resumeSession(token: string, sessionId: string): Promise<SessionSnapshot> {
  return request(`/learning/sessions/${sessionId}/resume`, token, { method: "POST" });
}

export function getStudentHistory(token: string, studentId: string): Promise<StudentHistory> {
  return request(`/learning/students/${studentId}/sessions`, token);
}

function rangeQuery(start: string | null, end: string | null): string {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function getStudentDashboard(
  token: string,
  studentId: string,
  start: string | null,
  end: string | null,
): Promise<DashboardData> {
  return request(`/learning/students/${studentId}/dashboard${rangeQuery(start, end)}`, token);
}

export function generateStudentReport(
  token: string,
  studentId: string,
  start: string | null,
  end: string | null,
  // AUD-X-04: required on the wire, so it is required here. Unlike `submitAnswer`'s
  // per-call `crypto.randomUUID()`, this key must be stable for as long as the request
  // *means* the same thing - a fresh key per call would let two clicks pay twice, which is
  // the defect. The caller owns that lifetime; see `StudentDashboardScreen`.
  idempotencyKey: string,
): Promise<StudentReport> {
  return request(`/learning/students/${studentId}/report${rangeQuery(start, end)}`, token, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
  });
}

// D-217: the bounded chat diagram (mirrors the backend `ChatVizSpec`). `labels` and
// `values` are the same length (2-4); `bar_model` reads them as labelled bars, `number_line`
// as marks on a line. The client renders it as a pure function of these numbers/strings.
export interface ChatViz {
  kind: "number_line" | "bar_model";
  caption: string;
  labels: string[];
  values: number[];
}

export interface ChatMessageResult {
  learning_session_id: string;
  reply_text: string;
  intent: string;
  viz?: ChatViz | null;
}

export function sendChatMessage(
  token: string,
  sessionId: string,
  questionVariantId: string,
  message: string,
): Promise<ChatMessageResult> {
  return request(`/learning/sessions/${sessionId}/chat`, token, {
    method: "POST",
    body: JSON.stringify({ question_variant_id: questionVariantId, message }),
  });
}

/**
 * A completed cycle's results by session id (U4/D-338).
 *
 * The live screen renders from the session snapshot; this is what makes `/results/:id` work
 * after that session is over, which is U4's fourth criterion. `learning_gain` is the whole gain
 * object, the same shape the snapshot carries, so `ResultsScreen` cannot tell the two apart.
 */
export function getSessionResults(
  token: string,
  learningSessionId: string,
): Promise<SessionResults> {
  return request(`/learning/sessions/${learningSessionId}/results`, token);
}
