import { useEffect, useRef, useState } from "react";

interface Props {
  // `null` when untimed (study phase never renders this component, but the exam-phase
  // policy field is nullable server-side too - see exam_policy.py) or before the first
  // overview fetch resolves.
  remainingSeconds: number | null;
  onExpire?: () => void;
}

// No backend push exists for the countdown (SPEC's "lazy check, no scheduler" posture,
// same as `flow.is_exam_expired`) - this ticks down locally between `remainingSeconds`
// prop updates (ExamScreen re-fetches `exam/overview` periodically) so the display stays
// smooth without hammering the server every second.
export function ExamTimer({ remainingSeconds, onExpire }: Props) {
  const [display, setDisplay] = useState<number | null>(remainingSeconds);
  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;
  const firedRef = useRef(false);

  useEffect(() => {
    setDisplay(remainingSeconds);
    if (remainingSeconds !== null && remainingSeconds > 0) firedRef.current = false;
  }, [remainingSeconds]);

  useEffect(() => {
    const id = window.setInterval(() => {
      setDisplay((prev) => (prev === null || prev <= 0 ? prev : prev - 1));
    }, 1000);
    return () => window.clearInterval(id);
  }, []);

  /**
   * D-391: expiry fires from an effect, and **not** from inside the `setDisplay` updater.
   *
   * Two things were wrong with calling it there, and the first walk of this path found both.
   * React runs updater functions during the render phase, so `onExpire()` - which is
   * `ExamScreen.handleExpire`, and calls `setStatusMessage`/`setModalOpen` - was a setState
   * into another component mid-render: "Cannot update a component (`ExamScreen`) while
   * rendering a different component (`ExamTimer`)". It happened to work and is the shape that
   * stops working under concurrent rendering.
   *
   * The worse one is the guard: the updater returned early on `prev <= 0`, so a countdown that
   * *arrives* at zero never fired at all. That is reachable by a plain reload after time ran
   * out - `remaining_seconds` comes back 0, nothing auto-finalizes, and `submit_answer` 409s
   * every attempt. Exactly the "unable to answer AND unable to submit" trap `ExamScreen`'s own
   * comment describes. Keying the effect on `display` covers both the tick to zero and the
   * arrival at zero, and `firedRef` still makes it once per countdown.
   */
  useEffect(() => {
    if (display === null || display > 0 || firedRef.current) return;
    firedRef.current = true;
    onExpireRef.current?.();
  }, [display]);

  if (display === null) return null;
  const minutes = Math.floor(display / 60);
  const seconds = display % 60;
  const urgent = display <= 60;
  // **Announce at milestones, not every second** (D-380).
  //
  // `aria-live="assertive"` interrupts whatever the screen reader is currently speaking, by
  // definition. Tied to a 1s interval it produced **sixty consecutive interruptions during
  // the last minute of a timed exam** - precisely when the student is trying to read the
  // question. The urgency was real and the delivery made the exam unusable for them.
  //
  // `polite` waits for a pause instead of cutting in, and the announcement is limited to the
  // 60/30/10-second marks, which is what a sighted student gets from glancing at a clock.
  // The visual `urgent` styling is unchanged - it costs nobody anything.
  const isMilestone = display === 60 || display === 30 || display === 10;

  return (
    <span
      className={`exam-timer${urgent ? " urgent" : ""}`}
      role="timer"
      aria-live={isMilestone ? "polite" : "off"}
      aria-label={`${minutes} minutes ${seconds} seconds remaining`}
    >
      {minutes}:{String(seconds).padStart(2, "0")}
    </span>
  );
}
