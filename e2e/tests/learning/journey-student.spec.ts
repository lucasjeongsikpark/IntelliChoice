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
  // produced a burst of 409s on `exam/overview` and `exam/items/{id}/time`, each a browser
  // console error. Allowed by path here so this journey still enforces "zero console
  // errors" for everything else - otherwise one known defect would mask every new one.
  //
  // **The "by path" half of that sentence was not true until D-355.** A plain
  // `"Failed to load resource"` string matches the message *text*, and Chromium puts the
  // failing URL in the location instead - so this line forgave every failed request in the
  // walk, on any path, at any status. A 409 on `POST /answers` was therefore invisible
  // twice over: forgiven here, and dropped by the verdict listener below. That is a
  // documented live defect (last-question-double-submit.spec.ts measured one on staging
  // 2026-08-06), and N of them produce exactly the `answered - graded == N` drift D-340
  // could not explain. Scoped to the two AUD-F-02 paths, which is what the comment above
  // always claimed.
  audit.allow({
    statuses: [409],
    consoleErrors: [
      { text: "Failed to load resource", url: /\/exam\/(overview|items\/[^/]+\/time)/ },
    ],
  });
  // **D-325: the study phase must not re-serve a question the exam already asked.**
  //
  // **Attached here, before the pre-exam, and that placement is the whole point (D-325).**
  // The first version sat next to `studyVerdicts` below - i.e. after `answerWholeExam` and
  // `finalizeExam` - so it never saw a pre-exam snapshot and collected `0 pre_exam, 6 study`.
  // The run did not fail: it *skipped*, because the positive control refuses to conclude
  // anything from one empty side. That is the control earning its place, and the reason the two
  // listeners in this file sit deliberately far apart rather than tidied together:
  // `studyVerdicts` must attach LATE so it only ever sees study answers, this one must attach
  // EARLY so it sees both phases. Moving either to match the other breaks it silently.
  //
  // Bucketed by the **server's** `phase` on each snapshot, never by `.phase-chip` - the chip
  // lags and renders behind a modal, which is the signal D-321 and D-324 were both burned by.
  //
  // **And asserted on the rendered stem, not on `question_variant_id`, because the id-based
  // form cannot fail.** ROADMAP U2 asked for "no study item's `question_variant_id` matches
  // any exam item's". A fresh variant row is minted on every serving, so that has always been
  // true and always will be - it would pass against the unfixed build, which is the AUD-F-12
  // false negative this suite refuses everywhere else. What repeats is the *content*:
  // `build_variant_row` sets `rendered_question` to the canonical variant's every time, so two
  // servings of one template are byte-identical. The stem is therefore the only thing worth
  // comparing.
  const stemsByPhase = new Map<string, Set<string>>();
  page.on("response", async (response) => {
    if (response.status() >= 300) return;
    try {
      const body = (await response.json()) as {
        phase?: unknown;
        items?: { rendered_question?: unknown }[] | null;
      };
      if (typeof body.phase !== "string" || !Array.isArray(body.items)) return;
      const bucket = stemsByPhase.get(body.phase) ?? new Set<string>();
      for (const item of body.items) {
        if (typeof item?.rendered_question === "string") bucket.add(item.rendered_question);
      }
      stemsByPhase.set(body.phase, bucket);
    } catch {
      // Not a JSON snapshot - nothing to collect.
    }
  });

  // **Its own student, not `studentPresent`** (D-365 §2). This walk named the isolation
  // finding `config.ts` states - *"two tests signing in as the same student resume each
  // other's exams"* - and was then the last spec still sharing it, with seventeen others.
  // In isolation it runs clean in ~15s; in a whole-suite run it recorded 7 refused
  // submissions and 2.3 minutes, because the session it joined had been left mid-study by
  // whichever spec got there first. D-288 gave the band walks and the refresh test their
  // own students and missed this one.
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentJourney);
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
  // **The phase the *server* last reported, which is what the study loop exits on (D-340).**
  // D-321 diagnosed the drift and added the reconciliation assertion below, but left the loop
  // reading `.phase-chip` - a DOM signal that lags a phase change and renders behind a modal.
  // Measured 2026-08-15 on run 3 of 4 at `7d1bf67`: **8 answers submitted, 4 graded as study**,
  // so the walk answered four post-exam questions believing they were study work.
  let serverPhase: string | null = null;
  // **Every submission the server refused, which nothing recorded before D-355.** The
  // listener below used to `return` on any non-2xx, so a refused answer left no trace at
  // all: not in the verdicts, not in the notes, and not in the teardown check either
  // (the console allowance above forgave it, and `clientErrors` is reported rather than
  // asserted). The drift this walk fails on is measured in exactly those units.
  const refusedAnswers: string[] = [];
  let lastStudyProgressSeen: "present" | "absent" | "(none yet)" = "(none yet)";
  page.on("response", async (response) => {
    if (response.request().method() !== "POST" || !response.url().endsWith("/answers")) return;
    if (response.status() >= 300) {
      const body = await response.text().catch(() => "(body unavailable)");
      refusedAnswers.push(`${response.status()} ${new URL(response.url()).pathname}`);
      audit.note(
        `answer REFUSED by the server: ${response.status()} ${response.url()} - ` +
          body.slice(0, 300),
      );
      return;
    }
    try {
      const body = (await response.json()) as {
        is_correct?: unknown;
        phase?: unknown;
        study_progress?: unknown;
        pending_interrupt?: { interrupt_type?: string } | null;
      };
      // Recorded as evidence, deliberately NOT used to exit the loop. `study_progress` is
      // `None` outside the study phase (D-272), which makes it look like a second
      // server-authoritative "study is over" bit - but `_study_progress` also returns
      // `None` when the study session row is missing or unreadable, so breaking on it
      // would end the walk early for reasons that have nothing to do with the phase. The
      // phase already exits the loop; this only has to explain a drift after the fact.
      lastStudyProgressSeen = body.study_progress == null ? "absent" : "present";
      // **Recorded before the `is_correct` filter, deliberately.** The filter selects *study*
      // answers; the phase is needed from every answer, including the one that ends the study
      // phase - which returns `post_exam` while still being a study answer.
      if (typeof body.phase === "string") serverPhase = body.phase;
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
    // **Exit on the server, not the screen (D-340).** The answer that *completes* the study
    // phase already returns `phase: "post_exam"`, so breaking on it leaks nothing: the walk
    // stops before submitting a single post-exam question. `.phase-chip` is consulted only
    // before any answer has been graded, where no server verdict exists yet - and `post[-_]`
    // matches both spellings, since the wire says `post_exam` and the chip says `post-exam`.
    const phase = serverPhase ?? (await currentPhase(page));
    // Breadcrumb only (D-340): the first attempt at this fix did not hold - two of four runs
    // still drifted - and the guess "the chip lags" cannot explain why the *server* phase failed
    // to stop the loop. Record what each iteration actually saw, so the next run names the
    // mechanism instead of prompting another guess (D-311's standing rule).
    audit.note(
      `study loop i=${i}: serverPhase=${serverPhase ?? "(none yet)"} ` +
        `chip=${serverPhase === null ? await currentPhase(page) : "(not read)"} ` +
        `answered=${studyAnswers} graded=${studyVerdicts.length} ` +
        `refused=${refusedAnswers.length} study_progress=${lastStudyProgressSeen}`,
    );
    if (phase && /post[-_]exam/i.test(phase)) break;
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
    // **`awaitAcceptance` makes `studyAnswers` mean "the server took this answer"** rather
    // than "the two clicks landed" (D-355). Under the old meaning the reconciliation
    // assertion below compared a count of *clicks* against a count of *gradings*, so any
    // refused or unobserved submission looked identical to the walk drifting out of the
    // study phase - the reading D-340 shipped a fix against and then had to retract.
    const stemBefore = await page.locator("h1").innerText().catch(() => "");
    if (
      !(await answerCurrentQuestion(page, {
        optionIndex: i,
        awaitAcceptance: true,
        onRefused: (status, url) => audit.note(`study submission refused: ${status} ${url}`),
      }))
    ) {
      await page.waitForTimeout(1000);
      continue;
    }
    studyAnswers += 1;
    // **Wait for the screen to move on before answering again** (D-365), and this is the
    // root cause of the drift the whole clause was about.
    //
    // A correct answer opens no pause, so nothing in this loop made it wait: the next
    // iteration answered whatever was still rendered, which was the *same item*, and the
    // server replied `409 item ... has already been answered`. Measured on staging with
    // D-355's instrumentation in place: two of them in one walk. Under the old harness each
    // was counted as an answer (clicks, not acceptances), dropped from the verdicts (non-2xx
    // returned early) and forgiven by the console allowance (never path-scoped) - which is
    // **exactly** the `answered - graded == N` signature D-340 could not explain.
    //
    // Either signal means the screen moved: a new question, or the pause the ladder opens on
    // a wrong answer (where re-answering the same item is legitimate and does not 409).
    await expect
      .poll(
        async () => {
          const pauseUp = await page.getByRole("heading", { name: /want a hand/i }).count();
          const stem = await page.locator("h1").innerText().catch(() => "");
          return pauseUp > 0 || stem !== stemBefore;
        },
        { timeout: 15_000 },
      )
      .toBeTruthy()
      .catch(() => undefined);
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

  // **Asserted before the reconciliation guard below, because it explains it.** If the
  // server refused submissions, the drift the guard reports is a *consequence*, and the
  // guard's own message ("the walk carried on past the end of the study phase") would name
  // the wrong cause - which is what happened for two sessions. A refused `POST /answers`
  // is a product finding, not a harness one: `last-question-double-submit.spec.ts` measured
  // a real 409 on staging from a read-only-lock / overview-poll race (2026-08-06).
  expect(
    refusedAnswers,
    `the server refused ${refusedAnswers.length} answer submission(s) during the study ` +
      `loop (${refusedAnswers.join(", ")}). Each one is a study answer the student ` +
      "believes they gave and the server never graded, and it inflates the reconciliation " +
      "drift asserted below without the walk having left the study phase at all (D-355)",
  ).toEqual([]);

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
  //
  // **The mechanism this message used to assert was retracted by D-340 and is not restated
  // here.** In the run that reddened 3-of-4, `serverPhase` stayed `study` across all twelve
  // iterations and the loop exited on the iteration limit - so "the walk carried on past the
  // end of the study phase" was never what happened, and the exit-condition fix shipped for
  // it did not stop the drift. What remains true is only the arithmetic: two counts that
  // should agree do not. D-355 removed the three ways this walk could produce that drift by
  // itself (clicks counted as answers, refusals dropped, refusals forgiven), so a drift that
  // survives all of them is now evidence about the *server*, and the notes above carry the
  // per-iteration state needed to say which.
  expect(
    studyAnswers - studyVerdicts.length,
    `${studyAnswers} submissions were accepted in the study loop but the server graded only ` +
      `${studyVerdicts.length} of them as study answers. Both counts now come from the ` +
      "server (D-355), so this is no longer explainable as the walk miscounting its own " +
      "clicks: read the per-iteration `study loop i=` notes for the phase, the refusal " +
      "count and whether `study_progress` was still present when the two diverged",
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

  // D-325: no question the exam asked may be re-served as study practice.
  const examStems = stemsByPhase.get("pre_exam") ?? new Set<string>();
  const studyStems = stemsByPhase.get("study") ?? new Set<string>();
  const repeated = [...studyStems].filter((stem) => examStems.has(stem));
  audit.note(
    `stems seen: ${examStems.size} pre_exam, ${studyStems.size} study, ` +
      `${repeated.length} repeated`,
  );
  // The positive control, on this suite's standing rule: both loops below iterate over what
  // was collected, so a run that captured no stems on either side would assert nothing and
  // report a pass. Skipping with the counts in hand says "this run did not look", which is a
  // different claim from "this run looked and found nothing".
  test.skip(
    examStems.size === 0 || studyStems.size === 0,
    `collected ${examStems.size} pre-exam and ${studyStems.size} study stems, so there was ` +
      "no pair of phases to compare and this run says nothing either way",
  );
  expect(
    repeated,
    `${repeated.length} study question(s) are byte-identical to a question this session's ` +
      "own pre-exam already asked, so the student practised exactly what they are re-scored " +
      "on and the learning gain the parent report is built from is inflated (D-325). First: " +
      JSON.stringify(repeated[0]?.slice(0, 120) ?? null),
  ).toEqual([]);

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
