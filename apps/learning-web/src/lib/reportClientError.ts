/**
 * Sends a browser crash to the server (U5/D-328), closing the gap D-315 left open.
 *
 * `ErrorBoundary`'s own docstring recorded why this did not exist: *"Sending one needs a decision
 * this component should not make on its own — an authenticated endpoint, a rate limit, and a PII
 * rule for message/stack text."* All three now exist server-side, so this is the client half.
 *
 * **Fire-and-forget, and it must stay that way.** A crash reporter that throws turns one broken
 * render into two, and one that blocks delays the fallback UI the student is waiting for. Every
 * failure path here ends in a swallowed promise.
 */

import { API_BASE } from "../api/client";

const TOKEN_KEY = "intellichoice.token";
/**
 * D-389: **absolute, via `API_BASE`, not a bare relative path.** The first walk of the crash loop
 * found every report 404ing against the vite dev server, because a relative URL resolves to the
 * *page's* origin - which is the API's origin only when the two are served together. On staging
 * they are (one CloudFront distribution, `/{app}/*` routed to the ALB), so this worked there and
 * has never worked in local development, the one place a developer would look for it. Every other
 * call in these apps already goes through `API_BASE`; this one was the exception, and no reason
 * for being one was recorded.
 */
const ENDPOINT = "/learning/client-errors";

/**
 * **The re-entrancy guard, and it is not optional.**
 *
 * `main.tsx` reports `window.onerror` and `unhandledrejection`. If this function's own `fetch`
 * rejects — offline, the API down, which are exactly the conditions a crash happens in — that
 * rejection is itself an unhandled rejection, which fires the listener, which calls this again.
 * Without a latch that is an unbounded loop against a server that has already stopped answering.
 *
 * A module-level boolean rather than a counter: once reporting has failed, nothing later in this
 * page's life is likely to succeed, and the server has a per-token limit for the case where it
 * does. Reset on nothing — a reload clears it, which is the right granularity.
 */
let reportingIsBroken = false;

interface ClientErrorReport {
  message: string;
  stack?: string;
  traceId?: string;
}

export function reportClientError({ message, stack, traceId }: ClientErrorReport): void {
  if (reportingIsBroken) return;

  const token = localStorage.getItem(TOKEN_KEY);
  // Unauthenticated crashes are dropped rather than sent. The endpoint requires a token by
  // design (an open sink is a log-injection endpoint), and a sign-in-screen crash has no student
  // to attribute it to anyway. `console.error` in `ErrorBoundary` still records it locally.
  if (!token) return;

  // `void` plus a `catch` rather than `await`: nothing may wait on this, and an unhandled
  // rejection here would re-enter through `main.tsx`'s listener.
  void fetch(`${API_BASE}${ENDPOINT}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      message,
      // `null` rather than omitted when absent, so the server's `extra="forbid"` model sees a
      // shape it declared rather than a missing key.
      stack: stack ?? null,
      trace_id: traceId ?? null,
    }),
    // The page may be unloading when a crash fires; `keepalive` lets the request outlive it.
    keepalive: true,
  }).catch(() => {
    reportingIsBroken = true;
  });
}
