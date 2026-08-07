interface Props {
  sub: string;
  role: string;
  studentId: string | null;
  onStart: () => void;
  onViewDashboard: () => void;
  onLogout: () => void;
  busy: boolean;
  error: string | null;
  /**
   * True only for a parent with more than one linked child. The switcher lives here, on
   * the one screen where no learning session is in flight: `nodes.bind()` refuses to move
   * an existing session to a different student (AUD-X-01), so the parent's route to a
   * second child is a second session, and this is where a second session starts.
   */
  canSwitchChild?: boolean;
  onSwitchChild?: () => void;
  /**
   * Which child this session will be for, when a parent is signed in.
   *
   * The screen used to say only "Signed in as parent-ext-2 (parent)". A parent with two
   * linked children picked one on the previous screen and then got no confirmation of who
   * was selected - "Switch child" implied a selection existed without naming it. Starting a
   * session writes real attempts against a real child, so the wrong one is not a cosmetic
   * mistake.
   */
  studentName?: string | null;
}

export function StartScreen({
  sub,
  role,
  studentId,
  onStart,
  onViewDashboard,
  onLogout,
  busy,
  error,
  canSwitchChild = false,
  onSwitchChild,
  studentName = null,
}: Props) {
  return (
    <div className="panel">
      <h1>Ready to learn</h1>
      <p className="subtitle">
        Signed in as <strong>{sub}</strong> ({role}).
      </p>
      {studentName && (
        <p className="subtitle">
          This session is for <strong>{studentName}</strong>.
        </p>
      )}
      {error && <p className="error">{error}</p>}
      <button disabled={busy} onClick={onStart}>
        {busy ? "Starting…" : "Start learning session"}
      </button>
      {studentId && (
        <button className="secondary" onClick={onViewDashboard}>
          View progress dashboard
        </button>
      )}
      {canSwitchChild && onSwitchChild && (
        <button className="link" disabled={busy} onClick={onSwitchChild}>
          Switch child
        </button>
      )}
      <button className="link" onClick={onLogout}>
        Sign out
      </button>
    </div>
  );
}
