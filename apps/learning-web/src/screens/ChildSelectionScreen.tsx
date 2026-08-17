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
  /**
   * The failure of the selection this screen performs, rendered inside it (D-380).
   *
   * **D-216 §5 fixed exactly this class and did not include this screen.** It gave `error`
   * to `AttendanceScreen` and `AssistancePanel` because "a refused/failed choice used to
   * show nothing at all", and this screen calls the same `session.respond`. So a parent
   * tapping their child, and hitting a 500, a dropped connection or the 401 D-375 now
   * handles, saw the card un-disable and nothing else - with no Cancel and no Back on the
   * two paths that deliberately omit `onCancel`.
   */
  error?: string | null;
}

export function ChildSelectionScreen({
  candidates,
  error,
  onSelect,
  busy,
  title = "Who's learning today?",
  onCancel,
}: Props) {
  return (
    <div className="panel">
      <h1>{title}</h1>
      {/* D-380: above the list, so it is visible without scrolling past the cards the parent
          just tried to tap. Same placement D-216 §5 chose for `AttendanceScreen`. */}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
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
