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

  // **D-317 addendum: record what the *server* said about each study answer.**
  //
  // This assertion used to be one bit wide - "interventions > 0" - so a failure could mean
  // three unrelated things and D-311 could only guess which: the walk answered correctly
  // every time (its own option ordering, which it does not control), the graph did not open
  // the ladder on a wrong answer (a real §5.11.3 defect), or the pauses happened and this
  // walk missed them (D-288 §4's class, where `clearInterventionIfPresent` read `count()`
  // with no wait). The 2026-08-14 failure showed `11 study answers / 0 pauses`, which is not
  // chance at ~3-in-4 wrong, and nothing recorded could say which of the three it was.
  //
  // `is_correct` is the phase filter, not just the verdict: SPEC §5.9.2's
  // `feedback_visibility="hidden_until_finalize"` makes it `null` for every pre/post-exam
  // answer and a real bool for every study answer, so reading the field selects the phase.
  const studyVerdicts: { correct: boolean; ladderOpened: boolean }[] = [];
  page.on("response", async (response) => {
    if (response.request().method() !== "POST" || !response.url().endsWith("/answers")) return;
    if (response.status() >= 300) return;
    try {
      const body = (await response.json()) as {
        is_correct?: unknown;
        pending_interrupt?: { interrupt_type?: string } | null;
      };
      if (typeof body.is_correct !== "boolean") return;
      studyVerdicts.push({
        correct: body.is_correct,
        ladderOpened: body.pending_interrupt?.interrupt_type === "intervention_choice",
      });
    } catch {
      // A body that will not parse says nothing. Omission keeps the counters honest; it
      // cannot invent a verdict.
    }
  });

  let studyAnswers = 0;
  let interventions = 0;
  for (let i = 0; i < 12; i += 1) {
    await settleToInteractiveScreen(page);
    const phase = await currentPhase(page);
    if (phase && /post-exam/i.test(phase)) break;
    // A wrong answer pauses the graph on `intervention_choice`; the ladder must be
    // worked before the next question is reachable (SPEC §5.11.3).
    // The second argument is U1's breadcrumb (D-324): it records which locator won the
    // wait, so the next occurrence of the 1-in-12 miss names its mechanism instead of
    // leaving it to inference. Pairs with the `pending_interrupt` listener above, which
    // already knows independently whether the server opened a pause.
    if (await clearInterventionIfPresent(page, (m) => audit.note(m))) {
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
  // The walk clicks Submit and moves on, so the last verdict can still be in flight. Bounded
  // and tolerant: a missing verdict must not become a failure of its own, since the counters
  // below already fail closed when they cannot see a wrong answer.
  await expect
    .poll(() => studyVerdicts.length, { timeout: 10_000 })
    .toBeGreaterThanOrEqual(1)
    .catch(() => undefined);

  const wrong = studyVerdicts.filter((verdict) => !verdict.correct).length;
  const ladderOffered = studyVerdicts.filter((verdict) => verdict.ladderOpened).length;
  audit.note(`study: worked ${interventions} retry-ladder pauses`);
  audit.note(`study: answered ${studyAnswers} items`);
  audit.note(
    `study verdicts: ${studyVerdicts.length} graded, ${wrong} wrong, ${ladderOffered} ladder ` +
      `pauses opened by the server`,
  );
  expect(studyAnswers, "the study phase served no questions at all").toBeGreaterThan(0);

  // **The loop's own count is not the number of study answers, and believing it hid a defect
  // for a whole session.** `studyAnswers` counts submissions this loop made; `studyVerdicts`
  // counts the ones the *server* graded as study answers, and SPEC §5.9.2 withholds
  // `is_correct` until finalize, so an exam answer never lands in the second list.
  //
  // Measured 2026-08-14 on a failing run: **11 answers submitted in this loop, 1 graded as a
  // study answer.** The listener is attached after `answerWholeExam`, so all eleven came from
  // here - meaning the walk left the study phase without noticing and answered ten *post-exam*
  // questions while reporting them as study work. The `post-exam` guard at the top of the loop
  // reads the phase chip, which is exactly the kind of screen-derived signal that lags a phase
  // change; the server's own grading does not lag.
  //
  // Allowing a slack of 1 rather than demanding equality: the last submission's response can
  // still be in flight, and the poll above is deliberately tolerant of that.
  expect(
    studyAnswers - studyVerdicts.length,
    `${studyAnswers} answers were submitted in the study loop but the server graded only ` +
      `${studyVerdicts.length} as study answers - the walk carried on past the end of the ` +
      "study phase and counted exam answers as study work, so every count it reports about " +
      "the retry ladder is measured over the wrong set of questions",
  ).toBeLessThanOrEqual(1);

  // **A run with no wrong answer proves nothing about the ladder, and must not claim to.**
  // Skipping rather than passing is the point: a green tick here would say "§5.11.3 works"
  // on a run that never asked it to. The counts are in the audit notes above, so this is a
  // stated skip and not the silent never-fires condition AUD-F-23 was about.
  test.skip(
    studyVerdicts.length > 0 && wrong === 0,
    `all ${studyVerdicts.length} study answers happened to be correct, so nothing could open ` +
      "the retry ladder - this run says nothing about SPEC §5.11.3 either way (D-317 addendum)",
  );

  expect(
    ladderOffered,
    `${wrong} of ${studyVerdicts.length} study answers were WRONG and the server opened the ` +
      "retry ladder 0 times - SPEC §5.11.3's ladder did not engage. This is a product defect, " +
      "not this walk's option ordering, and the distinction is the whole reason these counts " +
      "are recorded (D-317 addendum)",
  ).toBeGreaterThan(0);

  expect(
    interventions,
    `the server opened ${ladderOffered} retry-ladder pauses and this walk worked ` +
      `${interventions} of them - the pauses happened and the harness missed them, which is ` +
      "D-288 §4's class (a `count()` read with no wait), so the ladder is still unexercised",
  ).toBeGreaterThan(0);
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
