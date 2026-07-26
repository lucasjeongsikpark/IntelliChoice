/**
 * AUD-F probe: how many times does the learning app open its SSE stream while the student
 * does nothing?
 *
 * Surfaced by the capture fixture reporting 71 `net::ERR_ABORTED` requests against
 * `/learning/sessions/{id}/stream` in a single 38-second test - about two per second,
 * where `EventSource`'s own retry backoff is ~3s. Either the stream is being torn down and
 * recreated far more often than the hook intends, or the aborts are ordinary lifecycle
 * noise. Those have very different costs at 1,000 MAU, so this counts them over a fixed
 * idle window instead of arguing from the effect's dependency list.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";
import { chooseTopic, settleToInteractiveScreen, startSession } from "../../fixtures/learning-flow";

test.describe.configure({ timeout: 180_000 });

test("the SSE stream is not reopened repeatedly while the student sits still", async ({
  page,
  audit,
}) => {
  audit.allow({ failedRequests: true, consoleErrors: ["Failed to load resource"], statuses: [409] });

  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);
  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });

  // Count only what happens from here on, with no interaction at all.
  const mark = audit.network.length;
  const markedAt = audit.elapsed();
  await page.waitForTimeout(20_000);

  const after = audit.network.slice(mark);
  const streams = after.filter((entry) => entry.url.includes("/stream"));
  const aborted = audit.failedRequests.filter((entry) => entry.url.includes("/stream"));
  const window = audit.elapsed() - markedAt;

  audit.note(
    `${streams.length} /stream responses in ${window}ms of idle (${((streams.length / window) * 1000).toFixed(2)}/s)`,
  );
  audit.note(`aborted /stream requests over the whole test: ${aborted.length}`);

  // EventSource's default retry is ~3s, so even a stream that drops and reconnects
  // constantly should not exceed ~7 in 20s. Anything far above that is a reopen loop.
  expect(
    streams.length,
    `the SSE stream was (re)opened ${streams.length} times in ${window}ms with the student doing nothing`,
  ).toBeLessThanOrEqual(7);
});
