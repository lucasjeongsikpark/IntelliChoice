/**
 * Every way a chat turn can fail, rendered in a real browser (D-347).
 *
 * `response-shapes.spec.ts` covers the shapes the API returns when it *succeeds*, plus one
 * stubbed 500. It does not cover 401, 403, 409, 429, 504, a response whose `answer` is null,
 * or an interrupt type this build has no dialog for — and each of those was a dead end
 * before this phase: a raw wire string, a permanently blank turn, or a composer disabled
 * with nothing on screen to act on.
 *
 * Each test asserts two things deliberately: that the visitor is told something readable,
 * and that they are **not** shown the API's own text. The second is the regression that
 * matters, because the first can be satisfied by a message that merely happens to be
 * grammatical.
 */

import type { Page } from "@playwright/test";

import { CHAT_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { SHAPES } from "../../fixtures/chat-shapes";
import { seedGuest, thinkingPlaceholder } from "../../fixtures/session";
import { ask, stubChat } from "../../fixtures/stub-chat";

/** The composer's textarea, which is what "the visitor can carry on" means concretely. */
function composer(page: Page) {
  return page.locator("textarea");
}

/** A stored signed-in identity whose token the server will not accept. */
async function seedStoredToken(page: Page): Promise<void> {
  await page.addInitScript(() => {
    localStorage.setItem("intellichoice.chat_token", "stale.token.value");
    localStorage.setItem("intellichoice.chat_sub", "parent-ext-1");
    localStorage.setItem("intellichoice.chat_role", "parent");
  });
}

test.describe("failures the visitor can read and recover from", () => {
  test.beforeEach(async ({ page }) => {
    await seedGuest(page);
  });

  test("a 409 says what to do instead of naming an endpoint", async ({ page, audit }) => {
    // The exact wire text D-343 found: `/respond` in a sentence shown to a parent.
    // `stubChat` first: Playwright matches the *most recently registered* handler, so the
    // override below has to come second to win.
    await stubChat(page, { message: SHAPES["grounded answer"] });
    audit.allow({ statuses: [409], consoleErrors: ["Failed to load resource"] });
    await page.route("**/chat/sessions/*/messages", (route) =>
      route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "a pending interrupt must be resolved via /respond before continuing",
        }),
      }),
    );
    await page.goto(CHAT_WEB);
    await ask(page, "What are the Saturday hours?");

    const turn = page.locator(".bubble.turn-error");
    await expect(turn).toBeVisible();
    const text = (await turn.textContent()) ?? "";
    audit.note(`409 rendered as: ${text.trim()}`);
    expect(text).not.toContain("/respond");
    expect(text).toMatch(/answer the prompt above first/i);
  });

  test("a 429 tells the visitor to wait rather than showing a limiter's wording", async ({
    page,
    audit,
  }) => {
    await stubChat(page, { message: SHAPES["grounded answer"] });
    audit.allow({ statuses: [429], consoleErrors: ["Failed to load resource"] });
    await page.route("**/chat/sessions/*/messages", (route) =>
      route.fulfill({
        status: 429,
        contentType: "application/json",
        body: JSON.stringify({ detail: "rate limit exceeded" }),
      }),
    );
    await page.goto(CHAT_WEB);
    await ask(page, "What are the Saturday hours?");

    const turn = page.locator(".bubble.turn-error");
    await expect(turn).toBeVisible();
    await expect(turn).toContainText(/wait a moment/i);
  });

  test("a 503 with a server-written sentence is passed through, not replaced", async ({
    page,
    audit,
  }) => {
    // D-345's daily ceiling already writes a visitor-facing line naming a remedy. A generic
    // "something broke on our side" would be strictly worse, so `friendlyError` keeps 503
    // detail text — this is the test that stops a later tidy-up from flattening it.
    const written =
      "The assistant has reached its daily limit and can't answer new questions right now. " +
      "Please try again tomorrow, or contact your branch directly.";
    await stubChat(page, { message: SHAPES["grounded answer"] });
    audit.allow({
      statuses: [503],
      serverErrors: true,
      consoleErrors: ["Failed to load resource"],
    });
    await page.route("**/chat/sessions/*/messages", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: written }),
      }),
    );
    await page.goto(CHAT_WEB);
    await ask(page, "What are the Saturday hours?");

    await expect(page.locator(".bubble.turn-error")).toContainText("try again tomorrow");
  });

  test("an over-length question is told it is too long, not that something went wrong", async ({
    page,
    audit,
  }) => {
    // **The test D-378 shipped without, and the reason it shipped broken.** D-378 added a 422
    // rule keyed on the field name `query`, on the stated premise that the flattened detail
    // "contains the field". It does not: Pydantic v2 puts the field name only in
    // `loc: ["body", "query"]` and its `msg` names no field, so the rule could never match and
    // every over-length question fell through to the generic line — the exact outcome D-378
    // existed to prevent. Found in the *deployed bundle* by a live audit on 2026-08-16.
    //
    // The body below is Pydantic's real 422 shape, copied from what `AskMessageRequest.query`'s
    // `max_length=2000` actually emits. That fidelity is the whole test: a hand-simplified
    // `{detail: "query too long"}` would have passed against the broken code.
    await stubChat(page, { message: SHAPES["grounded answer"] });
    audit.allow({ statuses: [422], consoleErrors: ["Failed to load resource"] });
    await page.route("**/chat/sessions/*/messages", (route) =>
      route.fulfill({
        status: 422,
        contentType: "application/json",
        body: JSON.stringify({
          detail: [
            {
              type: "string_too_long",
              loc: ["body", "query"],
              msg: "String should have at most 2000 characters",
              ctx: { max_length: 2000 },
            },
          ],
        }),
      }),
    );
    await page.goto(CHAT_WEB);
    await ask(page, "What are the Saturday hours?");

    const turn = page.locator(".bubble.turn-error");
    await expect(turn).toBeVisible();
    const text = (await turn.textContent()) ?? "";
    audit.note(`422 rendered as: ${text.trim()}`);
    // Names the limit, so "try again" is advice the visitor can actually act on.
    await expect(turn).toContainText(/too long/i);
    await expect(turn).toContainText("2000");
    // And is not the generic line, which is what the defect produced.
    expect(text).not.toContain("Something didn't go through");
  });

  test("a turn whose answer is null renders something rather than nothing", async ({
    page,
    audit,
  }) => {
    // **The blank-turn class.** The assistant bubble used to be gated on
    // `turn.response.answer`, so this shape rendered the question and *nothing at all*
    // beneath it — while `Thinking…` was simultaneously suppressed because `response` was
    // non-null. Reachable on reload during a first turn.
    await stubChat(page, {
      message: { ...SHAPES["grounded answer"], answer: null, citations: [], suggested_followups: [] },
    });
    await page.goto(CHAT_WEB);
    await ask(page, "What are the Saturday hours?");

    const assistant = page.locator(".message-row.assistant .bubble");
    await expect(assistant).toBeVisible();
    await expect(thinkingPlaceholder(page)).toHaveCount(0);
    const text = ((await assistant.textContent()) ?? "").trim();
    audit.note(`null-answer turn rendered: ${text}`);
    expect(text.length).toBeGreaterThan(0);
  });

  test("an interrupt type with no dialog leaves the composer usable", async ({ page, audit }) => {
    // The composer was disabled for *any* pending interrupt while only three types have a
    // modal, so a fourth added server-side would deadlock the app with nothing on screen.
    await stubChat(page, {
      message: {
        ...SHAPES["grounded answer"],
        pending_interrupt: { interrupt_type: "some_future_approval" },
      },
    });
    await page.goto(CHAT_WEB);
    await ask(page, "What are the Saturday hours?");

    const notice = page.getByRole("alert").filter({ hasText: /can't show you/i });
    await expect(notice).toBeVisible();
    await expect(composer(page)).toBeEnabled();
    await expect(page.getByRole("button", { name: /start a new chat/i })).toBeVisible();
    audit.note("unknown interrupt type: notice shown, composer still usable");
  });
});

test.describe("an expired token", () => {
  test("401 returns the visitor to sign-in and keeps what they already asked", async ({
    page,
    audit,
  }) => {
    // `get_optional_claims` 401s a present-but-invalid token rather than downgrading to
    // anonymous, so before D-347 the stored token was never cleared: every retry failed
    // identically and `EventSource` reconnected against the same 401 forever. The
    // conversation surviving is the other half — an expiry is not the visitor's doing.
    // Seeded directly rather than through `seedSession`, which needs a real minted
    // token: the subject here is what happens when the stored token is *not* accepted,
    // so a placeholder is the accurate fixture.
    await seedStoredToken(page);
    await stubChat(page, { message: SHAPES["grounded answer"] });
    await page.goto(CHAT_WEB);
    await ask(page, "What are the Saturday hours?");
    // **Wait for the first answer to actually arrive before re-routing** (D-355).
    //
    // This used to be `expect(thinkingPlaceholder).toHaveCount(0)` alone, which is a
    // negative assertion with nothing in front of it: it passes *instantly*, before the
    // placeholder could have rendered, so it does not mean "the turn finished". Under
    // load the test then ran ahead of the browser and installed the 401 route below while
    // the FIRST ask's fetch was still being dispatched - and Playwright matches routes
    // when the request is issued, not when the click happened. So the first question got
    // the 401 meant for the second, the app signed out correctly, and the second `ask`
    // spent 30s looking for a composer on the login screen.
    //
    // Measured: fails in a full suite (local and staging), passes 16/16 in isolation -
    // the timing only loses when something else is loading the machine. The positive wait
    // is the fix and the stronger assertion; the placeholder check stays, now meaning
    // "and it is no longer thinking" rather than "nothing has happened yet".
    await expect(page.locator(".message-row.assistant .bubble").first()).toBeVisible();
    await expect(thinkingPlaceholder(page)).toHaveCount(0);

    await page.route("**/chat/sessions/*/messages", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "token_expired" }),
      }),
    );
    audit.allow({ statuses: [401], consoleErrors: ["Failed to load resource"] });
    await ask(page, "And on Sundays?");

    // Back at the login screen…
    await expect(page.getByRole("button", { name: /continue as guest/i })).toBeVisible();
    // …with the token cleared, so the next request is anonymous rather than a repeat 401.
    const stored = await page.evaluate(() => localStorage.getItem("intellichoice.chat_token"));
    expect(stored).toBeNull();
    // …and the conversation still in storage, ready to replay.
    const transcript = await page.evaluate(() =>
      sessionStorage.getItem("intellichoice.chat_transcript"),
    );
    expect(transcript).toContain("Saturday hours");
    audit.note("401: signed out, token cleared, transcript preserved");
  });

  test("a token and the guest flag cannot both win", async ({ page, audit }) => {
    // Nothing kept these mutually exclusive across a reload, and the e2e fixtures write
    // them independently. Both set meant: skip the login screen *and* send the stale token
    // on every request — a "guest" session 401ing with no visible cause.
    await seedStoredToken(page);
    await page.addInitScript(() => {
      localStorage.setItem("intellichoice.chat_guest", "1");
    });
    await stubChat(page, { message: SHAPES["grounded answer"] });
    await page.goto(CHAT_WEB);

    const guest = await page.evaluate(() => localStorage.getItem("intellichoice.chat_guest"));
    expect(guest, "the guest flag should have been cleared in favour of the token").toBeNull();
    await expect(page.locator(".who")).toContainText("parent");
    audit.note("token+guest reconciled in favour of the token");
  });
});

test.describe("a failing approval", () => {
  test("the error appears inside the dialog, not behind its scrim", async ({ page, audit }) => {
    // `.modal-overlay` is `position: fixed; inset: 0; z-index: 10` over a 40% scrim, and the
    // page-level error renders inside `.chat-page` beneath it. So a failing `POST /respond`
    // looked like nothing happening at all — on the one screen where the action is sending
    // real email.
    await seedGuest(page);
    audit.allow({
      statuses: [500],
      serverErrors: true,
      consoleErrors: ["Failed to load resource"],
    });
    await stubChat(page, { message: SHAPES["email_approval interrupt"] });
    await page.route("**/chat/sessions/*/respond", (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "transport blew up" }),
      }),
    );
    await page.goto(CHAT_WEB);
    await ask(page, "Please contact an administrator for me");

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await page.getByRole("button", { name: /approve/i }).click();

    const inDialog = dialog.locator(".modal-error");
    await expect(inDialog).toBeVisible();
    await expect(inDialog).not.toContainText("transport blew up");
    audit.note(`failed approval rendered in-dialog: ${(await inDialog.textContent())?.trim()}`);
    // Still open, so the visitor can retry or decline rather than being left guessing.
    await expect(dialog).toBeVisible();
  });
});
