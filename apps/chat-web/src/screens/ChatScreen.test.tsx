/**
 * D-413 (`AUD-CHAT-07`): what the three end states actually say, and that only one of them says it.
 *
 * The first component test in this project. It exists because the two claims this session makes
 * about wording and about double-rendering are *render* properties, unreachable from the hook:
 *
 * - the unresolved bubble must not tell a visitor their message was never sent, because it was;
 * - and it must not appear *beside* the "couldn't be sent" bubble, since both carry an `error`
 *   string and two bubbles for one turn is `EDGE-CHAT-07`, filed against this very screen.
 *
 * Rendering the real `ChatScreen` rather than asserting the conditions by hand is the point: the
 * conditions are what is under test, and a hand-copied version of them would pass whatever they said.
 *
 * ---
 *
 * **D-414: the disconnect banner's render condition — the last of the four assertions
 * OPEN_DECISIONS #14 was raised for.** The browser suite already holds the *positive* direction
 * (`stream-disconnect-visible.spec.ts` sees the banner and proves Reconnect opens a new stream). The
 * half it cannot hold is *"for `error` and nothing else"*: showing that a **healthy** stream produces
 * no banner needs a stream that opens and stays open, and `route.fulfill` cannot hold an SSE response
 * open — a control written on that assumption was measured flaky (1 pass / 2 failures) and deleted in
 * D-403. Here the state is a prop, so the negative direction is a fact rather than a race, which is
 * D-221's rule that a gate's negative controls are a first-class number rather than an afterthought.
 */

import type { ComponentProps } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { ChatScreen } from "./ChatScreen";
import type { ChatTurn } from "../types";

type ScreenProps = ComponentProps<typeof ChatScreen>;

function renderScreen(transcript: ChatTurn[], overrides: Partial<ScreenProps> = {}) {
  const onCancel = vi.fn();
  const onReconnect = vi.fn();
  const noop = vi.fn();
  const { container } = render(
    <ChatScreen
      who="Guest"
      transcript={transcript}
      meta={null}
      busy={false}
      streamState="open"
      onReconnect={onReconnect}
      error={null}
      unknownInterrupt={null}
      onSend={noop}
      onRetry={noop}
      onCancel={onCancel}
      onEscalate={noop}
      onLogout={noop}
      onSignIn={noop}
      onNewSession={noop}
      {...overrides}
    />,
  );
  return { container, onCancel, onReconnect };
}

/** Every assistant-side bubble for the single turn under test. */
function assistantBubbles(container: HTMLElement): string[] {
  return [...container.querySelectorAll(".message-row.assistant")].map(
    (row) => row.textContent ?? "",
  );
}

const QUESTION = "What are the Saturday hours?";

describe("a turn that was lost to a reload", () => {
  const unresolved: ChatTurn = {
    id: "turn-1",
    query: QUESTION,
    response: null,
    error: "We lost track of this question when the page reloaded.",
    unresolved: true,
  };

  test("renders exactly one bubble, and it offers to ask again", () => {
    const { container } = renderScreen([unresolved]);
    const bubbles = assistantBubbles(container);
    expect(bubbles).toHaveLength(1);
    expect(bubbles[0]).toContain("We lost track of this question");
    expect(screen.getByRole("button", { name: "Ask again" })).toBeTruthy();
  });

  test("does not claim the message was never sent", () => {
    const { container } = renderScreen([unresolved]);
    expect(assistantBubbles(container)[0]).not.toContain("couldn't be sent");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  test("is not announced as an alert - it is an update, not an emergency", () => {
    const { container } = renderScreen([unresolved]);
    expect(container.querySelector(".message-row.assistant [role='alert']")).toBeNull();
    expect(container.querySelector(".message-row.assistant [role='status']")).not.toBeNull();
  });
});

describe("the states it has to stay distinct from", () => {
  test("a turn that really failed to send still says so, with Try again", () => {
    // The control. Without it, "does not contain couldn't be sent" would pass for a screen that
    // never renders that sentence at all.
    const { container } = renderScreen([
      {
        id: "turn-1",
        query: QUESTION,
        response: null,
        error: "We can't reach the server right now.",
      },
    ]);
    const bubbles = assistantBubbles(container);
    expect(bubbles).toHaveLength(1);
    expect(bubbles[0]).toContain("couldn't be sent");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  test("a stopped turn keeps its own wording", () => {
    const { container } = renderScreen([
      {
        id: "turn-1",
        query: QUESTION,
        response: null,
        error: "You stopped this question.",
        cancelled: true,
      },
    ]);
    const bubbles = assistantBubbles(container);
    expect(bubbles).toHaveLength(1);
    expect(bubbles[0]).toContain("You stopped this question.");
    expect(bubbles[0]).not.toContain("couldn't be sent");
  });
});

describe("the disconnect banner", () => {
  const banner = (container: HTMLElement) => container.querySelector(".stream-banner");

  test("appears on error, says what is degraded, and its Reconnect control is wired", () => {
    const { container, onReconnect } = renderScreen([], { streamState: "error" });

    const el = banner(container);
    expect(el).not.toBeNull();
    expect(el?.textContent).toContain("Live updates are disconnected");
    // `role="alert"` because it appears without the visitor doing anything (D-403).
    expect(el?.getAttribute("role")).toBe("alert");

    screen.getByRole("button", { name: "Reconnect" }).click();
    expect(onReconnect).toHaveBeenCalledTimes(1);
  });

  test.each(["connecting", "open"] as const)(
    "does not appear while the stream is %s",
    (streamState) => {
      // **The assertion this file was waiting for.** `EventSource` retries transient drops by
      // itself, so a banner on `connecting` would flash on every retry and train the visitor to
      // ignore the one case that needs their hand. A browser cannot hold a healthy SSE stream open
      // under the harness, so this direction was untestable until the state became a prop.
      const { container } = renderScreen([], { streamState });
      expect(banner(container)).toBeNull();
      expect(screen.queryByRole("button", { name: "Reconnect" })).toBeNull();
    },
  );

  test("does not steal the alert role from a turn that really failed", () => {
    // Both use `role="alert"`. On a healthy stream the only alert on screen should be the turn's.
    const { container } = renderScreen(
      [{ id: "turn-1", query: QUESTION, response: null, error: "We can't reach the server." }],
      { streamState: "open" },
    );
    const alerts = [...container.querySelectorAll("[role='alert']")];
    expect(alerts).toHaveLength(1);
    expect(alerts[0].textContent).toContain("couldn't be sent");
  });
});

describe("the connection dot", () => {
  const dotLabel = (container: HTMLElement) =>
    container.querySelector(".who .sr-only")?.textContent;

  test("reads idle before any turn exists, not connecting", () => {
    // D-343, measured live: `streamState` initialises to "connecting" while the effect that opens
    // the stream deliberately returns early until the first turn exists - so a fresh session
    // announced an indefinite "connecting" for a connection that had never been attempted. The
    // browser suite asserts the *other* direction (`accessibility.spec.ts` checks the dot is not
    // idle once a turn exists); this is the direction the defect was in.
    const { container } = renderScreen([], { streamState: "connecting" });
    expect(dotLabel(container)).toBe("Not connected yet");
  });

  test("follows the real stream state once a turn exists", () => {
    const turn: ChatTurn = { id: "turn-1", query: QUESTION, response: null, error: null };
    expect(dotLabel(renderScreen([turn], { streamState: "open" }).container)).toBe(
      "Live updates connected",
    );
    expect(dotLabel(renderScreen([turn], { streamState: "error" }).container)).toBe(
      "Live updates disconnected",
    );
  });
});

describe("the Stop button on a pending turn", () => {
  test("names the turn it belongs to", () => {
    // D-413: wired as `onClick={onCancel}` this receives a `MouseEvent`, and the hook would ask
    // the server to cancel a turn id that does not exist.
    const { onCancel } = renderScreen([
      { id: "turn-1", query: QUESTION, response: null, error: null },
    ]);
    screen.getByRole("button", { name: "Stop" }).click();
    expect(onCancel).toHaveBeenCalledWith("turn-1");
  });

  test("appears once per pending turn, so two waiting turns can be told apart", () => {
    // The state a reload plus a new question produces, and the reason `onCancel` needs an id.
    const { container } = renderScreen([
      { id: "turn-1", query: QUESTION, response: null, error: null },
      { id: "turn-2", query: "And Sunday?", response: null, error: null },
    ]);
    expect(assistantBubbles(container)).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: "Stop" })).toHaveLength(2);
  });
});
