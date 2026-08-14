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

/**
 * The two delayed-narrative arms are `local`-only, and the reason is not convenience.
 *
 * The delay exists to make a ~26ms mock behave like real Bedrock. On staging the narrative
 * is *already* slow, so the delay would stack on top of a latency this file does not
 * control, and both arms would be measuring the sum of two waits rather than the ordering
 * they were written for. Arm 1's own subject - the exam screen surviving a late narrative,
 * measured through the dwell - is what `time-telemetry.spec.ts` measures on staging, and
 * that spec failing was how AUD-F-21 was found in the first place; arm 2's subject is a
 * purely client-side rule that the mock exercises exactly. So staging loses no coverage.
 *
 * This is a target skip with a stated reason, the same kind as `journey-chat.spec.ts`'s
 * dev-login skip (D-097) - deliberately not the kind AUD-F-23 was about, where a condition
 * silently never fired and four sessions of runs reported a journey as merely "skipped".
 * Arm 3 needs no faked timing and runs on both targets.
 */
const LOCAL_ONLY = "the SSE delay simulates real Bedrock latency, which staging already has (see this file's header)";

test("a narrative arriving mid-exam leaves the exam screen mounted and the dwell intact", async ({
  page,
  audit,
}) => {
  test.skip(TARGET !== "local", LOCAL_ONLY);
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

  // **Move off Question 1 before measuring anything.** This line is the whole reason this
  // arm can see AUD-F-24. A remount re-runs `useState(0)` and returns the student to
  // Question 1 - so an arm that sits on Question 1 and compares the position afterwards
  // compares 1 to 1 and passes through the defect. The first AUD-F-21 fix shipped green
  // against exactly that blind spot and truncated the dwell on staging anyway.
  // Waited for: `QuestionNavBar` renders only once `GET /exam/overview` has landed, which
  // is after the phase chip appears. Asserting the count immediately reads zero buttons.
  const nav = page.locator(".question-nav button, .exam-nav button");
  await expect(
    nav.nth(2),
    "no question navigator after the overview should have landed, so this arm cannot move off Question 1 and cannot detect a remount",
  ).toBeVisible({ timeout: 30_000 });
  await nav.nth(2).click();

  reported.length = 0;
  // The position span only - `.progress-bar` also holds the exam timer, which ticks down
  // during the dwell and would make any whole-element comparison fail on the clock rather
  // than on a remount.
  const position = page.locator(".progress-bar span", { hasText: /Question \d+ of \d+/ });
  const questionBefore = (await position.innerText()).trim();
  expect(
    questionBefore,
    "the navigator click did not move off Question 1, so a remount would be invisible here",
  ).not.toMatch(/Question 1 of/);
  const dwellStarted = Date.now();

  // Wait for the narrative rather than assuming a fixed delay puts it inside the dwell:
  // the arrival time is the mock's plus the delay, and a spec that measures an ordering
  // should wait for the ordering rather than race it. The dwell is topped up to DWELL_MS
  // afterwards, so the measurement below is still against a known minimum.
  const narrativeArrived = await narrativeContinue(page)
    .waitFor({ state: "visible", timeout: 45_000 })
    .then(() => true)
    .catch(() => false);
  const arrivedAt = Date.now() - dwellStarted;
  audit.note(`narrative arrived ${arrivedAt}ms into the dwell: ${narrativeArrived}`);
  // Non-vacuity: if the narrative never showed, this test measured nothing.
  expect(
    narrativeArrived,
    `no stage narrative arrived while the exam screen was up, so nothing was tested - the ${STREAM_DELAY_MS}ms SSE delay is supposed to land one mid-exam`,
  ).toBe(true);
  const remaining = DWELL_MS - (Date.now() - dwellStarted);
  if (remaining > 0) await page.waitForTimeout(remaining);

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

  // D-213: dismiss the narrative before navigating. It is now a `position: fixed` overlay
  // that intercepts pointer events until `Continue` is pressed - which is the requested
  // behaviour ("only that screen, and Continue goes to the question"), so the navigator
  // click below is genuinely unreachable while it is up rather than flaky.
  //
  // This does not weaken what the test measures. Every assertion above about the screen
  // staying mounted was made *while* the narrative was showing, which is the window the
  // defect lived in; the dwell flush only needs the narrative gone to reach the navigator.
  await narrativeContinue(page).click();
  await expect(narrativeContinue(page)).toHaveCount(0);

  // And the dwell telemetry (the exam screen's autosave signal - since AUD-L-14 the
  // report reads `response_time_ms` instead, but a truncated flush here would still mean
  // the screen unmounted mid-dwell). Navigating away flushes the dwell.
  await nav.nth(1).click();
  await page.waitForTimeout(1000);

  const max = reported.length > 0 ? Math.max(...reported) : 0;
  audit.note(`${reported.length} time reports, max=${max}ms over a ${DWELL_MS}ms dwell`);
  expect(
    max,
    `the longest reported dwell was ${max}ms after ${DWELL_MS}ms on one question - an unmount mid-dwell flushed a truncated measurement`,
  ).toBeGreaterThan(DWELL_MS * 0.5);
});

test("a narrative arriving after the student has answered is dropped, not interposed", async ({
  page,
  audit,
}) => {
  test.skip(TARGET !== "local", LOCAL_ONLY);
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

  // A *topic button*, not the `.card-list` container. The container assertion was written
  // when the topic screen rendered one list; D-319 groups it into "For you" / "All topics",
  // so `.card-list` legitimately resolves to two nodes and a strict-mode `toBeVisible()`
  // fails on the count rather than on the subject. What this test means by "the topic list
  // is rendered" is that the student can still see a topic, which is what this asserts and
  // what survives any future regrouping.
  await expect(
    page.locator(".card-list button").first(),
    "the topic list is not rendered beneath the narrative - the narrative replaced it",
  ).toBeVisible();

  // Dismissing it leaves the student on the screen that was already there, rather than
  // revealing it for the first time.
  await narrativeContinue(page).first().click();
  await expect(narrativeContinue(page)).toHaveCount(0);
  await expect(page.locator(".card-list button").first()).toBeVisible();
  audit.note("narrative and topic list coexisted, and dismissal left the topic list in place");
});
