import { useEffect, useRef } from "react";
import { useFocusTrap } from "../hooks/useFocusTrap";
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

/**
 * What to call the evidence list, per narrative stage (U3/D-325).
 *
 * The header used to be the constant "Why this is your next step", which is true of the three
 * narratives that precede work and false of the one that follows it: a `post_outro` fires
 * after the post-exam, when there is no next step - it is a summary of what just happened.
 * The snapshot carried the text and its evidence but never which stage produced them, so the
 * client had no way to tell the two situations apart and printed the forward-looking wording
 * over both.
 *
 * Unknown and absent stages fall back to the neutral wording rather than guessing, so an
 * older server (which sends no stage) reads as it always did.
 */
const EVIDENCE_TITLE: Record<string, string> = {
  pre_intro: "Why this is your next step",
  pre_outro: "Why this is your next step",
  study_step: "Why this is your next step",
  study_outro: "Why this is your next step",
  post_outro: "What this session showed",
};

const NEUTRAL_EVIDENCE_TITLE = "How we personalized this";

interface Props {
  narrative: string;
  evidence: string[];
  /** The stage that produced `narrative`; absent when the server did not say. */
  stage?: string | null;
  onContinue: () => void;
}

export function StageTransitionScreen({ narrative, evidence, stage, onContinue }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);

  // D-375: this was an initial focus move and nothing else, so Tab walked straight onto the
  // screen underneath - "still mounted and still focusable without this", as the comment it
  // replaces correctly observed, and then only solved for the first keystroke. The trap also
  // restores focus on close, which the single `focus()` never did.
  useFocusTrap(dialogRef);

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
    <div
      ref={dialogRef}
      tabIndex={-1}
      className="narrative-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="narrative-text"
    >
      <div className="narrative-card">
        <div className="gradient-bar" aria-hidden="true" />

        <p className="narrative-text" id="narrative-text">
          <RichText text={narrative} />
        </p>

        {evidence.length > 0 && (
          <section className="narrative-evidence">
            <h2 className="narrative-evidence-title">
              {(stage && EVIDENCE_TITLE[stage]) ?? NEUTRAL_EVIDENCE_TITLE}
            </h2>
            <ul className="narrative-evidence-list">
              {evidence.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </section>
        )}

        <button className="narrative-continue" onClick={onContinue}>
          Continue
        </button>
      </div>
    </div>
  );
}
