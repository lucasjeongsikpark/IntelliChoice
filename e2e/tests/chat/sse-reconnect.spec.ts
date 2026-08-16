/**
 * What the SSE stream does to the transcript when it reconnects (D-348).
 *
 * chat had no SSE spec at all - every other chat spec stubs the stream with a static comment
 * frame, so the snapshot handler was the one piece of `useChatSession` that no browser test
 * ever exercised. That is exactly where two defects were living:
 *
 * 1. every snapshot was applied to `prev[prev.length - 1]`, whatever turn it described; and
 * 2. `/stream` emits its initial snapshot on *every* connect, so a reconnect during an
 *    in-flight turn painted the previous turn's answer under the new question.
 *
 * The reconnect is a real one - `page.reload()` re-opens the stream - but the *content* of
 * the initial frame is stubbed, because the thing under test is what the client does with a
 * frame that names an older turn, not whether `EventSource` retries (the browser's job, and
 * not ours to assert).
 *
 * Falsified while writing: reverting the handler to `prev[prev.length - 1]` fails the first
 * test. The second passes either way and that is expected - it exercises a single-turn
 * transcript, where "the last turn" and "the matching turn" are the same bubble. Its subject
 * is the blank-turn recovery, not the matching rule.
 */

import type { Page, Route } from "@playwright/test";

import { CHAT_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { SHAPES } from "../../fixtures/chat-shapes";
import { seedGuest } from "../../fixtures/session";
import { ask, stubChat } from "../../fixtures/stub-chat";

/**
 * A stream that emits whatever frames the test supplies and then stays open, so the client
 * sees a live connection rather than a closed one it would retry against.
 */
async function stubStreamFrames(page: Page, frames: unknown[]): Promise<void> {
  await page.route("**/chat/sessions/*/stream**", (route: Route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
      body: frames.map((frame) => `data: ${JSON.stringify(frame)}\n\n`).join("") + ": open\n\n",
    }),
  );
}

test.beforeEach(async ({ page }) => {
  await seedGuest(page);
});

test("a reconnect describing an earlier turn does not overwrite a later one", async ({
  page,
  audit,
}) => {
  // **The clobber reproduction, driven the way it actually happens.** `/stream` sends its
  // initial snapshot on every connect, and that snapshot describes whatever the checkpoint
  // currently holds - which after a `/respond`, or simply on a thread whose latest write is
  // older than the browser's last turn, is not the newest bubble. Before D-348 the client
  // applied it to `prev[prev.length - 1]` regardless.
  await stubChat(page, { message: SHAPES["grounded answer"] });
  await page.goto(CHAT_WEB);
  await ask(page, "First question");
  await expect(page.locator(".message-row.assistant .bubble").first()).toContainText(
    "Baton Rouge",
  );

  await page.route("**/chat/sessions/*/messages", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...SHAPES["grounded answer"],
        answer: "Volunteers apply through the branch coordinator.",
        citations: [],
        suggested_followups: [],
      }),
    }),
  );
  await ask(page, "Second question");
  await expect(page.locator(".message-row.assistant .bubble").nth(1)).toContainText(
    "Volunteers apply",
  );

  // The reconnect's initial snapshot names turn *one*.
  const firstTurnId = await page.evaluate(() => {
    const raw = sessionStorage.getItem("intellichoice.chat_transcript") ?? "[]";
    return (JSON.parse(raw) as { id: string }[])[0]?.id ?? "";
  });
  expect(firstTurnId, "the transcript should carry the client's own turn ids").not.toBe("");
  await stubStreamFrames(page, [
    {
      ...SHAPES["grounded answer"],
      answer: "REPLAYED FIRST TURN",
      citations: [],
      suggested_followups: [],
      client_turn_id: firstTurnId,
    },
  ]);
  await page.reload();

  const second = page.locator(".message-row.assistant .bubble").nth(1);
  await expect(second).toContainText("Volunteers apply");
  await expect(second).not.toContainText("REPLAYED FIRST TURN");
  // And it did land where it belonged rather than being silently discarded.
  await expect(page.locator(".message-row.assistant .bubble").first()).toContainText(
    "REPLAYED FIRST TURN",
  );
  audit.note("a reconnect snapshot for turn one updated turn one and left turn two alone");
});

test("reloading mid-turn resolves the turn instead of leaving it blank", async ({
  page,
  audit,
}) => {
  // The other half. `journey-chat.spec.ts` reloads only *after* an answer arrives, so the
  // interesting case - a turn still in flight when the tab reloads - had never been walked.
  // On reload the transcript is replayed from storage with `response: null`, and the
  // stream's initial snapshot is the only thing that can finish it.
  await stubChat(page, { message: SHAPES["grounded answer"] });
  await page.goto(CHAT_WEB);
  await ask(page, "What are the Saturday hours?");
  await expect(page.locator(".message-row.assistant .bubble").first()).toContainText(
    "Baton Rouge",
  );

  const turnId = await page.evaluate(() => {
    const raw = sessionStorage.getItem("intellichoice.chat_transcript") ?? "[]";
    const turns = JSON.parse(raw) as { id: string; response: unknown }[];
    // Blank the response to reproduce "reloaded while this turn was still running".
    const blanked = turns.map((t, i) => (i === 0 ? { ...t, response: null, error: null } : t));
    sessionStorage.setItem("intellichoice.chat_transcript", JSON.stringify(blanked));
    return turns[0].id;
  });

  await stubStreamFrames(page, [
    {
      ...SHAPES["grounded answer"],
      answer: "Recovered from the checkpoint.",
      client_turn_id: turnId,
    },
  ]);
  await page.reload();

  const bubble = page.locator(".message-row.assistant .bubble").first();
  await expect(bubble).toContainText("Recovered from the checkpoint.");
  await expect(bubble).not.toHaveText("Thinking…");
  audit.note("a turn left in flight by a reload was completed by the stream's initial frame");
});
