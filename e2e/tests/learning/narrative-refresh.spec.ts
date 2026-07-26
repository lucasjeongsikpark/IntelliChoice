/**
 * AUD-F probe: does a page refresh re-show a stage narrative the student already
 * dismissed?
 *
 * `App.tsx` tracks dismissal in React state (`dismissedNarrative`, keyed by the narrative
 * text) while the backend keeps `stage_narrative` in the snapshot. React state does not
 * survive a reload, so the gate ahead of every phase branch closes again.
 *
 * This matters beyond the annoyance: SPEC Phase 11's own "done when" is that a refresh
 * restores the student's exact position, and `useLearningSession`'s docstring cites that
 * requirement explicitly. Landing on a narrative screen instead of the question is a
 * different position.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";
import {
  chooseTopic,
  dismissNarrativeIfPresent,
  settleToInteractiveScreen,
  startSession,
} from "../../fixtures/learning-flow";

test.describe.configure({ timeout: 180_000 });

// CONFIRMED DEFECT (AUD-F-05): the narrative returns after a reload, and one more click
// clears it. Expected-to-fail for the same reason as AUD-F-04 in journey-student.spec.ts.
test("a dismissed stage narrative stays dismissed across a refresh", async ({ page, audit }) => {
  test.fail();
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await startSession(page);

  // Dismiss whatever narrative appears, then get to the exam.
  const cleared = await settleToInteractiveScreen(page);
  audit.note(`narratives dismissed before the exam: ${cleared}`);
  await chooseTopic(page);
  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });

  const narrativeBefore = page.getByRole("button", { name: /^continue$/i });
  await expect(
    narrativeBefore,
    "a narrative was still up after settling - the precondition for this test did not hold",
  ).toHaveCount(0);

  await page.reload();

  // After the reload the student should be back on their exam question. If a narrative
  // screen is what loads instead, the dismissal did not survive.
  const narrativeAfter = page.getByRole("button", { name: /^continue$/i });
  const examAfter = page.locator(".phase-chip");
  await expect(narrativeAfter.or(examAfter).first()).toBeVisible({ timeout: 60_000 });

  const narrativeReturned = (await narrativeAfter.count()) > 0;
  if (narrativeReturned) {
    const text = await page.locator(".panel p, main p").first().innerText();
    audit.note(`after refresh the narrative returned: ${JSON.stringify(text.slice(0, 120))}`);
    // Confirm it is genuinely re-dismissable rather than a stuck state - which is what
    // separates this from a blocking defect.
    await dismissNarrativeIfPresent(page);
    const recovered = await examAfter
      .waitFor({ state: "visible", timeout: 30_000 })
      .then(() => true)
      .catch(() => false);
    audit.note(`dismissing again recovered the exam: ${recovered}`);
  } else {
    audit.note("after refresh the student went straight back to the exam - dismissal survived");
  }

  expect(
    narrativeReturned,
    "a refresh re-showed an already-dismissed stage narrative, so the student's restored position is the narrative screen rather than their question (SPEC Phase 11)",
  ).toBe(false);
});
