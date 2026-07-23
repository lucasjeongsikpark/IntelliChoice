import type { EmailApprovalInterrupt } from "../types";

interface Props {
  pending: EmailApprovalInterrupt;
  busy: boolean;
  onApprove: (approved: boolean) => void;
}

export function EmailApprovalModal({ pending, busy, onApprove }: Props) {
  return (
    <div className="modal-overlay">
      <div className="modal">
        <h2>Send to an administrator?</h2>
        <p className="dim">
          SPEC §5.1.4: no email is sent without your approval. Review the draft below.
        </p>
        <div className="email-preview">
          <strong>Subject</strong>
          <pre>{pending.email_subject}</pre>
          <strong>Body</strong>
          <pre>{pending.email_body}</pre>
        </div>
        <div className="modal-actions">
          <button className="secondary" disabled={busy} onClick={() => onApprove(false)}>
            Decline
          </button>
          <button disabled={busy} onClick={() => onApprove(true)}>
            Approve &amp; send
          </button>
        </div>
      </div>
    </div>
  );
}
