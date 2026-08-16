import { useRef } from "react";
import { useFocusTrap } from "../hooks/useFocusTrap";
import type { ExamOverview } from "../types";

interface Props {
  overview: ExamOverview;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

function questionList(numbers: number[]): string {
  return numbers.join(", ");
}

// Lists unanswered/flagged items before finalize (ROADMAP S23) - driven entirely by the
// client-held `exam/overview` snapshot, not by parsing the finalize endpoint's 422 body,
// so the same list is visible before the student ever attempts to submit.
export function SubmitConfirmationModal({ overview, busy, onConfirm, onCancel }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  // D-375: this used to be an initial `cancelRef.current?.focus()` and nothing else. Two Tab
  // presses then reached the exam options behind the scrim, where `1`-`4` or Enter answers a
  // question the student cannot see while this dialog is still asking whether to submit.
  useFocusTrap(dialogRef);

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape" && !busy) onCancel();
  }

  const unanswered = overview.items
    .filter((item) => item.status !== "answered")
    .map((item) => item.display_order + 1)
    .sort((a, b) => a - b);
  const flagged = overview.items
    .filter((item) => item.status === "flagged")
    .map((item) => item.display_order + 1)
    .sort((a, b) => a - b);

  return (
    <div className="modal-backdrop">
      <div
        ref={dialogRef}
        tabIndex={-1}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="submit-confirm-title"
        onKeyDown={handleKeyDown}
      >
        <h2 id="submit-confirm-title">Submit exam?</h2>
        {unanswered.length > 0 ? (
          <p>
            {unanswered.length} question{unanswered.length === 1 ? "" : "s"} still need{" "}
            {unanswered.length === 1 ? "s" : ""} an answer: {questionList(unanswered)}. They'll
            be marked incorrect if you submit now.
          </p>
        ) : (
          <p>Every question has an answer. You're ready to submit.</p>
        )}
        {flagged.length > 0 && (
          <p>
            Flagged for review: question{flagged.length === 1 ? "" : "s"}{" "}
            {questionList(flagged)}.
          </p>
        )}
        <button type="button" onClick={onConfirm} disabled={busy}>
          {busy ? "Submitting…" : "Submit exam"}
        </button>
        <button
          type="button"
          className="secondary"
          onClick={onCancel}
          disabled={busy}
        >
          Keep working
        </button>
      </div>
    </div>
  );
}
