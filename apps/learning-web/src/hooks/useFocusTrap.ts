import { useEffect, type RefObject } from "react";

const FOCUSABLE =
  "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])";

/**
 * Keep keyboard focus inside a dialog, and keep a pointer out of the page behind it.
 *
 * **Ported from chat-web's `ApprovalModal` (D-350), which is where this was written, argued
 * and measured (D-375).** learning-web's two modals shipped the half that looks like a focus
 * trap and is not: an initial focus move plus `aria-modal="true"`, with nothing keeping focus
 * inside. `aria-modal` hides the background from assistive technology, so a screen-reader
 * user was covered and a sighted keyboard user was not — different guarantees, only one of
 * them in the code, which is exactly the mistake chat's own docstring records catching live.
 *
 * **Why it matters more here than it did there.** Two Tab presses from "Submit exam?" put
 * focus on the exam options behind the scrim. The student presses `1`–`4` or Enter and
 * **answers a question they cannot see**, while a dialog asking whether to submit is still
 * up. On chat the equivalent reached a "new chat" button; here it reaches the scoring.
 *
 * **The duplication is deliberate and is the audit's own finding, stated rather than hidden.**
 * The right home for this is a shared TS package, which does not exist — D-219's `RichText`
 * carry-over is the same gap. Creating one changes both apps' builds, so it is a decision to
 * take on purpose rather than a side effect of a bug fix. Until then this file and
 * `chat-web/src/components/ApprovalModal.tsx` must be changed together.
 */
export function useFocusTrap(dialogRef: RefObject<HTMLElement | null>): void {
  // Move focus inside on open and put it back where it came from on close, so a keyboard
  // user is not returned to the top of the document after confirming or cancelling.
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    const first = dialog?.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? dialog)?.focus({ preventScroll: true });
    return () => previous?.focus?.({ preventScroll: true });
  }, [dialogRef]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      // Focusable children are re-read on every Tab rather than captured on open, because
      // these dialogs change shape while they are up - a button enables, an error line
      // appears.
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
  }, [dialogRef]);

  // `inert` on everything behind the dialog: it removes those elements from the tab order and
  // from hit-testing at once, which a keydown handler cannot do for a mouse. Applied to
  // `#root`'s children other than this dialog's own subtree, so it composes with whatever the
  // app renders rather than depending on a particular DOM shape.
  useEffect(() => {
    const dialog = dialogRef.current;
    const overlay = dialog?.closest(".modal-overlay") ?? dialog ?? null;
    const siblings = ([...(document.getElementById("root")?.children ?? [])] as HTMLElement[])
      .filter((element) => element !== overlay && !element.contains(overlay as Node));
    for (const element of siblings) element.inert = true;
    return () => {
      for (const element of siblings) element.inert = false;
    };
  }, [dialogRef]);
}
