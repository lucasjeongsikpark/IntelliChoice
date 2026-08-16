/**
 * The interactions a visitor performs that were never walked (D-352/D-353).
 *
 * Each of these covers a path the chat suite listed as untested: cancelling a slow turn,
 * signing in from an access hint, declining an email, dismissing a dialog with Escape, and
 * the *content* of the calendar dialog - which had been rendering "Event" and an empty date
 * range for as long as the fixture had been drifted, while a test that only asserted "a modal
 * is visible" passed.
 */

import type { Page } from "@playwright/test";

import { CHAT_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { SHAPES } from "../../fixtures/chat-shapes";
import { seedGuest } from "../../fixtures/session";
import { ask, stubChat } from "../../fixtures/stub-chat";

/** A `/messages` route that never answers, so the turn stays in flight. */
async function stubHangingTurn(page: Page): Promise<void> {
  await page.route("**/chat/sessions/*/messages", () => {
    /* deliberately never fulfilled */
  });
}

test.beforeEach(async ({ page }) => {
  await seedGuest(page);
});

test("a slow turn can be stopped, and stopping it is not reported as a failure", async ({
  page,
  audit,
}) => {
  // D-352. A cited answer takes 6-11s (measured live, D-343) with the composer disabled the
  // whole time, and there was no cancel of any kind - a hung request left `Thinking…`
  // pulsing until the visitor reloaded, which then landed on the blank-turn path.
  audit.allow({ failedRequests: true, consoleErrors: ["Failed to load resource"] });
  await stubChat(page, { message: SHAPES["grounded answer"] });
  await stubHangingTurn(page);
  await page.goto(CHAT_WEB);
  await ask(page, "Something slow");

  const thinking = page.locator(".bubble.dim").filter({ hasText: "Thinking…" });
  await expect(thinking).toBeVisible();
  await page.getByRole("button", { name: /^stop$/i }).click();

  // Stated on the turn, and *not* as an error: no alert role, no "couldn't be sent".
  await expect(page.getByText("You stopped this question.")).toBeVisible();
  await expect(page.locator(".bubble.turn-error")).toHaveCount(0);
  // And the visitor is free again, with a way to ask the same thing.
  await expect(page.locator("textarea")).toBeEnabled();
  await expect(page.getByRole("button", { name: /ask again/i })).toBeVisible();
  audit.note("cancelled turn: stated on the bubble, composer released, retry offered");
});

test("signing in from an access hint keeps the conversation", async ({ page, audit }) => {
  // D-353. `onLogin` was wired straight to `onLogout`, which calls `endSession()` - so a
  // guest who asked a parent-gated question and accepted the offer to sign in lost the
  // question the hint was *about*. Never observed, because no test had ever clicked it.
  await stubChat(page, { message: SHAPES["access hint"] });
  await page.goto(CHAT_WEB);
  await ask(page, "What is the attendance policy if my child misses a session?");
  await expect(page.locator(".access-hint-banner")).toBeVisible();

  await page.getByRole("button", { name: /^log in$/i }).click();

  // At the login screen…
  await expect(page.getByRole("button", { name: /continue as guest/i })).toBeVisible();
  // …with the conversation still in storage rather than thrown away…
  const transcript = await page.evaluate(() =>
    sessionStorage.getItem("intellichoice.chat_transcript"),
  );
  expect(transcript).toContain("attendance policy");
  // …and the anonymous session id dropped, so the next question is asked under the new
  // identity instead of 403ing on a session created before signing in.
  const sessionId = await page.evaluate(() =>
    sessionStorage.getItem("intellichoice.chat_session_id"),
  );
  expect(sessionId).toBeNull();
  audit.note("access-hint sign-in: transcript kept, anonymous session id dropped");
});

test("the calendar dialog shows the real event, not an empty placeholder", async ({
  page,
  audit,
}) => {
  // D-352's fixture correction. `chat-shapes.ts` carried `summary`/`start_time`, which no
  // backend has ever emitted; the modal reads `title`/`start_datetime`/`end_datetime`, so it
  // rendered "Event" and a bare " – ". The `renders:` loop passed throughout, because it
  // asserts only that a dialog appeared.
  await stubChat(page, { message: SHAPES["calendar_action interrupt"] });
  await page.goto(CHAT_WEB);
  await ask(page, "Add the parent session to my calendar");

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("Baton Rouge parent session");
  await expect(dialog).toContainText("Baton Rouge branch");
  // The date range must be a real range rather than the empty " – " the drift produced.
  const dates = (await dialog.locator("p.dim").first().textContent()) ?? "";
  expect(dates.replace(/[\s–-]/g, ""), `date range rendered as "${dates}"`).not.toBe("");
  audit.note(`calendar dialog date range: ${dates.trim()}`);
});

test("declining an email closes the dialog and says nothing was sent", async ({ page }) => {
  // Only the approve path had ever been walked, on the one screen where the action sends
  // real mail - so the *safe* half of a human-approval gate was the untested one.
  await stubChat(page, {
    message: SHAPES["email_approval interrupt"],
    respond: SHAPES["email declined"],
  });
  await page.goto(CHAT_WEB);
  await ask(page, "Please contact an administrator for me");

  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: /decline/i }).click();

  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator("textarea")).toBeEnabled();
});

test("Escape dismisses a dialog with its safe choice", async ({ page, audit }) => {
  // `ApprovalModal` maps Escape to the safe option for each dialog and its docstring calls
  // that safety-critical, but no test had pressed it.
  await stubChat(page, {
    message: SHAPES["email_approval interrupt"],
    respond: SHAPES["email declined"],
  });
  await page.goto(CHAT_WEB);
  await ask(page, "Please contact an administrator for me");
  await expect(page.getByRole("dialog")).toBeVisible();

  await page.keyboard.press("Escape");

  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator("textarea")).toBeEnabled();
  audit.note("Escape resolved the approval as a decline");
});
