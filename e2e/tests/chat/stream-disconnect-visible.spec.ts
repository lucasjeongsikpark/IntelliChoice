/**
 * D-403: a dead stream is visible and recoverable, not a pixel of hue.
 *
 * Three findings from the 2026-08-17 audit, and they are one defect wearing three numbers:
 * `EDGE-CHAT-02` ("the connection indicator stays green through a full network partition"),
 * `AUD-CHAT-11` ("its wording is screen-reader-only") and `EDGE-CHAT-04` ("conveyed only to
 * screen readers and by an 8px colour-only dot").
 *
 * **The audit was wrong about one thing, and measuring it changed the work.** Its note reads
 * *"chat has no liveness timer and no reconnect control, where learning-web has both."*
 * learning-web had the reconnect control (D-216) and, when this file was written, no liveness
 * timer either - so this file covers the half that was a genuine one-directional gap.
 *
 * **The liveness-timer half is done, in both apps, and this header claimed the opposite until
 * 2026-08-26** (the stale clause D-450 found). It said "no liveness timer either - both apps
 * only wire `onopen`/`onerror`", and named the blocker: the keep-alive was an SSE *comment*
 * (`: keep-alive`) which fires no client event, so a timer keyed on "last event received"
 * would have expired on every normal quiet period. D-404 made the keep-alive a named event
 * (`event: keepalive`) and D-405 then added the timer to *both* apps -
 * `STALE_AFTER_MS = 40_000`, chat's own in `apps/chat-web/src/api/stream.ts`, started at
 * creation rather than on `onopen`. Nothing is owed there.
 *
 * What is asserted: the disconnect is stated in words a sighted reader can read, and there is a
 * control that gets the stream back. Not the dot - the dot was already there and was the
 * complaint.
 *
 * **Why a 403 rather than `route.abort()`, which is what this spec used until 2026-08-26.**
 * Both make the banner appear (measured here: ~110ms either way), and only one of them leaves
 * the reconnect assertion meaning anything. The old comment called an aborted request "what a
 * terminal failure looks like to `EventSource`", and that is backwards: an abort is a *network*
 * error, and the browser retries those on its own backoff whether or not a connection ever
 * succeeded. Only a non-2xx response fails the connection permanently. Measured in both
 * harnesses on 2026-08-26, with the button never clicked:
 *
 * - `route.abort()` in **this** harness: **1 attempt at the banner -> 4 after 12s of idle**
 *   (and 7 after the click). Under it, "attempts grew after the click" is true whether or not
 *   the click did anything - the assertion below could not fail.
 * - `route.abort()` in learning-web's harness (D-450, the measurement that indicted this
 *   file): the same shape, **1 -> 5 over 12s of idle**.
 * - a **403** in this harness: **1 attempt, still 1 after 12s of idle, exactly 2 after the
 *   click** - identical to learning-web's numbers, so the two apps' stream/hook architecture
 *   behaves the same way here as well as looking the same.
 *
 * 403 is also the failure this product actually documents: `useChatSession`'s D-403 comment
 * names *"an expired token, a 403"* as the terminal case `EventSource`'s own retry does not
 * cover, which is why the manual control exists at all.
 *
 * **What is deliberately *not* asserted here, and it was written and deleted rather than
 * skipped.** The obvious control - "no banner while the stream is healthy" - cannot be written in
 * this harness, and it took a flaky test to find out why. `stubChat` fulfils the stream with one
 * comment frame and then the response body **ends**, so the browser sees the connection close,
 * `EventSource` fires `onerror`, and the banner appears - correctly. Whether an assertion runs
 * before or after that is a race: measured at 1 pass, 2 failures over three runs in isolation,
 * and it failed the full suite after passing on its own.
 *
 * The app is right and the test's premise was wrong: there is no healthy long-lived stream to
 * observe, because `route.fulfill` cannot hold one open. The property is still worth pinning -
 * that the banner renders for `error` and nothing else - and it is a one-line component
 * assertion in a unit test, which is a third concrete use case for the frontend test tooling
 * OPEN_DECISIONS #14 is about (after `errors.ts`'s rules and `downloadIcs`'s DOM contract).
 * D-417 §C7 priced the mock-hook route and declined it; the negative direction becoming
 * testable would be a new decision, not an addition to this file.
 */

import { CHAT_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { SHAPES } from "../../fixtures/chat-shapes";
import { seedGuest } from "../../fixtures/session";
import { ask, stubChat } from "../../fixtures/stub-chat";

test("a dead stream says so in words, and offers a way back", async ({ page, audit }) => {
  // Refusing the stream is the point of the test, so its 403 and the browser's console
  // complaint about it are expected noise rather than findings.
  audit.allow({ consoleErrors: ["Failed to load resource"], statuses: [403] });

  await seedGuest(page);
  await stubChat(page, { message: SHAPES["grounded answer"] });

  // Registered *after* `stubChat`, so it wins: Playwright runs the most recently added handler
  // first. The stream is refused with a 403 - terminal for `EventSource` (see the header), which
  // is what makes the reconnect assertion below able to fail.
  const streamAttempts: string[] = [];
  await page.route("**/chat/sessions/*/stream**", (route) => {
    streamAttempts.push(route.request().url());
    return route.fulfill({ status: 403, contentType: "text/plain", body: "forbidden" });
  });

  await page.goto(CHAT_WEB);
  // The stream effect only opens once a turn exists (a fresh session has no checkpoint), so the
  // question is what makes the connection - and therefore the failure - reachable at all.
  await ask(page, "What are the Saturday hours?");

  const banner = page.getByRole("alert").filter({ hasText: /live updates are disconnected/i });
  await expect(
    banner,
    "the stream died and the only signal was the dot's colour - which is EDGE-CHAT-04",
  ).toBeVisible({ timeout: 30_000 });

  audit.note(`stream attempts before reconnect: ${streamAttempts.length}`);
  const before = streamAttempts.length;
  expect(before, "the stream was never attempted, so nothing was being tested").toBeGreaterThan(0);

  await banner.getByRole("button", { name: /reconnect/i }).click();

  // The control's whole purpose: a *new* connection attempt. A 403 is terminal, so this number
  // cannot move on its own (measured: 1, still 1 after 12s of idle) - it moves because the
  // button bumped `streamNonce` and re-ran the stream effect, or it does not move at all.
  await expect
    .poll(() => streamAttempts.length, {
      timeout: 15_000,
      message: "Reconnect did not open a new stream, so the button is decorative",
    })
    .toBeGreaterThan(before);
  audit.note(`stream attempts after reconnect: ${streamAttempts.length}`);
});
