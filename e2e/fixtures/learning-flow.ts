/**
 * Driving the learning app's screens the way a student does.
 *
 * These helpers deliberately click real buttons rather than calling the API: the point
 * of AUD-F is the contract between the two, and every prior session's live findings came
 * from the seam, not from either side alone.
 */

import { expect, type Locator, type Page } from "@playwright/test";

export const PHASE_CHIP = ".phase-chip";

/**
 * Clicks through the learning app's re-render churn.
 *
 * Every SSE snapshot re-renders `App`, and several branches *replace* the whole screen
 * (the assistance panel replaces the exam view; the stage narrative used to do the same).
 * Playwright reports the result as "element is not stable" or "element was detached from
 * the DOM" on controls that are visibly present - measured on the topic card, the Submit
 * answer button, and the ladder's own buttons.
 *
 * That churn is AUD-F-01, recorded with measurements in tests/learning/narrative-race.
 * spec.ts. It is absorbed here rather than in each journey so that a *different* defect
 * does not present as this one, and so no journey silently depends on winning a race.
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
 * them has rendered (AUD-F-01), so a journey that dismisses once and moves on can be
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
    if ((await interactive.count()) > 0 || (await firstPause.count()) > 0) return dismissed;
    await page.waitForTimeout(250);
  }
  return dismissed;
}

/**
 * Picks a topic, tolerating the stage-narrative screen displacing the topic list
 * mid-click (measured at ~26ms of interactivity - see tests/learning/narrative-race.
 * spec.ts, AUD-F-01). Without the retry every journey inherits that race, so a real
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

/**
 * Answers the question currently on screen by picking an option and submitting.
 * Returns false when there is no answerable question (already answered, or the screen
 * is showing something else) so callers can drive a loop off it.
 */
export async function answerCurrentQuestion(page: Page): Promise<boolean> {
  // Retried for the same reason `chooseTopic` is: a stage narrative arriving over SSE
  // replaces the exam screen mid-interaction, including between selecting an option and
  // clicking Submit (AUD-F-01). Every journey would otherwise carry that flake.
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await dismissNarrativeIfPresent(page);
    const submit = page.getByRole("button", { name: /^submit answer$/i });
    if ((await submit.count()) === 0) return false;
    const options = page.locator(".options button.option");
    if ((await options.count()) === 0) {
      // A re-render can empty the option list for a moment. Returning false here would
      // report "no answerable question", which `answerWholeExam` reads as the end of the
      // exam - so a transient race would silently truncate the walk instead of failing it.
      await page.waitForTimeout(250);
      continue;
    }
    // Any option: correctness is not what this journey is testing, and picking the first
    // every time keeps the walk deterministic.
    //
    // `isEnabled()` with no timeout waits the full 15 s for an element detached under it and
    // then *throws*, escaping this retry loop entirely - which is how the student walk failed
    // one whole-suite run in S41 after passing the two before it. Every other interaction in
    // this file already degrades to a retry rather than an exception; this one did not.
    const first = options.first();
    const enabled = await first.isEnabled({ timeout: 2000 }).catch(() => false);
    if (!enabled) {
      await page.waitForTimeout(250);
      continue;
    }
    if ((await stableClick(first)) && (await stableClick(submit))) return true;
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

/** Opens the finalize modal and confirms it. */
export async function finalizeExam(page: Page): Promise<void> {
  await stableClick(page.locator(".panel > button", { hasText: /^submit exam$/i }).last());
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
 * pick one. This takes a hint, then leaves the ladder: "I'll try again now" resumes the
 * graph, "Got it — next question" is the terminal dismiss. False if no pause is up.
 */
export async function clearInterventionIfPresent(page: Page): Promise<boolean> {
  const firstPause = page.getByRole("heading", { name: /want a hand/i });
  const content = page.locator(".intervention-panel");
  if ((await firstPause.count()) === 0 && (await content.count()) === 0) return false;

  if ((await firstPause.count()) > 0) {
    await stableClick(page.getByRole("button", { name: /get a hint/i }));
  }

  // The requested hint does not reliably survive to be read: a later SSE snapshot
  // without `intervention` unmounts the panel (AUD-F-03, measured in
  // tests/learning/hint-displacement.spec.ts). So the exit button may never appear, and
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
  return true;
}
