import { useRef } from "react";
import { useFocusTrap } from "../hooks/useFocusTrap";
import type { EmailPreview, PendingInterrupt } from "../types";

interface Props {
  message: string | null | undefined;
  pendingInterrupt: PendingInterrupt | null | undefined;
  resolved: boolean;
  error: string | null;
  onAcknowledge: () => void;
  onAskBranchManager: () => void;
  onApproveEmail: (approved: boolean) => void;
  onBackToStart: () => void;
  busy: boolean;
}

/**
 * The email approval, as an actual dialog (D-381).
 *
 * **It was inline page flow, and that was measurable.** A live audit on 2026-08-16 found a
 * 775px document in a 577px viewport: "Send verification email" was clipped at the fold and
 * "Don't send" sat entirely outside it — `document.elementFromPoint` at its centre returned
 * `null`. Nothing indicated there was more below, so the screen read as having no controls at
 * all, and **the only partially visible control was the one that sends the email.**
 *
 * This is an external action under SPEC §5.1.4 — an email naming a minor, their grade and
 * their branch, sent to a branch manager. A gate whose decline button is off-screen is not a
 * gate. Three properties now hold, all of them borrowed rather than invented:
 *
 * - **It is a dialog.** `role="dialog"`, `aria-modal`, and `useFocusTrap` — the same shell
 *   `SubmitConfirmationModal` uses, so `inert` covers the page behind it too.
 * - **It scrolls.** The body is capped and scrolls; the action row is pinned below it, so the
 *   two buttons are visible whatever the email says.
 * - **Escape declines.** Not "closes": there is a pending `interrupt()` and dismissing it
 *   without answering would strand the graph. Declining is the safe answer, which is the rule
 *   chat-web's `ApprovalModal` already applies.
 */
function EmailApprovalDialog({
  preview,
  busy,
  onApproveEmail,
}: {
  preview: EmailPreview;
  busy: boolean;
  onApproveEmail: (approved: boolean) => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef);

  return (
    <div className="modal-backdrop">
      <div
        ref={dialogRef}
        tabIndex={-1}
        className="modal email-approval-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="email-approval-title"
        onKeyDown={(event) => {
          if (event.key === "Escape" && !busy) onApproveEmail(false);
        }}
      >
        <h2 id="email-approval-title">Send this to your Branch Manager?</h2>
        <div className="email-preview">
          <p>
            <strong>To:</strong> {preview.recipient}
          </p>
          <p>
            <strong>Subject:</strong> {preview.subject}
          </p>
          <pre>{preview.body}</pre>
        </div>
        <div className="modal-actions">
          <button disabled={busy} onClick={() => onApproveEmail(true)}>
            Send verification email
          </button>
          <button className="secondary" disabled={busy} onClick={() => onApproveEmail(false)}>
            Don't send
          </button>
        </div>
      </div>
    </div>
  );
}

export function AttendanceScreen({
  message,
  pendingInterrupt,
  resolved,
  error,
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

      {/* D-216: a failed resolve/respond used to show nothing at all on this screen -
          the click just didn't work. Same `error` the exam screen already renders. */}
      {error && <p className="error">{error}</p>}

      {!resolved && (
        <>
          {/* Second person, matching the message above them. The body used to talk about
              "the student" in the third person while this button said "I", which is two
              voices on one screen - see attendance.py's BLOCKED_MESSAGE. */}
          <button disabled={busy} onClick={onAskBranchManager}>
            Ask my Branch Manager to check
          </button>
          <button className="secondary" disabled={busy} onClick={onAcknowledge}>
            I did not come this week
          </button>
        </>
      )}

      {/* D-216: previously only the resolved state offered a way out, but the
          email-requested state says "once they confirm it, you can try again" and then
          left the student parked here with no action at all. Always reachable now.
          D-381: and no longer hidden while the approval is up - the dialog renders *over*
          this panel, so the exit is where it was before and is there again after. */}
      <button className="secondary" onClick={onBackToStart}>
        Back to start
      </button>

      {emailPreview && (
        <EmailApprovalDialog
          preview={emailPreview}
          busy={busy}
          onApproveEmail={onApproveEmail}
        />
      )}
    </div>
  );
}
