/**
 * The terminal walk: sign in → pre-exam → study → post-exam → **the results screen**.
 *
 * **This closes the first of the three coverage gaps the 2026-08-17 live audit named, and it
 * is the one that had survived longest.** No walk in this project's history — automated or
 * manual — had ever reached the post-exam results screen. Every number and sentence on it
 * (`ResultsScreen.tsx`) shipped, was reworded twice on the strength of code review, and had
 * never been rendered by anything that checks it. `journey-student.spec.ts:28-44` states the
 * boundary explicitly and gives a reason.
 *
 * **That stated reason is wrong, and measuring it is what made this spec possible.** It says
 * the study phase "never reaches the mastery bar" because the walk always answers first-option
 * and is therefore usually wrong. But a wrong answer does not stall a skill line: after
 * `study_outcomes.MAX_ATTEMPTS_PER_SKILL = 4` attempts, `ladder_step` returns `exhausted`,
 * `advance_study` labels the line `unresolved`, and `_serve_next_base_or_complete` moves to the
 * next of `study_plan.BASE_PROBLEM_COUNT = 5` target skills. Five lines × four attempts is a
 * hard upper bound of 20 study answers before the post-exam is built, whatever the student
 * does. The real blocker was `journey-student`'s 12-iteration loop cap, and a wrong answer
 * spends two iterations (answer, then clear the pause it opened) — so that walk could reach
 * ~6 answers, not 20. A bound, not a bar.
 *
 * So this spec is deliberately *not* an attempt to answer correctly. It answers like a student
 * who is struggling, works every pause, and arrives at the results screen by exhaustion, which
 * is a real path — `AttendanceStatus.UNKNOWN` being routine is the same kind of fact — and the
 * only one available to a browser that cannot see the correct option.
 *
 * What it checks, and why each one is worth the wall clock:
 *
 * 1. **The rendered numbers against the server's own `learning_gain`.** Not "a number
 *    appears": the exact values, read off the payload the screen was given.
 * 2. **The "up from" clause in both directions.** Present when the post-exam score is higher,
 *    absent when it is not. Scoring one direction only is how a gate passes for the wrong
 *    reason (D-221).
 * 3. **All three assistance counters against what the server actually served.** These had no
 *    live evidence at all, because `clearInterventionIfPresent` hard-coded "hint" until today.
 *    The defect class is not hypothetical: this screen once reported "Videos watched: 1" for a
 *    video that was only ever *displayed*, and the same counts reach the parent report.
 * 4. **No internal skill id on screen.** `unresolved_skills` is a list of internal ids and the
 *    screen must render only their count (CLAUDE.md rule 10). Asserted against the ids the
 *    payload actually carried, so it cannot pass by the list being empty.
 * 5. **The student's own dashboard**, reached from this screen's own button — another surface
 *    the audit lists as never exercised, and free once we are standing here.
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
  finalizeExam,
  settleToInteractiveScreen,
  startSession,
  type LadderRung,
} from "../../fixtures/learning-flow";

/**
 * 40 graded submissions plus ~20 ladder rounds against a real graph, and on staging every
 * rung is a real Bedrock call. `journey-student` budgets 300s for the first half of this;
 * measured locally at 3m40s on first run (see PROGRESS), so 900s is roughly 4× headroom
 * rather than a number picked to be large.
 */
test.describe.configure({ timeout: 900_000 });

/** Rotated across pauses so all three counters move. */
const RUNGS: LadderRung[] = ["hint", "solution", "video"];

interface Gain {
  pre_raw_score: number;
  post_raw_score: number;
  independent_correct_rate: number;
  hint_dependency: number;
  solution_dependency: number;
  unresolved_skills: string[];
}

test("a student walks all the way to the results screen (the V1 coverage gap)", async ({
  page,
  audit,
}) => {
  // Same allowance as `journey-student`, same reason and same narrow scope: AUD-F-02's
  // post-finalize 409 burst on two named paths, and nothing else. This walk finalizes
  // **twice**, so it meets that burst twice.
  audit.allow({
    statuses: [409],
    consoleErrors: [
      { text: "Failed to load resource", url: /\/exam\/(overview|items\/[^/]+\/time)/ },
    ],
  });

  /**
   * The server's own view, collected from the wire rather than recomputed here.
   *
   * `learning_gain` arrives on the `POST /answers` that completes the post-exam and on every
   * snapshot after it, so the last one seen is the one the screen was rendered from. Kept as
   * the whole object: several assertions below need different fields of the *same* payload,
   * and reading them from two different responses would let a mismatch hide.
   */
  let gain: Gain | null = null;
  /**
   * What the server actually served for each rung the walk chose.
   *
   * Counted from `POST /respond`, which carries the intervention synchronously
   * (`nodes.intervention_choice` builds it in the request; the personalizer only *refines* a
   * later SSE snapshot). The video rule is stated here as the product rule it comes from —
   * *a video with no `video_url` served nothing and must not be counted* — rather than by
   * re-using the app's own expression of it. A test that re-implements the predicate it is
   * checking cannot fail when the predicate is wrong, which is the AUD-F-12 trap this suite
   * refuses everywhere else.
   */
  const served: Record<LadderRung, number> = { hint: 0, solution: 0, video: 0 };
  let videosOfferedWithNoVideo = 0;

  /**
   * Every submission the **server accepted**, which is the only honest unit for "how many
   * items did this exam have" (D-288).
   *
   * **Measured on this spec's own first run**, and it is why this counter exists rather than
   * `answerWholeExam`'s return value: the post-exam took **10** accepted `POST /answers`
   * (t=14935…16236, all 200, and the question navigator showed all ten "answered, locked")
   * while `answerWholeExam` returned **9**. `answerCurrentQuestion` reports success from
   * `stableClick(submit)`, so a click that lands and whose element then detaches under the
   * post-click check is counted as a failure — the submission happened, the helper says it
   * did not, and the walk ends one item short of a complete exam it in fact completed.
   *
   * That is a precision limit of the shared helper, not a product defect, and fixing it there
   * would change every caller's meaning. Counting acknowledgements here costs one listener and
   * makes the assertion say what it means.
   */
  /**
   * Accepted submissions **bucketed by what the server said the answer was**, not by when this
   * listener happened to run.
   *
   * **A plain running total failed on staging and passed locally three times, which is the
   * signature of a listener-ordering race rather than a defect.** The measurement: the post-exam
   * navigator showed all ten items "answered, locked" while the post-exam bucket held **9**. The
   * study loop exits when `serverPhase` reaches `post_exam`, and `serverPhase` is set from a
   * `response` listener — so when the listener ran *after* `answerCurrentQuestion`'s own
   * `waitForResponse` resolved, the loop read a stale phase, answered the post-exam's first
   * question, and that acceptance landed in the study side of a before/after subtraction. Extra
   * latency makes the window wider, which is why the local runs never saw it.
   *
   * **The discriminator is `is_correct`, and my first attempt at it was wrong in a way worth
   * keeping written down.** I bucketed on `items == null`, reasoning from
   * `_submit_post_exam_answer`'s `AnswerResult(items=None)` (flow.py:965-967) — and the *wire* says
   * otherwise, because the router fills `items` from `result["last_items"]`, which is graph state
   * that survives from the last serving (sessions.py:1364). Result on staging: `{pre_exam: 10,
   * study: 24}` and **zero** post-exam answers. Reasoning from the raiser instead of the response
   * is the exact mistake this session's own ARCHITECTURE invariant is about, made while writing it.
   *
   * `is_correct` is the field that actually carries the phase: D-064 withholds correctness for a
   * pre/post-exam answer, masked by the phase the answer was **submitted** in (sessions.py:1363),
   * so an exam answer is `null` and a study answer is a real bool. `journey-student.spec.ts` states
   * this already — *"`is_correct` is the phase filter, not just the verdict"* — and it handles the
   * transition cleanly: the study answer that builds the post-exam was submitted in `study`, so it
   * is a bool and lands in the study bucket even though its `phase` reads `post_exam`.
   */
  const acceptedByPhase = new Map<string, number>();
  page.on("response", async (response) => {
    if (response.request().method() !== "POST" || !response.url().endsWith("/answers")) return;
    if (response.status() >= 300) return;
    try {
      const body = (await response.json()) as { phase?: unknown; is_correct?: unknown };
      const phase = typeof body.phase === "string" ? body.phase : "(unknown)";
      // A real bool means the server graded it as a study answer, whatever phase it reports.
      const key = typeof body.is_correct === "boolean" ? "study" : phase;
      acceptedByPhase.set(key, (acceptedByPhase.get(key) ?? 0) + 1);
    } catch {
      acceptedByPhase.set("(unparsed)", (acceptedByPhase.get("(unparsed)") ?? 0) + 1);
    }
  });
  const accepted = (phase: string) => acceptedByPhase.get(phase) ?? 0;

  page.on("response", async (response) => {
    if (response.status() >= 300) return;
    const url = response.url();
    const isRespond = response.request().method() === "POST" && url.endsWith("/respond");
    if (!isRespond && !url.includes("/learning/")) return;
    try {
      const body = (await response.json()) as {
        learning_gain?: Gain | null;
        intervention?: { type?: string; video_url?: string | null } | null;
      };
      if (body.learning_gain != null) gain = body.learning_gain;
      if (!isRespond) return;
      const help = body.intervention;
      if (help?.type === "hint" || help?.type === "solution") {
        served[help.type] += 1;
      } else if (help?.type === "video") {
        if (help.video_url) served.video += 1;
        else videosOfferedWithNoVideo += 1;
      }
    } catch {
      // Not JSON, or a stream. Silence keeps the counters honest; it cannot invent one.
    }
  });

  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentTerminal);
  await expectNotBlank(page);
  await startSession(page);
  await expectNotStuck(page, "Connecting…");
  await settleToInteractiveScreen(page);
  await chooseTopic(page);

  // ---- pre-exam -----------------------------------------------------------------------
  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });
  const preReported = await answerWholeExam(page);
  // Bounded wait: the last click's response can still be in flight when the helper returns.
  await expect
    .poll(() => accepted("pre_exam"), { timeout: 15_000 })
    .toBeGreaterThanOrEqual(10)
    .catch(() => undefined);
  audit.note(`pre-exam: ${accepted("pre_exam")} accepted (helper reported ${preReported})`);
  expect(accepted("pre_exam"), "the pre-exam is SPEC §5.9.2's fixed 10-item set").toBe(10);
  await finalizeExam(page);

  // ---- study --------------------------------------------------------------------------
  await settleToInteractiveScreen(page);
  await expect
    .poll(async () => currentPhase(page), { timeout: 60_000 })
    .toMatch(/study|post-exam/i);

  // The server's phase, never the chip: the chip lags a phase change and renders behind a
  // modal, which is the signal D-321 and D-340 were both burned by.
  let serverPhase: string | null = null;
  const refused: string[] = [];
  page.on("response", async (response) => {
    if (response.request().method() !== "POST" || !response.url().endsWith("/answers")) return;
    if (response.status() >= 300) {
      refused.push(`${response.status()} ${new URL(response.url()).pathname}`);
      audit.note(`answer REFUSED: ${response.status()} ${await response.text().catch(() => "")}`);
      return;
    }
    try {
      const body = (await response.json()) as { phase?: unknown };
      if (typeof body.phase === "string") serverPhase = body.phase;
    } catch {
      // Nothing to record.
    }
  });

  // **The bound is arithmetic, not a guess** (see the header): 5 skill lines × 4 attempts,
  // and a wrong answer costs a second iteration to clear the pause it opened. 60 leaves room
  // for the stage narrative and for a line that resolves early by a lucky first option,
  // without ever becoming an open-ended loop.
  let studyAnswers = 0;
  let pauses = 0;
  for (let i = 0; i < 60; i += 1) {
    await settleToInteractiveScreen(page);
    const phase = serverPhase ?? (await currentPhase(page));
    if (phase && /post[-_]exam/i.test(phase)) break;

    // Rotate the rung so every counter on the results screen has something to be checked
    // against. `pauses` rather than `i`, so the rotation follows pauses actually worked.
    const rung = RUNGS[pauses % RUNGS.length];
    if (await clearInterventionIfPresent(page, (m) => audit.note(`i=${i} ${m}`), rung)) {
      pauses += 1;
      continue;
    }

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
    // Wait for the screen to move before answering again (D-365): a correct answer opens no
    // pause, and without this the next iteration re-answers the same item and takes a 409.
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
  audit.note(
    `study: ${studyAnswers} answers, ${pauses} pauses worked, ` +
      `served hint=${served.hint} solution=${served.solution} video=${served.video} ` +
      `(videos with no catalog entry: ${videosOfferedWithNoVideo}), refused=${refused.length}`,
  );

  // A refused submission is a product finding in its own right, and asserted *before* the
  // phase check below because it explains it: a walk that never left the study phase because
  // the server rejected its answers must not be reported as "the study phase never ended".
  expect(
    refused,
    `the server refused ${refused.length} submission(s) (${refused.join(", ")})`,
  ).toEqual([]);

  expect(
    serverPhase,
    `after ${studyAnswers} study answers and ${pauses} ladder pauses the session was still ` +
      `in "${serverPhase}". The study phase has a hard bound — 5 target skills × 4 attempts ` +
      "before `ladder_step` returns `exhausted` — so not reaching the post-exam inside 60 " +
      "iterations means a skill line stopped resolving, which is a §5.11.7 defect and not a " +
      "harness limit. Read the `i=` notes for the last pause worked",
  ).toMatch(/post[-_]exam/i);

  // ---- post-exam ----------------------------------------------------------------------
  await settleToInteractiveScreen(page);
  await expect(page.locator(".phase-chip")).toHaveText(/post-exam/i, { timeout: 60_000 });
  const postReported = await answerWholeExam(page);
  await expect
    .poll(() => accepted("post_exam"), { timeout: 15_000 })
    .toBeGreaterThanOrEqual(10)
    .catch(() => undefined);
  audit.note(
    `post-exam: ${accepted("post_exam")} accepted (helper reported ${postReported}); ` +
      `all buckets ${JSON.stringify(Object.fromEntries(acceptedByPhase))}`,
  );
  expect(accepted("post_exam"), "the post-exam is §5.13.1's parallel-form 10-item set").toBe(10);
  await finalizeExam(page);

  // ---- the results screen, at last ----------------------------------------------------
  await settleToInteractiveScreen(page);
  await expect(
    page.getByRole("heading", { name: /nice work today/i }),
    "the post-exam finalized but the results screen never rendered — the first thing any " +
      "walk in this project has ever asked of it",
  ).toBeVisible({ timeout: 60_000 });
  await expectNotBlank(page);

  // Every assertion below reads this one payload. Skipping rather than passing if it never
  // arrived: the screen renders only when `snapshot.learning_gain` is present (App.tsx:654),
  // so "no payload seen" means this harness missed it, and a green tick would claim the
  // numbers were checked when nothing was compared.
  const observed: Gain | null = gain;
  test.skip(
    observed === null,
    "no `learning_gain` payload was observed on the wire, so there is nothing to compare the " +
      "rendered numbers against and this run says nothing about them either way",
  );
  // The double assertion is TypeScript's, not a claim of mine: `gain` is only ever written
  // inside the `response` listener, so control-flow analysis narrows it to `null` at every read
  // in this function body. `test.skip` above is what actually establishes it is not null.
  const g = observed as unknown as Gain;
  audit.note(
    `learning_gain: pre=${g.pre_raw_score} post=${g.post_raw_score} ` +
      `independent=${g.independent_correct_rate} hintDep=${g.hint_dependency} ` +
      `solutionDep=${g.solution_dependency} unresolved=${g.unresolved_skills.length}`,
  );

  const stat = (label: RegExp) =>
    page.locator(".stat", { has: page.locator(".stat-label", { hasText: label }) });

  await expect(stat(/^pre-exam$/i).locator(".stat-value")).toHaveText(String(g.pre_raw_score));
  await expect(stat(/^post-exam$/i).locator(".stat-value")).toHaveText(String(g.post_raw_score));
  await expect(stat(/solved independently/i).locator(".stat-value")).toHaveText(
    `${Math.round(g.independent_correct_rate * 100)}%`,
  );

  // **Both directions.** The "up from" clause is conditional on an improvement, so a run
  // where the student did not improve must *not* show it — and this walk answers first-option
  // throughout, so the no-improvement branch is the likely one. Asserting only the positive
  // case would leave the branch that actually renders here unchecked.
  const subtitle = page.locator("p.subtitle");
  await expect(subtitle).toContainText(`You scored ${g.post_raw_score} out of 10`);
  if (g.post_raw_score > g.pre_raw_score) {
    await expect(subtitle, "the score improved and the screen did not say so").toContainText(
      `up from ${g.pre_raw_score}`,
    );
  } else {
    await expect(
      subtitle,
      `the post-exam score (${g.post_raw_score}) did not beat the pre-exam (${g.pre_raw_score}) ` +
        "and the screen still claimed an improvement",
    ).not.toContainText(/up from/i);
  }

  // The three counters, against what the server served. `videosOfferedWithNoVideo` is
  // excluded from the expectation on purpose and reported separately: a §5.11.6 fallback put
  // help in front of nobody, and counting it is the exact defect that reached the parent
  // report once already.
  await expect(stat(/hints used/i).locator(".stat-value")).toHaveText(String(served.hint));
  await expect(stat(/solutions viewed/i).locator(".stat-value")).toHaveText(
    String(served.solution),
  );
  await expect(
    stat(/videos suggested/i).locator(".stat-value"),
    `the server served ${served.video} video(s) with a catalog entry and offered ` +
      `${videosOfferedWithNoVideo} without one; only the first kind put help on screen`,
  ).toHaveText(String(served.video));

  // A run that spent no rungs at all cannot say whether the counters work, and must not
  // claim to. This is the same stated-skip discipline the ladder assertions use.
  test.skip(
    served.hint + served.solution + served.video === 0,
    `the server served no assistance at all across ${pauses} pause(s), so all three counters ` +
      "were compared against zero and this run says nothing about them",
  );

  // CLAUDE.md rule 10: internal skill ids stay internal. Asserted against the ids this
  // payload actually carried, so an empty list makes it skip rather than silently pass.
  const pageText = (await page.locator(".panel").innerText()).toLowerCase();
  const leaked = g.unresolved_skills.filter((id) => pageText.includes(id.toLowerCase()));
  test.skip(
    g.unresolved_skills.length === 0,
    "the post-exam left no unresolved skills, so there was no internal id that could have " +
      "leaked and this run says nothing about rule 10",
  );
  expect(
    leaked,
    `the results screen printed ${leaked.length} internal skill id(s) to a K-12 student ` +
      `(first: ${JSON.stringify(leaked[0] ?? null)}). The screen is supposed to render only ` +
      "the count and defer names to the dashboard, which resolves them server-side",
  ).toEqual([]);

  // ---- the student's own dashboard, from this screen's own button ---------------------
  // Also on the audit's never-exercised list: the dashboard has no role gating, and every
  // walk that has ever opened it did so as a parent.
  // **This is where the walk earned its wall clock.** On its first pass to this point the
  // button did nothing at all, and the two notes below are what turned "the button is dead"
  // into a mechanism: the dashboard *mounted and fetched*, then the URL went back to
  // `/results/:id`. `view` is derived from `location.pathname`, and the effect that puts a
  // finished session in the URL listed `location.pathname` in its dependencies - so it
  // re-asserted the results URL over every navigation away from it. Fixed in App.tsx with a
  // once-per-session guard; kept measured here rather than described.
  const dashboardFetches: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/learning/students/")) dashboardFetches.push(request.url());
  });
  const pathBefore = await page.evaluate(() => location.pathname);
  await page.getByRole("button", { name: /view progress dashboard/i }).click();
  await expect(
    page.getByRole("heading", { name: /progress dashboard/i }),
    "the results screen's own copy says to see the progress dashboard, and its button did not " +
      "get there",
  ).toBeVisible({ timeout: 60_000 });

  // **And it has to still be there a moment later**, because the failure mode was a bounce
  // rather than a dead click: the first render was fine and a redirect took it away. A poll
  // that only has to be true once cannot see that.
  await page.waitForTimeout(2000);
  const pathAfter = await page.evaluate(() => location.pathname);
  audit.note(
    `dashboard: ${dashboardFetches.length} fetch(es), path ${pathBefore} -> ${pathAfter}`,
  );
  expect(
    pathAfter,
    `the dashboard opened and the URL returned to ${pathAfter} on its own, so the student is ` +
      "back on the results screen without having asked to be",
  ).toContain("dashboard");
  await expect(page.getByRole("heading", { name: /progress dashboard/i })).toBeVisible();
  await expectNotBlank(page);

  // **And back again**, because the round trip is the student's actual path and the fix above
  // changed what the URL says on the way home. The dashboard's Back goes to `/session`, and the
  // redirect no longer fires a second time, so the results screen now renders under `/session`
  // rather than under `/results/:id`. That is a deliberate consequence and not a regression: a
  // reload of `/session` with a completed session in `localStorage` renders the same screen
  // (App.tsx:654), and `/results/:id` remains the bookmarkable form. Asserted so the next person
  // to touch either path sees the trade rather than discovering it.
  await page.getByRole("button", { name: /^back$/i }).click();
  await expect(
    page.getByRole("heading", { name: /nice work today/i }),
    "Back from the dashboard did not return the student to their results",
  ).toBeVisible({ timeout: 30_000 });
  audit.note(`after Back: path ${await page.evaluate(() => location.pathname)}`);
});
