import { useEffect, useRef } from "react";
import { RichText } from "../components/RichText";

/**
 * The between-stage narrative: "here is what we are doing next, and why".
 *
 * **Why this is an overlay and not a screen.** The user asked for the narrative to be the
 * only thing on screen, with `Continue` moving on to the question. Rendering it *instead of*
 * the phase screen is exactly what AUD-F-21 and AUD-F-24 fixed, twice, and the reasons are
 * measured rather than theoretical (see the long comment in `App.tsx`): unmounting
 * `ExamScreen` fires its view-time cleanup early, flushing most of the dwell that parent
 * reports are built from, and re-runs `useState(0)` so the student is thrown back to
 * Question 1 with their selections gone.
 *
 * A `position: fixed` overlay gives the student what was asked for - nothing else is
 * visible or reachable until they press Continue - while the phase screen stays mounted and
 * at the same child index underneath it. The two requirements only look like they conflict.
 *
 * **Evidence is always visible.** It used to be a `<details>` the student had to open. Being
 * told *why* this stage was chosen is the point of the screen, and a disclosure triangle is
 * a good way to make sure nobody ever reads it.
 */

interface Props {
  narrative: string;
  evidence: string[];
  onContinue: () => void;
}

export function StageTransitionScreen({ narrative, evidence, onContinue }: Props) {
  const continueRef = useRef<HTMLButtonElement>(null);

  // Focus the only action, so Enter/Space works without reaching for the mouse and a screen
  // reader lands inside the dialog rather than wherever focus happened to be on the screen
  // underneath - which is still mounted and still focusable without this.
  useEffect(() => {
    continueRef.current?.focus();
  }, []);

  // Escape continues rather than doing nothing. There is only one way out of this dialog, so
  // the key that means "close" must take it - a dialog that swallows Escape reads as stuck.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onContinue();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onContinue]);

  // The page behind must not scroll while the overlay is up. Restores the previous value
  // rather than clearing it, so this composes with anything else that locks scrolling.
  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, []);

  return (
    <div className="narrative-overlay" role="dialog" aria-modal="true" aria-labelledby="narrative-text">
      <div className="narrative-card">
        <div className="gradient-bar" aria-hidden="true" />

        <p className="narrative-text" id="narrative-text">
          <RichText text={narrative} />
        </p>

        {evidence.length > 0 && (
          <section className="narrative-evidence">
            <h2 className="narrative-evidence-title">Why this is your next step</h2>
            <ul className="narrative-evidence-list">
              {evidence.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </section>
        )}

        <button ref={continueRef} className="narrative-continue" onClick={onContinue}>
          Continue
        </button>
      </div>
    </div>
  );
}
