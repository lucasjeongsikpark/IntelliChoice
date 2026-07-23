import type { ChatMeta, Role, TurnSnapshot } from "../types";

export const API_BASE =
  (import.meta.env.VITE_CHAT_API_URL as string | undefined) ?? "http://localhost:8002";

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

export function devToken(role: Role, sub: string): Promise<{ token: string }> {
  return request("/dev/token", null, {
    method: "POST",
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
): Promise<TurnSnapshot> {
  return request(`/chat/sessions/${chatSessionId}/messages`, token, {
    method: "POST",
    body: JSON.stringify({ query }),
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
