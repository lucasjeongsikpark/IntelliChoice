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
}: Props) {
  return (
    <div className="panel">
      <h1>Ready to learn</h1>
      <p className="subtitle">
        Signed in as <strong>{sub}</strong> ({role}).
      </p>
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
