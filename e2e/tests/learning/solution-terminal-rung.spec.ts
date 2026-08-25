/**
 * The other terminal rung. D-370 closed the roadmap's last engineering clause with a ✅ whose
 * own body says the **solution** rung has no e2e coverage - `video-intervention.spec.ts`
 * covers one of the two rungs that close the pause, and its comment names exactly this gap
 * ("hint 3 / any solution / any video close the pause"). This is the other one.
 *
 * **What was already here and why it is not this.** `assistance-panel-probe.spec.ts` clicks
 * "Show the solution" - and asserts that a panel became visible and counts its steps into an
 * audit note. That is a *capture probe*: it proves the screen is reachable, not that the rung
 * honours its contract. Nothing anywhere asserted that the pause closes, that the help is
 * still standing a second later, that the walk can go on, or that the attempt stops counting
 * as independent. Four claims, none of them held.
 *
 * ### The contract asserted here (SPEC §5.11.3-§5.11.7, D-207, D-358)
 *
 * 1. **The authored solution renders**, not a generated placeholder. D-207 serves the
 *    template's stored `canonical_solution` - 0 ms, 0 cost, no model call - so this rung is
 *    deterministic in *both* lanes rather than only under `MockBedrockProvider`.
 * 2. **The pause is closed.** A solution is terminal: `intervention_choice` returns
 *    `hint_ladder_awaiting_choice=False` and the panel must therefore offer the terminal
 *    dismiss and *no* further rung. The help stays on screen while the pause is shut - the
 *    exact state D-358 added a channel for, and the one where a deferred narrative frame used
 *    to erase a student's paid help (D-356/D-381).
 * 3. **The walk goes on.** The retry is served, the student can answer it, and the server
 *    takes that answer - no 409, no 500, no reopening of the pause that was just spent.
 * 4. **The attempt stops counting as independent**, where a student can see it. §5.11.5 says
 *    a later correct answer becomes `correct_after_solution` and never counts toward
 *    independent mastery; the dashboard's "Solved without help" is where that reaches a
 *    reader, so that is where it is read. See the block on it below for what this can and
 *    cannot prove from a browser.
 *
 * ### Why the "authored" check is not a step count, which is what it looks like it should be
 *
 * The obvious discriminator is that D-207's authored solutions are five or six steps and the
 * generated fallback is two. **Measured over the served bank, that is not safe**: the 73
 * authored `linear_equations` templates carry 2-8 steps, and **one of them has exactly two**.
 * A `steps > 2` assertion would fail on a correct build for 1 item in 73 - a 1.4% flake with
 * no defect behind it, on a walk that costs four minutes.
 *
 * So the placeholder is identified by *its own signature* instead, which is exact rather than
 * statistical. `MockBedrockProvider._solution_json` emits a fixed second step ("Apply the
 * skill's standard method to isolate the answer.") and sets `final_answer` to
 * `selected_answer` - **the wrong option the student just picked**. Both are asserted absent.
 * The second is the stronger of the two and holds against a real model as well as the mock: a
 * solution that reveals the student's own wrong answer as the answer is a defect in either
 * lane. The step count is recorded as a measurement (D-100's rule, the posture
 * `video-intervention.spec.ts` takes on video availability) rather than thresholded.
 *
 * ### Both lanes, by construction
 *
 * Nothing here branches on `TARGET`. The rung is free and deterministic on both (D-207), the
 * fixture student is seeded in both, and the dashboard read uses the same deep link
 * `dashboard-chart-labels.spec.ts` established. The staging execution is UD-2's to authorise;
 * this file is verified in the local lane only and needs no edit to run in the other.
 */

import type { Page } from "@playwright/test";

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";
import {
  answerCurrentQuestion,
  answerWholeExam,
  chooseTopic,
  currentPhase,
  finalizeExam,
  settleToInteractiveScreen,
  stableClick,
  startSession,
} from "../../fixtures/learning-flow";

test.describe.configure({ timeout: 300_000 });

/** The question currently on screen, or "" when no question card is up. */
async function currentStem(page: Page): Promise<string> {
  return page
    .locator("h1.question-stem")
    .first()
    .innerText()
    .catch(() => "");
}

test("the solution rung reveals the authored solution, closes the pause, and the walk goes on", async ({
  page,
  audit,
}) => {
  // The same known-defect allowance as the sibling ladder specs, **scoped by path** (D-355):
  // finalizing an exam emits a burst of 409s on the overview and item-time endpoints
  // (AUD-F-02). Deliberately *not* the bare `"Failed to load resource"` string - a 409 on
  // `POST /answers` is the one failure contract point 3 exists to detect, and an unscoped
  // allowance forgives it everywhere.
  audit.allow({
    statuses: [409],
    consoleErrors: [
      { text: "Failed to load resource", url: /\/exam\/(overview|items\/[^/]+\/time)/ },
    ],
  });

  // Its own student (M3-D370-SOLUTION-RUNG, following D-443). This spec creates a learning
  // session, finalizes an exam and spends an intervention, and the journeys mutate shared
  // per-student Postgres and MySQL state through one seeded account - so a spec sharing that
  // account picks up whatever the previous one left behind. `FIXTURES` in config.ts has the
  // measurement, and says why this is not `studentAssistance` even though both take the
  // solution.
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentSolution);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);

  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });
  const preAnswers = await answerWholeExam(page);
  audit.note(`pre-exam answers submitted: ${preAnswers}`);
  await finalizeExam(page);
  await settleToInteractiveScreen(page);
  await expect(page.locator(".phase-chip")).toHaveText(/study/i, { timeout: 120_000 });

  // Answer until the graph pauses on `intervention_choice`. Identical in shape to
  // `video-intervention.spec.ts`'s loop on purpose - the difference between the two specs is
  // which button gets clicked, and keeping everything before that the same is what makes the
  // pair comparable.
  //
  // `optionIndex: i` cycles the choice across questions (D-310). The ladder only opens on a
  // **wrong** answer, and with a fixed first-option choice this walk would depend on option A
  // happening to be wrong for some served item - an accident of the stored option order that
  // D-302 has already broken once.
  const menu = page.getByRole("heading", { name: /want a hand/i });
  const refused: string[] = [];
  let studyAnswers = 0;
  let reached = false;
  for (let i = 0; i < 30 && !reached; i += 1) {
    await settleToInteractiveScreen(page);
    if ((await menu.count()) > 0) {
      reached = true;
      break;
    }
    const phase = await currentPhase(page);
    if (phase && /post[-_]exam/i.test(phase)) break;

    const stemBefore = await currentStem(page);
    if (
      !(await answerCurrentQuestion(page, {
        optionIndex: i,
        awaitAcceptance: true,
        onRefused: (status, url) => refused.push(`${status} ${url}`),
      }))
    ) {
      await page.waitForTimeout(500);
      continue;
    }
    studyAnswers += 1;
    // **Wait for the screen to move on before answering again** (D-365). A *correct* answer
    // opens no pause, so nothing else in this loop makes it wait: the next iteration would
    // answer whatever was still rendered - the same item - and the server replies
    // `409 item ... has already been answered`, which the path-scoped allowance above
    // deliberately does not forgive. Either signal means the screen moved: a new question, or
    // the pause a wrong answer opens.
    await expect
      .poll(
        async () => (await menu.count()) > 0 || (await currentStem(page)) !== stemBefore,
        { timeout: 15_000 },
      )
      .toBeTruthy()
      .catch(() => undefined);
  }
  audit.note(`study answers before the pause: ${studyAnswers}, pause reached: ${reached}`);
  // A skip here is honest rather than a pass: every answer was correct, so no menu ever
  // opened and there was no solution rung to take. Cycling the option index makes that
  // outcome very unlikely (it needs the walk to be lucky on every skill in the phase) but not
  // impossible, and the same reasoning made `video-intervention.spec.ts` skip rather than
  // tick. Recorded either way in the note above, so "it ran" is a fact in the artifact.
  test.skip(!reached, "no intervention menu opened in this run (every answer was correct)");

  // The question the help is about, read off the locked card the server names
  // (`snapshot.assistance_question`, D-272), together with the wrong option the student
  // picked. That option text is the placeholder's own `final_answer`, which is what makes the
  // assertion further down a real discriminator rather than a shape check.
  const solvedStem = await currentStem(page);
  const chosenOption = await page
    .locator(".option.locked.chosen .option-text")
    .first()
    .innerText()
    .catch(() => "");
  audit.note(`the student's wrong pick: ${JSON.stringify(chosenOption)}`);

  // **The click no other spec asserts on.**
  await stableClick(page.getByRole("button", { name: /show the solution/i }));

  // **Wait for the solution *result*, not for "a panel"** - the mistake
  // `video-intervention.spec.ts` records having made and caught by reading its own artifact.
  // `.intervention-panel` is already on screen (it is the chooser), so waiting on it asserts
  // nothing. `<h2>Solution</h2>` in `.intervention-head` is rendered only by
  // `SolutionContent`, so this fails if the click does nothing.
  const panel = page.locator(".intervention-panel");
  const solutionHeading = page.getByRole("heading", { name: /^solution$/i });
  const resolved = await solutionHeading
    .waitFor({ state: "visible", timeout: 30_000 })
    .then(() => true)
    .catch(() => false);
  if (!resolved) {
    audit.note(
      "D-356/D-381 shape: the solution panel never appeared or was erased after /respond " +
        "returned it - check for a deferred stage_narrative frame published after the " +
        "solution choice, and for `help_is_on_screen` no longer covering the terminal rungs",
    );
  }
  expect(
    resolved,
    "clicking 'Show the solution' never produced the solution result screen. A solution is a " +
      "TERMINAL rung: it closes the pause, so `intervention` alone holds the panel up and a " +
      "snapshot that omits it wipes the help the student just spent their one intervention " +
      "on. That is the D-356 mechanism, fixed by D-358/D-381's `help_is_on_screen`",
  ).toBe(true);

  // ---- Contract point 1: the authored solution renders -----------------------------------

  const stepCount = await panel.locator(".solution-step").count();
  const explanations = await panel.locator(".solution-step .step-explanation").allInnerTexts();
  const finalAnswer = (await panel.locator(".solution-answer strong").innerText()).trim();
  audit.note(
    `solution rendered: ${stepCount} steps, final answer ${JSON.stringify(finalAnswer)}`,
  );

  expect(stepCount, "the solution panel rendered no steps at all").toBeGreaterThan(0);
  expect(
    explanations.filter((text) => text.trim().length === 0),
    "a solution step rendered with no explanation - a numbered card with nothing in it",
  ).toEqual([]);
  // Revealing the answer is the whole point of this rung (§5.11.5), so an empty one is worse
  // than a missing panel: the student has spent their intervention and been told nothing.
  expect(finalAnswer.length, "the solution rendered without a final answer").toBeGreaterThan(0);

  const panelText = await panel.innerText();
  // The generated placeholder's fixed second step. See the header for why this, and not a
  // step count, is the discriminator.
  expect(
    panelText,
    "the panel served the GENERATED two-step placeholder, not the template's stored " +
      "`canonical_solution`. D-207 prefers the authored solution because it was reviewed " +
      "before approval and costs nothing to serve; falling back to generation here means " +
      "either the template lost its solution or `tutor.stored_solution` rejected it",
  ).not.toMatch(/apply the skill's standard method to isolate the answer/i);
  if (chosenOption.trim().length > 0) {
    // `_solution_json` sets `final_answer` to the *selected* answer, so this is the same
    // placeholder check from the other side - and it stays meaningful against a real model,
    // where a "solution" that endorses the student's wrong option is a defect outright.
    expect(
      finalAnswer.toLowerCase(),
      "the revealed answer is the wrong option the student just chose - either the generated " +
        "placeholder is being served (it echoes `selected_answer`) or the solution is wrong",
    ).not.toBe(chosenOption.trim().toLowerCase());
  }
  // D-272's self-explanation prompt is part of what this rung shows, is rendered client-side,
  // and is the one thing on the panel that asks the student to do something with what they
  // just read. Cheap to hold, and its absence would be a silent regression.
  await expect(
    panel.locator(".self-explain"),
    "the worked solution rendered without the self-explanation prompt (D-272)",
  ).toBeVisible();

  // ---- Contract point 2: the pause is CLOSED ---------------------------------------------
  //
  // `hint_ladder_awaiting_choice` is false at every terminal rung, and `HelpView` reads that
  // as "offer the dismiss, not another round". So the assertion is two-sided: the terminal
  // dismiss is present, and every rung button is gone. A build that left the ladder open here
  // would offer a second paid intervention on an attempt whose outcome is already
  // `answer_revealed` - the student cannot get back to independent from here, and the UI must
  // not imply otherwise.
  await expect(
    panel.getByRole("button", { name: /got it/i }),
    "the terminal rung did not offer the way out ('Got it — next question')",
  ).toBeVisible();
  for (const [name, rung] of [
    ["a hint", /get a hint|next hint/i],
    ["the solution again", /show the solution/i],
    ["a video", /watch a video/i],
    ["the mid-ladder retry", /i'll try again now/i],
  ] as const) {
    await expect(
      panel.getByRole("button", { name: rung }),
      `the solution rung still offered ${name}, so the pause did not close - a solution is ` +
        "terminal (SPEC §5.11.5): the outcome is already `answer_revealed` and no further " +
        "rung can change that",
    ).toHaveCount(0);
  }

  // ---- Contract point 3: the walk goes on ------------------------------------------------

  await stableClick(panel.getByRole("button", { name: /got it/i }));
  await expect(
    page.locator(".solution-steps"),
    "'Got it — next question' left the solution on screen",
  ).toHaveCount(0, { timeout: 30_000 });
  await settleToInteractiveScreen(page);

  // The pause that was just spent must not reopen on its own. A *new* pause after the retry
  // answer below is legitimate (a second wrong answer earns its own ladder round); a chooser
  // standing here, before any new answer, would mean the intervention was spent on nothing.
  await expect(
    menu,
    "the intervention chooser reopened after the solution without a new answer - the pause " +
      "the student spent their one intervention on was re-served",
  ).toHaveCount(0);

  const retryStem = await currentStem(page);
  audit.note(`retry served: ${retryStem !== solvedStem ? "a new question" : "the same stem"}`);
  expect(
    retryStem.length,
    "no question was served after the solution was dismissed - the study flow stopped at the " +
      "terminal rung instead of running §5.11.7's retry ladder",
  ).toBeGreaterThan(0);

  const acceptedRetry = await answerCurrentQuestion(page, {
    optionIndex: 1,
    awaitAcceptance: true,
    onRefused: (status, url) => refused.push(`${status} ${url}`),
  });
  expect(
    acceptedRetry,
    "the server never graded the answer given after the solution. A refused submission here " +
      "is a study answer the student believes they gave and the server never took",
  ).toBe(true);
  // The screen has to move on afterwards, by one of the three legitimate routes: another
  // question, a fresh pause (this answer was wrong too), or the post-exam.
  const advanced = await expect
    .poll(
      async () => {
        if ((await menu.count()) > 0) return true;
        const phase = await currentPhase(page);
        if (phase && /post[-_]exam/i.test(phase)) return true;
        return (await currentStem(page)) !== retryStem;
      },
      { timeout: 30_000 },
    )
    .toBeTruthy()
    .then(() => true)
    .catch(() => false);
  expect(
    advanced,
    "the study phase did not move on after the post-solution answer was graded - the walk is " +
      "stuck on the question the solution was about",
  ).toBe(true);

  // Asserted after the walk rather than inside the loop, so the message can name every
  // refusal at once. Scoped to `POST /answers` by construction: `onRefused` only fires there.
  expect(
    refused,
    `the server refused ${refused.length} answer submission(s) during this walk ` +
      `(${refused.join(", ")}). Each one is an answer the student gave and the server never ` +
      "graded (D-355)",
  ).toEqual([]);

  // ---- Contract point 4: the attempt stops counting as independent ------------------------
  //
  // **The either/or in the task's Intended Behavior, resolved by reading learning-web.**
  // `ResultsScreen` has a "Solutions viewed" counter and `StudentDashboardScreen` has both a
  // "Support usage" breakdown and a "Solved without help" share - so a student-visible
  // surface *does* distinguish independent from after-solution outcomes, and no backend probe
  // is needed. The dashboard is the one reachable without finishing the whole session, and
  // the deep link is the one `dashboard-chart-labels.spec.ts` established ("View progress
  // dashboard" lives on `StartScreen`, which does not render while a session is in flight).
  //
  // **What this can prove and what it cannot.** `independent_count` counts study attempts
  // with none of hint/solution/video set, so the attempt that took the solution is excluded
  // by construction and the share must be under 100%. It cannot prove *which* attempt was
  // excluded - the bar chart renders its counts as SVG rectangles with no text - so the
  // legend is checked for the Solution series and the share for the exclusion, and that pair
  // is stated here rather than dressed up as more than it is. This walk never takes a hint or
  // a video, so a solution is the only thing that can have moved the number.
  await page.goto(`${LEARNING_WEB}/dashboard`);
  await expect(page.getByRole("heading", { name: /progress dashboard/i })).toBeVisible({
    timeout: 60_000,
  });

  const independence = page
    .locator(".stat")
    .filter({ hasText: /solved without help/i })
    .locator(".stat-value");
  const independenceText = (await independence.innerText()).trim();
  audit.note(`dashboard "Solved without help": ${independenceText}`);
  // "—" is the no-attempts placeholder. Reaching it after a study walk would mean the
  // dashboard cannot see the attempts that were just made, which is a different defect and
  // must not read as a pass.
  expect(
    independenceText,
    "the dashboard shows no independence figure at all after a study walk - its window does " +
      "not contain the attempts this walk just made",
  ).not.toBe("—");
  const independencePct = Number(independenceText.replace("%", ""));
  expect(Number.isFinite(independencePct), `unparseable share ${independenceText}`).toBe(true);
  expect(
    independencePct,
    "every study attempt counted as solved without help, including the one that was shown " +
      "the worked solution. SPEC §5.11.5: a solution-assisted attempt never counts toward " +
      "independent mastery, and this is where a student and a parent read that",
  ).toBeLessThan(100);

  const usage = page
    .locator("section.chart-section")
    .filter({ hasText: /support usage/i });
  await expect(usage, "the dashboard has no support-usage section").toBeVisible();
  await expect(
    usage.locator(".chart-empty"),
    "the support-usage chart reported no study attempts in range, after a walk that made some",
  ).toHaveCount(0);
  await expect(
    usage.locator(".recharts-legend-item-text").filter({ hasText: /^Solution$/ }),
    "the support-usage breakdown does not name Solution as its own series, so nothing on " +
      "this screen separates solution-assisted work from independent work",
  ).toBeVisible({ timeout: 30_000 });
});
