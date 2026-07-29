/**
 * The parent launch journeys: child-select → dashboard → report, both the
 * two-children interrupt path and the single-child auto-select path.
 *
 * S11's known parent auto-select gap is on the Phase 0B list, and
 * `useLearningSession`'s own docstring points at it, so this records what the browser
 * actually does rather than assuming either behavior.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { expectNotBlank, expectNotStuck, signInViaUi } from "../../fixtures/session";
import { settleToInteractiveScreen, stableClick, startSession } from "../../fixtures/learning-flow";

test.describe.configure({ timeout: 180_000 });

test("parent with two children is asked which child, and the choice sticks", async ({
  page,
  audit,
}) => {
  await signInViaUi(page, LEARNING_WEB, FIXTURES.parentTwoChildren);
  await expect(page.getByRole("heading", { name: /ready to learn/i })).toBeVisible();
  await startSession(page);

  // Settle *before* the first screen assertion, not after. S26 stage narratives are gated
  // ahead of every phase branch and only exist once an account has history, so whether one
  // interposes here is a function of how many times the suite has run against this fixture -
  // which is precisely the shared-state coupling S39 recorded as the e2e intermittency.
  // The child-selection screen renders its candidates as a `.card-list`, so settling stops
  // here rather than clicking past the interrupt this test is about.
  await settleToInteractiveScreen(page);
  await expect(page.getByRole("heading", { name: /who's learning today/i })).toBeVisible({
    timeout: 60_000,
  });
  const candidates = page.locator(".card-list button");
  const count = await candidates.count();
  audit.note(`child_selection offered ${count} candidates`);
  expect(count, "a parent with two linked children should be offered both").toBe(2);

  const chosen = (await candidates.first().innerText()).split("\n")[0];
  audit.note(`selected: ${chosen}`);
  await stableClick(candidates.first());

  // The interrupt must clear - it is the one interrupt path S38 found *stricter* than
  // the rest of the app, so a failure here would be a regression in the good pattern.
  await expect(page.getByRole("heading", { name: /who's learning today/i })).toHaveCount(0, {
    timeout: 60_000,
  });
  await expectNotStuck(page, "Connecting…");
  await expectNotBlank(page);
  await settleToInteractiveScreen(page);

  // Whatever screen follows, it must be a real one: the topic list or an exam.
  await expect(page.locator(".card-list, .phase-chip").first()).toBeVisible({ timeout: 60_000 });
});

test("parent with one child reaches a working screen without being asked to choose", async ({
  page,
  audit,
}) => {
  await signInViaUi(page, LEARNING_WEB, FIXTURES.parentOneChild);
  await startSession(page);

  // Same reason as the two-children journey above. This is the one that actually caught it:
  // it failed a whole-suite run on "Welcome back! Let's see what you remember today." with a
  // Continue button, which is none of the three locators below, having passed the run before.
  await settleToInteractiveScreen(page);

  const childPrompt = page.getByRole("heading", { name: /who's learning today/i });
  const topics = page.locator(".card-list");
  const exam = page.locator(".phase-chip");
  await expect(childPrompt.or(topics).or(exam).first()).toBeVisible({ timeout: 60_000 });

  const asked = (await childPrompt.count()) > 0;
  audit.note(
    asked
      ? "a single-child parent was still asked to choose (S11's auto-select gap, as documented)"
      : "a single-child parent was auto-selected",
  );
  if (asked) await stableClick(page.locator(".card-list button").first());

  await settleToInteractiveScreen(page);
  await expectNotBlank(page);
  await expect(page.locator(".card-list, .phase-chip").first()).toBeVisible({ timeout: 60_000 });
});

// CONFIRMED DEFECT (AUD-F-22): a parent has no dashboard entry point mid-session. The
// button is rendered by exactly two screens - `StartScreen`, which requires a resolved
// `studentId` a parent only gets *by starting a session*, and `ResultsScreen` at the end of
// a completed cycle - and `endSession()` clears `studentId`, so backing out does not help
// either. The only route to a child's progress dashboard is finishing a whole
// pre -> study -> post cycle.
//
// This was a conditional `test.skip(!reachable)` from S39 to S43, which meant four sessions
// of runs reported it as "skipped: no dashboard entry point from the current screen" - a
// sentence describing the defect, filed as a reason not to look. `test.fail()` instead, the
// same posture as AUD-F-04/AUD-F-05: the probe keeps running and keeps measuring, and it
// fails the run the day the gap is closed, which is the signal to promote it.
test("parent reaches the progress dashboard and generates a report", async ({ page, audit }) => {
  test.fail();
  await signInViaUi(page, LEARNING_WEB, FIXTURES.parentTwoChildren);

  // Resolve a student first, which is itself the contract being checked (App.tsx's
  // `dashboardStudentId`).
  await startSession(page);
  const childPrompt = page.getByRole("heading", { name: /who's learning today/i });
  if (await childPrompt.isVisible().catch(() => false)) {
    await stableClick(page.locator(".card-list button").first());
  }
  await settleToInteractiveScreen(page);

  const dashboardButton = page.getByRole("button", { name: /view progress dashboard/i });
  const reachable = await dashboardButton
    .first()
    .waitFor({ state: "visible", timeout: 20_000 })
    .then(() => true)
    .catch(() => false);
  audit.note(`dashboard button reachable mid-session: ${reachable}`);
  expect(
    reachable,
    "a parent who has resolved a child has no way to open that child's progress dashboard without completing an entire pre/study/post cycle - the dashboard button is only on StartScreen (which needs a studentId a parent gets by starting a session) and ResultsScreen (AUD-F-22)",
  ).toBe(true);

  await stableClick(dashboardButton.first());
  await expectNotBlank(page);
  await expectNotStuck(page, /loading/i);

  // A report is a paid generation path (AUD-L-02/AUD-X-08's ceiling), so this asserts the
  // button exists and the click resolves to *something* rather than demanding content.
  const reportButton = page.getByRole("button", { name: /report/i });
  if ((await reportButton.count()) > 0) {
    await stableClick(reportButton.first());
    await expectNotStuck(page, /generating/i, 60_000);
    audit.note("report generation resolved");
  } else {
    audit.note("no report button on the dashboard screen");
  }
  await expectNotBlank(page);
});
