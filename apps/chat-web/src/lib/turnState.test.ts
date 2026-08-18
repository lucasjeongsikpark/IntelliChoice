/**
 * D-413: the predicate both the render gate and the deadline read.
 *
 * These cases are not decorative - two of them are the reason `AUD-CHAT-07` exists. "A response is
 * present but unfinished" is the state a checkpoint holds when a process dies mid-turn, and it is
 * *pending*, so a deadline that only looked at `response === null` would leave exactly that case
 * stuck forever. And `reason: undefined` (a session checkpointed before D-351) has to count as
 * finished, or every old turn in storage would be re-marked as lost on the next reload.
 */

import { describe, expect, test } from "vitest";
import { isFinishedTurn, isPendingTurn } from "./turnState";
import type { ChatTurn, TurnSnapshot } from "../types";

function snapshot(overrides: Partial<TurnSnapshot> = {}): TurnSnapshot {
  return {
    chat_session_id: "sess-1",
    citations: [],
    escalation_recommended: false,
    suggested_followups: [],
    reason: null,
    ...overrides,
  };
}

function turn(overrides: Partial<ChatTurn> = {}): ChatTurn {
  return { id: "turn-1", query: "What are the Saturday hours?", response: null, ...overrides };
}

describe("isFinishedTurn", () => {
  test("an in-flight snapshot with everything cleared is not finished", () => {
    expect(isFinishedTurn(snapshot())).toBe(false);
  });

  test("a server-set reason finishes the turn even with no answer text", () => {
    expect(isFinishedTurn(snapshot({ reason: "OUT_OF_SCOPE" }))).toBe(true);
  });

  test("a checkpoint from before the reason field existed counts as finished", () => {
    expect(isFinishedTurn(snapshot({ reason: undefined }))).toBe(true);
  });

  test.each([
    ["answer text", { answer: "Saturdays 9-1." }],
    ["an access hint", { access_hint: { message: "Sign in with a parent account." } }],
    ["a citation", { citations: [{} as TurnSnapshot["citations"][number]] }],
    ["an escalation recommendation", { escalation_recommended: true }],
    ["a pending interrupt", { pending_interrupt: { interrupt_type: "location_consent" as const } }],
  ])("%s finishes a turn whose reason is missing", (_label, overrides) => {
    expect(isFinishedTurn(snapshot({ reason: null, ...overrides }))).toBe(true);
  });
});

describe("isPendingTurn", () => {
  test("no response at all is pending - the ordinary in-flight turn", () => {
    expect(isPendingTurn(turn())).toBe(true);
  });

  test("a response that is present but unfinished is still pending", () => {
    // The process-died-mid-turn case. `Thinking…` is on screen *with* a response object.
    expect(isPendingTurn(turn({ response: snapshot() }))).toBe(true);
  });

  test("a finished response is not pending", () => {
    expect(isPendingTurn(turn({ response: snapshot({ answer: "Saturdays 9-1." }) }))).toBe(false);
  });

  test.each([
    ["failed", { error: "We can't reach the server right now." }],
    ["stopped", { cancelled: true, error: "You stopped this question." }],
    ["unresolved", { unresolved: true, error: "We lost track of this question." }],
  ])("a %s turn is not pending, so the deadline can never re-mark it", (_label, overrides) => {
    expect(isPendingTurn(turn(overrides))).toBe(false);
  });
});
