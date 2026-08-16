/**
 * Keyboard and screen-reader guarantees for chat-web, and the mobile layout baseline (D-350).
 *
 * Every assertion here corresponds to something that was measured broken on staging with
 * chrome-devtools rather than inferred from the code:
 *
 * - four `Tab` presses escaped the location-consent dialog onto "new chat" behind the scrim,
 *   while `ApprovalModal`'s own docstring said that was the defect it had fixed;
 * - `.message-list` had no `role`/`aria-live`, so an answer arriving announced nothing;
 * - the composer textarea had no accessible name (Chrome DevTools flagged it live);
 * - the connection dot said "connecting" for a stream that had never been attempted;
 * - `App.css` had no width media query, so nothing about 360px had ever been observed.
 *
 * The `@mobile` tag routes the last test to the second Playwright project; everything else
 * runs on the desktop project as usual.
 */

import { CHAT_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { SHAPES } from "../../fixtures/chat-shapes";
import { seedGuest } from "../../fixtures/session";
import { ask, stubChat } from "../../fixtures/stub-chat";

test.beforeEach(async ({ page }) => {
  await seedGuest(page);
});

test("focus cannot leave an open dialog", async ({ page, audit }) => {
  // **The live repro, automated.** Tab far more times than the dialog has controls; focus
  // must still be inside it. Pressing exactly four times would only re-test the one path that
  // was observed - a loop past the control count proves the wrap rather than a lucky count.
  await stubChat(page, { message: SHAPES["location_consent interrupt"] });
  await page.goto(CHAT_WEB);
  await ask(page, "Which branch is nearest to me?");
  await expect(page.getByRole("dialog")).toBeVisible();

  for (let i = 0; i < 12; i += 1) {
    await page.keyboard.press("Tab");
    const inside = await page.evaluate(
      () => document.activeElement?.closest("[role=dialog]") !== null,
    );
    expect(inside, `focus escaped the dialog after ${i + 1} Tab presses`).toBe(true);
  }

  // Shift+Tab wraps the other way too.
  for (let i = 0; i < 6; i += 1) {
    await page.keyboard.press("Shift+Tab");
  }
  const stillInside = await page.evaluate(
    () => document.activeElement?.closest("[role=dialog]") !== null,
  );
  expect(stillInside, "focus escaped backwards out of the dialog").toBe(true);
  audit.note("18 Tab/Shift+Tab presses, focus never left the dialog");
});

test("the page behind an open dialog is inert", async ({ page }) => {
  // The half a keydown handler cannot cover: a pointer. Without `inert` the header buttons
  // behind the 40% scrim were still clickable outside the overlay's own bounds.
  await stubChat(page, { message: SHAPES["location_consent interrupt"] });
  await page.goto(CHAT_WEB);
  await ask(page, "Which branch is nearest to me?");
  await expect(page.getByRole("dialog")).toBeVisible();

  const backgroundIsInert = await page.evaluate(() => {
    const overlay = document.querySelector(".modal-overlay");
    const siblings = [...(document.getElementById("root")?.children ?? [])].filter(
      (element) => element !== overlay && !element.contains(overlay),
    );
    return siblings.length > 0 && siblings.every((element) => (element as HTMLElement).inert);
  });
  expect(backgroundIsInert).toBe(true);
});

test("an arriving answer is announced, and the composer has a name", async ({ page, audit }) => {
  await stubChat(page, { message: SHAPES["grounded answer"] });
  await page.goto(CHAT_WEB);

  // The conversation is a live region before anything is in it, so the first answer is
  // announced too - wiring it only once a turn exists would miss exactly that case.
  const log = page.getByRole("log");
  await expect(log).toHaveAttribute("aria-live", "polite");
  await expect(log).toHaveAttribute("aria-label", /conversation/i);

  // The one control a visitor spends all their time in was the one with no accessible name.
  await expect(page.getByRole("textbox", { name: /ask a question/i })).toBeVisible();

  await ask(page, "What are the Saturday hours?");
  await expect(log).toContainText("Baton Rouge");
  audit.note("conversation is role=log/aria-live=polite; composer is nameable");
});

test("the connection state is readable without colour, and does not claim a stream it never opened", async ({
  page,
  audit,
}) => {
  await stubChat(page, { message: SHAPES["grounded answer"] });
  await page.goto(CHAT_WEB);

  // Before the first turn there is no stream: `useChatSession`'s effect returns early until
  // `streamReady`, but the state initialised to "connecting" and the dot said so. Verified
  // live before the fix.
  await expect(page.getByText("Not connected yet")).toBeAttached();

  await ask(page, "What are the Saturday hours?");
  // …and once a turn exists it reports the real state rather than a colour nobody can read.
  await expect(page.locator(".stream-dot")).not.toHaveClass(/idle/);
  const label = await page.locator(".who .sr-only").textContent();
  expect(label).toMatch(/connect/i);
  audit.note(`stream state announced as: ${label}`);
});

test("@mobile the chat screen is usable at a phone width", async ({ page, audit }) => {
  const width = page.viewportSize()?.width ?? 0;
  expect(width, "this test must run on the mobile project").toBeLessThan(500);

  await stubChat(page, { message: SHAPES["calendar_action interrupt"] });
  await page.goto(CHAT_WEB);

  // Nothing may scroll the page sideways - the failure mode a fixed 24px root padding, a
  // non-wrapping header and an 18px h1 produce together at 360px.
  const overflows = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  expect(overflows, "the page scrolls horizontally at this width").toBe(false);

  await ask(page, "Add the parent session to my calendar");
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();

  // The three-button row must stack rather than crush "Add to Google Calendar" to nothing.
  const buttons = dialog.locator(".modal-actions button");
  await expect(buttons).toHaveCount(3);
  const boxes = await buttons.evaluateAll((nodes) =>
    nodes.map((node) => node.getBoundingClientRect().top),
  );
  expect(new Set(boxes).size, "the modal buttons are still on one row").toBe(3);
  for (const name of ["Cancel", "Download .ics", "Add to Google Calendar"]) {
    await expect(dialog.getByRole("button", { name })).toBeVisible();
  }
  audit.note(`mobile ${width}px: no horizontal overflow, modal actions stacked`);
});
