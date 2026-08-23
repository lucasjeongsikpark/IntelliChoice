/**
 * WORK-40-TZ: the calendar-approval surface's time must agree with the zone printed next to it.
 *
 * `CalendarActionModal` rendered `new Date(value).toLocaleString()` - no zone, no locale - beside a
 * `(${event.timezone})` suffix, so a parent in Seoul read a Chicago event's time in Seoul's zone
 * and approved an external action (non-negotiable rule 4) against a time that was not the event's.
 * This is the defect D-324 fixed in learning-web; the fix never crossed the app boundary.
 *
 * **The wire shape is mixed, and that is what the two `describe` blocks below encode.**
 * `CalendarEvent.start_datetime` reaches the SPA from two paths:
 *   - `chat_api.services.calendar_events.to_calendar_event` reads `OrgEvent.starts_at`, a
 *     `DateTime(timezone=True)` column, so the JSON carries an **offset** - a real instant, which
 *     has to be converted *into* `event.timezone` (`test_calendar_action.py` asserts exactly this
 *     shape: `start_datetime` starting `2023-11-01` with `timezone == "America/Chicago"`).
 *   - `chat_api.services.calendar.extract_calendar_event` does
 *     `datetime.fromisoformat(raw.start_datetime)` on a model-drafted string read out of a
 *     document, which is **naive** wall-clock (the dev fake emits `datetime(y, m, d, 9, 0)`).
 *     `intellichoice_adapters.ics._to_utc` fixes the meaning of that case for the whole codebase:
 *     `dt.replace(tzinfo=tz)` - a naive datetime is wall-clock *in `event.timezone`*. So its own
 *     components are already the answer and converting them would move the event.
 *
 * The process zone is pinned (`Asia/Seoul`, +09) so "not the viewer's zone" is falsifiable, with a
 * control asserting the pin took effect.
 */

import { describe, expect, test, vi } from "vitest";
import { formatEventDateTime } from "./eventDateTime";

// `vi.stubEnv` rather than `process.env.TZ =`: `tsconfig.app.json` compiles `src` with
// `types: ["vite/client"]`, so the node global is deliberately out of scope here.
vi.stubEnv("TZ", "Asia/Seoul");

const ORG_ZONE = "America/Chicago";

describe("the pinned viewer zone", () => {
  test("is the one these tests assume", () => {
    // Vacuity control: without the pin every "not the viewer's zone" assertion below would still
    // pass on a machine that happens to be set to the event's zone.
    expect(Intl.DateTimeFormat().resolvedOptions().timeZone).toBe("Asia/Seoul");
  });
});

describe("an instant (the org_events path: an offset on the wire)", () => {
  test("renders in the event's zone, not the viewer's", () => {
    // 17:00Z is noon in Chicago and 2am the next day in Seoul.
    const rendered = formatEventDateTime("2023-11-01T17:00:00+00:00", ORG_ZONE);
    expect(rendered).toBe("11/1/2023, 12:00 PM");
    expect(rendered).not.toContain("11/2/2023");
  });

  test("handles a Z suffix identically", () => {
    expect(formatEventDateTime("2023-11-01T17:00:00Z", ORG_ZONE)).toBe("11/1/2023, 12:00 PM");
  });

  test("handles a non-UTC offset by converting into the event's zone", () => {
    // Same instant written as Chicago local time by a server that serialized with its own offset.
    expect(formatEventDateTime("2023-11-01T12:00:00-05:00", ORG_ZONE)).toBe("11/1/2023, 12:00 PM");
  });

  test("pins the locale so the form is en-US M/D/YYYY for every reader", () => {
    expect(formatEventDateTime("2023-01-05T18:30:00Z", "UTC")).toBe("1/5/2023, 6:30 PM");
  });
});

describe("a naive wall-clock (the RAG-extraction path: no offset on the wire)", () => {
  test("renders its own components - the zone suffix already names the zone", () => {
    // `ics._to_utc` reads this as 09:00 *in* America/Los_Angeles; converting it would move it.
    expect(formatEventDateTime("2026-11-26T09:00:00", "America/Los_Angeles")).toBe(
      "11/26/2026, 9:00 AM",
    );
  });

  test("renders the same wall clock in every viewer zone", () => {
    const seoul = formatEventDateTime("2026-11-26T09:00:00", "America/Los_Angeles");
    vi.stubEnv("TZ", "America/New_York");
    const newYork = formatEventDateTime("2026-11-26T09:00:00", "America/Los_Angeles");
    vi.stubEnv("TZ", "Asia/Seoul");
    expect(newYork).toBe(seoul);
  });

  test("accepts microseconds, which `datetime.isoformat()` emits", () => {
    expect(formatEventDateTime("2026-11-26T09:00:00.123456", "America/Los_Angeles")).toBe(
      "11/26/2026, 9:00 AM",
    );
  });
});

describe("fallbacks fail toward the raw value, never a silently wrong conversion", () => {
  test("an unknown zone shows the value as written", () => {
    expect(formatEventDateTime("2023-11-01T17:00:00Z", "Mars/Olympus_Mons")).toBe(
      "2023-11-01T17:00:00Z",
    );
  });

  test("a missing zone shows the value as written rather than guessing one", () => {
    expect(formatEventDateTime("2023-11-01T17:00:00Z", null)).toBe("2023-11-01T17:00:00Z");
    expect(formatEventDateTime("2023-11-01T17:00:00Z", undefined)).toBe("2023-11-01T17:00:00Z");
  });

  test("an unparseable value is shown as-is", () => {
    expect(formatEventDateTime("sometime next Tuesday", ORG_ZONE)).toBe("sometime next Tuesday");
  });

  test("a non-string renders nothing", () => {
    expect(formatEventDateTime(undefined, ORG_ZONE)).toBe("");
    expect(formatEventDateTime(1730480400000, ORG_ZONE)).toBe("");
  });
});
