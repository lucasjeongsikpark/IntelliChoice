/**
 * Driving the learning app's screens the way a student does.
 *
 * These helpers deliberately click real buttons rather than calling the API: the point
 * of AUD-F is the contract between the two, and every prior session's live findings came
 * from the seam, not from either side alone.
 */

import { expect, type Locator, type Page } from "@playwright/test";

export const PHASE_CHIP = ".phase-chip";

/** The stage-narrative modal. `aria-modal`, and only an explicit Continue closes it. */
export const NARRATIVE_OVERLAY = ".narrative-overlay";

/**
 * Whether the server's last graded answer opened a retry-ladder pause, per page.
 *
 * **Why the harness needs to be told rather than to look** (D-324). `clearInterventionIfPresent`
 * used to race the pause against `.option-text` on the theory that "whichever screen materialises
 * first ends the wait", so a question with no pause would cost nothing. The breadcrumb added in the
 * same session measured what that race actually does: **16 calls, every one resolved in 2-4 ms, with
 * `options=4` present in all 16.** The options of the question just answered are still mounted when
 * the function is called, so the `.or(options)` branch is satisfied immediately and the wait has no
 * capacity to wait. Twelve of the sixteen returned false in ~3 ms; the four that worked a pause were
 * the ones where the pause had *already* arrived. D-288's fix was never waiting for anything.
 *
 * A fixed timeout instead would make every correct answer pay it, which is the cost D-288 was right
 * to avoid. The way out is that the server already says: `POST /answers` carries
 * `pending_interrupt.interrupt_type`, which D-318 was built to read. Recording it here turns "guess
 * from the DOM whether a pause is coming" into "wait only when one is known to be coming, and skip
 * instantly otherwise" - no race, and no timeout on the common path.
 *
 * A `WeakMap` keyed by `Page` so parallel workers and `journey-bands`' four sequential walks cannot
 * read each other's state, and so nothing is retained after a page closes.
 */
const pauseOpenedByLastAnswer = new WeakMap<Page, boolean>();
const answersListenerInstalled = new WeakSet<Page>();

/** SPEC §5.11.3's three ways forward from a wrong answer. */
export type LadderRung = "hint" | "solution" | "video";

/**
 * Quoted from `InterventionScreen.tsx:144-152`, and anchored on the words a student reads
 * rather than on a test id, so a copy change that alters the offer is a failure here rather
 * than a silent no-op.
 */
const RUNG_BUTTON: Record<LadderRung, RegExp> = {
  hint: /get a hint/i,
  solution: /show the solution/i,
  video: /watch a video/i,
};

/** Idempotent: `answerCurrentQuestion` calls this, so every caller gets it without opting in. */
function trackLadderPauses(page: Page): void {
  if (answersListenerInstalled.has(page)) return;
  answersListenerInstalled.add(page);
  page.on("response", async (response) => {
    if (response.request().method() !== "POST" || !response.url().endsWith("/answers")) return;
    if (response.status() >= 300) return;
    try {
      const body = (await response.json()) as {
        pending_interrupt?: { interrupt_type?: string };
      };
      pauseOpenedByLastAnswer.set(
        page,
        body.pending_interrupt?.interrupt_type === "intervention_choice",
      );
    } catch {
      // A body that is not JSON says nothing either way; leave the previous value alone.
    }
  });
}

/**
 * Closes a stage-narrative modal **only when one is actually covering the page**.
 *
 * Deliberately not `dismissNarrativeIfPresent`, for two reasons. It clicks with a raw
 * `click()` rather than `stableClick`, because `stableClick` calls *this* on failure and the
 * pair would recurse without bound. And it is gated on the overlay being present rather than
 * on a `^continue$` button existing anywhere, so it cannot consume a Continue that belongs
 * to some other screen.
 */
async function dismissBlockingNarrative(page: Page): Promise<boolean> {
  if ((await page.locator(NARRATIVE_OVERLAY).count()) === 0) return false;
  const button = page.getByRole("button", { name: /^continue$/i });
  if ((await button.count()) === 0) return false;
  return button
    .first()
    .click({ timeout: 5000 })
    .then(() => true)
    .catch(() => false);
}

/**
 * Clicks through the learning app's re-render churn.
 *
 * Every SSE snapshot re-renders `App`, and several branches *replace* the whole screen
 * (the assistance panel replaces the exam view; the stage narrative used to do the same).
 * Playwright reports the result as "element is not stable" or "element was detached from
 * the DOM" on controls that are visibly present - measured on the topic card, the Submit
 * answer button, and the ladder's own buttons.
 *
 * That churn is AUD-F-05, recorded with measurements in tests/learning/narrative-race.
 * spec.ts. It is absorbed here rather than in each journey so that a *different* defect
 * does not present as this one, and so no journey silently depends on winning a race.
 *
 * **Id corrected 2026-08-04 (D-174), and the citation itself carried the evidence.** This
 * said AUD-F-01, which is the `App.tsx` effect-dependency *refetch burst* - a request-volume
 * defect whose regression test is tests/learning/time-telemetry.spec.ts. The screen-replacing
 * swap described above, measured at ~26 ms in the very file cited on the line, is AUD-F-05.
 *
 * AUD-F-21 removed the largest single source of it - the narrative no longer replaces the
 * screen it arrives over - but the retries stay: the assistance panel and the ladder still
 * swap screens, and a retry that is no longer needed costs one extra locator call while a
 * missing one costs a flaky primary journey.
 */
export async function stableClick(target: Locator, attempts = 4): Promise<boolean> {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      await target.click({ timeout: 5000 });
      return true;
    } catch {
      // Detached or unstable: the app re-rendered under the cursor. Retry.
      //
      // **Or a stage-narrative modal arrived over the top, in which case retrying the same
      // click cannot ever work (D-324).** The overlay is `aria-modal` and closes only on an
      // explicit Continue, so Playwright kept reporting `<div class="narrative-overlay">
      // intercepts pointer events` and burned the whole timeout. Measured on staging
      // 2026-08-14: `time-telemetry` failed twice in a row this way, at 47s, having spent
      // 30s retrying a click into a dialog. The modal is *expected product behaviour* - the
      // harness's job is to close it, not to wait it out.
      await dismissBlockingNarrative(target.page());
    }
  }
  return false;
}

/** The phase label the ExamScreen shows, or null when no exam screen is up. */
export async function currentPhase(page: Page): Promise<string | null> {
  const chip = page.locator(PHASE_CHIP);
  if ((await chip.count()) === 0) return null;
  return (await chip.first().innerText()).trim();
}

export async function startSession(page: Page): Promise<void> {
  await page.getByRole("button", { name: /start learning session/i }).click();
}

/**
 * Waits until the app is showing a screen the student can actually act on, dismissing any
 * stage narratives that are up when it gets there.
 *
 * A single dismiss is not enough: narratives arrive over SSE *after* the screen beneath
 * them has rendered (AUD-F-05), so a journey that dismisses once and moves on can be
 * covered again a moment later. Returns how many narratives it had to clear.
 *
 * **The dismiss runs before the interactivity check, since AUD-F-21.** It used to run only
 * when *no* interactive element was on screen, which was sound while a narrative replaced
 * the phase screen: a narrative being up implied nothing else was. Now that the narrative
 * renders above the phase screen instead, both are present at once, so the old ordering
 * returned immediately and left the narrative standing - and the count it returns, which
 * `narrative-refresh.spec.ts` records as evidence, silently became 0 for every run. A
 * caller asking to settle wants nothing in the way, not merely something clickable.
 *
 * Safe to call unconditionally because `dismissNarrativeIfPresent` matches `Continue`
 * exactly, and `StageTransitionScreen` is the only screen with such a button - the
 * ladder's equivalent is "I'll try again now".
 */
export async function settleToInteractiveScreen(page: Page, timeoutMs = 30_000): Promise<number> {
  const deadline = Date.now() + timeoutMs;
  let dismissed = 0;
  while (Date.now() < deadline) {
    if (await dismissNarrativeIfPresent(page)) {
      dismissed += 1;
      continue;
    }
    // Any screen with a control the journey can drive. The retry-ladder's *first* pause
    // is a plain `.panel` with no distinguishing class, so it is matched by its heading -
    // leaving it out made this spin the full timeout on every study-loop iteration, which
    // is what pushed the full walk past even a 10-minute budget.
    const interactive = page.locator(".card-list, .phase-chip, .intervention-panel, .email-preview");
    const firstPause = page.getByRole("heading", { name: /want a hand/i });
    // **Present is not the same as reachable, and `.phase-chip` cannot tell them apart
    // (D-324).** Every locator above renders *behind* the stage-narrative modal, so this
    // returned "settled" on a screen whose every control was intercepted. That is the third
    // time this harness has read `.phase-chip` and been wrong - D-321's walk counted a whole
    // post-exam as study work on the same signal. The chip reports a phase; it has never
    // reported interactivity.
    const blocked = (await page.locator(NARRATIVE_OVERLAY).count()) > 0;
    if (!blocked && ((await interactive.count()) > 0 || (await firstPause.count()) > 0)) {
      return dismissed;
    }
    await page.waitForTimeout(250);
  }
  return dismissed;
}

/**
 * Picks a topic, tolerating the stage-narrative screen displacing the topic list
 * mid-click (measured at ~26ms of interactivity - see tests/learning/narrative-race.
 * spec.ts, AUD-F-05). Without the retry every journey inherits that race, so a real
 * defect elsewhere would be indistinguishable from this one.
 */
export async function chooseTopic(page: Page, label = /linear equations/i): Promise<void> {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    await dismissNarrativeIfPresent(page);
    const card = page.locator(".card-list button").filter({ hasText: label });
    const visible = await card
      .waitFor({ state: "visible", timeout: 15_000 })
      .then(() => true)
      .catch(() => false);
    if (!visible) {
      // Either the narrative is up (next iteration dismisses it) or the topic step is
      // already behind us - the phase chip decides which.
      if ((await page.locator(PHASE_CHIP).count()) > 0) return;
      continue;
    }
    if (await stableClick(card)) return;
  }
  throw new Error("could not select a topic after 5 attempts (narrative race or missing topic list)");
}

/** How long a submission may take to be graded before `awaitAcceptance` gives up on it. */
const ANSWER_VERDICT_TIMEOUT_MS = 45_000;

export interface AnswerOptions {
  /** Which option to pick, modulo the option count. See the note on cycling below. */
  optionIndex?: number;
  /**
   * Return whether the **server accepted** the submission rather than whether the clicks
   * landed (D-355).
   *
   * The default is the older, weaker meaning, and a caller that counts submissions is
   * counting the wrong thing under it: this function returns true the moment Submit is
   * clicked, so a submission the server *refuses* still increments the caller's tally.
   * `journey-student` reconciles its own count against the verdicts the server graded, and
   * a drift of 4-7 with the phase never leaving `study` (D-340) is exactly the shape a
   * silently-refused submission produces. Opt in where the count is load-bearing; leaving
   * every other caller on the click-based meaning keeps their timing unchanged.
   */
  awaitAcceptance?: boolean;
  /** Called once per submission the server refused, when `awaitAcceptance` is set. */
  onRefused?: (status: number, url: string) => void;
}

/**
 * Answers the question currently on screen by picking an option and submitting.
 * Returns false when there is no answerable question (already answered, or the screen
 * is showing something else) so callers can drive a loop off it - and, under
 * `awaitAcceptance`, also when the server refused the answer it did submit.
 */
export async function answerCurrentQuestion(
  page: Page,
  options: AnswerOptions = {},
): Promise<boolean> {
  // Retried for the same reason `chooseTopic` is: a stage narrative arriving over SSE
  // replaces the exam screen mid-interaction, including between selecting an option and
  // clicking Submit (AUD-F-05). Every journey would otherwise carry that flake.
  trackLadderPauses(page);
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await dismissNarrativeIfPresent(page);
    // AUD-F-27: wait out an in-flight submission before concluding there is nothing to
    // answer. While one is running the button reads "Submitting…", so the exact-name
    // locator below finds nothing - and this function returning false means "no answerable
    // question", which `answerWholeExam` reads as *the end of the exam*. It would therefore
    // stop early whenever a submit was still in flight, silently answering fewer items than
    // it reported. Bounded, so a genuinely absent button still returns false promptly.
    await page
      .getByRole("button", { name: /^submitting…$/i })
      .waitFor({ state: "detached", timeout: 15_000 })
      .catch(() => undefined);
    const submit = page.getByRole("button", { name: /^submit answer$/i });
    if ((await submit.count()) === 0) return false;
    const optionButtons = page.locator(".options button.option");
    if ((await optionButtons.count()) === 0) {
      // A re-render can empty the option list for a moment. Returning false here would
      // report "no answerable question", which `answerWholeExam` reads as the end of the
      // exam - so a transient race would silently truncate the walk instead of failing it.
      await page.waitForTimeout(250);
      continue;
    }
    // Any option: correctness is not what most of this harness is testing, and picking the
    // first every time keeps a walk deterministic.
    //
    // **`optionIndex` exists because "any option" is not good enough for one caller
    // (D-310).** The student walk asserts the retry ladder engaged, which only happens on a
    // *wrong* answer - so with a fixed index it depends on the first option happening to be
    // wrong for some study item, which is an accident of the stored option order, not a
    // property the test controls. D-302 re-tiered the bank and changed which items that walk
    // is served; the first option was then correct for all of them and the assertion failed on
    // staging with the app behaving perfectly. Cycling the index across questions makes a
    // wrong answer near-certain (all-correct needs the walk to be lucky on every item) without
    // changing any other caller's behaviour.
    //
    // `isEnabled()` with no timeout waits the full 15 s for an element detached under it and
    // then *throws*, escaping this retry loop entirely - which is how the student walk failed
    // one whole-suite run in S41 after passing the two before it. Every other interaction in
    // this file already degrades to a retry rather than an exception; this one did not.
    const count = await optionButtons.count();
    const chosen = optionButtons.nth((options.optionIndex ?? 0) % count);
    const enabled = await chosen.isEnabled({ timeout: 2000 }).catch(() => false);
    if (!enabled) {
      await page.waitForTimeout(250);
      continue;
    }
    if (!(await stableClick(chosen))) continue;
    if (!options.awaitAcceptance) {
      if (await stableClick(submit)) return true;
      continue;
    }
    // **Armed before the click, not after it.** The verdict can land before the click
    // promise resolves, and a waiter registered afterwards would miss it and then time out
    // on a submission that in fact succeeded - turning a working answer into a false
    // "refused". `.catch` keeps a timeout from becoming an unhandled rejection when the
    // click below fails and this promise is abandoned.
    const verdict = page
      .waitForResponse(
        (response) =>
          response.request().method() === "POST" && response.url().endsWith("/answers"),
        { timeout: ANSWER_VERDICT_TIMEOUT_MS },
      )
      .catch(() => null);
    if (!(await stableClick(submit))) {
      void verdict;
      continue;
    }
    const response = await verdict;
    // No response observed inside the window. Reported as "not accepted", which is the
    // safe direction: the caller under-counts rather than claiming a submission the
    // server may never have graded.
    if (response === null) return false;
    if (response.status() < 300) return true;
    options.onRefused?.(response.status(), response.url());
    return false;
  }
  return false;
}

/**
 * Answers every item of a batched pre/post exam. The screen advances itself after each
 * submission, so this walks the batch by repeatedly answering whatever is displayed.
 */
export async function answerWholeExam(page: Page, expectedItems = 10): Promise<number> {
  let answered = 0;
  for (let attempt = 0; attempt < expectedItems + 5; attempt += 1) {
    const position = await page.locator(".progress-bar").innerText();
    if (!(await answerCurrentQuestion(page))) break;
    answered += 1;
    // The last item does not advance (there is nowhere to advance to), so the position
    // text stays put - that is the loop's exit condition, not an error.
    await expect
      .poll(async () => (await page.locator(".progress-bar").innerText()) !== position, {
        timeout: 10_000,
      })
      .toBeTruthy()
      .catch(() => undefined);
    if (answered >= expectedItems) break;
  }
  return answered;
}

/**
 * Opens the finalize modal and confirms it.
 *
 * The locator was `.panel > button`, and D-241 moved the button into a `.submit-exam`
 * wrapper (it added the "N questions left to answer" hint beside it), so it had been
 * matching nothing: `stableClick` on an empty locator is a no-op, and the failure surfaced
 * one line later as "the modal never appeared". Four journeys were failing on it, including
 * `journey-student`, which is one of §2.6's own criteria. Confirmed pre-existing by running
 * this spec against `main` (2026-08-10) - it fails there identically.
 */
export async function finalizeExam(page: Page): Promise<void> {
  await stableClick(page.locator(".submit-exam > button", { hasText: /^submit exam$/i }).last());
  const modal = page.locator(".modal-backdrop .modal");
  await expect(modal).toBeVisible();
  await stableClick(modal.getByRole("button", { name: /^submit exam$/i }));
  await expect(modal).toHaveCount(0, { timeout: 30_000 });
}

/**
 * Clears the stage-narrative screen if it is showing. S26 interposes it ahead of
 * whatever the phase would otherwise render, so a journey that does not dismiss it
 * looks stuck at the next step.
 *
 * Scoped to the narrative screen's own Continue button rather than any /continue/ match,
 * so it cannot accidentally consume a ladder button.
 */
export async function dismissNarrativeIfPresent(page: Page): Promise<boolean> {
  const button = page.getByRole("button", { name: /^continue$/i });
  if ((await button.count()) === 0) return false;
  return stableClick(button.first());
}

/**
 * Works the retry ladder when the graph pauses on `intervention_choice`.
 *
 * SPEC §5.11.3 gives a wrong answer exactly three ways forward - Hint / Solution /
 * Video - so there is deliberately no "decline" at the first pause and a journey must
 * pick one. This takes the requested rung (a hint unless told otherwise), then leaves the
 * ladder: "I'll try again now" resumes the graph, "Got it — next question" is the terminal
 * dismiss. False if no pause is up.
 *
 * **`rung` exists because "hint" was hard-coded here, and that is why two of the three
 * assistance counters on the results screen had no live evidence** (the V1 coverage gap).
 * Every walk in the suite spent hints and only hints, so `solutionCount` and `videoCount`
 * were rendered from numbers no test had ever moved off zero - and the one defect this class
 * has already produced in the wild was a *counter* defect ("Videos watched: 1" for a video
 * that was only ever displayed, ResultsScreen.tsx:59-65).
 */
export async function clearInterventionIfPresent(
  page: Page,
  /**
   * Breadcrumb sink (U1, D-324). **Instrument only — this function's behaviour is
   * deliberately unchanged.**
   *
   * D-321 closed the question of *whether* SPEC §5.11.3 works: on the one staging walk in
   * twelve that failed, the server had opened one ladder pause and the walk worked zero of
   * them. What was never established is *why* the wait below misses it, and D-311's standing
   * refusal to add another guess applies — so this records what the wait saw rather than
   * changing what it does.
   *
   * What makes the recording sufficient: the `if` further down decides purely on those two
   * `count()` reads, so capturing them **is** capturing the reason it returned false. Paired
   * with `journey-student.spec.ts`'s D-318 listener — which reads `pending_interrupt` off the
   * `POST /answers` response and therefore knows independently that the server *did* open a
   * pause — a failing run says both halves at once: the graph offered the ladder, and the
   * harness's race was won by something else. That is a mechanism, not a theory.
   *
   * Costs nothing and adds no waiting, on purpose. A version that waited a few seconds to see
   * whether the pause showed up late would both slow every no-pause question and risk
   * becoming the fix by accident, which would spend the failure this is meant to explain.
   */
  note?: (message: string) => void,
  /**
   * Which rung to spend at the *first* pause, where all three are offered and the screen is
   * `intervention === null` (InterventionScreen.tsx:143-165). A reopened pause has a
   * different button set and is left to the exit path below either way.
   */
  rung: LadderRung = "hint",
): Promise<boolean> {
  const firstPause = page.getByRole("heading", { name: /want a hand/i });
  const content = page.locator(".intervention-panel");

  // **Wait for the pause to ARRIVE, not merely test whether it has** (D-288).
  //
  // This used to read `count()` once and return false the instant neither locator was
  // present. Locally that is right - MockBedrock answers in milliseconds, so the pause is
  // already on screen. Against staging it is a race the walk always lost: a wrong answer's
  // intervention arrives over SSE after a real network round trip, the walk read "no
  // pause", and `answerCurrentQuestion` then clicked straight through the panel. Measured
  // on the first whole staging run: 11 study answers, **0 ladder pauses**, on a walk that
  // picks the first option every time and is therefore wrong ~74% of the time (the bank's
  // correct answer sits at A in 26% of items). The retry ladder - SPEC §5.11.3, the
  // centrepiece of the study phase - had never once been exercised against staging, and
  // only `expect(interventions).toBeGreaterThan(0)` noticed.
  //
  // Raced against the question's own options rather than given a fixed timeout, so a
  // question with genuinely no pause costs nothing: whichever screen materialises first
  // ends the wait.
  const options = page.locator(".option-text");
  const startedAt = Date.now();

  // **Wait only when the server said a pause is coming (D-324).** `pauseOpenedByLastAnswer`'s
  // docstring has the measurement that retired the old `.or(options)` race: it resolved in 2-4 ms
  // every time because the answered question's options are still mounted, so this never waited for
  // anything and caught the pause only when it had already arrived. `undefined` means no graded
  // answer has been seen on this page yet - fall back to the bounded wait rather than assume, since
  // "not observed" and "no pause" are different claims.
  const expectPause = pauseOpenedByLastAnswer.get(page);
  if (expectPause === false) {
    // A correct answer opens no pause, so there is nothing to wait for and the old race's one real
    // virtue - costing nothing on this path - is kept.
    if (note) note("ladder wait: skipped, server opened no pause on the last answer");
    return false;
  }
  if (expectPause === undefined) {
    // Nothing has been graded on this page yet - this is the first turn of a walk's loop, before
    // any answer - so no *answer-driven* pause can possibly be in flight. Falling through to the
    // count check rather than returning early, because a pause belonging to a **resumed** session
    // arrives in the initial snapshot and is already on screen; what is not needed is a wait for
    // something that cannot arrive. Measured on a local suite before this branch existed: three
    // such calls burned the full 15s timeout each, 45s for zero pauses found.
    if (note) note("ladder wait: no answer graded on this page yet, checking without waiting");
  } else {
    await firstPause
      .or(content)
      .first()
      .waitFor({ state: "visible", timeout: 15_000 })
      .catch(() => undefined);
  }
  const waitedMs = Date.now() - startedAt;

  const pauseCount = await firstPause.count();
  const panelCount = await content.count();

  if (note) {
    // Visibility as well as presence: the race resolves on `visible`, so a locator that is
    // attached-but-hidden did not win it. `.first()` on each because `.option-text` matches
    // one per option and strict mode would throw on the bare locator.
    const [pauseVisible, panelVisible, optionsVisible] = await Promise.all([
      firstPause
        .first()
        .isVisible()
        .catch(() => false),
      content
        .first()
        .isVisible()
        .catch(() => false),
      options
        .first()
        .isVisible()
        .catch(() => false),
    ]);
    // `optionsVisible` is still recorded, but it can no longer *win*: it is the evidence that
    // the answered question's options remain mounted, which is what made the old race a no-op.
    const wonBy = pauseVisible
      ? "first-pause"
      : panelVisible
        ? "panel"
        : `TIMED OUT after waiting (options still mounted: ${optionsVisible})`;
    note(
      `ladder wait: won by ${wonBy} after ${waitedMs}ms ` +
        `(pause=${pauseCount}, panel=${panelCount}, options=${await options.count()}) ` +
        `-> ${pauseCount === 0 && panelCount === 0 ? "RETURNED FALSE" : "worked the pause"}`,
    );
  }

  if (pauseCount === 0 && panelCount === 0) return false;

  if ((await firstPause.count()) > 0) {
    if (note) note(`ladder: spending the "${rung}" rung`);
    await stableClick(page.getByRole("button", { name: RUNG_BUTTON[rung] }));
  }

  // The requested hint does not reliably survive to be read: a later SSE snapshot
  // without `intervention` unmounts the panel (measured in
  // tests/learning/hint-displacement.spec.ts, which deliberately carries no finding id -
  // "AUD-F-03" here was a mis-citation; that id is the exam-position finding).
  // So the exit button may never appear, and
  // its absence is not a journey failure - the graph has already moved on.
  const tryAgain = page.getByRole("button", { name: /i'll try again now/i });
  const gotIt = page.getByRole("button", { name: /got it — next question/i });
  const exitVisible = await tryAgain
    .or(gotIt)
    .first()
    .waitFor({ state: "visible", timeout: 15_000 })
    .then(() => true)
    .catch(() => false);
  if (exitVisible) await stableClick((await tryAgain.count()) > 0 ? tryAgain : gotIt);

  // **This pause is spent, so stop expecting it (D-324).** Found by the breadcrumb rather than by
  // reading the code: the first version of this fix set the flag from `POST /answers` and never
  // cleared it, so the caller's `continue` came straight back here with `expectPause` still true and
  // waited the full 15s for a pause that had just been worked. Measured on a local suite: **3 such
  // timeouts, 45s**, and they are exactly the 3 lines the breadcrumb reported as `TIMED OUT` while
  // 7 real pauses were worked. The flag means "the last graded answer opened a pause that is still
  // outstanding", and consuming it is what makes that true again.
  pauseOpenedByLastAnswer.set(page, false);
  return true;
}
