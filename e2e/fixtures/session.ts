/**
 * Getting a browser into an authenticated state, two ways.
 *
 * `signInViaUi` drives the real dev-login screen, so the screen itself is audited. It
 * only works where `/dev/token` is open to an unauthenticated caller - i.e. locally.
 *
 * `seedSession` mints the token out of band and writes it into localStorage before the
 * app's first render. Needed on staging (the frontend never sends the
 * `X-Staging-Token-Secret` header `/dev/token` requires there, D-097), and useful
 * locally to start a journey mid-way without re-driving login every time.
 */

import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { CHAT_API, CHAT_WEB, LEARNING_API, STAGING_TOKEN_SECRET, TARGET } from "../config";

export type App = "learning" | "chat";

const API_BASE: Record<App, string> = { learning: LEARNING_API, chat: CHAT_API };

/** Both apps namespace their own localStorage keys - chat prefixes with `chat_`. */
const STORAGE_KEYS: Record<App, { token: string; sub: string; role: string }> = {
  learning: {
    token: "intellichoice.token",
    sub: "intellichoice.sub",
    role: "intellichoice.role",
  },
  chat: {
    token: "intellichoice.chat_token",
    sub: "intellichoice.chat_sub",
    role: "intellichoice.chat_role",
  },
};

export interface Account {
  readonly role: string;
  readonly sub: string;
}

export async function mintToken(
  request: APIRequestContext,
  app: App,
  account: Account,
): Promise<string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const secret = STAGING_TOKEN_SECRET[app];
  if (secret) headers["X-Staging-Token-Secret"] = secret;

  const response = await request.post(`${API_BASE[app]}/dev/token`, {
    headers,
    data: { role: account.role, sub: account.sub },
  });
  // Deliberately does not echo the response body on failure: a 200 body *is* a token.
  expect(
    response.status(),
    `POST ${app} /dev/token returned ${response.status()} (a secret-gated endpoint returns 404 to a caller without the header)`,
  ).toBe(200);
  const body = (await response.json()) as { token: string };
  return body.token;
}

/**
 * Writes the session into localStorage ahead of the app's first script, because both
 * `App`s read localStorage in a `useState` initializer - setting it after load would
 * need a reload to take effect.
 */
export async function seedSession(
  page: Page,
  app: App,
  account: Account,
  token: string,
): Promise<void> {
  const keys = STORAGE_KEYS[app];
  await page.addInitScript(
    ([storageKeys, value]) => {
      const k = storageKeys as { token: string; sub: string; role: string };
      const v = value as { token: string; sub: string; role: string };
      localStorage.setItem(k.token, v.token);
      localStorage.setItem(k.sub, v.sub);
      localStorage.setItem(k.role, v.role);
    },
    [keys, { token, sub: account.sub, role: account.role }] as const,
  );
}

/** Chat's guest path is a localStorage flag, not a token (SPEC §18-C3 anonymous-OK). */
export async function seedGuest(page: Page): Promise<void> {
  await page.addInitScript(() => {
    localStorage.setItem("intellichoice.chat_guest", "1");
  });
}

/**
 * Drives the real login screen: pick the role, type the external id, click Sign in.
 * The fixture-account `<select>` is deliberately not used - it sets both fields at
 * once, which would hide a mismatch between the two.
 *
 * **On staging this delegates to `seedSession` instead**, because the login screen
 * cannot work there: `/dev/token` is secret-gated (D-097) and the frontend never sends
 * the header, so the screen renders "Not Found" under the Sign in button. That was not
 * a hypothetical - it is what all ten specs calling this helper actually did the first
 * time the staging suite was ever run (S42/AUD-F-18): **18 failures, every one of them
 * this**. The module docstring above has described out-of-band seeding as the staging
 * path since the harness was written; only the journeys never took it.
 *
 * A journey whose *subject* is the login screen must therefore skip on staging rather
 * than call this - see `journey-chat.spec.ts`'s real-login-screen test.
 */
export async function signInViaUi(page: Page, url: string, account: Account): Promise<void> {
  if (TARGET === "staging") {
    const app: App = url === CHAT_WEB ? "chat" : "learning";
    const token = await mintToken(page.request, app, account);
    await seedSession(page, app, account, token);
    await page.goto(url);
    await expect(page.getByRole("button", { name: /^sign in$/i })).toHaveCount(0, {
      timeout: 15000,
    });
    return;
  }
  await page.goto(url);
  await page.getByRole("button", { name: /sign in/i }).waitFor();
  // Located through each field's own label: both screens have two `<select>`s, and
  // matching on option text alone would hit the fixture picker as well as the role.
  await page.locator("label.field").filter({ hasText: "Role" }).locator("select").selectOption(account.role);
  await page
    .locator("label.field")
    .filter({ hasText: /External id/i })
    .locator("input")
    .fill(account.sub);
  await page.getByRole("button", { name: /sign in/i }).click();
  // The login screen is gone once a token exists; anything else means login failed.
  await expect(page.getByRole("button", { name: /^sign in$/i })).toHaveCount(0, {
    timeout: 15000,
  });
}

/**
 * Criterion 3's "zero blank/stuck states", as a check rather than an eyeball.
 *
 * A React render that produces nothing still returns 200 with a mounted `#root`, so
 * neither the HTTP status nor the absence of an error proves anything was shown. This
 * asserts the app rendered *visible text of its own* beyond the persistent shell.
 */
export async function expectNotBlank(page: Page): Promise<void> {
  const main = page.locator("#root");
  await expect(main).toBeVisible();
  const text = ((await main.innerText()) ?? "").trim();
  // The learning shell contributes header + footer on every screen; chat's header is
  // inside its own page div. Anything under this length is the shell and nothing else.
  const shellOnly = text.replace(/IntelliChoice|Adaptive Learning|©.*|intellichoice\.org/g, "").trim();
  expect(shellOnly.length, `#root rendered no content of its own (full text: ${JSON.stringify(text)})`).toBeGreaterThan(
    0,
  );
}

/**
 * Asserts a transient state actually resolved. `stuckText` is the placeholder the app
 * shows while waiting ("Thinking…", "Connecting…", "Loading the next question…"); if
 * it is still on screen after the timeout, the journey is stuck, which is a finding
 * even though nothing errored.
 */
/** The in-flight placeholder, located by role rather than by its text.
 *
 * **D-352 broke every exact-text assertion against it and nothing said so.** The placeholder
 * used to be a bubble whose whole text was `Thinking…`, so `not.toHaveText("Thinking…")` was a
 * real gate. Adding a Stop button *inside* that bubble made its text `Thinking… Stop`, which is
 * not equal to `Thinking…` - so the assertion started passing the instant the placeholder
 * appeared, and `expectAnswered` stopped waiting for answers at all. Caught on staging by
 * `expectNotStuck`, which uses `getByText` (a substring match) and therefore still worked: the
 * reload fired 40ms after session creation, before a single `/messages` request was sent.
 *
 * Locating the element rather than matching its text is what makes this stable against the
 * next thing added inside it.
 */
export function thinkingPlaceholder(page: Page) {
  return page.getByRole("status").filter({ hasText: "Thinking…" });
}

export async function expectNotStuck(
  page: Page,
  stuckText: string | RegExp,
  timeout = 30000,
): Promise<void> {
  await expect(
    page.getByText(stuckText),
    `still showing ${String(stuckText)} after ${timeout}ms - a stuck state, not an error`,
  ).toHaveCount(0, { timeout });
}
