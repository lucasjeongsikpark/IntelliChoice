/**
 * AUD-F-03, the half a refresh test cannot see: the restored position must be applied **once
 * per phase**, not on every overview fetch.
 *
 * `journey-student.spec.ts` covers the finding itself (answer two, refresh, land back on
 * question 3). This file covers the bad fix that would pass that test and be worse than the
 * defect. The position is derived from the exam overview - the first item still needing an
 * answer - and the overview is polled every 20 s (`OVERVIEW_POLL_MS`). Re-deriving on each
 * poll would mean a student who navigated back to review an answered question got yanked
 * forward again seconds later, with no way to stay put and nothing on screen explaining why.
 *
 * That defect is silent and delayed, which is why this test waits rather than asserting
 * immediately: nothing errors, no request fails, the student is simply moved. An assertion
 * taken right after the click would pass against the broken version.
 *
 * The precondition is established before anything is asserted about it. A run that never
 * reached question 3 would otherwise have nothing to navigate back *from* and would report a
 * pass for a session that sat on question 1 throughout - the vacuous-pass shape D-171 §2 and
 * `narrative-refresh.spec.ts`'s own rewrite are both about.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";
import {
  answerCurrentQuestion,
  chooseTopic,
  settleToInteractiveScreen,
  startSession,
} from "../../fixtures/learning-flow";

test.describe.configure({ timeout: 180_000 });

/** The exam screen has to come back after the reload, and on staging that is a real wait. */
const EXAM_RETURN_MS = 60_000;
/**
 * Comfortably past `OVERVIEW_POLL_MS` (20 s in ExamScreen.tsx), so this outlives at least one
 * poll tick. A shorter wait would pass against the very fix this test exists to reject.
 */
const PAST_ONE_POLL_MS = 26_000;

const positionText = (page: import("@playwright/test").Page) =>
  page.locator(".progress-bar").innerText();

/** e.g. "Pre-exam Question 3 of 10" -> 3. Null when no position is rendered yet. */
function questionNumber(text: string): number | null {
  const match = /Question (\d+) of \d+/.exec(text);
  return match?.[1] ? Number(match[1]) : null;
}

test("after a refresh, navigating back to an answered question stays there", async ({
  page,
  audit,
}) => {
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);
  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });

  // Two answers, so question 1 is answered-and-locked and the screen has advanced to 3.
  await answerCurrentQuestion(page);
  await answerCurrentQuestion(page);
  const reached = await expect
    .poll(async () => questionNumber(await positionText(page)), { timeout: 30_000 })
    .toBe(3)
    .then(() => true)
    .catch(() => false);
  test.skip(
    !reached,
    "could not reach question 3, so there is no answered question to navigate back to and " +
      "this run says nothing either way",
  );

  await page.reload();
  await settleToInteractiveScreen(page);
  await expect
    .poll(async () => questionNumber(await positionText(page)), { timeout: EXAM_RETURN_MS })
    .toBe(3);
  audit.note("position restored to question 3 after the refresh");

  // Question 1 is answered and locked, which is exactly the case a student reviews.
  await page.getByRole("button", { name: /^Question 1, answered, locked$/ }).click();
  await expect
    .poll(async () => questionNumber(await positionText(page)), { timeout: 15_000 })
    .toBe(1);
  audit.note(`jumped back to question 1; waiting ${PAST_ONE_POLL_MS} ms for a poll tick`);

  await page.waitForTimeout(PAST_ONE_POLL_MS);
  const settled = questionNumber(await positionText(page));
  audit.note(`position after the wait: ${settled}`);
  expect(
    settled,
    "the student was moved off the answered question they navigated back to - the position " +
      "restore is re-applying on every overview fetch instead of once per phase",
  ).toBe(1);
});
