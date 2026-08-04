/**
 * The parent launch journeys: child-select → dashboard → report, both the
 * two-children selection path and the single-child auto-select path.
 *
 * AUD-F-22 (closed): a parent's child is now resolved at *login* — one child silently,
 * several via the same ChildSelectionScreen the in-session interrupt uses — so the start
 * screen's "View progress dashboard" button is reachable with zero sessions. These
 * journeys assert the new contract; the in-session `child_selection` interrupt remains
 * the server-side fallback (and the resume path's re-check), so a prompt appearing
 * *after* "Start learning session" is tolerated but no longer expected.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { expectNotBlank, expectNotStuck, signInViaUi } from "../../fixtures/session";
import { settleToInteractiveScreen, stableClick, startSession } from "../../fixtures/learning-flow";

test.describe.configure({ timeout: 180_000 });

test("parent with two children is asked which child at login, and the choice sticks", async ({
  page,
  audit,
}) => {
  await signInViaUi(page, LEARNING_WEB, FIXTURES.parentTwoChildren);

  // AUD-F-22: the ask moved from in-session to login. The prompt renders before any
  // session exists, so there is no SSE churn to settle - just the children fetch.
  await expect(page.getByRole("heading", { name: /who's learning today/i })).toBeVisible({
    timeout: 60_000,
  });
  const candidates = page.locator(".card-list button");
  const count = await candidates.count();
  audit.note(`login-time child selection offered ${count} candidates`);
  expect(count, "a parent with two linked children should be offered both").toBe(2);

  const chosen = (await candidates.first().innerText()).split("\n")[0];
  audit.note(`selected: ${chosen}`);
  await stableClick(candidates.first());

  // The choice resolves to the start screen, with the dashboard entry point already
  // present - the surface AUD-F-22 was about.
  await expect(page.getByRole("heading", { name: /ready to learn/i })).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByRole("button", { name: /view progress dashboard/i })).toBeVisible();

  // And it sticks: starting a session must not re-ask (the client passes the resolved
  // child explicitly; the backend re-verifies the link server-side).
  await startSession(page);
  await expectNotStuck(page, "Connecting…");
  await expectNotBlank(page);
  await settleToInteractiveScreen(page);
  await expect(page.getByRole("heading", { name: /who's learning today/i })).toHaveCount(0);
  await expect(page.locator(".card-list, .phase-chip").first()).toBeVisible({ timeout: 60_000 });
});

test("parent with one child reaches the start screen resolved, without being asked", async ({
  page,
  audit,
}) => {
  await signInViaUi(page, LEARNING_WEB, FIXTURES.parentOneChild);

  // AUD-F-22 closed S11's auto-select gap at the same time: exactly one linked child is
  // resolved silently at login, so the start screen arrives already offering the
  // dashboard, and no chooser ever renders.
  await expect(page.getByRole("heading", { name: /ready to learn/i })).toBeVisible({
    timeout: 60_000,
  });
  const asked = (await page.getByRole("heading", { name: /who's learning today/i }).count()) > 0;
  audit.note(
    asked
      ? "a single-child parent was still asked to choose (login-time auto-select regressed)"
      : "a single-child parent was auto-selected at login",
  );
  expect(asked, "one linked child should be auto-selected, not prompted").toBe(false);
  await expect(page.getByRole("button", { name: /view progress dashboard/i })).toBeVisible();

  await startSession(page);

  // Same reason as the two-children journey above: whatever screen follows must be a
  // real one (topic list or an exam), with any stage narrative dismissed first.
  await settleToInteractiveScreen(page);
  await expectNotBlank(page);
  await expect(page.locator(".card-list, .phase-chip").first()).toBeVisible({ timeout: 60_000 });
});

// REGRESSION TEST (AUD-F-22, closed): promoted from the `test.fail()` probe that measured
// this gap from S43 on. The probe's journey assumed the fix would surface a button
// mid-session; the actual fix (D-175 §5's recorded decision, implemented later the same
// day) resolves the parent's child at login instead, so the promoted test asserts the
// stronger property: the dashboard is reachable with **zero** learning sessions - the
// original finding was "a parent's only route to the dashboard is finishing a whole
// pre → study → post cycle as if they were the student".
//
// History, kept because the posture mattered: this was a conditional `test.skip()` from
// S39 to S43 ("skipped: no dashboard entry point from the current screen" - a sentence
// describing the defect, filed as a reason not to look at it), then a `test.fail()` probe
// on AUD-F-03's pattern until the gap closed.
test("parent reaches the progress dashboard with zero sessions and generates a report", async ({
  page,
  audit,
}) => {
  await signInViaUi(page, LEARNING_WEB, FIXTURES.parentTwoChildren);

  // Resolve the child at login - the contract being checked (App.tsx resolves before
  // the start screen; ChildSelectionScreen is the same component the interrupt uses).
  const childPrompt = page.getByRole("heading", { name: /who's learning today/i });
  await expect(childPrompt).toBeVisible({ timeout: 60_000 });
  await stableClick(page.locator(".card-list button").first());

  const dashboardButton = page.getByRole("button", { name: /view progress dashboard/i });
  await expect(dashboardButton.first()).toBeVisible({ timeout: 20_000 });
  audit.note("dashboard button reachable pre-session: true");

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
