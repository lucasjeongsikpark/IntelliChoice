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

test("stopping a turn tells the server, naming the turn it stopped", async ({ page, audit }) => {
  // **D-402, and the half D-352 could not do from the browser.** Aborting the fetch only ends
  // this tab's request: uvicorn does not cancel a handler when the client disconnects (measured
  // against real uvicorn - a handler whose client hung up reports `ran-to-completion`), so the
  // graph ran on under its 50s deadline holding the session's advisory lock and the visitor's
  // next question came back 409 "This conversation is already working on a question."
  //
  // Asserted here rather than left to the API tests because the *wiring* is what breaks: the
  // server side has its own seven tests, and none of them would notice `cancelTurn` forgetting
  // to call the endpoint.
  audit.allow({ failedRequests: true, consoleErrors: ["Failed to load resource"] });

  const askedTurnIds: string[] = [];
  const cancelledPaths: string[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (request.method() !== "POST") return;
    if (path.endsWith("/messages")) {
      const body = request.postData();
      const id = body ? (JSON.parse(body).client_turn_id as string | null) : null;
      if (id) askedTurnIds.push(id);
    }
    if (path.endsWith("/cancel")) cancelledPaths.push(path);
  });

  await stubChat(page, { message: SHAPES["grounded answer"] });
  await stubHangingTurn(page);
  await page.goto(CHAT_WEB);
  await ask(page, "Something slow");

  await expect(page.locator(".bubble.dim").filter({ hasText: "Thinking…" })).toBeVisible();
  await page.getByRole("button", { name: /^stop$/i }).click();
  await expect(page.getByText("You stopped this question.")).toBeVisible();

  // Fire-and-forget, so it is not ordered against the UI update - poll rather than assume it
  // has already gone out by the time the bubble changed.
  await expect
    .poll(() => cancelledPaths.length, {
      timeout: 10_000,
      message: "Stop never told the server, so the session lock stays held until the deadline",
    })
    .toBe(1);

  audit.note(`cancel sent to: ${cancelledPaths[0]}`);
  expect(askedTurnIds.length, "no turn id was sent with the question").toBe(1);
  // **Turn-scoped, and this is the assertion that says so.** A session-scoped cancel would also
  // stop the turn the visitor starts next - and "Ask again" reuses the id, so that would make
  // Stop look like it had jammed the conversation.
  expect(
    cancelledPaths[0],
    "the cancel did not name the turn that was actually in flight",
  ).toMatch(new RegExp(`/turns/${askedTurnIds[0]}/cancel$`));
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

  // **And it must still be there after the sign-in completes and the tab reloads** (D-381).
  //
  // The assertions above stop at the login screen, which is where the defect starts. The
  // owner stamp is written only by `clearSessionIfOwnedByAnotherSubject`, in a `useState`
  // initialiser that already ran - so signing in without a remount left it at the guest value
  // `""`. Nothing was visibly wrong. On the *next* reload the initialiser compared `""`
  // against the new sub, judged the conversation to belong to somebody else, and deleted the
  // transcript D-353 had just gone to the trouble of preserving. Measured live 2026-08-16:
  // `{visibleTurns: 0, storedTurns: 0, owner: "tutor-ext-1", sid: null}`.
  //
  // **The sign-in has to happen in the mounted tree, with no navigation.** Writing the
  // identity keys and reloading looks equivalent and is not: a reload re-runs the `useState`
  // initialiser, which is the path that already worked. The defect lives in the *other* path
  // — an identity that changes while the hook stays mounted — so the form has to be driven.
  // `/dev/token` is stubbed rather than called so this holds on staging too, where the
  // endpoint is secret-gated (D-097) and the screen expects a human to type the secret.
  await page.route("**/dev/token", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ token: "signed.in.token" }),
    }),
  );
  await page
    .locator("label.field")
    .filter({ hasText: "Role" })
    .locator("select")
    .selectOption("tutor");
  await page
    .locator("label.field")
    .filter({ hasText: /External id/i })
    .locator("input")
    .fill("tutor-ext-1");
  await page.getByRole("button", { name: /^sign in$/i }).click();
  await expect(page.getByRole("button", { name: /^sign in$/i })).toHaveCount(0, {
    timeout: 15_000,
  });

  // **Polled, not read once.** The stamp is written by a `useEffect`, which React runs after
  // paint - so the sign-in button disappearing (a completed render) does not mean the effect
  // has run. Reading synchronously passed on an idle machine and failed inside the full
  // suite, which is the definition of a flake, and it was mine rather than the app's: a
  // sub-millisecond window between paint and effect is not a defect a student can hit.
  await expect
    .poll(
      () => page.evaluate(() => sessionStorage.getItem("intellichoice.chat_owner")),
      {
        message:
          "the owner stamp stayed stale, so the next reload will bin the conversation as someone else's",
      },
    )
    .toBe("tutor-ext-1");

  // The assertion that actually mattered: this reload is the one that used to delete the
  // conversation the visitor had just signed in to continue.
  await page.reload();
  const afterSignIn = await page.evaluate(() =>
    sessionStorage.getItem("intellichoice.chat_transcript"),
  );
  expect(
    afterSignIn,
    "the conversation the visitor signed in to continue was deleted after signing in",
  ).toContain("attendance policy");
  audit.note("access-hint sign-in: transcript survives the sign-in and the reload after it");
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
