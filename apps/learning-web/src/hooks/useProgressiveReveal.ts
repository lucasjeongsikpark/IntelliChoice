import { useEffect, useRef, useState } from "react";

/**
 * Reveal an **already-complete, already-validated** reply a few characters at a time.
 *
 * The ask was "stream the answer instead of showing it finished". This is deliberately not
 * token streaming, and the distinction is a safety one rather than an implementation
 * shortcut.
 *
 * A tutor reply is checked for leaked answers before it is allowed to reach a student
 * (`answer_text_leaked` / the structured-output validation path - SPEC §5.25.3, §5.27).
 * That check runs on the whole reply. Streaming tokens as the model produces them would put
 * text in front of a child *before* anything had judged it, and the failure mode is
 * precisely the one the check exists to prevent: the answer arriving in the first sentence
 * and being read before the rest is refused. There is no way to un-show it.
 *
 * So the reply is validated first and then revealed. The student gets the same "it is
 * arriving" feel, and nothing is displayed that has not already passed the gate.
 *
 * Reveal is by wall-clock rather than per-frame count, so a slow frame does not slow the
 * text down, and `prefers-reduced-motion` shows it complete immediately - progressive text
 * is motion, and a reader who has asked for less of it should not have to wait for prose.
 */

/** Fast enough not to feel like waiting, slow enough to read as arriving. */
const CHARS_PER_SECOND = 900;

export function useProgressiveReveal(totalLength: number, enabled: boolean): number {
  const [revealed, setRevealed] = useState(enabled ? 0 : totalLength);
  const frameRef = useRef(0);

  useEffect(() => {
    if (!enabled) {
      setRevealed(totalLength);
      return;
    }

    const reduced =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setRevealed(totalLength);
      return;
    }

    let start = 0;
    const step = (timestamp: number) => {
      if (start === 0) start = timestamp;
      const elapsedSeconds = (timestamp - start) / 1000;
      const next = Math.min(totalLength, Math.floor(elapsedSeconds * CHARS_PER_SECOND));
      setRevealed(next);
      if (next < totalLength) frameRef.current = requestAnimationFrame(step);
    };

    setRevealed(0);
    frameRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frameRef.current);
  }, [totalLength, enabled]);

  return revealed;
}
