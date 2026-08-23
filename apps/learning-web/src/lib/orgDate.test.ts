/**
 * DRIFT-59-DATE-SHIFT: the two properties D-324 bought, now assertable without a browser.
 *
 * The zone/locale pinning was already correct for an **instant** (`...T19:05:00Z`) - that was
 * D-324's fix, and the first two cases below are its regression guard. What was still armed is the
 * **date-only** shape: `new Date("2026-08-22")` is UTC midnight by specification, so rendering it
 * with `timeZone: "America/Chicago"` (UTC-5/-6) prints the *previous* calendar day. A value that
 * names no time cannot be moved between zones - there is no instant to convert - so it has to be
 * read back in the zone it was written in.
 *
 * The process zone is pinned to `Asia/Seoul` (+09, and on the other side of UTC from the org) so
 * "does not depend on the viewer" is a claim these tests can actually fail on; `viewer zone` below
 * is the control that proves the pin took effect rather than silently reading the host's zone.
 */

import { describe, expect, test, vi } from "vitest";
import { UNKNOWN_TIME_ZONE, buildDateLabelFormatter } from "./orgDate";

// `vi.stubEnv` rather than assigning `process.env.TZ` directly: this app's `tsconfig.app.json`
// compiles `src` with `types: ["vite/client"]` only, so the node global is deliberately not in
// scope here. Node re-reads `TZ` on assignment, so the change reaches `Intl` either way.
vi.stubEnv("TZ", "Asia/Seoul");

const ORG_ZONE = "America/Chicago";

describe("the pinned viewer zone", () => {
  test("is the one these tests assume", () => {
    // Vacuity control: if the runner ever stops honouring a runtime `TZ` change, every
    // "not the viewer's zone" assertion below would still pass while asserting nothing.
    expect(Intl.DateTimeFormat().resolvedOptions().timeZone).toBe("Asia/Seoul");
  });
});

describe("buildDateLabelFormatter on an instant", () => {
  test("renders the org's calendar day, not the viewer's (D-324)", () => {
    // 2026-08-22T19:05Z is still Aug 22 in Chicago and already Aug 23 in Seoul.
    const label = buildDateLabelFormatter(ORG_ZONE)("2026-08-22T19:05:00Z");
    expect(label).toBe("8/22/2026");
    expect(label).not.toBe("8/23/2026");
  });

  test("pins the locale to en-US so the rendered form is M/D/YYYY", () => {
    expect(buildDateLabelFormatter(ORG_ZONE)("2026-01-05T12:00:00Z")).toBe("1/5/2026");
  });

  test("honours a tz-aware org-midnight instant, which is what the server sends", () => {
    // `_accuracy_trend` emits `2026-08-22T00:00:00-05:00`, tz-aware on purpose.
    expect(buildDateLabelFormatter(ORG_ZONE)("2026-08-22T00:00:00-05:00")).toBe("8/22/2026");
  });

  test("falls back to UTC as an honest 'not told'", () => {
    expect(buildDateLabelFormatter(UNKNOWN_TIME_ZONE)("2026-08-22T19:05:00Z")).toBe("8/22/2026");
  });

  test("ignores non-string values (recharts hands `unknown`)", () => {
    const format = buildDateLabelFormatter(ORG_ZONE);
    expect(format(undefined)).toBe("");
    expect(format(17)).toBe("");
  });
});

describe("buildDateLabelFormatter on a date-only value", () => {
  test("renders that calendar day in a behind-UTC org zone, not the day before", () => {
    // The armed edge: UTC midnight read in Chicago is 7pm the previous day.
    expect(buildDateLabelFormatter(ORG_ZONE)("2026-08-22")).toBe("8/22/2026");
  });

  test("renders the same calendar day in every zone", () => {
    const zones = ["America/Chicago", "America/Los_Angeles", "UTC", "Asia/Seoul", "Pacific/Kiritimati"];
    const labels = new Set(zones.map((zone) => buildDateLabelFormatter(zone)("2026-01-01")));
    expect([...labels]).toEqual(["1/1/2026"]);
  });
});
