/**
 * WORK-40-TZ at the surface: the time a human reads before approving an external action.
 *
 * The unit-level rules live in `lib/eventDateTime.test.ts`. What this file adds is the property the
 * defect actually broke, which is a property of the *rendered line* rather than of a function: the
 * time and the zone printed beside it name the same moment. A modal that renders
 * "11/2/2023, 2:00:00 AM (America/Chicago)" is not a rule-4 approval surface - it asks a parent to
 * consent to a time that was never proposed.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { CalendarActionModal } from "./CalendarActionModal";
import type { CalendarActionInterrupt } from "../types";

// A viewer nine hours ahead of UTC, so a Chicago afternoon is the following morning here.
vi.stubEnv("TZ", "Asia/Seoul");

/** The `org_events` path's shape: a tz-aware instant plus the event's own zone. */
function pending(event: Record<string, unknown> | null): CalendarActionInterrupt {
  return { interrupt_type: "calendar_action", calendar_event: event };
}

const FALL_MEETING = {
  title: "Fall Parent Meeting",
  start_datetime: "2023-11-01T17:00:00+00:00",
  end_datetime: "2023-11-01T19:00:00+00:00",
  timezone: "America/Chicago",
  location: "Main Hall",
  description: "",
  source_document_id: "org-event:fall-parent-meeting",
};

function renderModal(event: Record<string, unknown> | null = FALL_MEETING): string {
  render(
    <CalendarActionModal pending={pending(event)} busy={false} error={null} onChoose={vi.fn()} />,
  );
  return screen.getByText(/–/).textContent ?? "";
}

describe("the calendar approval line", () => {
  test("the pinned viewer zone took effect", () => {
    // Vacuity control: on a machine already set to America/Chicago the assertions below would
    // pass while testing nothing.
    expect(Intl.DateTimeFormat().resolvedOptions().timeZone).toBe("Asia/Seoul");
  });

  test("the times agree with the zone suffix beside them", () => {
    expect(renderModal()).toBe("11/1/2023, 12:00 PM – 11/1/2023, 2:00 PM (America/Chicago)");
  });

  test("the viewer's own zone does not appear in it", () => {
    // 17:00Z is 2am on the 2nd in Seoul: the day and the hour were both wrong before the fix.
    const line = renderModal();
    expect(line).not.toContain("11/2/2023");
    expect(line).not.toContain("2:00 AM");
  });

  test("an event with no zone shows the values as written rather than the viewer's clock", () => {
    const line = renderModal({ ...FALL_MEETING, timezone: undefined });
    expect(line).toBe("2023-11-01T17:00:00+00:00 – 2023-11-01T19:00:00+00:00");
  });

  test("a naive wall-clock event renders the clock the document stated", () => {
    // The RAG-extraction path: no offset on the wire, so 9am *is* 9am in the named zone.
    const line = renderModal({
      ...FALL_MEETING,
      start_datetime: "2026-11-26T09:00:00",
      end_datetime: "2026-11-26T17:00:00",
      timezone: "America/Los_Angeles",
    });
    expect(line).toBe("11/26/2026, 9:00 AM – 11/26/2026, 5:00 PM (America/Los_Angeles)");
  });

  test("an absent event still renders the modal rather than throwing", () => {
    render(
      <CalendarActionModal pending={pending(null)} busy={false} error={null} onChoose={vi.fn()} />,
    );
    expect(screen.getByRole("heading", { name: /add to your calendar\?/i })).toBeTruthy();
  });
});
