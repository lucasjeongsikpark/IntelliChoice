import type {
  DashboardData,
  ExamOverview,
  Role,
  SessionSnapshot,
  StudentHistory,
  StudentReport,
} from "../types";

export const API_BASE = (import.meta.env.VITE_LEARNING_API_URL as string | undefined) ??
  "http://localhost:8001";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(`API error ${status}: ${JSON.stringify(detail)}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, token: string | null, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (init?.headers) Object.assign(headers, init.headers);
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
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

export interface ChatMessageResult {
  learning_session_id: string;
  reply_text: string;
  intent: string;
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
