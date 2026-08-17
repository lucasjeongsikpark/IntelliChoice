/**
 * An expired token must end at the sign-in screen, from **any** screen (D-381).
 *
 * D-375 established the rule and wired it to one path. `handleSignedOut` was passed to
 * `useLearningSession`, whose `run()` wraps the graph mutations — so an expiry during an
 * answer or a stage advance recovered correctly, and nothing else did. A live browser audit
 * on 2026-08-16 expired a token and opened `/dashboard`: the three GETs behind that screen
 * each rendered *"You've been signed out. Sign in again to keep going."* above a **Try again**
 * button, and Try again re-fired the same dead token. Forever. `localStorage` still held it,
 * so a reload skipped the login screen as well.
 *
 * That is the shape D-375's own docstring calls out — a message naming a remedy no screen
 * offers — reproduced in the paths D-375 did not cover. The fix moved the decision into
 * `client.ts`'s `request()`, so it cannot be missed by a call site again.
 *
 * **Why the dashboard is the right screen to assert on** rather than the session flow: it is
 * the read-only screen furthest from `run()`, so it fails if anyone re-scopes the handler back
 * to the mutation path. A token lives one hour and a full session is 25-40 questions, so this
 * is a routine path, not an edge case.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";

const TOKEN_KEY = "intellichoice.token";

test("an expired token on the dashboard returns the user to sign-in instead of looping", async ({
  page,
  audit,
}) => {
  // Every request on the dashboard 401s, and each one logs a console warning plus a failed
  // resource load. Both are the *handled* path, which is what this test is asserting.
  audit.allow({ statuses: [401], consoleErrors: ["Failed to load resource"] });

  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await page.getByRole("button", { name: /view progress dashboard/i }).click();
  await expect(page.getByRole("heading", { name: /progress dashboard/i })).toBeVisible({
    timeout: 60_000,
  });

  // **The 401 is stubbed rather than provoked by corrupting the token, and that is not a
  // shortcut — it is the only thing that works on both targets.** On staging `seedSession`
  // installs the identity through `addInitScript`, which Playwright re-runs on *every*
  // navigation: writing a junk token and reloading put the valid one straight back, so no
  // request ever 401'd and this test failed on staging while passing locally. Measured on the
  // first staging run of this spec.
  //
  // Stubbing also states the subject more honestly. What is under test is the *client's*
  // reaction to a 401 on a read path — not the server's willingness to reject a bad token,
  // which `error-states.spec.ts` covers on the chat side and which is not this app's code.
  await page.route("**/learning/**", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "expired" }),
    }),
  );
  await page.reload();

  // The whole assertion: sign-in is reachable, without the user knowing to press anything.
  await expect(page.getByRole("button", { name: /^sign in$/i })).toBeVisible({ timeout: 60_000 });

  // And the dead token is gone, which is what makes the *next* reload work too. Before the
  // fix this key survived every retry, so the login screen could never render.
  const stored = await page.evaluate(([key]) => localStorage.getItem(key), [TOKEN_KEY] as const);
  expect(stored, "the rejected token is still in localStorage, so a reload will skip sign-in").toBeNull();
  audit.note("401 on a read path cleared the stored token and rendered sign-in");
});
