/**
 * The org-zone date seam: every date a viewer reads on the dashboard is formatted here.
 *
 * It lives in `lib/` rather than inside `StudentDashboardScreen` because it was module-private
 * there, which made the one property that matters - that a rendered day does not depend on where
 * the reader is sitting - assertable only through a browser test
 * (`e2e/tests/learning/dashboard-chart-labels.spec.ts`, deferred). The decision record below
 * travelled with the code.
 */

/**
 * The zone to display in when the server did not say (an older server, mid-deploy).
 *
 * `UTC`, matching `DashboardResponse.org_time_zone`'s own Pydantic default, and
 * deliberately **not** `America/Chicago`: a second copy of the org's zone in the client is
 * exactly the skew that serving the field removes, and it would go stale silently the day
 * `ORG_TIMEZONE` is confirmed to something else. UTC is an honest "not told".
 */
export const UNKNOWN_TIME_ZONE = "UTC";

/**
 * Formats a UTC instant as the **organization's** calendar day (D-324).
 *
 * Every date on this screen came from `toLocaleDateString()` with no arguments, which reads
 * two things off the *viewer's* machine: the zone and the locale. Both were wrong to depend
 * on. A parent opening the same dashboard from another country saw the org's days shifted,
 * and any attempt after ~7pm Central - already tomorrow in UTC - could be drawn on a day
 * the student did not work. The zone is now served (`org_time_zone`, resolved from
 * `ORG_TIMEZONE` by `intellichoice_shared.org_time`), so client and server cannot disagree
 * about which day a number belongs to.
 *
 * The locale is pinned to `en-US` for the same reason rather than left to the browser: the
 * organization reads `M/D/YYYY`, and an axis that silently switches to `D/M/YYYY` for some
 * readers is a different label for the same day. It also makes the rendered form assertable
 * - `dashboard-chart-labels.spec.ts` matches on `\d{1,2}/\d{1,2}/\d{4}`.
 */
/**
 * A bare `YYYY-MM-DD`. `new Date` reads this shape as **UTC midnight** by specification (unlike a
 * date-*time* with no offset, which it reads as the viewer's local time), which is what makes the
 * shift below deterministic rather than viewer-dependent.
 */
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

export function buildDateLabelFormatter(timeZone: string): (value: unknown) => string {
  return (value) => {
    if (typeof value !== "string") return "";
    // A date-only value names a calendar day, not an instant, so there is nothing to convert
    // *into* `timeZone` - and converting anyway subtracted a day. `2026-08-22` became UTC
    // midnight and then `8/21/2026` in Chicago (UTC-5): a bar drawn on a day the student did
    // not work, which is the same class of error D-324 fixed for instants. Reading the value
    // back in the zone `new Date` parsed it in returns the day that was written, in every
    // viewer's browser and for every `timeZone` this is called with.
    //
    // The formatting still goes through `Intl` rather than string arithmetic so `en-US`'s
    // M/D/YYYY form has exactly one definition here, shared with the instant path below.
    const renderZone = DATE_ONLY.test(value) ? "UTC" : timeZone;
    return new Date(value).toLocaleDateString("en-US", { timeZone: renderZone });
  };
}
