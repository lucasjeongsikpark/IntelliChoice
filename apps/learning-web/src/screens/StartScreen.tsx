interface Props {
  sub: string;
  role: string;
  studentId: string | null;
  onStart: () => void;
  onViewDashboard: () => void;
  onLogout: () => void;
  busy: boolean;
  error: string | null;
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
      <button className="link" onClick={onLogout}>
        Sign out
      </button>
    </div>
  );
}
