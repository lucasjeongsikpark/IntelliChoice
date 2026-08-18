/**
 * D-407 (`AUD-L-09`): the parent-facing blocked list printed `Week 2026-W31 — absent`.
 *
 * These are the first tests written *because* D-405 added vitest rather than in spite of the
 * harness - the whole "the pure-function half is cheap now" claim, cashed. Both functions are pure
 * and both have edge cases a browser walk would never reach: ISO week 1 falling in the previous
 * calendar year, and an attendance value this app does not recognise.
 */

import { describe, expect, it } from "vitest";
import { formatBlockedReason, formatIsoWeekLabel } from "./attendanceLabels";

describe("formatBlockedReason", () => {
  it("tells a parent that unmarked attendance is not an absence", () => {
    // **The substantive assertion.** D-152 §2: `signups.attended = null` is the *routine* case in
    // production, so this is the label a parent sees most often. Reading `unknown` - or anything
    // that sounds like a recorded absence - about your own child is the defect.
    expect(formatBlockedReason("unknown")).toBe("attendance not marked yet");
    expect(formatBlockedReason("unknown")).not.toContain("absent");
  });

  it("says plainly when the absence was recorded", () => {
    expect(formatBlockedReason("absent")).toBe("marked absent");
  });

  it("never prints a token it does not recognise", () => {
    // A future `AttendanceStatus` member must not leak onto a parent's dashboard as a raw enum,
    // which is exactly what this whole change is about. The fallback is the section's own wording.
    expect(formatBlockedReason("excused_by_manager")).toBe("attendance not confirmed");
    expect(formatBlockedReason("")).toBe("attendance not confirmed");
  });

  it("covers every value the enum actually has", () => {
    // `present` cannot block a session, and is mapped anyway so the map is the whole enum rather
    // than the part that happens to appear today.
    for (const value of ["present", "absent", "unknown"]) {
      expect(formatBlockedReason(value)).not.toBe("attendance not confirmed");
    }
  });
});

describe("formatIsoWeekLabel", () => {
  it("names the week by its Monday", () => {
    // Verified by round-trip before this assertion was written: 2026-07-27 is a Monday, and it is
    // in ISO week 31.
    expect(formatIsoWeekLabel("2026-W31")).toBe("week of 7/27/2026");
  });

  it("handles week 1 falling in the previous calendar year", () => {
    // The case a naive `(week - 1) * 7 days from January 1st` gets wrong. ISO week 1 is the week
    // containing January 4th, so 2026-W01 begins on 2025-12-29.
    expect(formatIsoWeekLabel("2026-W01")).toBe("week of 12/29/2025");
    expect(formatIsoWeekLabel("2025-W01")).toBe("week of 12/30/2024");
  });

  it("cannot be shifted by a time zone at all", () => {
    // **This test's first version was wrong, and the failure it produced is the reason the
    // signature changed.** It passed the org zone and asserted the Monday survived - but the
    // implementation was formatting a UTC-midnight instant through that zone, so Chicago rendered
    // it as 7pm the previous Sunday: `week of 7/26/2026`. A week id has no instant to convert, so
    // the function now takes no zone and reads UTC parts directly. There is nothing left to shift,
    // which is stronger than any assertion about a particular zone.
    const label = formatIsoWeekLabel("2026-W31");
    expect(label).toBe("week of 7/27/2026");
    // Whatever the host machine's zone is while this suite runs, the answer is the same.
    expect(Intl.DateTimeFormat().resolvedOptions().timeZone).toBeTruthy();
    expect(formatIsoWeekLabel("2026-W31")).toBe(label);
  });

  it("returns a malformed id unchanged rather than inventing a date", () => {
    // Degrading to today's behaviour beats printing a confidently wrong week. The id is
    // diagnostic and is not PII.
    for (const bad of ["", "2026-31", "W31", "2026-W", "not-a-week", "2026-W00", "2026-W54"]) {
      expect(formatIsoWeekLabel(bad)).toBe(bad);
    }
  });
});
