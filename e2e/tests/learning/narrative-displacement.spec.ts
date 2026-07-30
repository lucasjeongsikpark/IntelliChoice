/**
 * AUD-F-21 regression test (S43 continuation): a stage narrative renders *above* the
 * screen the student is using, never instead of it.
 *
 * `App.tsx` used to return `StageTransitionScreen` as a sibling branch of the phase
 * screens, so a narrative arriving mid-phase unmounted whatever was on screen. Measured
 * on staging: a 2116ms flush against a 15,000ms dwell (the upstream half of AUD-L-14's
 * "0.0 minutes next to 26 attempts"), and a student returned to Question 1 with their
 * cached batch gone because the remount re-ran `useState(0)`.
 *
 * **The reason this file has to fake a slow narrative.** `stage_narrative` is an LLM call.
 * `MockBedrockProvider` returns in ~26ms, so locally the narrative is in the first snapshot
 * before the exam screen has ever rendered and there is nothing to displace - which is
 * exactly why S39-S41's local runs were green while staging failed three times in a row.
 * That is the third finding in this shape (AUD-C-02, AUD-F-19, AUD-F-21), so rather than
 * leave this class visible only to a staging run, the SSE connect is *delayed* here until
 * after the exam screen is up. The narrative then arrives while the student is working,
 * which is the real Bedrock timing reproduced on the mock.
 *
 * The delay is applied to the request, not the payload: `_initial_snapshot` fires
 * `pre_intro` on first SSE connect when the checkpoint carries no narrative yet
 * (routers/stream.py), so postponing the connect postpones the narrative without faking
 * any content or touching the app's own code paths.
 *
 * Each test asserts the narrative actually arrived before asserting anything about it. A
 * displacement test that silently passes because nothing was ever displaced is the same
 * false negative `make scan-traces` refuses to allow (AUD-F-12) and the same reason
 * smoke.spec.ts exists.
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

/** How long the SSE connect is held back, i.e. how late the narrative arrives. */
const STREAM_DELAY_MS = 6_000;

/**
 * Hold back the SSE connect so the narrative lands after the phase screen has rendered.
 * `route.continue()` rather than `route.fulfill()`: the response is a live stream and must
 * come from the real server, so only the *start* of it is postponed.
 */
async function delayStreamConnect(page: import("@playwright/test").Page): Promise<void> {
  let delayed = false;
  await page.route(/\/stream(\?|$)/, async (route) => {
    if (!delayed) {
      delayed = true;
      await new Promise((resolve) => setTimeout(resolve, STREAM_DELAY_MS));
    }
    await route.continue();
  });
}

const narrativeContinue = (page: import("@playwright/test").Page) =>
  page.getByRole("button", { name: /^continue$/i });

test("a narrative arriving mid-exam leaves the exam screen mounted and the dwell intact", async ({
  page,
  audit,
}) => {
  // Same allowance as time-telemetry.spec.ts: a time report still in flight when the page
  // navigates is aborted by design (the hook is fire-and-forget).
  audit.allow({ failedRequests: true });

  const reported: number[] = [];
  page.on("request", (request) => {
    if (!/\/exam\/items\/[^/]+\/time$/.test(request.url())) return;
    const body = request.postData();
    if (!body) return;
    try {
      reported.push((JSON.parse(body) as { elapsed_ms: number }).elapsed_ms);
    } catch {
      // Not JSON - nothing to measure.
    }
  });

  await delayStreamConnect(page);
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);
  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });

  // The exam screen is up and the narrative has not arrived yet - the window the defect
  // lived in. Dwell across the narrative's arrival.
  const DWELL_MS = 15_000;
  reported.length = 0;
  // The position span only - `.progress-bar` also holds the exam timer, which ticks down
  // during the dwell and would make any whole-element comparison fail on the clock rather
  // than on a remount.
  const position = page.locator(".progress-bar span", { hasText: /Question \d+ of \d+/ });
  const questionBefore = (await position.innerText()).trim();
  await page.waitForTimeout(DWELL_MS);

  // Non-vacuity: if the narrative never showed, this test measured nothing.
  const narrativeArrived = (await narrativeContinue(page).count()) > 0;
  audit.note(`narrative visible after a ${DWELL_MS}ms dwell: ${narrativeArrived}`);
  expect(
    narrativeArrived,
    `no stage narrative arrived during the dwell, so nothing was tested - the ${STREAM_DELAY_MS}ms SSE delay is supposed to land one mid-exam`,
  ).toBe(true);

  // The fix, stated three ways. Under the old sibling branch all three failed together.
  await expect(
    page.locator(".phase-chip"),
    "the exam screen unmounted when the narrative arrived - this is also what stalls the post-finalize journey wait, which polls for .phase-chip",
  ).toHaveCount(1);
  await expect(
    page.locator(".options button.option").first(),
    "the question's options are gone while the narrative is showing",
  ).toBeVisible();
  const questionAfter = (await position.innerText()).trim();
  audit.note(`progress before narrative: "${questionBefore}", after: "${questionAfter}"`);
  expect(
    questionAfter,
    "the exam screen remounted, so useState(0) re-initialised and the student was returned to the first question",
  ).toBe(questionBefore);

  // And the measurement the parent report is built from. Navigating away flushes the dwell.
  const nav = page.locator(".question-nav button, .exam-nav button");
  if ((await nav.count()) > 1) await nav.nth(1).click();
  await page.waitForTimeout(1000);

  const max = reported.length > 0 ? Math.max(...reported) : 0;
  audit.note(`${reported.length} time reports, max=${max}ms over a ${DWELL_MS}ms dwell`);
  expect(
    max,
    `the longest reported dwell was ${max}ms after ${DWELL_MS}ms on one question - an unmount mid-dwell flushes a truncated measurement into time_spent_minutes`,
  ).toBeGreaterThan(DWELL_MS * 0.5);
});

test("a narrative arriving after the student has answered is dropped, not interposed", async ({
  page,
  audit,
}) => {
  audit.allow({ failedRequests: true });

  await delayStreamConnect(page);
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);
  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });

  // Answer before the narrative can arrive. This is the "student is already working" state
  // that a stage *intro* has nothing useful to say to, and pushing the question down the
  // page mid-thought is its own defect.
  const answered = await answerCurrentQuestion(page);
  expect(answered, "could not answer a question before the narrative arrived").toBe(true);

  // Long enough for the delayed connect and its snapshot to land.
  await page.waitForTimeout(STREAM_DELAY_MS + 4_000);

  const shown = await narrativeContinue(page).count();
  audit.note(`narrative screens showing after answering: ${shown}`);
  await expect(
    page.locator(".phase-chip"),
    "the exam screen should still be the screen in front of the student",
  ).toHaveCount(1);
  expect(
    shown,
    "a stage narrative interposed after the student had already answered a question",
  ).toBe(0);
});

test("when a narrative shows before the student has acted, the screen beneath it survives", async ({
  page,
  audit,
}) => {
  // No delay here: locally the mock puts the narrative in the very first snapshot, which is
  // the *other* ordering, and the co-existence contract has to hold in both. This is the one
  // arm of this file that would have caught AUD-F-21 without faking any timing - the old
  // code returned the narrative screen alone, so `.card-list` was absent.
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await startSession(page);

  const shown = await narrativeContinue(page)
    .waitFor({ state: "visible", timeout: 60_000 })
    .then(() => true)
    .catch(() => false);
  expect(shown, "no stage narrative appeared at the start of the session").toBe(true);

  await expect(
    page.locator(".card-list"),
    "the topic list is not rendered beneath the narrative - the narrative replaced it",
  ).toBeVisible();

  // Dismissing it leaves the student on the screen that was already there, rather than
  // revealing it for the first time.
  await narrativeContinue(page).first().click();
  await expect(narrativeContinue(page)).toHaveCount(0);
  await expect(page.locator(".card-list")).toBeVisible();
  audit.note("narrative and topic list coexisted, and dismissal left the topic list in place");
});
