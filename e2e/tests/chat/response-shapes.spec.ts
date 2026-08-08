/**
 * Renders every response shape the chat API can emit, in a real browser.
 *
 * This is the sub-item that kept S37 at ⏸: it enumerated all fourteen shapes against
 * the render code and reported twelve correct, but never rendered one. The two it
 * called broken (AUD-C-04, AUD-C-10) have their own tests at the bottom, written to
 * *pass when the bug is present* and named so, so Phase 0B's fix flips them from
 * documented-defect to regression — see the comment on each.
 */

import { CHAT_API, CHAT_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { SHAPES, SHAPE_NAMES } from "../../fixtures/chat-shapes";
import { ask, stubChat } from "../../fixtures/stub-chat";
import { seedGuest } from "../../fixtures/session";

/** The bubble that appears while a turn is in flight, and AUD-C-10's stuck state. */
const THINKING = "Thinking…";

test.beforeEach(async ({ page }) => {
  await seedGuest(page);
});

test("the fourteen shapes are the fourteen the API declares (drift control)", async ({
  page,
  audit,
}) => {
  // Guards the whole file: if `MessageResponse` grows a field, these fixtures are stale
  // and every render below is auditing a shape the backend no longer emits. Runs one
  // *real*, un-stubbed turn and compares field sets.
  await page.goto(CHAT_WEB);
  const response = await page.request.post(`${CHAT_API}/chat/sessions`, {
    failOnStatusCode: false,
  });
  test.skip(response.status() !== 200, "chat-api not reachable for the drift control");
  const { chat_session_id: sessionId } = (await response.json()) as { chat_session_id: string };
  const turn = await page.request.post(`${CHAT_API}/chat/sessions/${sessionId}/messages`, {
    data: { query: "What are the Saturday hours?" },
    failOnStatusCode: false,
  });
  expect(turn.status()).toBe(200);
  const live = Object.keys((await turn.json()) as Record<string, unknown>).sort();
  const fixture = Object.keys(SHAPES["grounded answer"]).sort();
  audit.note(`live /messages fields: ${live.join(",")}`);
  expect(live, "the API's field set drifted from e2e/fixtures/chat-shapes.ts").toEqual(fixture);
});

for (const name of SHAPE_NAMES) {
  test(`renders: ${name}`, async ({ page, audit }) => {
    const shape = SHAPES[name];
    await stubChat(page, { message: shape });
    await page.goto(CHAT_WEB);
    await ask(page, `probe: ${name}`);

    // Every shape must leave the turn resolved - no permanent Thinking… bubble.
    await expect(page.getByText(THINKING)).toHaveCount(0, { timeout: 20_000 });

    if (shape.pending_interrupt) {
      // An interrupt shape has no answer text; what must be visible is the modal that
      // resolves it. `App.tsx` renders one per known interrupt_type.
      const interruptType = shape.pending_interrupt.interrupt_type as string;
      await expect(
        page.locator(".modal-overlay .modal"),
        `${interruptType} produced no visible modal - the composer is disabled with nothing to resolve it`,
      ).toBeVisible();
      audit.note(`${interruptType}: modal rendered`);
    } else if (shape.access_hint?.message === shape.answer) {
      // D-220: an access-hint turn carries its text in the banner, not in a second answer
      // bubble, so `.first()` here rather than a strict single match - the block below is
      // what asserts the text appears exactly once, and it names the duplication when it
      // does not. Without this, a regression trips the strict-mode check first and reports
      // "answer text never rendered", which is the opposite of what went wrong.
      await expect(
        page.getByText(shape.answer!.slice(0, 40), { exact: false }).first(),
        `answer text for "${name}" never rendered`,
      ).toBeVisible();
    } else {
      // An answer shape must show its own text. A shape whose answer never reaches the
      // DOM is the S22.5 blank-turn class.
      await expect(
        page.getByText(shape.answer!.slice(0, 40), { exact: false }),
        `answer text for "${name}" never rendered`,
      ).toBeVisible();
    }

    if (shape.citations.length > 0) {
      await expect(page.locator(".citation-chip")).toHaveCount(shape.citations.length);
    }
    if (shape.escalation_recommended) {
      await expect(page.locator(".escalation-banner")).toBeVisible();
    }
    if (shape.access_hint) {
      // D-220: `toHaveCount(1)`, not `toBeVisible()`. The backend sets
      // `answer = hint.message`, so before the fix this sentence reached the DOM twice -
      // once as the answer bubble, once inside `AccessHintBanner` - and a logged-out
      // parent read the same line back to back. Counting is what makes that a failure;
      // visibility passes happily with two copies on screen.
      await expect(
        page.getByText(shape.access_hint.message),
        "the access-hint message rendered more than once - the answer bubble and the " +
          "banner are both showing it",
      ).toHaveCount(1);
      await expect(page.locator(".access-hint-banner")).toBeVisible();
    }
    if (shape.ics_content) {
      await expect(page.getByRole("button", { name: /download \.ics/i })).toBeVisible();
    }
    if (shape.suggested_followups.length > 0) {
      await expect(page.locator(".suggestion-chips .chip")).toHaveCount(
        shape.suggested_followups.length,
      );
    }
  });
}

test("AUD-C-11 rendered: the no-source refusal shows a citation beside a sentence denying one exists", async ({
  page,
}) => {
  // Not a harness artifact - S37 observed this shape live. The finding is that the two
  // render *together*, which only a rendered page can show.
  //
  // ⚠️ D-164 fixed AUD-C-11 in the BACKEND (`qa._no_answer` now gets `[]` on the
  // low-confidence branch), and this test cannot see that: the shape below is a hardcoded
  // stub, so it passes whether the bug exists or not. It did NOT flip from
  // documented-defect to regression the way this file's docstring describes for AUD-C-04
  // and AUD-C-10 - it can't, and keeping it without saying so would be D-163's mistake
  // (a fixture that can only pass, read as evidence).
  //
  // What it is still good for: this shape is now UNREACHABLE from the API, so this is the
  // record of what a user would see if it ever came back. The actual regression guard is
  // `apps/chat-api/tests/test_qa_service.py::test_the_no_source_refusal_carries_no_citations`,
  // which was watched failing before the fix.
  await stubChat(page, { message: SHAPES["no-source refusal with citations (AUD-C-11)"] });
  await page.goto(CHAT_WEB);
  await ask(page, "something no document covers");

  const bubble = page.locator(".message-row.assistant .bubble").last();
  await expect(bubble).toContainText("don't have an approved source");
  await expect(bubble.locator(".citation-chip")).toHaveCount(1);
  await expect(bubble.locator(".citation-chip")).toContainText("Branch Handbook");
});

test("AUD-C-10 regression: an API error resolves the turn into a retryable error bubble", async ({
  page,
  audit,
}) => {
  // Inverted in Phase 0B, exactly as the original version of this test said it should
  // be: it was written to PASS while the defect existed ("Thinking… persists 3s after a
  // 500"), so the fix failing it was the signal to rewrite it as a regression test.
  //
  // The 500 is the subject of the test, and Chromium logs its own console error for any
  // failed fetch ("Failed to load resource: ... 500"), which is the browser reporting
  // the stub rather than a defect. Both are allowed here and nowhere else.
  audit.allow({
    statuses: [500],
    serverErrors: true,
    consoleErrors: ["Failed to load resource"],
  });
  await stubChat(page, { message: 500 });
  await page.goto(CHAT_WEB);
  await ask(page, "this turn will 500");

  // The turn resolves: the stuck bubble is gone and the failure is stated in its place.
  const failedBubble = page.locator(".message-row.assistant .bubble.turn-error");
  await expect(failedBubble).toBeVisible();
  await expect(failedBubble).toContainText("couldn't be sent");
  // The page-level banner still renders - it was never the problem, it just could not
  // clear a per-turn bubble.
  await expect(page.locator("p.error")).toBeVisible();

  // The wait is the whole point of the original finding: "no timeout" meant the stuck
  // state never resolved on its own. Held here to prove the fix is not merely a slower
  // version of the same bug.
  await page.waitForTimeout(3000);
  await expect(
    page.getByText(THINKING),
    "AUD-C-10 has regressed: a failed turn is rendering as permanently in-flight again",
  ).toHaveCount(0);

  // And the dead end is a dead end no longer: retry re-sends the same turn, and when
  // the API is healthy again the turn completes in place rather than being abandoned.
  await stubChat(page, { message: SHAPES["grounded answer"] });
  await page.getByRole("button", { name: /try again/i }).click();
  const bubble = page.locator(".message-row.assistant .bubble").last();
  await expect(bubble).toContainText("open 9am to 1pm on Saturdays");
  await expect(page.locator(".bubble.turn-error")).toHaveCount(0);
  // One question asked, one question shown - retrying in place must not duplicate it.
  await expect(page.locator(".message-row.user .bubble")).toHaveCount(1);
  audit.note("AUD-C-10 fixed: the 500 renders a retryable error bubble, and retry completes the same turn");
});

test("AUD-C-04 rendered: a paused turn shows the previous turn's answer and citations", async ({
  page,
  audit,
}) => {
  // Two turns: the first grounded, the second pausing on an interrupt. The interrupt
  // shape carries the *previous* answer because pausing nodes never return, so nothing
  // resets those fields (AUD-C-04). Rendered, that is a stale answer sitting above a
  // modal about something else.
  const previous = SHAPES["grounded answer"];
  const paused = {
    ...SHAPES["email_approval interrupt"],
    // What the API actually returns: the interrupt plus the prior turn's presentation.
    answer: previous.answer,
    citations: previous.citations,
  };
  await stubChat(page, { message: paused });
  await page.goto(CHAT_WEB);
  await ask(page, "email an administrator about something else entirely");

  const bubble = page.locator(".message-row.assistant .bubble").last();
  await expect(bubble).toContainText("open 9am to 1pm on Saturdays");
  await expect(bubble.locator(".citation-chip")).toHaveCount(1);
  await expect(page.getByText(/Question from a student about Saturday hours/)).toBeVisible();
  audit.note(
    "AUD-C-04 reproduced in a browser: the paused turn's bubble shows the prior answer + citation while the approval modal is open",
  );
});

test("the composer is disabled while an interrupt is pending, and re-enabled after resolving it", async ({
  page,
}) => {
  // S37's latent gap: `busy = pending !== null`, so an unrecognised interrupt_type would
  // disable the composer with no modal to clear it. This proves the *known* types do
  // clear, which is what makes the latent case a real (if unreachable) deadlock.
  await stubChat(page, {
    message: SHAPES["email_approval interrupt"],
    respond: SHAPES["email sent"],
  });
  await page.goto(CHAT_WEB);
  await ask(page, "please email an administrator");

  await expect(page.locator("textarea")).toBeDisabled();
  await page.getByRole("button", { name: /approve & send/i }).click();
  await expect(page.locator("textarea")).toBeEnabled({ timeout: 20_000 });
  await expect(page.getByText("I've sent your question")).toBeVisible();
});
