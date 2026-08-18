import type { ChatMeta, Role, TurnSnapshot } from "../types";

export const API_BASE =
  (import.meta.env.VITE_CHAT_API_URL as string | undefined) ?? "http://localhost:8002";

/**
 * D-352: every request carries a deadline.
 *
 * There was no timeout anywhere in this client - no `AbortController`, no `AbortSignal`, no
 * `signal` on any fetch - so a hung request left `busy` true, the composer disabled and
 * `Thinking…` pulsing with no way out but a page reload. 55s is deliberately just above the
 * server's own 50s turn deadline (D-346, itself set under CloudFront's 60s origin read
 * timeout), so the ordering is: the server stops the work and answers, *then* this fires only
 * if even that answer never arrives. A client timeout below the server's would abandon turns
 * the backend was about to complete and pay for.
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

async function request<T>(path: string, token: string | null, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (init?.headers) Object.assign(headers, init.headers);
  if (token) headers.Authorization = `Bearer ${token}`;

  // D-352: a caller's own signal (the Cancel button) composes with the deadline, so whichever
  // fires first aborts the request. `AbortSignal.any` rather than one wrapping the other,
  // because a cancelled request and a timed-out one must both actually abort - chaining them
  // by hand is how one of the two ends up ignored.
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const signal = init?.signal ? AbortSignal.any([init.signal, timeout]) : timeout;

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers, signal });
  if (!res.ok) {
    // A `Response` body can only be consumed once - `res.json()` still reads (and
    // locks) the stream even when it throws on invalid JSON, so a `res.text()`
    // fallback in the catch block throws "body stream already read" instead of
    // recovering. Read once as text, then attempt to parse that string - found live
    // when a non-JSON error body (a CloudFront/ALB timeout page) hit this exact path.
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

export function createSession(token: string | null): Promise<{ chat_session_id: string }> {
  return request("/chat/sessions", token, { method: "POST" });
}

// SPEC §18-C3: anonymous-OK, no session/graph state - safe to call before a first
// message is ever sent (welcome card + role-aware suggestion chips).
export function getChatMeta(token: string | null): Promise<ChatMeta> {
  return request("/chat/meta", token, { method: "GET" });
}

export function postMessage(
  token: string | null,
  chatSessionId: string,
  query: string,
  // D-164: forward an already-asked question to an administrator instead of asking a new
  // one. The server skips scope classification and goes to the escalation path, which
  // still rate-limits and still pauses for approval before anything is sent.
  escalate = false,
  // D-348: this client's id for the turn. The server treats it as opaque and echoes it on
  // the response and on every later snapshot, which is what lets the SSE handler tell which
  // bubble a snapshot belongs under.
  clientTurnId?: string,
  // D-352: the Cancel affordance next to `Thinking…`. Only this call takes one - it is the
  // only request that can plausibly run for tens of seconds.
  signal?: AbortSignal,
): Promise<TurnSnapshot> {
  return request(`/chat/sessions/${chatSessionId}/messages`, token, {
    method: "POST",
    body: JSON.stringify({ query, escalate, client_turn_id: clientTurnId ?? null }),
    signal,
  });
}

export type RespondBody =
  | { interrupt_type: "email_approval"; approved: boolean }
  | { interrupt_type: "calendar_action"; choice: "google" | "ics" | "cancel" }
  | {
      interrupt_type: "location_consent";
      approved: boolean;
      zip_code?: string | null;
      city?: string | null;
      address?: string | null;
      latitude?: number | null;
      longitude?: number | null;
    };

/**
 * D-402: ask the server to stop the turn it is running.
 *
 * Aborting the fetch is not enough and never was: uvicorn does not cancel a handler when the
 * client disconnects, so the graph ran on under its 50s deadline holding the per-session
 * advisory lock, and the *next* question came back 409 "This conversation is already working on
 * a question." Nothing the browser can do on its own releases that lock.
 *
 * Turn-scoped, because "Ask again" reuses the id and a session-scoped stop would kill the retry.
 *
 * Deliberately **not** awaited by the caller and deliberately swallowing its own failure: Stop
 * has already taken effect locally by the time this is sent, so a failed cancel must degrade to
 * the old behaviour (the turn finishes server-side) rather than surface an error for an action
 * the visitor has already seen succeed.
 */
export function cancelTurn(
  token: string | null,
  chatSessionId: string,
  clientTurnId: string,
): Promise<void> {
  return request(
    `/chat/sessions/${chatSessionId}/turns/${encodeURIComponent(clientTurnId)}/cancel`,
    token,
    { method: "POST" },
  ).then(
    () => undefined,
    () => undefined,
  );
}

export function respondToInterrupt(
  token: string | null,
  chatSessionId: string,
  body: RespondBody,
): Promise<TurnSnapshot> {
  return request(`/chat/sessions/${chatSessionId}/respond`, token, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
