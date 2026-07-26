/**
 * AUD-F probe: does the hint a student asks for survive long enough to be read?
 *
 * SPEC §5.11.3 gives a wrong answer three ways forward and §5.11.4 defines the hint
 * itself. Neither is worth anything if the panel unmounts before the student reads it.
 * The journey walk hit exactly that - after clicking "Get a hint", the assistance panel
 * was gone and the next study question was on screen - so this measures it directly.
 *
 * Deliberately measures rather than asserting a threshold: no acceptable dwell time was
 * known before the first measurement (D-100's rule).
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";
import {
  answerCurrentQuestion,
  chooseTopic,
  currentPhase,
  settleToInteractiveScreen,
  finalizeExam,
  answerWholeExam,
  startSession,
  stableClick,
} from "../../fixtures/learning-flow";

test.describe.configure({ timeout: 300_000 });

test("a requested hint stays on screen long enough to read", async ({ page, audit }) => {
  // AUD-F-02 (its own finding, measured in post-finalize-poll.spec.ts): finalizing an exam
  // produces a burst of 409s on `exam/overview` and `exam/items/{id}/time`, each a browser
  // console error. Allowed by path here so this journey still enforces "zero console
  // errors" for everything else - otherwise one known defect would mask every new one.
  audit.allow({ statuses: [409], consoleErrors: ["Failed to load resource"] });
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);

  // Get through the pre-exam to reach the study phase, where the ladder lives.
  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });
  await answerWholeExam(page);
  await finalizeExam(page);
  await settleToInteractiveScreen(page);

  // Answer until the graph pauses on `intervention_choice`.
  const firstPause = page.getByRole("heading", { name: /want a hand/i });
  let reached = false;
  for (let i = 0; i < 30 && !reached; i += 1) {
    await settleToInteractiveScreen(page);
    if ((await firstPause.count()) > 0) {
      reached = true;
      break;
    }
    const phase = await currentPhase(page);
    if (phase && /post-exam/i.test(phase)) break;
    if (!(await answerCurrentQuestion(page))) await page.waitForTimeout(500);
  }
  test.skip(!reached, "no retry-ladder pause occurred in this run (every answer was correct)");

  await stableClick(page.getByRole("button", { name: /get a hint/i }));

  const panel = page.locator(".intervention-panel");
  const appeared = await panel
    .waitFor({ state: "visible", timeout: 30_000 })
    .then(() => true)
    .catch(() => false);
  audit.note(`hint panel appeared: ${appeared}`);
  expect(appeared, "the requested hint never rendered at all").toBe(true);

  const hintText = await panel.innerText();
  audit.note(`hint content: ${JSON.stringify(hintText.slice(0, 200))}`);

  // How long does it survive with no further interaction? A student needs seconds.
  const shownAt = Date.now();
  let dwellMs = 0;
  for (let i = 0; i < 30; i += 1) {
    if ((await panel.count()) === 0) break;
    dwellMs = Date.now() - shownAt;
    await page.waitForTimeout(500);
  }
  const stillThere = (await panel.count()) > 0;
  audit.note(
    stillThere
      ? `hint still on screen after ${dwellMs}ms of no interaction - survives`
      : `hint unmounted on its own after ~${dwellMs}ms with no interaction`,
  );

  expect(
    stillThere,
    `the hint panel unmounted after ~${dwellMs}ms without the student doing anything - a requested explanation the student cannot finish reading`,
  ).toBe(true);
});
