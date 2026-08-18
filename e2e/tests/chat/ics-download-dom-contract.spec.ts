/**
 * D-399: OPEN_DECISIONS #13's residual — hold D-352 by watching the calls, not the browser.
 *
 * **Three attempts have now been made on this fix, and this is the first one that holds it.**
 * D-352 fixed two browser-fragility bugs in `downloadIcs`: the anchor was never appended to the
 * document, and `revokeObjectURL` ran synchronously on the line after `click()`. Its own comment
 * said Chromium tolerates both. V11 (D-392) wrote a real-download assertion and found it could not
 * discriminate the fix. W5 (D-397) added a WebKit project on the recommendation that WebKit is
 * strict about exactly these two mistakes — and **both specs passed on WebKit too**.
 *
 * The reason all of that failed is the same reason this works. Those tests asserted a *browser's
 * reaction* to broken code, and a browser is free to be forgiving; Playwright may also drive
 * downloads through the automation protocol rather than the ordinary download path, which would
 * make the class invisible to every engine it can drive. This test asserts the **code's contract
 * with the DOM** instead: was the anchor in `document.body` at the moment `click()` was called, and
 * did `revokeObjectURL` wait for a later task. *No engine can be lenient about a call that was
 * never made.*
 *
 * The user chose "the unit test" for this. It is written here rather than in jsdom because neither
 * frontend has any unit-test setup at all — no vitest, no jsdom, no testing-library — so the jsdom
 * route means introducing a test framework and CI wiring to a solo-maintained project, and
 * exporting `downloadIcs` out of `ChatScreen.tsx` purely to be imported by a test. This gets the
 * same property, against the real component in a real browser, for one spec file and no new
 * dependency. The framework is still worth having one day; it is not worth having *for this*.
 *
 * Both assertions were falsified against the pre-D-352 code before this file was kept.
 */

import { CHAT_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { SHAPES } from "../../fixtures/chat-shapes";
import { seedGuest } from "../../fixtures/session";
import { ask, stubChat } from "../../fixtures/stub-chat";

interface DownloadProbe {
  /** One entry per `click()` on an anchor carrying a `download` attribute. */
  clicks: { inDocument: boolean; download: string }[];
  /** Whether `revokeObjectURL` ran, and whether a macrotask had elapsed since the click. */
  revoked: boolean;
  revokedAfterATick: boolean;
}

declare global {
  interface Window {
    __icsProbe?: DownloadProbe;
  }
}

/**
 * Patch `HTMLAnchorElement.prototype.click` and `URL.revokeObjectURL` before any app code runs.
 *
 * The tick test is the subtle half. `revokedAfterATick` is set from a flag that a
 * `setTimeout(…, 0)` scheduled *during* the click turns on. The pre-D-352 shape calls
 * `revokeObjectURL` on the line after `click()` returns, which is still the same task, so that
 * flag is false when it runs. The D-352 shape defers with its own `setTimeout(…, 0)`, scheduled
 * after the click returns and therefore queued behind this one, so the flag is true. Comparing
 * timestamps instead would not discriminate them: the broken version also revokes "later", by
 * microseconds.
 */
async function installDownloadProbe(page: import("@playwright/test").Page): Promise<void> {
  await page.addInitScript(() => {
    const probe: DownloadProbe = { clicks: [], revoked: false, revokedAfterATick: false };
    window.__icsProbe = probe;
    let aTickHasPassed = false;

    const originalClick = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = function patchedClick(this: HTMLAnchorElement) {
      if (this.hasAttribute("download")) {
        probe.clicks.push({
          // The property under test: an anchor that is not in the document is not guaranteed to
          // do anything when clicked. Read at click time, because `downloadIcs` removes it again
          // immediately afterwards - reading later would see `false` for correct code.
          inDocument: document.body.contains(this),
          download: this.download,
        });
        aTickHasPassed = false;
        setTimeout(() => {
          aTickHasPassed = true;
        }, 0);
      }
      return originalClick.call(this);
    };

    const originalRevoke = URL.revokeObjectURL.bind(URL);
    URL.revokeObjectURL = (url: string) => {
      probe.revoked = true;
      probe.revokedAfterATick = aTickHasPassed;
      return originalRevoke(url);
    };
  });
}

test("@browser downloadIcs appends the anchor before clicking and revokes on a later tick", async ({
  page,
}) => {
  await installDownloadProbe(page);
  await seedGuest(page);
  await stubChat(page, {
    message: SHAPES["calendar_action interrupt"],
    respond: SHAPES[".ics result"],
  });
  await page.goto(CHAT_WEB);
  await ask(page, "Add the parent session to my calendar");

  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: /add to your calendar\?/i }),
    "the calendar question did not pause for consent, so the download was never reachable",
  ).toBeVisible({ timeout: 60_000 });
  await dialog.getByRole("button", { name: /\.ics|download/i }).click();

  const downloadButton = page.locator("button.ics-download");
  await expect(downloadButton).toBeVisible();
  await Promise.all([page.waitForEvent("download", { timeout: 30_000 }), downloadButton.click()]);

  // The deferred revoke has to be given its tick before the probe is read, or `revoked` is false
  // for correct code and this test fails the fix it exists to protect.
  await expect
    .poll(async () => (await page.evaluate(() => window.__icsProbe?.revoked)) === true, {
      timeout: 10_000,
      message: "revokeObjectURL was never called, so the blob URL leaks for the tab's lifetime",
    })
    .toBe(true);

  const probe = await page.evaluate(() => window.__icsProbe);
  expect(probe, "the probe never installed, so nothing below was measured").toBeTruthy();

  expect(
    probe!.clicks.length,
    "expected exactly one download anchor click for one .ics download",
  ).toBe(1);

  expect(
    probe!.clicks[0].inDocument,
    "the download anchor was clicked while detached from the document - the first half of what " +
      "D-352 fixed, which no browser assertion in this suite could see",
  ).toBe(true);

  expect(
    probe!.clicks[0].download,
    "the anchor carried the wrong filename, so this measured the wrong click",
  ).toBe("intellichoice-event.ics");

  expect(
    probe!.revokedAfterATick,
    "revokeObjectURL ran in the same task as click() - the second half of D-352. The browser is " +
      "not guaranteed to have read the blob yet, and on a stricter engine the file is empty",
  ).toBe(true);
});
