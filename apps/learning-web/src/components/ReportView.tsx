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

function formatFactValue(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (Array.isArray(value)) return value.length > 0 ? value.join(", ") : null;
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    return entries.length > 0
      ? entries.map(([k, v]) => `${k}: ${typeof v === "number" ? v.toFixed(2) : v}`).join("; ")
      : null;
  }
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
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
                const formatted = formatFactValue(report.verified_facts[key]);
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
            <p>{report.interpretation_text}</p>
          </div>
          <div className="report-block">
            <h3>Recommendations</h3>
            <p>{report.recommendations_text}</p>
          </div>
        </>
      )}
    </div>
  );
}
