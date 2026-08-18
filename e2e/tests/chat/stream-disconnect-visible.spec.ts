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
 * learning-web has the reconnect control (D-216) and **no liveness timer either** - both apps
 * only wire `onopen`/`onerror`. So this file covers the half that was a genuine one-directional
 * gap; the liveness timer is a separate change to *both* apps, and it needs a server change
 * first, because the keep-alive is an SSE comment (`: keep-alive`) which fires no client event.
 * A timer keyed on "last event received" would therefore claim a disconnect during any normal
 * quiet period - making the indicator lie in the opposite direction, which is worse than the
 * silence being fixed here.
 *
 * What is asserted: the disconnect is stated in words a sighted reader can read, and there is a
 * control that gets the stream back. Not the dot - the dot was already there and was the
 * complaint.
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
 */

import { CHAT_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { SHAPES } from "../../fixtures/chat-shapes";
import { seedGuest } from "../../fixtures/session";
import { ask, stubChat } from "../../fixtures/stub-chat";

test("a dead stream says so in words, and offers a way back", async ({ page, audit }) => {
  // Aborting the stream is the point of the test, so its failures are expected noise.
  audit.allow({ failedRequests: true, consoleErrors: ["Failed to load resource"] });

  await seedGuest(page);
  await stubChat(page, { message: SHAPES["grounded answer"] });

  // Registered *after* `stubChat`, so it wins: Playwright runs the most recently added handler
  // first. The stream is refused outright, which is what a terminal failure looks like to
  // `EventSource` - a non-2xx or a dead socket, the case its own retry does not cover.
  const streamAttempts: string[] = [];
  await page.route("**/chat/sessions/*/stream**", (route) => {
    streamAttempts.push(route.request().url());
    return route.abort();
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

  // The control's whole purpose: a *new* connection attempt. Before D-403 there was no path to
  // one short of a full reload, because `EventSource` retries only after a successful
  // connection drops and a terminal failure is final.
  await expect
    .poll(() => streamAttempts.length, {
      timeout: 15_000,
      message: "Reconnect did not open a new stream, so the button is decorative",
    })
    .toBeGreaterThan(before);
});
