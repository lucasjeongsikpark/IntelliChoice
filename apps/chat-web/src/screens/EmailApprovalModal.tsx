import { ApprovalModal } from "../components/ApprovalModal";
import type { EmailApprovalInterrupt } from "../types";

interface Props {
  pending: EmailApprovalInterrupt;
  busy: boolean;
  error?: string | null;
  onApprove: (approved: boolean) => void;
}

export function EmailApprovalModal({ pending, busy, error, onApprove }: Props) {
  return (
    // Escape declines: the safe half of an approval whose other half sends real email.
    <ApprovalModal
      titleId="email-approval-title"
      error={error}
      onDismiss={() => onApprove(false)}
    >
      <h2 id="email-approval-title">Send to an administrator?</h2>
      {/* D-219: this read "SPEC §5.1.4: no email is sent without your approval." An
          internal specification section number, on the screen where a parent decides
          whether to send a message. The promise it makes is worth keeping; the citation
          is for the codebase, not the reader. */}
      <p className="dim">Nothing is sent without your approval. Review the draft below.</p>
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
    </ApprovalModal>
  );
}
