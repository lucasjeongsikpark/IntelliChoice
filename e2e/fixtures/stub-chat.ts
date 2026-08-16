/**
 * Route interception for chat-web, so one specific response shape can be put in front
 * of the real renderer.
 *
 * This is the only place in the harness that fakes a backend, and it is deliberate:
 * §2.3 asks for "every degraded/refusal/empty response shape actually rendered", and
 * several of those shapes need a Bedrock outage, a rate limiter, or a conflicting
 * corpus to occur naturally. Interception renders the shape; `response-shapes.spec.ts`
 * separately runs an un-stubbed turn as the control that the shapes are real.
 */

import type { Page, Route } from "@playwright/test";
import type { Shape } from "./chat-shapes";
import { SESSION_ID } from "./chat-shapes";

function json(route: Route, body: unknown, status = 200): Promise<void> {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

export interface StubOptions {
  /** What `/messages` returns. A number instead of a shape returns that HTTP status. */
  message: Shape | number;
  /** What `/respond` returns, when the test resolves an interrupt. */
  respond?: Shape;
}

export async function stubChat(page: Page, options: StubOptions): Promise<void> {
  await page.route("**/chat/meta", (route) =>
    json(route, {
      welcome_text: "Ask about branches, schedules, or volunteering.",
      suggested_prompts: ["Where is the nearest branch?", "What are Saturday hours?"],
    }),
  );

  await page.route("**/chat/sessions", (route) =>
    route.request().method() === "POST"
      ? json(route, { chat_session_id: SESSION_ID })
      : route.fallback(),
  );

  // Correct MIME type and a comment frame: `EventSource` treats a wrong content type as
  // a fatal error *and logs it to the console*, which would land in the audit capture as
  // a finding the harness itself caused.
  await page.route("**/chat/sessions/*/stream**", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
      body: ": stubbed\n\n",
    }),
  );

  await page.route("**/chat/sessions/*/messages", (route) =>
    typeof options.message === "number"
      ? json(route, { detail: "stubbed failure" }, options.message)
      : json(route, options.message),
  );

  if (options.respond) {
    const respond = options.respond;
    await page.route("**/chat/sessions/*/respond", (route) => json(route, respond));
  }
}

/**
 * Types a query and sends it, without waiting for any particular outcome.
 *
 * **The explicit wait is not decoration** (D-355). `fill()` auto-waits only for
 * `actionTimeout` (15s local, 30s staging), and the first `ask` after a `goto` is racing
 * React deciding *which screen to render*: the composer does not exist on the login
 * screen, so a slow hydration is indistinguishable from "there is no composer". Measured
 * once in a full local suite - the 401 spec failed here at 15s having passed in 596ms in
 * isolation, after five minutes of learning journeys had loaded the same machine. A flake
 * anywhere reddens a whole run, and this suite's runs are counted consecutively.
 *
 * It weakens nothing: a composer that never appears still fails, and now says so.
 */
export async function ask(page: Page, query: string): Promise<void> {
  const composer = page.locator("textarea");
  await composer.waitFor({ state: "visible", timeout: 60_000 });
  await composer.fill(query);
  await page.getByRole("button", { name: /^send$/i }).click();
}
