import type { PendingInterrupt } from "../types";

interface Props {
  message: string | null | undefined;
  pendingInterrupt: PendingInterrupt | null | undefined;
  resolved: boolean;
  onAcknowledge: () => void;
  onAskBranchManager: () => void;
  onApproveEmail: (approved: boolean) => void;
  onBackToStart: () => void;
  busy: boolean;
}

export function AttendanceScreen({
  message,
  pendingInterrupt,
  resolved,
  onAcknowledge,
  onAskBranchManager,
  onApproveEmail,
  onBackToStart,
  busy,
}: Props) {
  const emailPreview = pendingInterrupt?.interrupt_type === "email_approval"
    ? pendingInterrupt.email_preview
    : null;

  return (
    <div className="panel">
      <h1>Attendance check</h1>
      <p className="message">{message}</p>

      {emailPreview && (
        <div className="email-preview">
          <p>
            <strong>To:</strong> {emailPreview.recipient}
          </p>
          <p>
            <strong>Subject:</strong> {emailPreview.subject}
          </p>
          <pre>{emailPreview.body}</pre>
          <button disabled={busy} onClick={() => onApproveEmail(true)}>
            Send verification email
          </button>
          <button className="secondary" disabled={busy} onClick={() => onApproveEmail(false)}>
            Don't send
          </button>
        </div>
      )}

      {!emailPreview && !resolved && (
        <>
          <button disabled={busy} onClick={onAskBranchManager}>
            Ask the Branch Manager to verify
          </button>
          <button className="secondary" disabled={busy} onClick={onAcknowledge}>
            Confirm I did not attend
          </button>
        </>
      )}

      {!emailPreview && resolved && (
        <button className="secondary" onClick={onBackToStart}>
          Back to start
        </button>
      )}
    </div>
  );
}
