/**
 * D-413 (`AUD-CHAT-07`): a turn replayed by a reload, and the Stop button that did nothing.
 *
 * **Why these are unit tests.** `sse-reconnect.spec.ts` already walks the *happy* half in a real
 * browser - reload mid-turn, the stream's initial snapshot lands, the turn resolves. What it cannot
 * walk is the snapshot that never comes, because the property takes `REQUEST_TIMEOUT_MS` (55s) of
 * wall clock to observe and the harness cannot hold an SSE response open (D-403 measured a browser
 * control written on that assumption as flaky and deleted it). Fake timers make 55 seconds free.
 *
 * `EventSource` is not implemented by jsdom, so the fake below is the whole stream: "a snapshot
 * arrived" is something these tests state rather than wait for. It is deliberately local rather
 * than shared with `api/stream.test.ts`'s fake - that one drives *named* events to test the
 * liveness timer, this one drives `onmessage` snapshots, and a shared fixture would have to serve
 * both without either test saying so.
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { REQUEST_TIMEOUT_MS } from "../api/client";
import { isPendingTurn } from "../lib/turnState";
import { useChatSession } from "./useChatSession";
import type { ChatTurn, TurnSnapshot } from "../types";

const SESSION_ID = "sess-1";
const SUB = "student-ext-1";
const REPLAYED_ID = "turn-replayed";

/** The parts of `EventSource` `openSessionStream` touches, and nothing else. */
class FakeEventSource {
  static last: FakeEventSource | undefined;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  // A plain field rather than a `readonly url` parameter property: `erasableSyntaxOnly`
  // forbids TS-only syntax that emits runtime code (D-405 caught this the first time).
  url: string;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.last = this;
  }

  addEventListener(): void {}
  close(): void {}

  /** Deliver a snapshot the way `/stream` does on connect. */
  deliver(snapshot: TurnSnapshot): void {
    this.onmessage?.({ data: JSON.stringify(snapshot) });
  }
}

function snapshot(overrides: Partial<TurnSnapshot> = {}): TurnSnapshot {
  return {
    chat_session_id: SESSION_ID,
    citations: [],
    escalation_recommended: false,
    suggested_followups: [],
    reason: null,
    ...overrides,
  };
}

function pendingTurn(id = REPLAYED_ID): ChatTurn {
  return { id, query: "What are the Saturday hours?", response: null, error: null };
}

/** Put a transcript in `sessionStorage` the way a previous page life would have left it. */
function seed(turns: ChatTurn[]): void {
  sessionStorage.setItem("intellichoice.chat_session_id", SESSION_ID);
  sessionStorage.setItem("intellichoice.chat_owner", SUB);
  sessionStorage.setItem("intellichoice.chat_transcript", JSON.stringify(turns));
}

/**
 * A `fetch` that never answers but does honour its signal, like the real one - so an aborted
 * request rejects with `AbortError` and `postTurn`'s catch runs exactly as in production.
 */
function hangingFetch(): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(
    (_url: string, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () =>
          reject(new DOMException("The operation was aborted.", "AbortError")),
        );
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function cancelCalls(fetchMock: ReturnType<typeof vi.fn>, turnId: string): string[] {
  return fetchMock.mock.calls
    .map((call) => String(call[0]))
    .filter((url) => url.includes(`/turns/${turnId}/cancel`));
}

function mount() {
  return renderHook(() => useChatSession("tok", SUB));
}

describe("a turn replayed from storage after a reload", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.stubGlobal("EventSource", FakeEventSource);
    FakeEventSource.last = undefined;
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  test("reaches a retryable state at the deadline instead of pulsing forever", () => {
    seed([pendingTurn()]);
    const { result } = mount();

    // Before the deadline it is still `Thinking…`, which is correct: the graph may well be
    // working. Marking it early would contradict an answer that is about to arrive.
    act(() => void vi.advanceTimersByTime(REQUEST_TIMEOUT_MS - 1));
    expect(result.current.transcript[0].unresolved).toBeFalsy();

    act(() => void vi.advanceTimersByTime(1));
    const turn = result.current.transcript[0];
    expect(turn.unresolved).toBe(true);
    // `response: null` is what makes the bubble render at all - see the deadline's comment.
    expect(turn.response).toBeNull();
    expect(turn.error).toBeTruthy();
    // The one thing this state must not claim. A replayed turn shows `Thinking…` *because* the
    // question was sent, so "couldn't be sent" would be the `AEL-01` defect: a failure path
    // stating the opposite of what happened.
    expect(turn.error).not.toMatch(/sent/i);
  });

  test("clears an unfinished response, which is what makes the bubble render at all", () => {
    // The process-died-mid-turn case: the checkpoint holds a snapshot with everything cleared at
    // turn start, so `Thinking…` is on screen *with* a response object. Every failed-turn bubble
    // requires `!turn.response`, so leaving it would put the turn in a state that renders
    // nothing - a blank gap instead of a stuck one, which is worse.
    seed([{ ...pendingTurn(), response: snapshot({ client_turn_id: REPLAYED_ID }) }]);
    const { result } = mount();

    act(() => void vi.advanceTimersByTime(REQUEST_TIMEOUT_MS));

    expect(result.current.transcript[0].unresolved).toBe(true);
    expect(result.current.transcript[0].response).toBeNull();
  });

  test("a snapshot that arrives first wins, and the deadline then does nothing", () => {
    seed([pendingTurn()]);
    const { result } = mount();

    act(() => {
      FakeEventSource.last?.deliver(
        snapshot({ answer: "Saturdays 9-1.", reason: "ANSWER", client_turn_id: REPLAYED_ID }),
      );
    });
    act(() => void vi.advanceTimersByTime(REQUEST_TIMEOUT_MS * 2));

    const turn = result.current.transcript[0];
    expect(turn.response?.answer).toBe("Saturdays 9-1.");
    expect(turn.unresolved).toBeFalsy();
    expect(turn.error).toBeNull();
  });

  test("the deadline covers only the replayed turn, not one sent in this page life", async () => {
    seed([pendingTurn()]);
    hangingFetch();
    const { result } = mount();

    await act(async () => {
      void result.current.sendMessage("and Sunday?");
    });
    expect(result.current.transcript).toHaveLength(2);

    act(() => void vi.advanceTimersByTime(REQUEST_TIMEOUT_MS * 2));

    expect(result.current.transcript[0].unresolved).toBe(true);
    // The live turn is already bounded by its own `AbortSignal.timeout`; a second deadline here
    // would report the same failure twice, from two places, with two different wordings.
    expect(result.current.transcript[1].unresolved).toBeFalsy();
  });

  test("stopping it tells the server and marks the turn, where before nothing happened", () => {
    seed([pendingTurn()]);
    const fetchMock = hangingFetch();
    const { result } = mount();

    act(() => result.current.cancelTurn(REPLAYED_ID));

    const turn = result.current.transcript[0];
    expect(turn.cancelled).toBe(true);
    expect(turn.error).toBe("You stopped this question.");
    // D-402's endpoint, addressed by (session, turn) - which a replayed turn has, and which the
    // in-flight refs do not after a reload.
    expect(cancelCalls(fetchMock, REPLAYED_ID)).toHaveLength(1);
  });

  test("stopping it does not abort a different turn that is genuinely in flight", async () => {
    seed([pendingTurn()]);
    const fetchMock = hangingFetch();
    const { result } = mount();

    await act(async () => {
      void result.current.sendMessage("and Sunday?");
    });
    const liveId = result.current.transcript[1].id;

    act(() => result.current.cancelTurn(REPLAYED_ID));
    // Let any rejection from an aborted request settle before asserting.
    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.transcript[0].cancelled).toBe(true);
    // The previous version aborted `inFlightRef` unconditionally, so this turn - whose Stop was
    // never clicked - was the one that actually stopped.
    expect(result.current.transcript[1].cancelled).toBeFalsy();
    expect(result.current.transcript[1].error).toBeNull();
    expect(cancelCalls(fetchMock, liveId)).toHaveLength(0);
  });

  test("an answer that arrives after the deadline replaces the apology", () => {
    // Unlike a turn the visitor *stopped* - where a late answer stays suppressed because they
    // withdrew the question (D-381) - nobody withdrew this one. The answer is strictly better
    // than the apology, and the flag has to be cleared with it.
    seed([pendingTurn()]);
    const { result } = mount();

    act(() => void vi.advanceTimersByTime(REQUEST_TIMEOUT_MS));
    expect(result.current.transcript[0].unresolved).toBe(true);

    act(() => {
      FakeEventSource.last?.deliver(
        snapshot({ answer: "Saturdays 9-1.", reason: "ANSWER", client_turn_id: REPLAYED_ID }),
      );
    });

    const turn = result.current.transcript[0];
    expect(turn.response?.answer).toBe("Saturdays 9-1.");
    expect(turn.unresolved).toBe(false);
    expect(turn.error).toBeNull();
  });

  test("asking again clears the lost-turn state, so the retry shows as pending", async () => {
    // Found by re-reading the change rather than by a failing test: `retryTurn` cleared
    // `cancelled` and would have left `unresolved` set, so the retried turn would have run with
    // "We lost track of this question" still on screen and no `Thinking…` anywhere.
    seed([pendingTurn()]);
    hangingFetch();
    const { result } = mount();

    act(() => void vi.advanceTimersByTime(REQUEST_TIMEOUT_MS));
    expect(result.current.transcript[0].unresolved).toBe(true);

    await act(async () => {
      void result.current.retryTurn(REPLAYED_ID);
    });

    const turn = result.current.transcript[0];
    expect(turn.unresolved).toBe(false);
    expect(turn.error).toBeNull();
    expect(isPendingTurn(turn)).toBe(true);
  });

  test("the deadline leaves a turn the visitor already stopped alone", () => {
    seed([pendingTurn()]);
    hangingFetch();
    const { result } = mount();

    act(() => result.current.cancelTurn(REPLAYED_ID));
    act(() => void vi.advanceTimersByTime(REQUEST_TIMEOUT_MS * 2));

    const turn = result.current.transcript[0];
    expect(turn.cancelled).toBe(true);
    expect(turn.unresolved).toBeFalsy();
    // "You stopped this question." must survive: the visitor's own action outranks a timeout.
    expect(turn.error).toBe("You stopped this question.");
  });
});
