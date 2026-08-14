/**
 * D-319, the half a browser screenshot cannot guard: **no two labels on a chart axis may be
 * identical**, and a date axis must not repeat itself.
 *
 * Both defects were found by looking at the dashboard, which is exactly why they survived so
 * long — nothing in the suite reads a chart. The mastery axis rendered
 * "Add and subtract…denominators" twice (two bars, two masteries, no way to tell which was
 * which) and the difficulty axis printed `8/13/2026` five times. Neither is a crash, neither
 * logs anything, and both make the chart say something false to the one person the dashboard
 * exists for.
 *
 * **It earned its keep on its first staging run, and against the date axis rather than the
 * skill axis (D-323 → D-324).** Local fixtures never reach the density that breaks the date
 * formatter; staging's ~70-point axes do. It read `8/7/2026` fifteen times off one axis,
 * which killed the first version of the fix — one that blanked a repeat only when the tick's
 * `index` happened to address the data array, and printed everything when it did not. The
 * replacement claims each distinct label for exactly one value and needs no index at all.
 * The paragraph below still applies to the *skill* axis, which remains forward-looking.
 *
 * **This asserts the invariant, not the fix.** `buildSkillLabelFormatter`'s collision case
 * needs two skills whose names differ only in the middle, and the fixture students study
 * `linear_equations`, whose five skill names already separate. So on today's data this test
 * passes for both the fixed and the unfixed build — which is stated here rather than left for
 * someone to discover, because a test that cannot fail is the AUD-F-12 false negative. Its
 * value is forward-looking: the day the seeded curriculum grows a colliding pair (the fractions
 * skills already in the bank would do it), this fails instead of shipping an unreadable chart.
 * The fix itself was measured against the shipped function through the Vite dev server; see
 * `buildSkillLabelFormatter`'s docstring for that recipe.
 *
 * The precondition is asserted before anything is concluded from it: a dashboard with no
 * chart at all would otherwise report a pass for a page that rendered nothing, which is the
 * vacuous shape `narrative-refresh.spec.ts` was rewritten to avoid.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";

test.describe.configure({ timeout: 180_000 });

test("no chart axis renders two identical labels", async ({ page, audit }) => {
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await page.getByRole("button", { name: /view progress dashboard/i }).click();
  await expect(page.getByRole("heading", { name: /progress dashboard/i })).toBeVisible({
    timeout: 60_000,
  });

  // Recharts renders asynchronously into a ResponsiveContainer, and **the wait has to be for a
  // *labelled* tick, not any tick.** Waiting for `.recharts-cartesian-axis-tick-value` alone
  // was satisfied by the `0 / 0.25 / 0.5` numeric axis of a chart that had already rendered,
  // so the read below ran before the skill chart existed and the test reported a pass having
  // examined nothing - caught here only because the positive control further down refuses that
  // outcome. A wait whose condition is not the thing you are about to measure is not a wait.
  const rendered = await page
    .locator(".recharts-cartesian-axis-tick-value")
    .filter({ hasText: /[a-z]/i })
    .first()
    .waitFor({ state: "attached", timeout: 30_000 })
    .then(() => true)
    .catch(() => false);
  test.skip(
    !rendered,
    "this student has no charted history on this target, so there are no axis labels to " +
      "check and this run says nothing either way",
  );

  // **Read per chart wrapper, and read the *tick-labels* group.** `.recharts-yAxis` is the
  // axis line and in this recharts version the tick text is not inside it - it lives in a
  // sibling `.recharts-yAxis-tick-labels`. Querying the axis returned five empty arrays while
  // 35 tick values sat in the same document, which is a silent zero and would have made every
  // assertion below iterate over nothing. Confirmed against the real DOM by walking a tick's
  // parent chain rather than by guessing a second selector.
  const axes = await page.evaluate(() => {
    const read = (chart: Element, selector: string) =>
      [...chart.querySelectorAll(selector)].map((group) =>
        [...group.querySelectorAll(".recharts-cartesian-axis-tick-value")].map(
          (tick) => tick.textContent?.trim() ?? "",
        ),
      );
    const charts = [...document.querySelectorAll(".recharts-wrapper")];
    return {
      y: charts.flatMap((c) => read(c, ".recharts-yAxis-tick-labels")),
      x: charts.flatMap((c) => read(c, ".recharts-xAxis-tick-labels")),
    };
  });

  const categoryAxes = axes.y.filter((ticks) => ticks.some((t) => /[a-z]/i.test(t)));
  const dateAxes = axes.x.filter((ticks) => ticks.some((t) => /\d{1,2}\/\d{1,2}\/\d{4}/.test(t)));
  audit.note(
    `axes read: ${axes.y.length} y (${categoryAxes.length} with text labels), ` +
      `${axes.x.length} x (${dateAxes.length} with dates)`,
  );

  // **The positive control, and it is the whole reason this file is not decoration.** Both
  // loops below iterate over what was found, so a page that rendered no labelled axis would
  // run zero assertions and report a pass - the AUD-F-12 false negative, and the one this
  // suite refuses to allow anywhere else. Skipping with the counts in hand says "this run did
  // not look", which is a different claim from "this run looked and found nothing wrong".
  test.skip(
    categoryAxes.length === 0 && dateAxes.length === 0,
    `the dashboard rendered ${axes.y.length} y-axes and ${axes.x.length} x-axes but none ` +
      "carried a skill label or a date, so there was nothing to check for duplicates",
  );

  for (const ticks of categoryAxes) {
    const seen = ticks.filter((t) => t !== "");
    const duplicates = seen.filter((t, i) => seen.indexOf(t) !== i);
    expect(
      duplicates,
      `two bars on one chart carry the same label ${JSON.stringify(duplicates)} - a parent ` +
        "cannot tell which skill each row is, which is the chart's only job (D-319)",
    ).toEqual([]);
  }

  // A date axis may legitimately repeat a *value* (several attempts in one afternoon); what
  // it must not do is print that day more than once.
  //
  // **This assertion was weaker and its failure message was wrong (D-323 → D-324).** It read
  // `dates.some((t, i) => dates[i - 1] === t)` over the array *after* blanks were filtered
  // out, so it could not distinguish "8/7 twice in a row" from "8/7, a blank, 8/7" - and it
  // reported the former either way. It also only ever looked at adjacent pairs, which was
  // the wrong invariant: `buildDateTickFormatter` now claims each distinct label for exactly
  // one value, so **one printed tick per day** is the property, not "no two neighbours
  // match". Checking for duplicates anywhere is both stronger and unambiguous, and needs no
  // reasoning about what the blanks between them mean.
  for (const ticks of axes.x) {
    const dates = ticks.filter((t) => /\d{1,2}\/\d{1,2}\/\d{4}/.test(t));
    const duplicates = [...new Set(dates.filter((t, i) => dates.indexOf(t) !== i))];
    expect(
      duplicates,
      `a date axis printed ${JSON.stringify(duplicates)} more than once out of ` +
        `${dates.length} labels - each day is meant to be printed exactly once, so the axis ` +
        "says which day a run of points belongs to instead of repeating itself",
    ).toEqual([]);
  }
});
