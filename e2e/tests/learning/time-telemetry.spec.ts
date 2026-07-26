/**
 * AUD-F probe: what `elapsed_ms` values does the exam screen actually report?
 *
 * S36's AUD-L-14 found `time_spent_minutes` reading 0.0 next to `attempts_count: 26`, with
 * 140 item-state rows summing to 0 ms against 41,250 ms of real `response_time_ms` - and
 * attributed it to the report summing client telemetry. That says where the zero is read,
 * not where it comes from. This measures the client side, which only a browser can see.
 *
 * The mechanism under test: `ExamScreen`'s view-time effect resets `viewStartRef` in its
 * body and reports `Date.now() - viewStartRef.current` in its cleanup, and its dependency
 * list includes `onRecordTime` - which `App.tsx` passes as an inline arrow, so it is a new
 * identity on every render. If that is right, each report covers the gap between two
 * renders rather than the time the student spent on the question, and the values will be
 * tiny regardless of how long the student actually sits there.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";
import { chooseTopic, settleToInteractiveScreen, startSession } from "../../fixtures/learning-flow";

test.describe.configure({ timeout: 180_000 });

test("reported item time reflects how long the student actually spent", async ({ page, audit }) => {
  // CONFIRMED DEFECT (AUD-F-01): 885 reports in a 15s dwell, longest 94ms. Expected-to-fail
  // so the numbers keep being measured every run while the suite stays green; a Phase 0B
  // fix makes it pass unexpectedly, which is the signal to promote it to a regression test.
  test.fail();
  audit.allow({ statuses: [409], consoleErrors: ["Failed to load resource"], failedRequests: true });

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

  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);
  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });

  // Sit on one question for a known, deliberately long time and touch nothing. Any honest
  // dwell measurement has to notice 15 seconds.
  const DWELL_MS = 15_000;
  reported.length = 0;
  await page.waitForTimeout(DWELL_MS);
  // Navigating away is what flushes the view-time for the item being left.
  const nav = page.locator(".question-nav button, .exam-nav button");
  if ((await nav.count()) > 1) await nav.nth(1).click();
  await page.waitForTimeout(1000);

  const total = reported.reduce((sum, value) => sum + value, 0);
  const max = reported.length > 0 ? Math.max(...reported) : 0;
  audit.note(`${reported.length} time reports during a ${DWELL_MS}ms dwell`);
  audit.note(`reported values: total=${total}ms, max=${max}ms, sample=${JSON.stringify(reported.slice(0, 12))}`);

  // The student demonstrably spent DWELL_MS on one question. If no single report gets
  // anywhere near that, the client is not measuring dwell time at all - which is the
  // upstream half of AUD-L-14, and it is invisible from the database alone.
  expect(
    max,
    `the longest single reported dwell was ${max}ms after the student sat on one question for ${DWELL_MS}ms - the client reports render intervals, not time on task`,
  ).toBeGreaterThan(DWELL_MS * 0.5);
});
