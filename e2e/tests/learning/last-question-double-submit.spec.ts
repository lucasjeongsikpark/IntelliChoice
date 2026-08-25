/**
 * D-207 regression test: answering the *last* question of an exam must not be re-submittable.
 *
 * **The measurement this exists for.** Staging's own access log, 2026-08-06T20:12:46.914Z:
 *
 *     POST /learning/sessions/{id}/answers  status_code 409  duration_ms 15.4
 *
 * the eleventh `POST /answers` of a ten-question exam, rejected by
 * `flow.ensure_item_unanswered`. 15 ms means it never reached a graph turn - a pre-flight
 * refusal, i.e. a duplicate.
 *
 * **Why the last question specifically.** `handleSubmitClick` advances to the next question
 * after a submit, and a question the student is no longer looking at cannot be double-clicked.
 * On the last one there is nowhere to advance to, so they stay put - and the lock that should
 * stop them comes from `overview`, which is fetched on a poll. `onFetchOverview()` fires
 * immediately after `onSubmit`, but the answer POST is still in flight, so the overview that
 * comes back still reports the item `unseen`. `isReadOnly` stays false, the options re-enable,
 * and a second Submit is a 409 the student sees.
 *
 * The fix consults `answeredSelections` - written synchronously in `handleSubmitClick` -
 * alongside the server's status, so the lock does not wait on a round trip.
 *
 * **Why the assertion is a request count.** A disabled-attribute check would pass the moment
 * the poll eventually catches up, which is the same thing the bug does, just later. Counting
 * `POST /answers` for one question is the only form of "the duplicate never happened" that
 * cannot be satisfied by the defect.
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

test.describe.configure({ timeout: 240_000 });

/** Wide enough that the second click lands before the overview poll could have locked anything. */
const ANSWER_DELAY_MS = 1_200;

test("the last exam question cannot be answered twice", async ({ page, audit }) => {
  test.skip(TARGET !== "local", "the injected delay simulates the latency staging already has");

  const answerPosts: string[] = [];
  const conflicts: number[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && /\/answers$/.test(request.url())) {
      answerPosts.push(request.url());
    }
  });
  page.on("response", (response) => {
    if (/\/answers$/.test(response.url()) && response.status() === 409) {
      conflicts.push(response.status());
    }
  });

  // Hold the POST open so the window between "submitted" and "locked" is as wide as
  // staging's ~200-400 ms really is. Locally it is ~1 ms and the defect is invisible - the
  // same reason `mutation-serialization.spec.ts` injects a delay.
  await page.route(/\/answers$/, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, ANSWER_DELAY_MS));
    await route.continue();
  });

  // Its own student, not `studentPresent` (WORK-13-FIXTURES). This spec creates a
  // learning session, and the journeys mutate shared per-student Postgres and MySQL
  // state through one seeded account - so a spec sharing that account picks up
  // whatever the previous one left behind. `FIXTURES` in config.ts has the
  // measurement: 7 refused submissions and 2.3 minutes against 15 seconds.
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentDoubleSubmit);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);
  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });

  // Walk to the last question. The position label is the exam's own count, so this does not
  // hard-code 10 and will not silently pass if the batch size changes.
  const position = page.locator(".progress-bar span").nth(1);
  const positionText = (await position.innerText()).trim();
  const total = Number(/of (\d+)/.exec(positionText)?.[1] ?? 0);
  expect(total, `could not read the exam length from ${JSON.stringify(positionText)}`).toBeGreaterThan(1);
  audit.note(`exam length: ${total}`);

  for (let i = 0; i < total - 1; i += 1) {
    const answered = await answerCurrentQuestion(page);
    expect(answered, `could not answer question ${i + 1}`).toBe(true);
  }
  await expect(position).toHaveText(new RegExp(`Question ${total} of ${total}`), {
    timeout: 30_000,
  });

  const postsBeforeLast = answerPosts.length;
  const options = page.locator(".options button.option");
  await options.first().click();
  await page.getByRole("button", { name: /^submit answer$/i }).click();

  // The student, seeing the question still on screen and the options apparently live, tries
  // again. Two attempts, so a lock that only lands after the first retry still fails here.
  for (let attempt = 0; attempt < 2; attempt += 1) {
    await page.waitForTimeout(300);
    const clickable = await options
      .nth(1)
      .click({ timeout: 1_000, trial: true })
      .then(() => true)
      .catch(() => false);
    audit.note(`retry ${attempt + 1}: options still clickable = ${clickable}`);
    if (clickable) {
      await options.nth(1).click();
      const submit = page.getByRole("button", { name: /^submit answer$/i });
      if (await submit.isVisible().catch(() => false)) {
        await submit.click({ timeout: 1_000 }).catch(() => undefined);
      }
    }
  }

  await page.waitForTimeout(ANSWER_DELAY_MS + 800);
  const postsForLast = answerPosts.length - postsBeforeLast;
  audit.note(`POST /answers for the last question: ${postsForLast}; 409s seen: ${conflicts.length}`);

  expect(
    postsForLast,
    `the last question was submitted ${postsForLast} times - the read-only lock waits on the overview poll, so the student can re-answer a question that is already recorded (measured on staging as a 409 at 2026-08-06T20:12:46.914Z)`,
  ).toBe(1);
  expect(
    conflicts.length,
    "a POST /answers took a 409 - a duplicate submission reached the server and the student was shown a conflict for work that had already succeeded",
  ).toBe(0);
});
