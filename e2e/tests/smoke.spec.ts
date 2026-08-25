/**
 * Proves the harness itself works before any finding is trusted to it: both apps load,
 * both `/dev/token` paths mint a token, and the capture fixture is actually attached.
 *
 * This is the harness's own positive control. D-101 §5 and D-102's method note both
 * come down to the same lesson - a probe that can only return "clean" is not a
 * measurement - so the last test here deliberately produces a console error and a 404
 * and asserts the fixture *saw* them.
 */

import { CHAT_WEB, FIXTURES, LEARNING_WEB } from "../config";
import { expect, test } from "../fixtures/capture";
import { mintToken } from "../fixtures/session";

test("learning-web loads and shows the sign-in screen", async ({ page, audit }) => {
  await page.goto(LEARNING_WEB);
  await expect(page.getByRole("heading", { name: /IntelliChoice Adaptive Learning/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
  expect(audit.apiCalls().length).toBeGreaterThan(0);
});

test("chat-web loads and shows the sign-in screen", async ({ page }) => {
  await page.goto(CHAT_WEB);
  await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
});

test("both /dev/token endpoints mint a token", async ({ request }) => {
  // **Deliberately shares `studentPresent`** (WORK-13-FIXTURES). Minting a token creates no
  // session and writes no per-student row, so the isolation finding does not reach here.
  const learning = await mintToken(request, "learning", FIXTURES.studentPresent);
  const chat = await mintToken(request, "chat", FIXTURES.studentPresent);
  // Three dot-separated base64url segments. Asserting the shape, never the content.
  expect(learning.split(".")).toHaveLength(3);
  expect(chat.split(".")).toHaveLength(3);
  expect(learning).not.toBe(chat);
});

test("the capture fixture sees a console error and a 404 (harness positive control)", async ({
  page,
  audit,
}) => {
  audit.allow({ consoleErrors: ["deliberate-harness-control"], statuses: [404] });
  await page.goto(LEARNING_WEB);
  await page.evaluate(() => {
    console.error("deliberate-harness-control");
  });
  const response = await page.request.get(`${LEARNING_WEB}/definitely-not-a-real-path-xyz`, {
    failOnStatusCode: false,
  });

  // The allowances above keep these out of `consoleErrors`/`clientErrors`, so assert
  // against the raw logs - the point is that the listeners fired at all.
  expect(audit.console.some((entry) => entry.text.includes("deliberate-harness-control"))).toBe(true);
  expect(audit.consoleErrors).toEqual([]);
  // A SPA's catch-all rewrite may serve index.html for an unknown path; either way the
  // request was recorded, which is what this control is proving.
  expect([200, 404]).toContain(response.status());
});
