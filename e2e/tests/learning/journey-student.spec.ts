/**
 * The student launch journey, end to end through the browser:
 * sign in → start → topic → pre-exam → study → post-exam → results.
 *
 * INTEGRATION_PLAN §2.3 lists this as the first of AUD-F's "every launch user journey"
 * and §2.6 criterion 3 requires it to pass with zero console errors, zero 5xx, and zero
 * blank/stuck states. All three are enforced by the capture fixture at teardown, over
 * the whole run rather than at any one step.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { expectNotBlank, expectNotStuck, signInViaUi } from "../../fixtures/session";
import {
  answerCurrentQuestion,
  answerWholeExam,
  chooseTopic,
  clearInterventionIfPresent,
  currentPhase,
  settleToInteractiveScreen,
  finalizeExam,
  startSession,
} from "../../fixtures/learning-flow";

// A full three-phase walk is ~25 graded submissions against a real graph.
test.describe.configure({ timeout: 300_000 });

/**
 * Covers sign-in → start → topic → the full 10-item pre-exam → finalize → study entry,
 * including the retry ladder.
 *
 * It deliberately stops short of post-exam and results, and the reason is a limitation of
 * *this harness*, not a product defect: to stay deterministic the walk always picks the
 * first option, so it answers wrong nearly every time, the study phase never reaches the
 * mastery bar that ends it, and post-exam is never served. Measured: 22 answers and 18
 * ladder responses in 6 minutes with the study phase still advancing normally, zero 5xx.
 * S36 completed four full journeys through the API precisely because it could choose
 * answers; a browser cannot see the correct one.
 *
 * Closing the gap needs the walk to read the answer off the ladder's "Show the solution"
 * panel and then answer correctly - a real student path, and the right shape for it. Left
 * as carry-over rather than rushed, because a walk that fakes progress is worse than one
 * with a stated boundary.
 */
test("student walks sign-in → pre-exam → finalize → study (the ladder included)", async ({
  page,
  audit,
}) => {
  // AUD-F-02 (its own finding, measured in post-finalize-poll.spec.ts): finalizing an exam
  // produces a burst of 409s on `exam/overview` and `exam/items/{id}/time`, each a browser
  // console error. Allowed by path here so this journey still enforces "zero console
  // errors" for everything else - otherwise one known defect would mask every new one.
  audit.allow({ statuses: [409], consoleErrors: ["Failed to load resource"] });
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await expectNotBlank(page);

  await expect(page.getByRole("heading", { name: /ready to learn/i })).toBeVisible();
  await startSession(page);

  // "Connecting…" is the SSE gap between session create and the first snapshot; it must
  // resolve, and D-032/S26 record that it silently did not once before.
  await expectNotStuck(page, "Connecting…");

  await settleToInteractiveScreen(page);
  await chooseTopic(page);

  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });
  const preAnswered = await answerWholeExam(page);
  audit.note(`pre-exam: answered ${preAnswered} items`);
  expect(preAnswered, "the pre-exam is SPEC §5.9.2's fixed 10-item set").toBe(10);
  await finalizeExam(page);

  // The study phase interposes a stage narrative, then serves one question at a time.
  await settleToInteractiveScreen(page);
  await expect
    .poll(async () => currentPhase(page), { timeout: 60_000 })
    .toMatch(/study|post-exam/i);

  let studyAnswers = 0;
  let interventions = 0;
  for (let i = 0; i < 12; i += 1) {
    await settleToInteractiveScreen(page);
    const phase = await currentPhase(page);
    if (phase && /post-exam/i.test(phase)) break;
    // A wrong answer pauses the graph on `intervention_choice`; the ladder must be
    // worked before the next question is reachable (SPEC §5.11.3).
    if (await clearInterventionIfPresent(page)) {
      interventions += 1;
      continue;
    }
    // `optionIndex: i` cycles the choice across questions (D-310). The ladder only engages on
    // a WRONG answer, and with a fixed first-option choice this walk depended on the first
    // option happening to be wrong for some item - an accident of the stored option order.
    // D-302 changed which items are served here and the accident stopped holding, so the
    // assertion below failed on staging while the app behaved correctly.
    if (!(await answerCurrentQuestion(page, { optionIndex: i }))) {
      await page.waitForTimeout(1000);
      continue;
    }
    studyAnswers += 1;
  }
  audit.note(`study: worked ${interventions} retry-ladder pauses`);
  audit.note(`study: answered ${studyAnswers} items`);
  expect(studyAnswers, "the study phase served no questions at all").toBeGreaterThan(0);
  expect(interventions, "the retry ladder never engaged, so it went unexercised").toBeGreaterThan(0);
  await expectNotBlank(page);
});

// AUD-F-03 regression test, promoted 2026-08-04 exactly as its own marker instructed: it was
// a `test.fail()` probe measuring a confirmed defect (going back to "Question 1 of 10" from
// question 3), and the fix made it "pass unexpectedly", which is the signal to drop the
// marker. **The finding id was wrong here and is corrected**: this behaviour is AUD-F-03;
// AUD-F-04 is the narrative returning after a refresh (narrative-refresh.spec.ts).
//
// **The "shifted by one" claim that used to end this comment was wrong, and the sweep it
// asked for is what disproved it (2026-08-04, D-174).** Every AUD-F-01 and AUD-F-02 citation
// in the suite is correct - F-01 traces to the refetch burst (time-telemetry.spec.ts) and
// F-02 to the post-finalize 409 burst (post-finalize-poll.spec.ts). The real mis-citations
// were one family, off by four not one: five references called the ~26 ms narrative-
// displacement race AUD-F-01 when it is AUD-F-05.
//
// The position is now derived from the exam overview rather than persisted, and applied once
// per phase - `exam-position-refresh.spec.ts` covers the "once per phase" half, which this
// test cannot see.
test("a refresh mid-exam restores the exact position (SPEC Phase 11)", async ({ page, audit }) => {
  // Its own student, NOT studentPresent (D-288). Staging's sessions persist, so a second
  // test signing in as the full walk's student resumes that walk's exam mid-flight -
  // measured on staging as "answerWholeExam returned 1 of 10" and a refresh comparison
  // between two different questions (PROGRESS 2026-08-07). Resume-on-sign-in is the
  // *feature this test exists to check*, which is exactly why it must not share a student.
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentResume);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);
  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });

  // **Count the answers the SERVER acknowledged, not the clicks (D-288).**
  //
  // `answerCurrentQuestion` returns as soon as it clicks Submit; it waits out the POST only
  // at the start of the next call. The restore below lands on *the first item still needing
  // an answer*, so a second answer still in flight at reload brings the student back to a
  // question this test has already left - two entirely different questions, which is the
  // staging symptom carried since 2026-08-07 and read there as session sharing.
  //
  // Waiting on the "Submitting…" button label was the first fix and is itself a race: if
  // React has not re-rendered yet the label is absent, and `waitFor({state:"detached"})`
  // resolves against nothing. `networkidle` is no good either - the SSE stream never goes
  // idle. Counting acknowledged 2xx responses is the only form with nothing to lose to
  // timing.
  const acknowledged: string[] = [];
  page.on("response", (response) => {
    if (
      response.request().method() === "POST" &&
      response.url().includes("/answers") &&
      response.status() < 300
    ) {
      acknowledged.push(response.url());
    }
  });

  // Answer two, so the restored position is provably not just "the first question".
  await answerCurrentQuestion(page);
  await answerCurrentQuestion(page);
  await expect
    .poll(() => acknowledged.length, { timeout: 30_000 })
    .toBeGreaterThanOrEqual(2);
  const before = await page.locator(".progress-bar").innerText();
  const questionBefore = await page.locator("h1").innerText();
  audit.note(`before refresh: ${before.replace(/\s+/g, " ")}`);

  await page.reload();

  // `settleToInteractiveScreen` used to be here because a reload re-showed the
  // already-dismissed narrative (AUD-F-04, fixed 2026-08-04 - see narrative-refresh.spec.ts).
  // Kept anyway: it settles the screen rather than only clearing narratives, and this test is
  // about the position, so it should not start depending on AUD-F-04 staying fixed.
  await settleToInteractiveScreen(page);
  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });
  await expectNotStuck(page, "Loading the next question…");
  await expectNotBlank(page);
  const questionAfter = await page.locator("h1").innerText();
  audit.note(`after refresh: ${(await page.locator(".progress-bar").innerText()).replace(/\s+/g, " ")}`);
  expect(
    questionAfter,
    "a refresh did not restore the question the student was on - SPEC Phase 11's own 'done when'",
  ).toBe(questionBefore);
});
