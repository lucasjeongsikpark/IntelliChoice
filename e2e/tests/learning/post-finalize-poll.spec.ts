/**
 * AUD-F-02 regression test (S41): after `POST /exam/finalize` succeeds the client must
 * stop talking to the exam endpoints.
 *
 * It used to keep polling `GET /exam/overview` and posting `/exam/items/{id}/time` into a
 * closed exam, and the server answers 409 to every one. Each failed fetch is a browser
 * console error, so a single journey accumulated dozens - a direct §2.6 criterion-3
 * failure ("zero console errors") independent of any user-visible symptom.
 *
 * Measured across the two fixes, because they are not the same defect:
 *
 *   before                        35 × 409 in a 96 ms burst
 *   after the AUD-F-01 fix alone   1 × 409  (POST .../time)
 *   after the AUD-F-02 guard       0
 *
 * That middle row is why the AUD-F-01 fix was not allowed to close this. The burst was
 * effect churn, but the last request is not: the view-time autosave flushes on unmount, and
 * the screen unmounts *because* the exam was finalized, so one 409 survives a fix that
 * removes every other one. `ExamScreen` now tracks the finalize in a ref and suppresses
 * both the flush and the poll tick. Confirmed to fail with that guard reverted.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";
import {
  answerWholeExam,
  chooseTopic,
  currentPhase,
  settleToInteractiveScreen,
  finalizeExam,
  startSession,
} from "../../fixtures/learning-flow";

test.describe.configure({ timeout: 300_000 });

test("no request 409s after the exam is finalized", async ({ page, audit }) => {
  // The 409s are this test's subject: it must be the assertion below that reports them,
  // with their count and timing, not a teardown check that only says "a request failed".
  audit.allow({ statuses: [409], consoleErrors: ["Failed to load resource"] });

  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);
  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });
  await answerWholeExam(page);

  const beforeFinalize = audit.network.length;
  await finalizeExam(page);

  // Sit still for a full overview poll period (OVERVIEW_POLL_MS is 20s) plus margin,
  // touching nothing. Anything that fires now is the client polling on its own.
  await page.waitForTimeout(25_000);
  const phase = await currentPhase(page);
  audit.note(`phase 25s after finalize: ${phase ?? "(no exam screen)"}`);

  const after = audit.network.slice(beforeFinalize);
  const conflicts = after.filter((entry) => entry.status === 409);
  const byPath = new Map<string, number>();
  for (const entry of conflicts) {
    const path = new URL(entry.url).pathname.replace(/\/sessions\/[^/]+/, "/sessions/{id}");
    byPath.set(`${entry.method} ${path}`, (byPath.get(`${entry.method} ${path}`) ?? 0) + 1);
  }
  for (const [path, count] of byPath) audit.note(`after finalize: ${count} × 409 ${path}`);

  // A leaked interval spreads evenly across the 25s; a remount burst clusters at the
  // start. The difference decides whether this is unbounded or bounded, so it is
  // measured rather than assumed.
  if (conflicts.length > 0) {
    const firstAt = conflicts[0].at;
    const lastAt = conflicts[conflicts.length - 1].at;
    audit.note(
      `409 window: first at +${firstAt}ms, last at +${lastAt}ms, spread ${lastAt - firstAt}ms over ${conflicts.length} requests`,
    );
    const finalizeAt = audit.network[beforeFinalize - 1]?.at ?? 0;
    const tail = conflicts.filter((entry) => entry.at > finalizeAt + 5000).length;
    audit.note(`409s still arriving >5s after finalize: ${tail}`);
  }
  audit.note(`total console errors this run: ${audit.console.filter((c) => c.type === "error").length}`);

  expect(
    conflicts.length,
    `the client made ${conflicts.length} requests the server rejected with 409 after finalize succeeded; each one is a console error`,
  ).toBe(0);
});
