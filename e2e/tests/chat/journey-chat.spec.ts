/**
 * The chat launch journeys against the real backend (no stubs): guest and each signed-in
 * role ask a question and get a rendered answer.
 *
 * The role loop is the browser-side counterpart to S37's strongest negative result
 * (pre-retrieval role/branch/date filtering held for all five audiences). That was
 * measured at the API; this checks the *rendered* turn for each audience, which is the
 * half that was missing.
 */

import { CHAT_WEB, FIXTURES, TARGET } from "../../config";
import { expect, test } from "../../fixtures/capture";
import {
  expectNotBlank,
  expectNotStuck,
  mintToken,
  seedGuest,
  seedSession,
  signInViaUi,
} from "../../fixtures/session";
import { ask } from "../../fixtures/stub-chat";

test.describe.configure({ timeout: 180_000 });

/**
 * Waits for the turn to resolve into a rendered assistant bubble.
 *
 * Order matters. Checking "no Thinking… on screen" first passes *immediately* when the
 * placeholder has not rendered yet - a green assertion about a turn that had not started,
 * which is what made this intermittently report a stuck turn whose `/messages` request the
 * network log showed was never even sent. So: wait for a bubble to exist, then wait for it
 * to stop being the placeholder.
 */
async function expectAnswered(page: import("@playwright/test").Page): Promise<string> {
  const bubble = page.locator(".message-row.assistant .bubble").last();
  await expect(bubble).toBeVisible({ timeout: 30_000 });
  await expect(bubble).not.toHaveText("Thinking…", { timeout: 90_000 });
  const text = (await bubble.innerText()).trim();
  expect(text.length, "the assistant bubble rendered empty - the S22.5 blank-turn class").toBeGreaterThan(0);
  return text;
}

test("a guest asks an in-scope question and sees a rendered answer", async ({ page, audit }) => {
  await seedGuest(page);
  await page.goto(CHAT_WEB);

  // The welcome card is anonymous-OK (SPEC §18-C3) and must render before any turn.
  await expect(page.locator(".composer textarea")).toBeVisible();
  await expectNotBlank(page);

  await ask(page, "What are the Saturday hours?");
  const answer = await expectAnswered(page);
  audit.note(`guest answer (${answer.length} chars): ${JSON.stringify(answer.slice(0, 140))}`);
  await expectNotBlank(page);
});

test("the welcome card's suggested prompt works as a one-click turn", async ({ page, audit }) => {
  await seedGuest(page);
  await page.goto(CHAT_WEB);

  // Waited for, not counted immediately. `App.tsx` fetches `/chat/meta` in an effect, so a
  // `count()` taken right after `goto` reads the DOM before the response lands and returns
  // 0 every time - which is why this test skipped on every run since it was written,
  // including all of S39-S42. It was never a data gap: `chat_suggestions` carries seven
  // active `public` rows and `suggestions_for_role` returns the first four to a guest.
  // A skip that never stops skipping tests nothing, so the absence is now a failure.
  const chips = page.locator(".suggestion-chips .chip, .welcome-card button");
  await expect(
    chips.first(),
    "no suggestion chips rendered for a guest - GET /chat/meta returned no public suggestions, or the welcome card did not render",
  ).toBeVisible({ timeout: 30_000 });
  const available = await chips.count();
  audit.note(`welcome suggestions offered: ${available}`);

  const label = await chips.first().innerText();
  await chips.first().click();
  // The clicked prompt must appear as the user's own turn, not vanish.
  await expect(page.locator(".message-row.user .bubble").last()).toContainText(label.trim().slice(0, 30));
  await expectAnswered(page);
});

for (const [name, account] of [
  ["student", FIXTURES.studentPresent],
  ["parent", { role: "parent", sub: "parent-ext-1" }],
  ["tutor", { role: "tutor", sub: "tutor-ext-1" }],
  ["branch_manager", { role: "branch_manager", sub: "branch_manager-ext-1" }],
] as const) {
  test(`a signed-in ${name} asks a question and sees a rendered answer`, async ({
    page,
    request,
    audit,
  }) => {
    const token = await mintToken(request, "chat", account);
    await seedSession(page, "chat", account, token);
    await page.goto(CHAT_WEB);

    // Deliberately not phrased around a named branch: "…at the Baton Rouge branch"
    // routes to the branch-locator intent and pauses on the location-consent modal
    // instead of answering, which the locator journey below covers on purpose.
    await ask(page, "What are the Saturday hours?");
    const answer = await expectAnswered(page);
    const citations = await page.locator(".citation-chip").count();
    audit.note(`${name}: ${citations} citations, answer ${answer.length} chars`);
    await expectNotBlank(page);
  });
}

test("the branch locator asks consent before any location is collected, and declining is honored", async ({
  page,
  audit,
}) => {
  await seedGuest(page);
  await page.goto(CHAT_WEB);
  await ask(page, "Where is the nearest branch to me?");

  // SPEC §5.1.3/§5.1.4: the notice comes *before* collection, and declining is an option.
  const modal = page.locator(".modal-overlay .modal");
  await expect(modal).toBeVisible({ timeout: 90_000 });
  const notice = await modal.locator(".notice").innerText();
  audit.note(`consent notice: ${JSON.stringify(notice.slice(0, 200))}`);
  expect(notice.trim().length, "the consent modal rendered with no notice text").toBeGreaterThan(0);
  await expect(modal.getByRole("button", { name: /don't use my location/i })).toBeVisible();
  // The composer is correctly locked while the interrupt is pending.
  await expect(page.locator(".composer textarea")).toBeDisabled();

  await modal.getByRole("button", { name: /don't use my location/i }).click();
  await expect(modal).toHaveCount(0, { timeout: 90_000 });
  await expectAnswered(page);
  await expect(page.locator(".composer textarea")).toBeEnabled();
});

test("sharing a ZIP through the locator modal returns a rendered answer", async ({ page, audit }) => {
  await seedGuest(page);
  await page.goto(CHAT_WEB);
  await ask(page, "Where is the nearest branch to me?");

  const modal = page.locator(".modal-overlay .modal");
  await expect(modal).toBeVisible({ timeout: 90_000 });
  await modal.locator("label.field").filter({ hasText: /ZIP code/i }).locator("input").fill("70802");
  await modal.getByRole("button", { name: /^share location$/i }).click();

  await expect(modal).toHaveCount(0, { timeout: 90_000 });
  const answer = await expectAnswered(page);
  audit.note(`locator answer: ${JSON.stringify(answer.slice(0, 160))}`);
  await expectNotBlank(page);
});

test("an out-of-scope question is refused visibly rather than answered", async ({ page, audit }) => {
  await seedGuest(page);
  await page.goto(CHAT_WEB);
  await ask(page, "Who won the 1998 World Cup?");
  const answer = await expectAnswered(page);
  audit.note(`out-of-scope reply: ${JSON.stringify(answer.slice(0, 200))}`);
  // The refusal must be visible text; a silent empty turn is the defect class.
  expect(answer.length).toBeGreaterThan(10);
});

test("a new chat clears the transcript and the composer stays usable", async ({ page, audit }) => {
  await seedGuest(page);
  await page.goto(CHAT_WEB);
  await ask(page, "What are the Saturday hours?");
  await expectAnswered(page);
  await expect(page.locator(".message-row.user")).toHaveCount(1);

  await page.getByRole("button", { name: /new chat/i }).click();
  await expect(page.locator(".message-row")).toHaveCount(0);
  await expect(page.locator(".composer textarea")).toBeEnabled();

  // A second turn must still resolve after the reset. The question is deliberately *not*
  // "Where is the nearest branch?" - that is the branch-locator prompt (the two locator
  // journeys below use it verbatim), so it pauses on the location-consent modal and the
  // assistant bubble stays on "Thinking…" forever. This test asked it and spent 90 s waiting
  // for an answer the product is correctly refusing to give until consent is resolved.
  // The role-loop above carries the same warning; it had not been applied here.
  await ask(page, "How do I enroll a student?");
  const answer = await expectAnswered(page);
  audit.note(`second turn after reset (${answer.length} chars)`);
  await expect(page.locator(".message-row.user")).toHaveCount(1);
});

test("signing in through the real login screen reaches a usable chat", async ({ page }) => {
  // The only test here whose subject *is* the login screen, so it is the only one that
  // must not take `signInViaUi`'s staging shortcut. On staging that screen cannot work
  // by design - `/dev/token` is secret-gated (D-097) and the frontend sends no header -
  // so this asserts nothing there and skips explicitly rather than passing vacuously.
  // The real login screen is S44's subject; this skip should disappear with it.
  test.skip(TARGET === "staging", "the dev-login screen is secret-gated on staging (D-097)");
  await signInViaUi(page, CHAT_WEB, FIXTURES.studentPresent);
  await expect(page.locator(".composer textarea")).toBeVisible();
  await ask(page, "What are the Saturday hours?");
  await expectAnswered(page);
});

test("a refresh mid-conversation restores the transcript", async ({ page, audit }) => {
  await seedGuest(page);
  await page.goto(CHAT_WEB);
  await ask(page, "What are the Saturday hours?");
  const before = await expectAnswered(page);

  await page.reload();

  // `useChatSession` persists the transcript in sessionStorage and reconciles the last
  // turn over SSE on reconnect - so the answer must still be there, not a fresh page.
  await expect(page.locator(".message-row.assistant .bubble").last()).toBeVisible({
    timeout: 30_000,
  });
  const after = (await page.locator(".message-row.assistant .bubble").last().innerText()).trim();
  audit.note(`transcript survived refresh: ${after.slice(0, 80) === before.slice(0, 80)}`);
  await expectNotStuck(page, "Thinking…", 30_000);
  await expectNotBlank(page);
});
