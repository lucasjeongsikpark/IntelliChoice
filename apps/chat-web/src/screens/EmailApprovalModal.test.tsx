/**
 * D-420 (B4): what the approval modal actually sends, which is the half a browser walk cannot see.
 *
 * `journey-chat.spec.ts` and the audit walks can confirm the modal appears, that Decline closes it,
 * and that Escape declines. What they cannot cheaply assert is the **shape of the resume payload** —
 * whether a note reaches the server, whether a *declined* approval carries one, and whether an empty
 * textarea sends `""` or nothing. Those are the properties that decide what an administrator reads,
 * and every one of them is a callback argument rather than a pixel.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { EmailApprovalModal } from "./EmailApprovalModal";
import type { EmailApprovalInterrupt } from "../types";

const PENDING: EmailApprovalInterrupt = {
  interrupt_type: "email_approval",
  email_subject: "IntelliChoice Q&A escalation - session sess-1",
  email_body: "Question: Who do I ask about billing?",
};

function renderModal(onApprove = vi.fn()) {
  render(<EmailApprovalModal pending={PENDING} busy={false} error={null} onApprove={onApprove} />);
  return {
    onApprove,
    note: screen.getByLabelText(/anything else the administrator should know/i),
    send: screen.getByRole("button", { name: /approve & send/i }),
    decline: screen.getByRole("button", { name: /decline/i }),
  };
}

function type(field: HTMLElement, value: string): void {
  // `fireEvent.change`, not a hand-dispatched `input`. React tracks a controlled value through its
  // own property descriptor, so setting `.value` and dispatching an event leaves the component's
  // state untouched - and the failure mode is worse than a red test: the whitespace-only and empty
  // cases below both *passed* that way, because the value had never changed at all. A test that
  // asserts "nothing was sent" is exactly the one that cannot tell "trimmed to nothing" from
  // "never typed".
  fireEvent.change(field, { target: { value } });
}

describe("the approval modal's note", () => {
  test("the draft is shown read-only and the note is the only editable field", () => {
    const { note } = renderModal();
    // The server composes the frame; a freely editable body would make "your original question is
    // preserved" a convention the first edit could remove (D-420).
    expect(screen.getByText(/Question: Who do I ask about billing\?/)).toBeTruthy();
    expect(document.querySelectorAll("textarea")).toHaveLength(1);
    expect(note.tagName).toBe("TEXTAREA");
  });

  test("what is typed is sent with the approval", () => {
    const { onApprove, note, send } = renderModal();
    type(note, "It is urgent - the deadline is Friday.");
    send.click();
    expect(onApprove).toHaveBeenCalledWith(true, "It is urgent - the deadline is Friday.");
  });

  test("an empty note sends nothing rather than an empty string", () => {
    // `append_user_note` treats blank as absent anyway, so this is depth rather than the only
    // control - but sending `""` would put an empty field on the wire for every approval and make
    // the server's "did they write anything?" a question about whitespace.
    const { onApprove, send } = renderModal();
    send.click();
    expect(onApprove).toHaveBeenCalledWith(true, undefined);
  });

  test("a whitespace-only note sends nothing", () => {
    const { onApprove, note, send } = renderModal();
    type(note, "   \n  ");
    send.click();
    expect(onApprove).toHaveBeenCalledWith(true, undefined);
  });

  test("declining carries no note, even if one was typed", () => {
    // Nothing is sent, so there is nothing for a note to attach to - and a server receiving one on
    // a decline would be right to wonder which of the two it should believe.
    const { onApprove, note, decline } = renderModal();
    type(note, "please do send this");
    decline.click();
    expect(onApprove).toHaveBeenCalledWith(false);
  });

  test("the field is bounded to the server's limit so the cap is felt while typing", () => {
    // The server answers 422 past 1000 rather than truncating, so an unbounded textarea would let
    // someone write a paragraph and be refused for it. The server's bound is still the one that
    // decides; this only stops the visitor discovering it on submit.
    const { note } = renderModal();
    expect((note as HTMLTextAreaElement).maxLength).toBe(1000);
  });

  test("the controls are disabled while a decision is in flight", () => {
    const onApprove = vi.fn();
    render(
      <EmailApprovalModal pending={PENDING} busy={true} error={null} onApprove={onApprove} />,
    );
    expect(screen.getByRole("button", { name: /approve & send/i })).toHaveProperty("disabled", true);
    expect(
      screen.getByLabelText(/anything else the administrator should know/i),
    ).toHaveProperty("disabled", true);
  });
});
