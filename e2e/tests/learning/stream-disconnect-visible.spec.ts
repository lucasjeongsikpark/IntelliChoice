/**
 * D-427: the learning-web half of "a dead stream says so in words, and offers a way back".
 *
 * chat-web has had this spec since D-403; learning-web has had the *control* since D-216 and
 * never had the spec. D-417 §C7 named that asymmetry precisely - *"the banner appears" is
 * browser-testable and no learning-web spec asserts it today* - and D-427, re-reading C7
 * rather than re-litigating it, folded the one owed artifact into `PLAYWRIGHT-LANE`: write
 * **and run** it in a serialized browser-lane window, because a spec written outside one is an
 * unrun, coverage-shaped artifact. This is that file.
 *
 * What is asserted, and it is one direction only: with a snapshot already on screen and the
 * SSE stream terminally dead, the disconnect is stated in **words a sighted reader can read**,
 * and the control next to those words opens a *new* stream attempt. Not the connection dot -
 * the dot was always there and being colour-only was the original complaint (EDGE-CHAT-04).
 *
 * **What is deliberately not asserted, and re-filing it as missing coverage is the failure
 * mode C7's in-code comment exists to stop.** The complement - *"and the banner appears at no
 * other time"* - is testable nowhere cheaply. It needs a stream that opens and **stays** open;
 * `route.fulfill` cannot hold an SSE response open, and the browser control written on that
 * assumption for chat-web was measured flaky (1 pass / 2 failures in isolation, then a
 * full-suite failure) and deleted in D-403. The mock-`useLearningSession` route is what D-414
 * priced and C7 declined. Neither belongs here, and if the negative direction ever becomes
 * testable that is a new decision, not an addition to this file.
 *
 * **Why a 403 rather than `route.abort()`, which is what the chat spec uses.** Measured here
 * on 2026-08-26, both make the banner appear (~650-730ms), and only one of them leaves the
 * reconnect assertion meaning anything:
 *
 * - `route.abort()` is a *network* error, so `EventSource` reconnects on its own backoff:
 *   **1 -> 5 attempts over 12s of idle with the button never clicked.** Under it,
 *   "attempts grew after the click" is true whether or not the click did anything.
 * - a non-2xx response is **terminal** - the browser fails the connection permanently and
 *   never retries: **1 attempt, still 1 after 12s idle, exactly 2 after the click.**
 *
 * 403 is also the failure this product actually documents: both `useLearningSession`'s D-216
 * comment and `App.tsx`'s streamBanner comment name *"an expired token, a 403"* as the case
 * `EventSource`'s own retry does not cover, which is why the manual control exists at all.
 *
 * The snapshot does not come from the stream, which is what makes the kill point free to be
 * the *first* attempt: every REST action in `useLearningSession` calls `setSnapshot` with the
 * response body, and the stream only opens once `chooseStudent` has run `resolve_student`
 * (`checkpointReady`). So the walk below reaches Pre-exam over REST with the stream dead from
 * the first attempt on - which is D-216's premise stated as a test: the last snapshot stays on
 * screen, still actionable, and before D-216 said nothing about being stale.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";
import { PHASE_CHIP, chooseTopic, settleToInteractiveScreen, startSession } from "../../fixtures/learning-flow";

test.describe.configure({ timeout: 180_000 });

test("a dead learning stream says so in words, and offers a way back", async ({ page, audit }) => {
  // Refusing the stream is the subject of the test, so its 403 and the browser's console
  // complaint about it are expected noise rather than findings.
  audit.allow({ consoleErrors: ["Failed to load resource"], statuses: [403] });

  // Registered before the first navigation, so no attempt is ever missed - including the one
  // the stream effect makes the moment `checkpointReady` flips.
  const streamAttempts: string[] = [];
  await page.route("**/learning/sessions/*/stream**", (route) => {
    streamAttempts.push(route.request().url());
    return route.fulfill({ status: 403, contentType: "text/plain", body: "forbidden" });
  });

  // Its own student (D-443). Its own rather than `studentSseReconnect`'s in particular: that
  // spec asserts a *ceiling* on how often the app reopens `/stream` by itself, which is the
  // exact quantity this one distorts on purpose.
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentDisconnect);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);
  // A snapshot is on screen and the student can act on it, with the stream already dead - the
  // has-snapshot branch is the only one that renders the banner (with no snapshot the recovery
  // screen takes over instead, which is the state D-216 was *not* about).
  await expect(
    page.locator(PHASE_CHIP),
    "the walk never reached a phase over REST, so the banner's branch was never entered",
  ).toHaveText(/pre-exam/i, { timeout: 60_000 });

  const banner = page.getByRole("alert").filter({ hasText: /live updates are disconnected/i });
  await expect(
    banner,
    "the stream was dead and the only signal was the connection dot's colour - EDGE-CHAT-04",
  ).toBeVisible({ timeout: 30_000 });

  audit.note(`stream attempts before reconnect: ${streamAttempts.length}`);
  const before = streamAttempts.length;
  expect(before, "the stream was never attempted, so nothing was being tested").toBeGreaterThan(0);

  await banner.getByRole("button", { name: /reconnect/i }).click();

  // The control's whole purpose. A 403 is terminal for `EventSource`, so this number cannot
  // move on its own (measured: 1, still 1 after 12s of idle) - it moves because the button
  // bumped `streamNonce` and re-ran the stream effect, or it does not move at all.
  await expect
    .poll(() => streamAttempts.length, {
      timeout: 15_000,
      message: "Reconnect did not open a new stream, so the button is decorative",
    })
    .toBeGreaterThan(before);
  audit.note(`stream attempts after reconnect: ${streamAttempts.length}`);
});
