/**
 * D-391: the exam timer runs out, and the student is not trapped.
 *
 * One of the last never-walked paths from the 2026-08-17 audit, and the one with the worst failure
 * mode. `ExamScreen`'s own comment states the design and the risk in the same breath: an expired
 * exam **refuses further answers** (`submit_answer` → 409 "exam time limit exceeded - finalize to
 * submit"), so if `handleExpire`'s automatic finalize does not work, a student who ran out of time
 * "would be unable to answer AND unable to submit - trapped in a screen with no exit". Nothing had
 * ever driven that path.
 *
 * **The interesting case is expiry with unanswered questions**, which is the realistic one — a
 * student runs out of time *because* they did not finish. `handleExpire` calls `onFinalize(false)`,
 * the server refuses it (SPEC §5.9/§5.13: finalizing with unanswered items requires
 * `confirm_unanswered`), and the fallback opens the confirmation modal so there is still a way out.
 * Three things therefore have to hold, and only the third is the one that matters:
 *
 *   1. the student is told what happened rather than watching a silent submit;
 *   2. the modal explains that unanswered questions are graded incorrect, because it is now the
 *      only path forward and consenting to it should be informed;
 *   3. confirming actually finalizes and the session moves on.
 *
 * **The clock is patched, not the payload.** `route.fetch()` fetches the real `/exam/overview` and
 * only `remaining_seconds` is overwritten. Fabricating that response would mean inventing items,
 * positions and statuses — and a fixture body invented to satisfy a test proves only that the test
 * agrees with itself (D-386). The countdown is client-side by design (`ExamTimer` ticks locally, no
 * backend push), so a small seed value is exactly what the client sees when time really is short.
 *
 * **Its own student (D-288).** This walk *finalizes* an exam, which is the one session state a
 * later spec cannot resume past, so `student-ext-13` exists for it rather than sharing.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";
import {
  PHASE_CHIP,
  chooseTopic,
  settleToInteractiveScreen,
  startSession,
} from "../../fixtures/learning-flow";

test.describe.configure({ timeout: 240_000 });

/**
 * Two ways a student meets a finished clock, and only the first was imaginable before this walk:
 *
 *  - **6** - it runs out while they are on the screen, the ordinary case;
 *  - **0** - the overview *arrives* already expired, which is what a reload after time ran out
 *    looks like. Before D-391 the countdown only fired on the transition to zero, so this case
 *    fired nothing at all: no auto-finalize, and `submit_answer` 409s every attempt. This is the
 *    case that was actually broken.
 */
for (const secondsLeft of [6, 0] as const) {
test(`an expired exam finalizes itself instead of trapping the student (remaining=${secondsLeft})`, async ({ page, audit }) => {
  // The finalize the client attempts first is *refused* by the server - that refusal is the
  // subject, not a fault - and Chromium logs the 4xx as a console error.
  audit.allow({
    statuses: [400, 409],
    consoleErrors: ["Failed to load resource"],
  });

  // **Counted after the fetch resolves, not when the handler starts.** The first version
  // incremented on entry and then read the counter from the test body, which raced: the handler
  // was still inside `route.fetch()` when the assertion ran, so the walk skipped itself with "no
  // timer" while the timer was in the response it had not finished reading. Same shape as D-288
  // and D-389 - count the acknowledgement, not the attempt.
  let handled = 0;
  let observedRemaining: unknown;
  let patched = 0;
  await page.route("**/learning/sessions/*/exam/overview", async (route) => {
    const response = await route.fetch();
    const body = (await response.json()) as Record<string, unknown>;
    observedRemaining = body.remaining_seconds;
    // Only if the server actually offers a countdown: a null here means this build has no time
    // limit configured, and silently inventing one would test a feature rather than the product.
    if (body.remaining_seconds !== null && body.remaining_seconds !== undefined) {
      body.remaining_seconds = secondsLeft;
      patched += 1;
    }
    handled += 1;
    await route.fulfill({ response, json: body });
  });

  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentExpiry);
  await startSession(page);
  await settleToInteractiveScreen(page);
  // The exam does not begin - and `/exam/overview` is not fetched - until a topic is chosen. The
  // first version of this walk asserted before this line and skipped itself with "no timer",
  // which was the walk stopping short rather than the product lacking a clock.
  await chooseTopic(page);
  await expect(page.locator(PHASE_CHIP)).toHaveText(/pre-exam/i, { timeout: 60_000 });

  await expect
    .poll(() => handled, {
      message: "the exam screen never fetched /exam/overview, so nothing below was exercised",
      timeout: 30_000,
    })
    .toBeGreaterThan(0);
  test.skip(
    patched === 0,
    `this build served remaining_seconds=${JSON.stringify(observedRemaining)}, so there is no ` +
      "timer to run out - skipping rather than fabricating one",
  );

  // 1. The student is told, rather than watching the screen submit by itself.
  await expect(
    page.getByText(/time.s up/i),
    "the exam expired silently - the student saw a submit they did not ask for and no reason for it",
  ).toBeVisible({ timeout: 60_000 });

  // 2. The way out exists and explains its own cost. `handleExpire` finalizes without
  // `confirm_unanswered` first; the server refuses while items are unanswered, and this modal is
  // the fallback that keeps the screen escapable.
  const modal = page.locator(".modal, [role='dialog']").first();
  await expect(
    modal,
    "the automatic finalize was refused and no modal opened - this is the trapped student the " +
      "ExamScreen comment warns about: answers are 409'd and there is no way to submit",
  ).toBeVisible({ timeout: 30_000 });
  // Quoted from what the modal actually renders, not from what this test first assumed it would.
  // The copy is better than "unanswered": it names the count, lists the question numbers, and says
  // the consequence in a student's words (SPEC §5.10.3).
  await expect(modal).toContainText(/questions still need an answer/i);
  await expect(modal).toContainText(/marked incorrect if you submit now/i);
  // D-391: the same sentence rendered "still need  an answer" with a double space here, and
  // "still need s an answer" with **one** unanswered question - the `{" "}` was on the wrong side
  // of the conditional plural. Asserted so the space cannot drift back.
  await expect(modal).not.toContainText(/need {2,}an answer|need s an answer/i);

  // 3. The one that matters: confirming actually gets them out.
  const confirm = modal.getByRole("button", { name: /submit|finish|confirm/i }).first();
  await confirm.click();

  await expect(
    page.locator(PHASE_CHIP),
    "the student confirmed the submit and the exam did not finalize, which leaves them exactly " +
      "where they started with no remaining action",
  ).not.toHaveText(/pre-exam/i, { timeout: 60_000 });

  audit.note(`EXAM EXPIRY | overview patched ${patched}x | phase after confirm: ` +
    `${await page.locator(PHASE_CHIP).innerText()}`);
});
}
