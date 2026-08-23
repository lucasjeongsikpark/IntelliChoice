/**
 * The calendar-approval time seam (WORK-40-TZ; the chat-web half of D-324's defect class).
 *
 * `CalendarActionModal` formatted event times with `new Date(value).toLocaleString()` - no zone and
 * no locale, so both were read off the *viewer's* machine - and printed the result beside a
 * `(${event.timezone})` suffix naming a different zone. Under `TZ=Asia/Seoul` a Chicago event at
 * `2023-11-01T17:00:00+00:00` rendered "11/2/2023, 2:00:00 AM (America/Chicago)": wrong time, wrong
 * day, and self-contradictory on the one surface where a human approves an external action
 * (non-negotiable rule 4). Approval is only meaningful if what was approved is what was shown.
 *
 * **The wire shape is mixed, so the meaning of the string has to be read off the string itself.**
 * `CalendarEvent.start_datetime` (`packages/shared/.../calendar.py`, SPEC §5.23.2) is a Python
 * `datetime` serialized by `model_dump(mode="json")`, and it reaches the SPA two ways:
 *
 *   - **Offset present - a real instant.** `services.calendar_events.to_calendar_event` copies
 *     `OrgEvent.starts_at`, a `DateTime(timezone=True)` column, so the JSON carries `+00:00`/`Z`.
 *     An instant says nothing about which wall clock to read it on, so it is converted *into*
 *     `event.timezone` - the zone the suffix already promises.
 *   - **No offset - naive wall-clock.** `services.calendar.extract_calendar_event` builds the event
 *     from `datetime.fromisoformat(<model-drafted string>)`, read out of a document ("September 1 at
 *     6:30 PM"), and nothing tags it. `intellichoice_adapters.ics._to_utc` settles what that means
 *     for the whole codebase - `dt.replace(tzinfo=tz)`, i.e. wall-clock **in `event.timezone`** - so
 *     its own components are already the answer. Converting them would move the event, and
 *     `new Date` would compound it by reading an offsetless date-*time* as the *viewer's* local
 *     time (the one shape where it does not default to UTC).
 *
 * Both branches therefore render "the wall clock in `event.timezone`"; they differ only in how the
 * string is interpreted before formatting. The locale is pinned to `en-US` for D-324's reason: the
 * organization reads M/D/YYYY, and an approval surface that silently switches to D/M/YYYY for some
 * readers shows two different days for the same event.
 */

/** A trailing `Z` or `±HH:MM`/`±HHMM` - the string is tagged, so it denotes an instant. */
const HAS_OFFSET = /(?:Z|[+-]\d{2}:?\d{2})$/i;

/** A bare `YYYY-MM-DD`, which `new Date` reads as UTC midnight rather than as local time. */
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

const FORMAT: Intl.DateTimeFormatOptions = {
  year: "numeric",
  month: "numeric",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
};

/**
 * Formats one end of a calendar event for the approval modal.
 *
 * Every failure path returns the value **as written** rather than a converted guess: a raw
 * `2023-11-01T17:00:00Z` carries its own offset and is honest, while a time rendered in a zone we
 * could not confirm is a wrong time that looks right - the worse of the two on an approval surface.
 */
export function formatEventDateTime(value: unknown, timeZone: unknown): string {
  if (typeof value !== "string") return "";
  const raw = value.trim();
  if (raw === "") return "";

  const tagged = HAS_OFFSET.test(raw);
  // An untagged date-time is re-tagged as UTC and then read back in UTC, which returns the exact
  // components that were written - the wall clock the naive path meant.
  const instant = new Date(tagged || DATE_ONLY.test(raw) ? raw : `${raw}Z`);
  if (Number.isNaN(instant.getTime())) return raw;

  const zone = typeof timeZone === "string" && timeZone.trim() !== "" ? timeZone.trim() : null;
  const renderZone = tagged ? zone : "UTC";
  // A tagged instant with no zone to convert into cannot be rendered as a wall clock at all.
  if (renderZone === null) return raw;

  try {
    return instant.toLocaleString("en-US", { ...FORMAT, timeZone: renderZone });
  } catch {
    // `Intl` throws `RangeError` on an unknown IANA name (a stale document, a typo in a row).
    return raw;
  }
}
