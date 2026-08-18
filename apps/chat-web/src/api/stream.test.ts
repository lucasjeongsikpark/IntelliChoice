/**
 * D-405: the stream liveness timer — the assertion OPEN_DECISIONS #14 was blocking.
 *
 * `EventSource` fires `onerror` when the browser *notices* a drop. A silent network partition can
 * leave it believing the connection is fine, which is `EDGE-CHAT-02`: the indicator stayed on
 * "Live updates connected" through a full partition. W11 (D-403) shipped the reconnect control and
 * had to defer this, because the keepalive was an SSE *comment* and fired no client event - there
 * was nothing to time against. W12a (D-404) made it `event: keepalive`. This is the timer.
 *
 * **Why this is a unit test and not a browser test, measured rather than assumed.** The property
 * needs a stream that opens, stays open, and then goes quiet for 40s. `route.fulfill` cannot hold
 * an SSE response open - a browser control written on that assumption was measured flaky (1 pass /
 * 2 failures) and deleted in W11 - and a 40s timeout cannot be shortened from a browser test. Fake
 * timers make the whole thing deterministic and instant.
 *
 * `EventSource` is not implemented by jsdom, which is convenient rather than a limitation: the fake
 * below is fully controlled, so "a keepalive arrived" and "40 seconds passed" are things the test
 * states rather than hopes for.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { STALE_AFTER_MS, openSessionStream } from "./stream";

/** The parts of `EventSource` this module touches, and nothing else. */
class FakeEventSource {
  static last: FakeEventSource | undefined;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  closed = false;
  private listeners = new Map<string, Set<() => void>>();

  // A plain field, not a `public url` parameter property: this project's tsconfig sets
  // `erasableSyntaxOnly`, which forbids TS-only syntax that emits runtime code. The first build
  // after adding these tests caught it, which is itself the point - the test files are inside
  // `tsc -b` rather than beside it.
  url: string;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.last = this;
  }

  addEventListener(type: string, handler: () => void): void {
    const set = this.listeners.get(type) ?? new Set();
    set.add(handler);
    this.listeners.set(type, set);
  }

  close(): void {
    this.closed = true;
  }

  /** Drive a named event, as the server's `event: keepalive` frame would. */
  emit(type: string): void {
    for (const handler of this.listeners.get(type) ?? []) handler();
  }
}

describe("openSessionStream liveness", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal("EventSource", FakeEventSource);
    FakeEventSource.last = undefined;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  function open() {
    const states: string[] = [];
    const close = openSessionStream("session-1", null, () => {}, (s) => states.push(s));
    const source = FakeEventSource.last;
    if (!source) throw new Error("no EventSource was constructed");
    return { states, close, source };
  }

  it("reports error when nothing arrives for the stale window", () => {
    const { states, source } = open();
    source.onopen?.();
    expect(states).toEqual(["open"]);

    // One second short: still trusted. This half is what stops the indicator crying disconnect
    // during a normal pause, which would be worse than the silence it replaces.
    vi.advanceTimersByTime(STALE_AFTER_MS - 1000);
    expect(states).toEqual(["open"]);

    vi.advanceTimersByTime(1000);
    expect(states).toEqual(["open", "error"]);
  });

  it("a keepalive keeps a quiet stream trusted indefinitely", () => {
    const { states, source } = open();
    source.onopen?.();

    // Six windows' worth of time with a keepalive every 15s, as the server actually sends them.
    // Before D-404 this was impossible to express: the keepalive was a comment and arrived as
    // nothing at all, so any timer would have expired here and reported a healthy stream dead.
    for (let elapsed = 0; elapsed < STALE_AFTER_MS * 6; elapsed += 15_000) {
      vi.advanceTimersByTime(15_000);
      source.emit("keepalive");
    }

    expect(states, "a live-but-quiet stream was reported as disconnected").toEqual(["open"]);
  });

  it("a snapshot also counts as proof of life", () => {
    const { states, source } = open();
    source.onopen?.();

    vi.advanceTimersByTime(STALE_AFTER_MS - 1000);
    source.onmessage?.({ data: JSON.stringify({ chat_session_id: "session-1" }) });
    vi.advanceTimersByTime(STALE_AFTER_MS - 1000);

    expect(states, "a stream delivering snapshots was reported as disconnected").toEqual(["open"]);
  });

  it("an unparsable frame still counts as proof of life", () => {
    // The frame is skipped (D-216) but the bytes arrived, so the connection is demonstrably up.
    // Counting only *parsable* frames would report a server sending malformed snapshots as
    // disconnected, which points the reader at the network instead of at the payload.
    const { states, source } = open();
    source.onopen?.();

    vi.advanceTimersByTime(STALE_AFTER_MS - 1000);
    source.onmessage?.({ data: "not json" });
    vi.advanceTimersByTime(STALE_AFTER_MS - 1000);

    expect(states).toEqual(["open"]);
  });

  it("tearing the stream down cancels the timer", () => {
    const { states, close, source } = open();
    source.onopen?.();
    close();

    vi.advanceTimersByTime(STALE_AFTER_MS * 2);

    expect(source.closed).toBe(true);
    expect(
      states,
      "a closed stream reported a disconnect - the timer outlived the consumer, so a component " +
        "that has unmounted gets a state update and a banner for a stream nobody is watching",
    ).toEqual(["open"]);
  });

  it("a connect that never opens is reported too", () => {
    // The timer starts at construction, not at `onopen`. A connect that hangs with no response
    // produces neither `onopen` nor `onerror`, and before this the indicator sat on "connecting"
    // forever - the same indefinite-state defect D-350 fixed for a different cause.
    const { states } = open();

    vi.advanceTimersByTime(STALE_AFTER_MS);

    expect(states).toEqual(["error"]);
  });
});
