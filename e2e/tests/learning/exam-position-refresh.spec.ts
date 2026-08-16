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

import { FIXTURES, LEARNING_WEB, TARGET } from "../../config";
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
  //
  // **Waiting for the server to take them, not for the screen to move** (D-360). The screen
  // advances optimistically, so polling it proves only that the *client* believes two
  // answers landed. Measured on staging: the poll below reached question 3, the reload
  // restored to question **2**, and the restore is right - it lands on the first item still
  // needing an answer, and the second submission was still in flight. That is D-288's
  // mechanism, which `journey-student.spec.ts` already guards by counting acknowledged
  // responses; this spec polled the DOM instead and inherited the race.
  await answerCurrentQuestion(page, { awaitAcceptance: true });
  await answerCurrentQuestion(page, { awaitAcceptance: true });
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

/**
 * D-317 / the second half of D-288: the screen must not render an *answerable* question
 * before it knows which question the student is on.
 *
 * D-288 was read for six days as "the restore fails after a mid-exam refresh". It does not
 * fail; it is late by one round trip. The screen becomes interactive on the SSE snapshot,
 * while the position rides on `GET /exam/overview` - so between those two the student saw
 * Question 1, unlocked, with a working Submit button and no navigator. Measured on staging
 * over six reloads: 3 of 6 caught the window, the widest at **2.7 s**, and the DOM probe that
 * settled it read `navPresent=false` at the failure and `navPresent=true` three seconds later
 * with the position correct. Every earlier explanation looked for a broken restore.
 *
 * **This test has to manufacture the window, and that is the point rather than a shortcut.**
 * Locally the overview lands within milliseconds of the snapshot, which is precisely why five
 * sessions of green local runs never saw a defect that failed on staging repeatedly - the
 * same blindness `narrative-displacement.spec.ts` documents for the ~26 ms mock narrative.
 * Delaying the response reproduces staging's ordering without faking any content: the app's
 * own code paths, the real server, one late reply.
 *
 * The assertion is about what is *reachable*, not about what is drawn. A student who can
 * click Submit on question 1 while their answer to question 1 is already recorded takes
 * D-207's 409, so "no answerable question until the position is known" is the invariant, and
 * the loading placeholder is how it is kept.
 */
const OVERVIEW_DELAY_MS = 3_000;

test("a mid-exam refresh never shows an answerable question before the position is known", async ({
  page,
  audit,
}) => {
  test.skip(
    TARGET !== "local",
    "the delay manufactures staging's own latency; on staging it would stack on top of it",
  );
  audit.allow({ failedRequests: true });

  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);
  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });

  await answerCurrentQuestion(page);
  await answerCurrentQuestion(page);
  const reached = await expect
    .poll(async () => questionNumber(await positionText(page)), { timeout: 30_000 })
    .toBe(3)
    .then(() => true)
    .catch(() => false);
  test.skip(
    !reached,
    "never reached question 3, so a refresh has no position to be wrong about and this run " +
      "says nothing either way",
  );

  // Hold back everything that carries the position, so the reloaded screen is interactive
  // long before it can know where the student is. `route.continue()`, not `fulfill()`: the
  // response must be the real server's, only later.
  await page.route(/\/exam\/(overview|viewed)(\?|$)/, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, OVERVIEW_DELAY_MS));
    await route.continue();
  });

  await page.reload();
  await settleToInteractiveScreen(page);

  // The window itself. Sampled rather than checked once, because a single reading could land
  // either side of it and report a pass for a run that never opened the window at all.
  let sawAnswerableWrongQuestion = false;
  let sawPlaceholder = false;
  const deadline = Date.now() + OVERVIEW_DELAY_MS - 500;
  while (Date.now() < deadline) {
    const state = await page.evaluate(() => ({
      position: document.querySelector(".progress-bar")?.textContent ?? "",
      submittable:
        document.querySelector<HTMLButtonElement>("button.submit-answer, button[type=submit]") !==
          null || /submit answer/i.test(document.body.innerText),
      loading: /loading the next question/i.test(document.body.innerText),
    }));
    if (state.loading) sawPlaceholder = true;
    if (state.submittable && /Question 1 of/.test(state.position)) {
      sawAnswerableWrongQuestion = true;
      break;
    }
    await page.waitForTimeout(100);
  }
  audit.note(`during the ${OVERVIEW_DELAY_MS}ms window: placeholder=${sawPlaceholder}, answerable-Q1=${sawAnswerableWrongQuestion}`);

  expect(
    sawAnswerableWrongQuestion,
    "the exam rendered question 1 with a working Submit while the student was actually on " +
      "question 3 - the position was still unknown and the screen answered anyway (D-288/D-317)",
  ).toBe(false);

  // And the gate must open, not merely hold - a screen that never renders is a worse defect.
  await expect
    .poll(async () => questionNumber(await positionText(page)), { timeout: EXAM_RETURN_MS })
    .toBe(3);
  audit.note("gate opened and the position restored to question 3");
});
