import { useEffect, useRef, type ReactNode } from "react";

/**
 * The shared shell for the three approval dialogs (D-219).
 *
 * Every external action in this app goes through one of them - sending an email, adding a
 * calendar event, using the user's location - which is CLAUDE.md #4's human-approval rule.
 * Walked on staging 2026-08-08, all three were a plain `div.modal`: no `role`, no
 * `aria-modal`, no accessible name, and `document.activeElement` still on `<body>` while the
 * dialog was up. A screen-reader user got no announcement that anything had appeared, was
 * never moved into it, and could tab straight through to the page behind - on the one screen
 * in the product where a mis-click sends real email.
 *
 * `learning-web`'s `SubmitConfirmationModal` already did this correctly, so this is the
 * codebase disagreeing with itself rather than an open design question. Written once here
 * because there are three call sites, not two.
 */

interface Props {
  /** Must match the `id` of the heading passed in `children`. */
  titleId: string;
  children: ReactNode;
  /**
   * What Escape means. Always the *safe* choice for that dialog - decline the send, skip the
   * calendar add, withhold the location - never the one that acts. A dialog that swallows
   * Escape reads as stuck, but a dialog where Escape approves something is worse.
   */
  onDismiss: () => void;
}

export function ApprovalModal({ titleId, children, onDismiss }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const onDismissRef = useRef(onDismiss);
  onDismissRef.current = onDismiss;

  // Move focus inside on open and put it back where it came from on close, so a keyboard
  // user is not returned to the top of the document after approving or declining.
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    const first = dialog?.querySelector<HTMLElement>(
      "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])",
    );
    (first ?? dialog)?.focus({ preventScroll: true });
    return () => previous?.focus?.({ preventScroll: true });
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onDismissRef.current();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // The page behind must not scroll while a dialog is up. Restores the previous value rather
  // than clearing it, so this composes with anything else that locks scrolling.
  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, []);

  return (
    <div className="modal-overlay">
      <div
        className="modal"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        {children}
      </div>
    </div>
  );
}
