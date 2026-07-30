/**
 * AUD-F-27 regression test: every answer the student submits must reach the server.
 *
 * `useLearningSession.run()` serializes mutations, and it used to *discard* any call that
 * arrived while another was in flight - returning `null` with no request, no error and no
 * retry, while `ExamScreen` had already advanced the question and displayed "Answer
 * submitted for question N". Measured on staging in one run: **2 of 10 answers reached the
 * server in `journey-student`, 1 of 10 in `hint-displacement`, and the finalize was
 * dropped too** (its modal then sat there with a dead-looking confirm button). A dropped
 * answer is scored incorrect, which corrupts the pre-exam score, the learning gain derived
 * from it, and the parent report built on that.
 *
 * **Why this file delays a request.** The window is the server's response time: ~200-400ms
 * on staging against ~1ms locally, so on the mock the next click never lands inside it and
 * the defect is invisible - the fifth finding in this session's "only staging can see it"
 * family (AUD-C-02, AUD-F-19, AUD-F-21, AUD-F-26, AUD-F-27) and the third that is a race
 * the mock is too fast to lose. Rather than leave this class visible only to a staging run,
 * the answer POST is held open here so a local run reproduces staging's timing exactly.
 *
 * The assertion is a *count*, deliberately, not a disabled-attribute check: what the
 * student cares about is that their work was recorded, and counting the requests is the
 * only form of that claim which cannot pass while the underlying bug is present. The
 * "Submitting…" label is asserted too, but as corroboration - it is the visible half of the
 * same fix (the `busy` prop `App.tsx` had hardcoded to `false`).
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

/** Long enough that a human-speed second click lands inside it; short enough to keep the run quick. */
const ANSWER_DELAY_MS = 1_200;
const ANSWERS_TO_SUBMIT = 3;

test("every submitted answer reaches the server, even when the previous one is still in flight", async ({
  page,
  audit,
}) => {
  // Local-only for the same reason as narrative-displacement's delayed arms: the delay
  // simulates staging's latency, and stacking it on staging's real latency would measure
  // the sum of two waits rather than the behaviour. Staging covers this natively - it is
  // where the defect was found, by `journey-student` and `hint-displacement`.
  test.skip(TARGET !== "local", "the injected delay simulates the latency staging already has");

  const answerPosts: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && /\/answers$/.test(request.url())) {
      answerPosts.push(request.url());
    }
  });

  // Hold the answer POST open so the next interaction arrives while it is still in flight -
  // `route.continue()` after a timer, so the real endpoint still does the real work.
  await page.route(/\/answers$/, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, ANSWER_DELAY_MS));
    await route.continue();
  });

  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);
  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });

  // Corroboration that the `busy` prop is actually reaching the screen: submit once and
  // catch the in-flight label. Raced deliberately loosely - if the button has already
  // settled by the time this looks, the count assertion below is still the real check.
  const options = page.locator(".options button.option");
  await options.first().click();
  const submit = page.getByRole("button", { name: /^submit answer$/i });
  await submit.click();
  const sawSubmitting = await page
    .getByRole("button", { name: /^submitting…$/i })
    .waitFor({ state: "visible", timeout: ANSWER_DELAY_MS })
    .then(() => true)
    .catch(() => false);
  audit.note(`saw the in-flight "Submitting…" label: ${sawSubmitting}`);

  // Then answer the rest through the normal helper, which clicks real controls and so is
  // held back by the disabled state exactly as a student's clicks would be.
  for (let i = 1; i < ANSWERS_TO_SUBMIT; i += 1) {
    const answered = await answerCurrentQuestion(page);
    expect(answered, `could not answer question ${i + 1}`).toBe(true);
  }
  // Let the last in-flight request finish before counting.
  await page.waitForTimeout(ANSWER_DELAY_MS + 500);

  audit.note(`answers submitted: ${ANSWERS_TO_SUBMIT}, POST /answers sent: ${answerPosts.length}`);
  expect(
    answerPosts.length,
    `the student submitted ${ANSWERS_TO_SUBMIT} answers and only ${answerPosts.length} reached the server - the rest were discarded by the in-flight guard while the screen said they had been submitted (AUD-F-27)`,
  ).toBe(ANSWERS_TO_SUBMIT);
  expect(
    sawSubmitting,
    'the "Submitting…" label never appeared, so `busy` is not reaching ExamScreen - the controls stay live during a mutation and a second click can still be discarded',
  ).toBe(true);
});
