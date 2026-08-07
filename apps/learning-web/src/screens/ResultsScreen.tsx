import type { LearningGain } from "../types";

interface Props {
  gain: LearningGain;
  hintCount: number;
  solutionCount: number;
  videoCount: number;
  onDone: () => void;
  onViewDashboard: () => void;
}

export function ResultsScreen({
  gain,
  hintCount,
  solutionCount,
  videoCount,
  onDone,
  onViewDashboard,
}: Props) {
  const improved = gain.post_raw_score > gain.pre_raw_score;

  return (
    <div className="panel">
      <div className="gradient-bar" aria-hidden="true" />
      <h1>Nice work today!</h1>
      <p className="subtitle">
        You completed {gain.post_raw_score} of 10 on your post-exam
        {improved && ` — up from ${gain.pre_raw_score} on the pre-exam.`}
      </p>

      <div className="stat-grid">
        <div className="stat">
          <span className="stat-value">{gain.pre_raw_score}</span>
          <span className="stat-label">Pre-exam</span>
        </div>
        <div className="stat">
          <span className="stat-value">{gain.post_raw_score}</span>
          <span className="stat-label">Post-exam</span>
        </div>
        <div className="stat">
          <span className="stat-value">{Math.round(gain.independent_correct_rate * 100)}%</span>
          <span className="stat-label">Solved independently</span>
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat">
          <span className="stat-value">{hintCount}</span>
          <span className="stat-label">Hints used</span>
        </div>
        <div className="stat">
          <span className="stat-value">{solutionCount}</span>
          <span className="stat-label">Solutions viewed</span>
        </div>
        {/* "suggested", not "watched": the video intervention renders a link that opens
            YouTube in a new tab, and this counter increments when that link is *shown*.
            Nothing observes whether the student followed it, let alone watched anything.
            Noticed on staging 2026-08-07 - a run that only ever displayed the link reported
            "Videos watched: 1". The same count reaches the parent report, where claiming a
            child watched a video they never opened is the kind of small false statement that
            costs a parent's trust in every other number on the page. */}
        <div className="stat">
          <span className="stat-value">{videoCount}</span>
          <span className="stat-label">Videos suggested</span>
        </div>
      </div>

      {gain.unresolved_skills.length > 0 && (
        // Deliberately no skill names here (CLAUDE.md: internal skill ids stay
        // internal) - the progress dashboard resolves them to display names
        // server-side (services/history.py) for exactly this purpose.
        <p className="dim">
          {gain.unresolved_skills.length === 1
            ? "One more skill to strengthen"
            : `${gain.unresolved_skills.length} skills to strengthen`}{" "}
          — see the progress dashboard for details.
        </p>
      )}

      <button onClick={onDone}>Back to start</button>
      <button className="secondary" onClick={onViewDashboard}>
        View progress dashboard
      </button>
    </div>
  );
}
