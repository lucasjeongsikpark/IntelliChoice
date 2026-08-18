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
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { ChatScreen } from "./ChatScreen";
import type { ChatTurn } from "../types";

function renderScreen(transcript: ChatTurn[], onCancel = vi.fn()) {
  const noop = vi.fn();
  const { container } = render(
    <ChatScreen
      who="Guest"
      transcript={transcript}
      meta={null}
      busy={false}
      streamState="open"
      onReconnect={noop}
      error={null}
      unknownInterrupt={null}
      onSend={noop}
      onRetry={noop}
      onCancel={onCancel}
      onEscalate={noop}
      onLogout={noop}
      onSignIn={noop}
      onNewSession={noop}
    />,
  );
  return { container, onCancel };
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
