/**
 * D-415: learning-web's first component test, and the properties it holds are all about *time*.
 *
 * Two of the four could not be walked in a browser at any reasonable cost - "nothing appears for the
 * first eight seconds" and "the button does not exist before the deadline" both need the clock driven
 * rather than waited on. The other two are cheap here and would be a full journey walk there.
 *
 * It also exercises the `setupFiles` mirrored into this app by D-413 before any component test
 * existed to need it: without RTL's `cleanup`, the second `render` in this file would leave the first
 * one's markup in `document.body` and the "not before the deadline" assertions would match the
 * previous test's DOM.
 */

import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { STALE_AFTER_MS } from "../api/stream";
import { CONNECT_EXIT_AFTER_MS, ConnectingPanel } from "./ConnectingPanel";

const exitButton = () => screen.queryByRole("button", { name: "Back to start" });

describe("ConnectingPanel", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  test("says it is connecting and offers nothing at first", () => {
    // The healthy case, which is the common one: milliseconds locally, up to 2.7s on staging. A
    // student must not be offered a way to discard a session that is loading fine.
    render(<ConnectingPanel onBackToStart={vi.fn()} />);
    expect(screen.getByText("Connecting…")).toBeTruthy();
    expect(exitButton()).toBeNull();
    expect(screen.queryByText(/taking longer/i)).toBeNull();
  });

  test("still offers nothing one millisecond before the deadline", () => {
    render(<ConnectingPanel onBackToStart={vi.fn()} />);
    act(() => void vi.advanceTimersByTime(CONNECT_EXIT_AFTER_MS - 1));
    expect(exitButton()).toBeNull();
  });

  test("reveals a way out, explained, once the wait is too long", () => {
    const onBackToStart = vi.fn();
    render(<ConnectingPanel onBackToStart={onBackToStart} />);

    act(() => void vi.advanceTimersByTime(CONNECT_EXIT_AFTER_MS));

    // The sentence before the button: at this point nothing is known to have failed, and a bare
    // button reads as "something is broken".
    expect(screen.getByText(/taking longer than usual/i)).toBeTruthy();
    const button = exitButton();
    expect(button).not.toBeNull();

    button?.click();
    expect(onBackToStart).toHaveBeenCalledTimes(1);
  });

  test("leaves no timer behind when the wait ends", () => {
    // The wait ending *is* this component unmounting - the snapshot arrived, or the stream errored
    // and the takeover screen replaced it. A surviving timer would set state on a dead tree.
    const { unmount } = render(<ConnectingPanel onBackToStart={vi.fn()} />);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  test("the deadline lands well inside the stream's own, or it would never render", () => {
    // Not a property of the component but of the number: past `STALE_AFTER_MS` the liveness timer
    // has already flipped the stream to `error` and the takeover screen has replaced this panel, so
    // a later deadline would be an escape hatch nobody could ever see.
    expect(CONNECT_EXIT_AFTER_MS).toBeLessThan(STALE_AFTER_MS / 2);
  });
});
