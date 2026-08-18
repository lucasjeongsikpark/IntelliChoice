/**
 * D-392: the calendar interrupt's three branches, and a download that actually downloads.
 *
 * The last never-walked path on the 2026-08-17 audit's list, and the file it tests **says outright
 * that it was never tested**. D-352 fixed two browser-fragility bugs in `downloadIcs` — the anchor
 * was never appended to the document, and `revokeObjectURL` ran synchronously on the line after
 * `click()`, before the browser had necessarily read the blob — and its own comment explains why
 * nothing caught them: *"Chromium tolerates both, which is why the e2e suite (Chromium-only) has
 * been asserting the button is visible and never that a download happens."*
 *
 * **This file does not verify that fix, and finding that out was the point of writing it.** The
 * plan was that `page.waitForEvent("download")` would fail without the appended anchor, and that
 * reading the bytes would fail against a synchronous `revokeObjectURL`. Measured instead: with
 * `downloadIcs` reverted to its pre-D-352 form, **both tests below still pass**. Chromium really
 * does tolerate both, exactly as D-352 said - so no Chromium-only assertion can hold that fix, and
 * the honest statement is that **D-352 remains unverified by this suite**, for a reason that is
 * about the suite's shape rather than about the test. Holding it needs a second browser engine,
 * which is a CI-cost decision rather than an assertion (OPEN_DECISIONS #13).
 *
 * **Update, D-397: the second engine was added, and it did not close this either.** Both tests are
 * now tagged `@browser` and also run on WebKit, which #13 recommended precisely because it is
 * strict about detached anchors and revoked object URLs. Re-measured with `downloadIcs` reverted:
 * **both pass on WebKit too.** That measurement has a positive control - changing the download
 * filename in the same edit fails the same spec with `Received: "PROOF-THE-EDIT-IS-LIVE.ics"` - so
 * the reverted code really was being served and this is a true negative, not a stale bundle. A
 * plausible reason, untested and recorded as a guess: Playwright drives downloads through the
 * automation protocol rather than the browser's ordinary download path, so this class may be
 * invisible to *every* Playwright engine rather than to Chromium in particular.
 *
 * So the paragraph above stands unedited and the remedy it named turned out not to be one. What
 * the WebKit project does buy is narrower and real: these paths now run on the engine every
 * iPhone and iPad uses.
 *
 * What these tests *do* hold, which is still more than "the button is visible": the control appears
 * when and only when a file exists, a real download fires with the right filename, and the bytes
 * are a well-formed VCALENDAR. A broken blob, a missing control, a wrong filename or truncated
 * content all fail here.
 *
 * The three branches are `google | ics | cancel` (`nodes.py:968`), and there is a fourth path worth
 * knowing about that this file does **not** cover: an `McpToolError` from `calendar.create_event`
 * falls back to generating the `.ics` (SPEC §5.29). Driving it means making the MCP call fail
 * server-side, which no browser test can do from the outside - recorded rather than skipped
 * silently.
 *
 * Every asserted string is quoted from `nodes.py`'s constants rather than paraphrased (D-386).
 */

import { CHAT_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { SHAPES } from "../../fixtures/chat-shapes";
import { seedGuest } from "../../fixtures/session";
import { ask, stubChat } from "../../fixtures/stub-chat";

const CALENDAR_QUESTION = "Add the parent session to my calendar";

// Without this the app renders sign-in and there is no composer to type into - which is how the
// first run of this file failed, with a 60s wait on a textarea that was never going to appear.
test.beforeEach(async ({ page }) => {
  await seedGuest(page);
});

/** Quoted from `chat_api/graph/nodes.py:199`. */
const CANCELLED = "Okay, nothing was added to your calendar.";

async function reachTheCalendarDialog(
  page: import("@playwright/test").Page,
  respond: (typeof SHAPES)[keyof typeof SHAPES],
) {
  // Stubbed to reach the dialog, exactly as `interaction.spec.ts` does: the local mock backend
  // does not classify this question as a calendar action, so the interrupt has to be supplied.
  // What is *not* stubbed is the part under test - `downloadIcs` builds the Blob and drives the
  // anchor for real.
  await stubChat(page, { message: SHAPES["calendar_action interrupt"], respond });
  await page.goto(CHAT_WEB);
  await ask(page, CALENDAR_QUESTION);
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: /add to your calendar\?/i }),
    "the calendar question did not pause for consent, so no branch below was reachable",
  ).toBeVisible({ timeout: 60_000 });
  return dialog;
}

test("@browser choosing .ics downloads a real file, not just a visible button", async ({
  page,
}) => {
  const dialog = await reachTheCalendarDialog(page, SHAPES[".ics result"]);
  await dialog.getByRole("button", { name: /\.ics|download/i }).click();

  const downloadButton = page.locator("button.ics-download");
  await expect(
    downloadButton,
    "the turn said a file was available and offered no way to get it",
  ).toBeVisible();

  // A real download event, not a visible button - the difference D-352's comment complained about.
  // It does *not* discriminate the appended anchor: see this file's header for the measurement.
  const [download] = await Promise.all([
    page.waitForEvent("download", { timeout: 30_000 }),
    downloadButton.click(),
  ]);

  expect(download.suggestedFilename()).toBe("intellichoice-event.ics");

  // Reading the bytes catches a truncated or empty file. It does not catch the early
  // `revokeObjectURL` either - Chromium had already read the blob by then in every run.
  const path = await download.path();
  expect(path, "the download produced no file on disk").toBeTruthy();
  const { readFileSync } = await import("node:fs");
  const contents = readFileSync(path, "utf-8");
  expect(contents.startsWith("BEGIN:VCALENDAR"), `not an iCalendar file: ${contents.slice(0, 60)}`)
    .toBe(true);
  expect(contents).toContain("BEGIN:VEVENT");
  expect(contents.trimEnd().endsWith("END:VCALENDAR")).toBe(true);
});

test("@browser cancelling adds nothing and says so", async ({ page }) => {
  const dialog = await reachTheCalendarDialog(page, SHAPES["calendar cancelled"]);
  await dialog.getByRole("button", { name: /not now|cancel|no thanks/i }).click();

  await expect(page.locator(".bubble").last()).toContainText(CANCELLED, { timeout: 60_000 });
  // The branch's whole point: nothing was created, so nothing is offered.
  await expect(
    page.locator("button.ics-download"),
    "the cancelled branch still offered a calendar file",
  ).toBeHidden();
  await expect(page.getByRole("dialog")).toBeHidden();
});
