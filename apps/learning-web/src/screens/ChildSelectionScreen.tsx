import type { ChildCandidate } from "../types";

interface Props {
  candidates: ChildCandidate[];
  onSelect: (studentId: string) => void;
  busy: boolean;
  /** Heading text. The default is the login/interrupt wording; the switcher overrides it. */
  title?: string;
  /**
   * When passed, the screen is dismissable. Omitted on the two paths that must resolve a
   * child before anything else can happen (login-time resolution and the in-session
   * `child_selection` interrupt) - there is nothing to go back *to* on either. The
   * switcher passes it, because backing out of a switch has to leave the current child
   * bound rather than unbind it.
   */
  onCancel?: () => void;
}

export function ChildSelectionScreen({
  candidates,
  onSelect,
  busy,
  title = "Who's learning today?",
  onCancel,
}: Props) {
  return (
    <div className="panel">
      <h1>{title}</h1>
      <div className="card-list">
        {candidates.map((c) => (
          <button
            key={c.student_external_id}
            className="card"
            disabled={busy}
            onClick={() => onSelect(c.student_external_id)}
          >
            <strong>{c.display_name}</strong>
            <span>
              Grade {c.grade} · {c.branch_name}
            </span>
          </button>
        ))}
      </div>
      {onCancel && (
        <button className="link" disabled={busy} onClick={onCancel}>
          Cancel
        </button>
      )}
    </div>
  );
}
