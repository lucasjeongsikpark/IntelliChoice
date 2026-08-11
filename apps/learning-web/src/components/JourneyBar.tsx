import type { StudyProgress } from "../types";

/**
 * D-272: "how much longer is this?", answered.
 *
 * A session is a 10-question pre-exam, then five skill lines of study, then a 10-question
 * post-exam - 25 to 40 questions - and nothing on screen said so. The student saw
 * "Practice question 4" with no denominator and no way to tell whether they were near the
 * end or a third of the way in.
 *
 * Two things are shown, and the split is the design rather than a compromise:
 *
 * 1. **Where in the session** - three named stages. Fixed, so it is always truthful, and it
 *    is what answers "when does this end".
 * 2. **Where in study** - "Skill 3 of 5", plus which try of the current one. Only rendered
 *    during study, because that is the only phase where it means anything.
 *
 * There is deliberately no single percentage. Rolling the two together would need a
 * question total, and the retry ladder makes that unknowable in advance - a bar that ran
 * backwards when a student needed an extra try would punish them for needing it, which is
 * the opposite of what a progress indicator is for.
 *
 * The stage names are the student's words, not the graph's. `pre_exam` / `post_exam` are
 * phases; "Warm-up" and "Check-in" are what they are for.
 */
const STAGES: { key: string; label: string; hint: string }[] = [
  { key: "pre_exam", label: "Warm-up", hint: "See what you already know" },
  { key: "study", label: "Practice", hint: "Work through your skills" },
  { key: "post_exam", label: "Check-in", hint: "See how much you grew" },
];

function stageIndex(phase: string): number {
  const found = STAGES.findIndex((stage) => stage.key === phase);
  // `completed` sits past the last stage, so everything reads as done.
  return found === -1 ? (phase === "completed" ? STAGES.length : 0) : found;
}

export function JourneyBar({
  phase,
  progress,
}: {
  phase: string;
  progress?: StudyProgress | null;
}) {
  const current = stageIndex(phase);
  const inStudy = phase === "study" && progress != null && progress.skills_total > 0;

  return (
    <div className="journey">
      <ol className="journey-stages">
        {STAGES.map((stage, index) => {
          const state = index < current ? "done" : index === current ? "current" : "upcoming";
          return (
            <li key={stage.key} className={`journey-stage ${state}`}>
              <span className="journey-marker" aria-hidden="true">
                {state === "done" ? "✓" : index + 1}
              </span>
              <span className="journey-stage-text">
                <span className="journey-stage-label">{stage.label}</span>
                <span className="journey-stage-hint">{stage.hint}</span>
              </span>
              {/* The visual state is colour and a glyph; this is the same fact in words,
                  so it is not carried by colour alone. */}
              <span className="sr-only">
                {state === "done" ? " (finished)" : state === "current" ? " (you are here)" : ""}
              </span>
            </li>
          );
        })}
      </ol>

      {inStudy && progress && (
        <div className="journey-study">
          <div className="journey-study-head">
            <span className="journey-study-skill">
              {progress.current_skill_name
                ? `Skill ${progress.current_skill_position ?? progress.skills_resolved + 1} of ${
                    progress.skills_total
                  } — ${progress.current_skill_name}`
                : `Skill ${progress.skills_resolved + 1} of ${progress.skills_total}`}
            </span>
            {/* Only shown from the second try onward. On the first one it would be a
                countdown to failure attached to a question the student has not seen yet. */}
            {progress.attempt_in_line > 1 && (
              <span className="journey-study-try">
                Try {progress.attempt_in_line} of {progress.max_attempts}
              </span>
            )}
          </div>
          <div
            className="journey-meter"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={progress.skills_total}
            aria-valuenow={progress.skills_resolved}
            aria-label={`${progress.skills_resolved} of ${progress.skills_total} skills finished`}
          >
            {Array.from({ length: progress.skills_total }, (_, index) => (
              <span
                key={index}
                className={`journey-meter-cell ${
                  index < progress.skills_resolved
                    ? "done"
                    : index === progress.skills_resolved
                      ? "current"
                      : ""
                }`}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
