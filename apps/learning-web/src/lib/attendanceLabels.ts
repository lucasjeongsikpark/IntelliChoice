/**
 * D-407 (`AUD-L-09`): the parent-facing blocked list said `Week 2026-W31 — absent`.
 *
 * Two internal tokens on the one screen a parent reads about their child, and the second one is
 * the substantive half. `blocked_reason` is an `AttendanceStatus` value, and **`unknown` is the
 * routine case in production, not a rare one** — D-152 §2 records that `signups.attended = null`
 * ("the branch manager has not marked it yet") is common. The server already keeps the two apart,
 * answering `UNKNOWN_MESSAGE` for one and `BLOCKED_MESSAGE` for the other; the dashboard collapsed
 * both to a raw enum, so a parent read `unknown` about their child's attendance where the truth is
 * "nobody has marked it yet". That is not polish - it is the difference between "your child missed
 * a session" and "the branch has not filled in the register".
 *
 * Pure functions in their own module so they can be unit-tested, which is possible at all only
 * since D-405 added vitest. This is the "the pure-function half is cheap now" claim being cashed.
 */

/** `AttendanceStatus` (`intellichoice_shared.profiles`) - the closed set this maps. */
const REASON_LABELS: Record<string, string> = {
  // Marked absent by a person. A real recorded absence.
  absent: "marked absent",
  // **Not** an absence: nobody has recorded anything yet (D-152 §2, the routine case).
  unknown: "attendance not marked yet",
  // Cannot block a session, and included so the map is the whole enum rather than the part that
  // happens to appear here today.
  present: "marked present",
};

/**
 * A parent-readable reason for a blocked week.
 *
 * An unrecognised value falls back to the section's own wording rather than being printed. Showing
 * a parent a token this app does not understand is the defect being fixed, and a new
 * `AttendanceStatus` member would surface in the API's own tests long before it reached here.
 */
export function formatBlockedReason(reason: string): string {
  return REASON_LABELS[reason] ?? "attendance not confirmed";
}

const ISO_WEEK = /^(\d{4})-W(\d{2})$/;

/**
 * `2026-W31` → `week of 7/27/2026`.
 *
 * **Takes no time zone, and the first version did - the test caught a category error.** It formatted
 * the week's Monday as a UTC *instant* through the organization's zone, so midnight Monday UTC
 * rendered as 7pm **Sunday** in Chicago and the label read `week of 7/26/2026`. An ISO week id has
 * no time component: it is a calendar label, and converting one through a zone can only move it.
 * `formatOrgDate` on the dashboard needs the zone because `blocked_at` is a real instant; this does
 * not, so the parts are read directly and there is nothing to shift.
 *
 * `M/D/YYYY` by hand rather than `toLocaleDateString`, for D-324's reason without its machinery:
 * the organization reads that shape, and a label that silently becomes `D/M/YYYY` for some readers
 * is a different label for the same week.
 *
 * **ISO weeks, not naive arithmetic.** Week 1 is the week containing January 4th, so `2026-W01`
 * starts on **2025-12-29** - in the previous calendar year, which is the case a
 * `(week - 1) * 7 days from January 1st` implementation gets wrong. Verified by round-trip before
 * the test was written: the Monday this returns for `2026-W31` is 2026-07-27, and 2026-07-27 is in
 * ISO week 31.
 *
 * A malformed id is returned unchanged rather than hidden. It is diagnostic, it is not PII, and
 * degrading to today's behaviour is better than inventing a date.
 */
export function formatIsoWeekLabel(weekId: string): string {
  const match = ISO_WEEK.exec(weekId);
  if (match === null) return weekId;
  const year = Number(match[1]);
  const week = Number(match[2]);
  if (week < 1 || week > 53) return weekId;

  const jan4 = new Date(Date.UTC(year, 0, 4));
  // Monday=1..Sunday=7, because `getUTCDay()` is Sunday=0 and ISO weeks start on Monday.
  const jan4IsoDay = jan4.getUTCDay() === 0 ? 7 : jan4.getUTCDay();
  const week1Monday = Date.UTC(year, 0, 4 - (jan4IsoDay - 1));
  const monday = new Date(week1Monday + (week - 1) * 7 * 86_400_000);

  // UTC parts, never a locale conversion: see this function's docstring for the day this shifted.
  const month = monday.getUTCMonth() + 1;
  const day = monday.getUTCDate();
  return `week of ${month}/${day}/${monday.getUTCFullYear()}`;
}
