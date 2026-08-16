import { useEffect, useRef, type ReactNode } from "react";

const FOCUSABLE =
  "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])";

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
 *
 * **The paragraph above described a fix that was not implemented, and D-350 caught it live.**
 * "Could tab straight through to the page behind" was named as the defect being closed, but
 * only the *initial* focus move and `aria-modal` ever shipped - nothing kept focus inside.
 * Measured on staging with chrome-devtools: four `Tab` presses from inside the
 * location-consent dialog put focus on the "new chat" button behind the scrim, on the screen
 * whose next control sends real email. `aria-modal` hides the background from assistive
 * technology, which is why a screen-reader user was covered and a sighted keyboard user was
 * not; those are different guarantees and only one of them was in the code.
 *
 * A docstring asserting a property the code lacks is worse than no docstring: it is the
 * reason nobody re-checked. Both halves are real now - the Tab wrap below, and `inert` on the
 * page behind so a pointer cannot reach it either.
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
  /**
   * D-347: the failure of the action this dialog performs, rendered *inside* it.
   *
   * The page-level error banner lives in `.chat-page`, and `.modal-overlay` is
   * `position: fixed; inset: 0; z-index: 10` with a 40% scrim - so a failing `POST /respond`
   * set an error nobody could see. The visitor clicked "Approve & send", the dialog did not
   * move, and nothing appeared to happen at all. On the one screen in this product where the
   * action is sending real email, "nothing appeared to happen" is the worst available
   * outcome: the honest states are *sent* and *not sent*, and silence reads as neither.
   */
  error?: string | null;
}

export function ApprovalModal({ titleId, children, onDismiss, error }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const onDismissRef = useRef(onDismiss);
  onDismissRef.current = onDismiss;

  // Move focus inside on open and put it back where it came from on close, so a keyboard
  // user is not returned to the top of the document after approving or declining.
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    const first = dialog?.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? dialog)?.focus({ preventScroll: true });
    return () => previous?.focus?.({ preventScroll: true });
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onDismissRef.current();
        return;
      }
      if (event.key !== "Tab") return;

      // Focusable children are re-read on every Tab rather than captured on open, because
      // these dialogs change shape while they are up: `LocationConsentModal`'s "Share
      // location" button enables once a ZIP is typed, and D-347 added an error line.
      const dialog = dialogRef.current;
      if (dialog === null) return;
      const focusable = [...dialog.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
        (element) => !element.hasAttribute("disabled") && element.tabIndex !== -1,
      );
      if (focusable.length === 0) {
        // Nothing to cycle between, so hold focus on the dialog itself rather than let Tab
        // escape to the page behind.
        event.preventDefault();
        dialog.focus({ preventScroll: true });
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || active === dialog)) {
        event.preventDefault();
        last.focus({ preventScroll: true });
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus({ preventScroll: true });
      } else if (active !== null && !dialog.contains(active)) {
        // Focus was already outside when Tab was pressed - pull it back rather than let it
        // walk further away.
        event.preventDefault();
        first.focus({ preventScroll: true });
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // `inert` on everything behind the dialog: it removes those elements from the tab order and
  // from hit-testing at once, which a keydown handler cannot do for a mouse. Applied to
  // `#root`'s children other than this overlay's own subtree, so it composes with whatever the
  // app renders rather than depending on a particular DOM shape.
  useEffect(() => {
    const overlay = dialogRef.current?.closest(".modal-overlay") ?? null;
    const siblings = ([...(document.getElementById("root")?.children ?? [])] as HTMLElement[])
      .filter((element) => element !== overlay && !element.contains(overlay as Node));
    for (const element of siblings) element.inert = true;
    return () => {
      for (const element of siblings) element.inert = false;
    };
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
        {error && (
          <p className="error modal-error" role="alert">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
