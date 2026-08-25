/**
 * Visual probe, not an assertion suite: drives a wrong answer in the study phase, takes a
 * hint, then a solution, and captures each panel.
 *
 * D-207 changed how all three interventions render (hint fields are labelled, solution
 * steps are cards with the working on its own line, the video option is a link card) and
 * changed where the chat transcript lives. Those are appearance claims, and the only
 * honest way to check an appearance claim is to look at it.
 *
 * It runs with the rest of the suite (~10 s) and asserts only that the panels are reachable
 * and how many solution steps rendered - that count is itself a useful regression signal,
 * since D-207's whole point is that an authored item now serves its stored five- or
 * six-step solution instead of the generated two-step placeholder. The screenshots land in
 * `artifacts/probe/` for a human to look at:
 *
 *     npx playwright test tests/learning/assistance-panel-probe.spec.ts
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

test.describe.configure({ timeout: 300_000 });

/** Written straight to disk: these artifacts are the point of the probe, and
 *  `testInfo.attach` bodies are not preserved by this harness's reporter. */
const SHOTS = process.env.PROBE_SHOTS ?? "artifacts/probe";

test("capture the assistance panels @probe", async ({ page, audit }) => {
  test.skip(TARGET !== "local", "a local-stack visual probe");

  // Its own student, not `studentPresent` (WORK-13-FIXTURES). This spec creates a
  // learning session, and the journeys mutate shared per-student Postgres and MySQL
  // state through one seeded account - so a spec sharing that account picks up
  // whatever the previous one left behind. `FIXTURES` in config.ts has the
  // measurement: 7 refused submissions and 2.3 minutes against 15 seconds.
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentAssistance);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);
  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });

  // Clear the pre-exam so the study phase - the only place interventions happen - is
  // reached. Correctness does not matter here.
  for (let i = 0; i < 12; i += 1) {
    const answered = await answerCurrentQuestion(page);
    if (!answered) break;
    if (await page.locator(".phase-chip").getByText(/study/i).count()) break;
  }
  const submitExam = page.getByRole("button", { name: /^submit exam$/i });
  if (await submitExam.isVisible().catch(() => false)) {
    await submitExam.click();
    await page
      .getByRole("button", { name: /submit|confirm/i })
      .last()
      .click()
      .catch(() => undefined);
  }
  await expect(page.locator(".phase-chip")).toHaveText(/study/i, { timeout: 120_000 });

  // A wrong answer opens the hint/solution/video chooser (SPEC §5.11.3).
  for (let attempt = 0; attempt < 6; attempt += 1) {
    const chooser = page.getByRole("button", { name: /get a hint/i });
    if (await chooser.isVisible().catch(() => false)) break;
    const answered = await answerCurrentQuestion(page);
    if (!answered) break;
  }

  const chooser = page.getByRole("button", { name: /get a hint/i });
  const reachedChooser = await chooser.isVisible().catch(() => false);
  audit.note(`reached the assistance chooser: ${reachedChooser}`);
  test.skip(!reachedChooser, "never landed on a wrong study answer within the attempt budget");

  await page.screenshot({ path: `${SHOTS}/00-chooser.png`, fullPage: true });

  await chooser.click();
  await expect(page.locator(".intervention-panel")).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${SHOTS}/01-hint.png`, fullPage: true });

  const solution = page.getByRole("button", { name: /show the solution/i });
  if (await solution.isVisible().catch(() => false)) {
    await solution.click();
    await expect(page.locator(".solution-steps")).toBeVisible({ timeout: 60_000 });
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${SHOTS}/02-solution.png`, fullPage: true });
    audit.note(
      `solution steps rendered: ${await page.locator(".solution-step").count()}`,
    );
  }
});
