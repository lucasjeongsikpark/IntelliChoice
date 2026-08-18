import { useEffect, useState } from "react";

/**
 * D-415: what a student sees while the first snapshot of their session is on its way — and what
 * they can do about it once that has taken too long.
 *
 * **The wait was already bounded, and the bound was 40 seconds.** `App` renders this when a session
 * exists but no snapshot has arrived. The exits are a snapshot arriving, the request's own
 * `AbortSignal.timeout` (55s), or the stream's liveness timer (`STALE_AFTER_MS`, 40s) flipping
 * `streamState` to `error`, which replaces this panel with the "We lost the connection" screen and
 * its own way back. So nothing here is permanent — but for up to 40 seconds this was a panel with
 * one sentence on it and no control of any kind, which is `AUD-L-07`'s shape ("a screen with zero
 * controls") arrived at by waiting rather than by failing.
 *
 * **Why the exit is delayed rather than simply present.** This same panel renders during an entirely
 * healthy connect, which is milliseconds locally and was measured at up to **2.7 s** on staging
 * (D-317). A "Back to start" button sitting there from the first frame invites a student to destroy
 * a session that was loading correctly, and `endSession()` is not undoable. So the control is
 * revealed only once the wait is longer than any healthy connect has been measured to take.
 *
 * **The timer lives here, and that placement is the design.** `App` cannot compute "is the student
 * waiting?" as a boolean without duplicating `renderContent`'s branch order - and a boolean computed
 * a level up would keep counting while the dashboard is on screen, so a student who navigated in
 * later would find the escape hatch already revealed, having served its delay somewhere they never
 * saw. Mounting *is* the condition: this component exists exactly while the wait is real, and
 * unmounting resets it for nothing.
 */

/**
 * How long the wait runs before the student is offered a way out.
 *
 * Derived rather than picked: comfortably above the 2.7 s worst healthy connect measured on staging
 * (D-317 set its own gate to 5 s against that same number, and this is deliberately more
 * conservative because the cost of firing early is a discarded session rather than a delayed
 * render), and far enough below the stream's 40 s `STALE_AFTER_MS` that it is genuinely earlier than
 * the takeover screen it would otherwise duplicate.
 */
export const CONNECT_EXIT_AFTER_MS = 8000;

export function ConnectingPanel({ onBackToStart }: { onBackToStart: () => void }) {
  const [overdue, setOverdue] = useState(false);

  useEffect(() => {
    const id = window.setTimeout(() => setOverdue(true), CONNECT_EXIT_AFTER_MS);
    return () => window.clearTimeout(id);
  }, []);

  return (
    <div className="panel">
      <p>Connecting…</p>
      {overdue && (
        <>
          {/* Stated before the control, because a button with no explanation reads as "something
              is broken" - and at this point nothing is known to be. */}
          <p className="dim">This is taking longer than usual.</p>
          <button className="secondary" onClick={onBackToStart}>
            Back to start
          </button>
        </>
      )}
    </div>
  );
}
