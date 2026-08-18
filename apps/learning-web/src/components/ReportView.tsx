import { RichText } from "./RichText";
import { groupSkillsByBand, joinSkillNames } from "../lib/masteryBands";
import type { StudentReport } from "../types";

interface Props {
  report: StudentReport | null;
  busy: boolean;
  error: string | null;
  onGenerate: () => void;
}

const _FACT_LABELS: Record<string, string> = {
  pre_raw_score: "Pre-exam score",
  post_raw_score: "Post-exam score",
  raw_gain: "Growth",
  overall_accuracy: "Overall accuracy",
  weak_skill_names: "Skills to strengthen",
  hint_count: "Hints used",
  solution_count: "Solutions viewed",
  // "Videos suggested", not "watched" - the counter increments when a video link is
  // *offered* (the choice was made), and nothing verifies playback. The results screen
  // already says "suggested" for the same number; a parent report must not claim more
  // than the student screen does (D-216).
  video_count: "Videos suggested",
  independent_correct_rate: "Independent correct rate",
  attempts_count: "Attempts",
  time_spent_minutes: "Time spent (minutes)",
  tutor_review_flagged: "Tutor review recommended",
};

/**
 * Facts whose value is a proportion in [0, 1] and must be read as a percentage.
 *
 * **This is a correctness fix, not formatting.** `formatFactValue` rendered every number the
 * same way, so a student opened their own report and read `Overall accuracy: 0.24` directly
 * above `Solved independently: 88%` — two renderings of the same kind of quantity, one of
 * them a number no child has a use for. Worse, `0.24` invites being read as 24 *of
 * something*, and the report is the artefact a parent trusts (SPEC §5.10.3 asks for
 * age-appropriate, growth-oriented language, which starts with the number being legible).
 *
 * Keyed by fact name rather than sniffed from the value: `raw_gain` of `0.5` is half a
 * question, not 50%, and a range check would silently convert it.
 */
const _RATE_FACTS = new Set(["overall_accuracy", "independent_correct_rate"]);

function formatFactValue(key: string, value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (Array.isArray(value)) return value.length > 0 ? value.join(", ") : null;
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    // Nested values here are `mastery_by_skill`-shaped: skill name -> weighted score in
    // [0, 1], so the same percentage rule applies and for the same reason.
    return entries.length > 0
      ? entries
          .map(([k, v]) => `${k}: ${typeof v === "number" ? formatRate(v) : v}`)
          .join("; ")
      : null;
  }
  if (typeof value === "number") {
    if (_RATE_FACTS.has(key)) return formatRate(value);
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function formatRate(value: number): string {
  return `${Math.round(value * 100)}%`;
}


/**
 * D-409: `mastery_by_skill` as two counted bands rather than a joined run-on.
 *
 * Returns `null` when there is nothing to show, so the fact disappears exactly as every other
 * `formatFactValue`-driven row does when its value is absent - a parent with no mastery data yet
 * should not read an empty heading.
 *
 * The count leads and the names follow: "Confident (12)" is the shape, and the names are the detail
 * for a parent who wants it. `weak_skill_names` keeps its own row too, because it is a fact in its
 * own right and removing it here would change what the report claims.
 */
function renderMasteryBands(label: string, facts: Record<string, unknown>) {
  const mastery = facts.mastery_by_skill;
  if (mastery === null || mastery === undefined || typeof mastery !== "object") return null;
  const table = mastery as Record<string, unknown>;
  if (Object.keys(table).length === 0) return null;
  const weakFact = facts.weak_skill_names;
  const weak = Array.isArray(weakFact) ? weakFact.filter((n): n is string => typeof n === "string") : [];
  const bands = groupSkillsByBand(table, weak);

  const rows: { band: string; names: string[] }[] = [
    { band: "Confident", names: bands.confident },
    { band: "Still practising", names: bands.practising },
  ];

  return (
    <li key="mastery_by_skill">
      {label}:
      <ul>
        {rows.map(({ band, names }) => {
          const joined = joinSkillNames(names);
          if (joined === null) return null;
          return (
            <li key={band}>
              {band} ({names.length}): {joined}
            </li>
          );
        })}
      </ul>
    </li>
  );
}

export function ReportView({ report, busy, error, onGenerate }: Props) {
  return (
    <div className="report-section">
      <h2>Student report</h2>
      <button onClick={onGenerate} disabled={busy}>
        {busy ? "Generating…" : report ? "Regenerate report" : "Generate report"}
      </button>
      {error && <p className="error">{error}</p>}

      {report && (
        <>
          <div className={`report-block${report.generated ? "" : " facts-only"}`}>
            <h3>Verified</h3>
            <ul>
              {Object.entries(_FACT_LABELS).map(([key, label]) => {
                /* D-409 (`AUD-L-10`): `mastery_by_skill` is the one fact whose value is not a
                   sentence. Measured on the live build at **39 skills** joined into a single
                   paragraph - `name: 80%; name: 60%; …` - on the artefact a parent trusts. The
                   numbers were already legible (`_RATE_FACTS` above), but 39 of them in a run-on
                   has no shape a parent can read.

                   Grouped into the two bands the *server* already classifies, via
                   `weak_skill_names`. Two rather than three, and no threshold in this app: see
                   `lib/masteryBands.ts` for why a middle cut would put a third definition of a
                   classification boundary on a parent-facing report. */
                if (key === "mastery_by_skill") {
                  return renderMasteryBands(label, report.verified_facts);
                }
                const formatted = formatFactValue(key, report.verified_facts[key]);
                if (formatted === null) return null;
                return (
                  <li key={key}>
                    {label}: {formatted}
                  </li>
                );
              })}
            </ul>
            {!report.generated && (
              <p className="dim">
                Facts-only summary (the personalized write-up couldn't be verified this
                time).
              </p>
            )}
          </div>
          <div className="report-block">
            <h3>Interpretation</h3>
            <p>
              <RichText text={report.interpretation_text} />
            </p>
          </div>
          <div className="report-block">
            <h3>Recommendations</h3>
            <p>
              <RichText text={report.recommendations_text} />
            </p>
          </div>
        </>
      )}
    </div>
  );
}
