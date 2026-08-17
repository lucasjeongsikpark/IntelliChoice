/**
 * Sends a browser crash to the server, closing the gap `ErrorBoundary` recorded as carry-over.
 *
 * The learning-web twin (`lib/reportClientError.ts`) drops any crash with no bearer token,
 * because `/learning/client-errors` requires one. **This one must not do that**: chat's primary
 * caller is anonymous (SPEC §5.19.1), so the same rule would discard the majority of the crashes
 * the sink exists to see — the exact objection `ErrorBoundary`'s docstring raised against
 * copying learning's design here. `/chat/client-errors` accepts anonymous reports and rate-limits
 * them in a shared bucket instead; see that router's docstring for the gate and what it gives up.
 *
 * **Fire-and-forget, and it must stay that way.** A crash reporter that throws turns one broken
 * render into two, and one that blocks delays the fallback UI the visitor is waiting for. Every
 * failure path here ends in a swallowed promise.
 */

import { API_BASE } from "../api/client";

const TOKEN_KEY = "intellichoice.chat_token";
const SESSION_ID_KEY = "intellichoice.chat_session_id";
/**
 * D-389: **absolute, via `API_BASE`, not a bare relative path.** The first walk of the crash loop
 * found every report 404ing against the vite dev server, because a relative URL resolves to the
 * *page's* origin - which is the API's origin only when the two are served together. On staging
 * they are (one CloudFront distribution, `/{app}/*` routed to the ALB), so this worked there and
 * has never worked in local development, the one place a developer would look for it. Every other
 * call in these apps already goes through `API_BASE`; this one was the exception, and no reason
 * for being one was recorded.
 */
const ENDPOINT = "/chat/client-errors";

/**
 * **The re-entrancy guard, and it is not optional.**
 *
 * `main.tsx` reports `window.onerror` and `unhandledrejection`. If this function's own `fetch`
 * rejects — offline, the API down, which are exactly the conditions a crash happens in — that
 * rejection is itself an unhandled rejection, which fires the listener, which calls this again.
 * Without a latch that is an unbounded loop against a server that has already stopped answering.
 *
 * chat-web previously had no latch and needed none, because nothing in its error path made a
 * network call. Adding the report adds the hazard, so the latch arrives with it.
 */
let reportingIsBroken = false;

interface ClientErrorReport {
  message: string;
  stack?: string;
  traceId?: string;
}

export function reportClientError({ message, stack, traceId }: ClientErrorReport): void {
  if (reportingIsBroken) return;

  // Present for a signed-in parent or tutor, absent for the anonymous visitor who is this
  // app's normal case. Absent is not a reason to drop the report here.
  const token = localStorage.getItem(TOKEN_KEY);
  // `sessionStorage`, matching `useChatSession`. Correlation only — the server logs it and
  // never trusts it, so a crash before any session exists simply sends null.
  const sessionId = sessionStorage.getItem(SESSION_ID_KEY);

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  // `void` plus a `catch` rather than `await`: nothing may wait on this, and an unhandled
  // rejection here would re-enter through `main.tsx`'s listener.
  void fetch(`${API_BASE}${ENDPOINT}`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      message,
      // `null` rather than omitted when absent, so the server's `extra="forbid"` model sees a
      // shape it declared rather than a missing key.
      stack: stack ?? null,
      trace_id: traceId ?? null,
      chat_session_id: sessionId,
    }),
    // The page may be unloading when a crash fires; `keepalive` lets the request outlive it.
    keepalive: true,
  }).catch(() => {
    reportingIsBroken = true;
  });
}
