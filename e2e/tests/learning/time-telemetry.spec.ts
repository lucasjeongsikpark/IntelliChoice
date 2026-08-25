/**
 * AUD-F-01 regression test (S41): the exam screen must report *dwell time*, and must not
 * re-run its effects on every render.
 *
 * S36's AUD-L-14 found `time_spent_minutes` reading 0.0 next to `attempts_count: 26`, with
 * 140 item-state rows summing to 0 ms against 41,250 ms of real `response_time_ms` - and
 * attributed it to the report summing client telemetry. That says where the zero is read,
 * not where it comes from. This measures the client side, which only a browser can see.
 *
 * The mechanism: `ExamScreen`'s view-time effect resets `viewStartRef` in its body and
 * reports `Date.now() - viewStartRef.current` in its cleanup, and its dependency list
 * includes `onRecordTime`; the overview poll effect likewise depends on `onFetchOverview`.
 * `App.tsx` used to pass both as inline arrows - a new identity on every render - so every
 * SSE snapshot tore both effects down and re-ran them.
 *
 * Measured on one question with the student touching nothing for 15 seconds:
 *
 *   before (2026-07-27)   899 time reports, longest 68 ms;   903 GET /exam/overview
 *   after                   1 time report,  15,009 ms;         2 GET /exam/overview
 *
 * Both halves are asserted. The *value* assertion alone is not enough: a fix that made the
 * reports accurate while leaving the effect churn in place would still be a database write
 * per render on the primary journey's hot path, which is the P1 (D-103 §2). Both were
 * confirmed to fail with the fix reverted before this was promoted from a `test.fail()`
 * probe (D-107 §1 - a regression test that has never been seen to fail asserts nothing).
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";
import {
  chooseTopic,
  settleToInteractiveScreen,
  stableClick,
  startSession,
} from "../../fixtures/learning-flow";

test.describe.configure({ timeout: 180_000 });

test("reported item time reflects how long the student actually spent", async ({ page, audit }) => {
  // A time report still in flight when the screen unmounts is aborted by design (the hook
  // is explicitly fire-and-forget), so the abort itself is not a finding - its volume was.
  audit.allow({ failedRequests: true });

  // Capture the request bodies - the status code alone says nothing about the value.
  const reported: number[] = [];
  page.on("request", (request) => {
    if (!/\/exam\/items\/[^/]+\/time$/.test(request.url())) return;
    const body = request.postData();
    if (!body) return;
    try {
      reported.push((JSON.parse(body) as { elapsed_ms: number }).elapsed_ms);
    } catch {
      // Not JSON - nothing to measure.
    }
  });

  // The second half of AUD-F-01: the poll effect re-installing its interval on every render.
  let overviewFetches = 0;
  page.on("request", (request) => {
    if (request.method() === "GET" && /\/exam\/overview$/.test(request.url())) overviewFetches += 1;
  });

  // Its own student, not `studentPresent` (WORK-13-FIXTURES). This spec creates a
  // learning session, and the journeys mutate shared per-student Postgres and MySQL
  // state through one seeded account - so a spec sharing that account picks up
  // whatever the previous one left behind. `FIXTURES` in config.ts has the
  // measurement: 7 refused submissions and 2.3 minutes against 15 seconds.
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentTimeTelemetry);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);
  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });

  // Sit on one question for a known, deliberately long time and touch nothing. Any honest
  // dwell measurement has to notice 15 seconds.
  const DWELL_MS = 15_000;
  reported.length = 0;
  overviewFetches = 0;
  await page.waitForTimeout(DWELL_MS);
  // Navigating away is what flushes the view-time for the item being left.
  const nav = page.locator(".question-nav button, .exam-nav button");
  // `stableClick`, not a bare `click()`, because entering the pre-exam raises a stage
  // narrative and that modal intercepts pointer events until an explicit Continue (D-324).
  // A bare click retried into the dialog for its full 30s timeout and failed the test twice
  // running on staging; `stableClick` closes a blocking overlay and retries.
  if ((await nav.count()) > 1) {
    expect(
      await stableClick(nav.nth(1)),
      "could not reach the exam navigator to leave question 1 - without that click no " +
        "view-time flush happens and the measurement below would be of nothing",
    ).toBe(true);
  }
  await page.waitForTimeout(1000);

  const total = reported.reduce((sum, value) => sum + value, 0);
  const max = reported.length > 0 ? Math.max(...reported) : 0;
  audit.note(`${reported.length} time reports during a ${DWELL_MS}ms dwell`);
  audit.note(`reported values: total=${total}ms, max=${max}ms, sample=${JSON.stringify(reported.slice(0, 12))}`);
  audit.note(`${overviewFetches} GET /exam/overview during the same window`);

  // The student demonstrably spent DWELL_MS on one question. If no single report gets
  // anywhere near that, the client is not measuring dwell time at all - which is the
  // upstream half of AUD-L-14, and it is invisible from the database alone.
  expect(
    max,
    `the longest single reported dwell was ${max}ms after the student sat on one question for ${DWELL_MS}ms - the client reports render intervals, not time on task`,
  ).toBeGreaterThan(DWELL_MS * 0.5);

  // Counting the writes, not just checking their values: leaving one question generates one
  // flush, and a bound of 3 tolerates a stray remount without tolerating effect churn.
  // Measured at 1 after the fix, 899 before.
  expect(
    reported.length,
    `${reported.length} time reports for a single question - one flush per question is the contract, anything more is per-render effect churn writing to the database`,
  ).toBeLessThanOrEqual(3);

  // OVERVIEW_POLL_MS is 20s, so a 15s dwell allows the effect's own immediate fetch on mount
  // and nothing else. 4 leaves room for the submit-driven refresh and a phase settle.
  // Measured at 2 after the fix, 903 before.
  expect(
    overviewFetches,
    `${overviewFetches} GET /exam/overview in ${DWELL_MS}ms against a declared 20000ms poll interval - the poll effect is re-installing its interval on every render`,
  ).toBeLessThanOrEqual(4);
});
