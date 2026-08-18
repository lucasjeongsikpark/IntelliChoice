import { useState } from "react";
import { ApprovalModal } from "../components/ApprovalModal";
import type { EmailApprovalInterrupt } from "../types";

/**
 * D-420/B4: the visitor's own addition to the draft, bounded to match the server.
 *
 * `EmailApprovalChoice.note` is `max_length=1000` and answers **422** past it rather than
 * truncating, so a textarea with no bound would let someone type a paragraph and get a validation
 * error for their trouble. Mirroring the number here means the limit is felt while typing instead of
 * on submit; the server's bound is still the one that decides, because a client-side `maxLength` is
 * a courtesy rather than a control.
 */
const MAX_NOTE_CHARS = 1000;

interface Props {
  pending: EmailApprovalInterrupt;
  busy: boolean;
  error?: string | null;
  onApprove: (approved: boolean, note?: string) => void;
}

export function EmailApprovalModal({ pending, busy, error, onApprove }: Props) {
  const [note, setNote] = useState("");
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
      {/* **D-420: the draft is read-only and this is the only editable field**, which is the
          decision rather than a limitation. The server composes the opening line, the question
          verbatim and the session id; a freely editable body would make "your original question is
          preserved" a convention that the first edit could remove. Whatever is typed here arrives
          under its own heading, quoted, so an administrator can tell it from the system's words. */}
      <label className="note-field" htmlFor="email-approval-note">
        Anything else the administrator should know? <span className="dim">(optional)</span>
      </label>
      <textarea
        id="email-approval-note"
        value={note}
        maxLength={MAX_NOTE_CHARS}
        rows={3}
        disabled={busy}
        placeholder="Optional - added to the message above"
        onChange={(event) => setNote(event.target.value)}
      />
      <div className="modal-actions">
        {/* Declining passes no note at all rather than an empty string: nothing is sent, so
            there is nothing for a note to be attached to, and a server that received one on a
            decline would be right to wonder which it should believe. */}
        <button className="secondary" disabled={busy} onClick={() => onApprove(false)}>
          Decline
        </button>
        <button disabled={busy} onClick={() => onApprove(true, note.trim() || undefined)}>
          Approve &amp; send
        </button>
      </div>
    </ApprovalModal>
  );
}
