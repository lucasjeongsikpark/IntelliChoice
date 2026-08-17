/**
 * U4/D-327: the two things URL routing is *for*, asserted rather than assumed.
 *
 * Before this the whole app lived at one URL and the destination was a `useState<View>`, so a
 * reload on the dashboard threw the student back to the session flow and the browser's Back
 * button left the app entirely. Both are now properties of the address bar.
 *
 * **What is deliberately NOT asserted here: a per-phase URL.** The session's screen is chosen by
 * the server's `phase`, and a bookmarkable `/exam` could send a student to an exam the graph has
 * already finalized - the address bar disagreeing with the session state is a worse defect than
 * the one being fixed. The URL owns only "session flow vs dashboard"; the phase owns the rest.
 *
 * **`/results` used to be uncovered here "because it is not bookmarkable and cannot be yet". That
 * stopped being true on 2026-08-15 and this comment did not (corrected 2026-08-17, V1/D-383).**
 * D-338 added `GET /learning/sessions/{id}/results` and `BookmarkedResultsScreen`, so the results
 * half of U4's "dashboard and results are bookmarkable" is real. It is covered by
 * `journey-terminal.spec.ts`, which is the only spec that can reach a completed session, and this
 * file stays scoped to "session flow vs dashboard".
 *
 * The correction is worth more than the sentence. A stale *"cannot be done"* comment costs more
 * than a stale fact, because the next person reads it and stops: `journey-student.spec.ts`
 * carried one saying the study phase "never reaches the mastery bar", which is why nothing walked
 * to the results screen for weeks — the bound is arithmetic (5 skills × 4 attempts) and had been
 * reachable all along.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";

test.describe.configure({ timeout: 180_000 });

test("the dashboard survives a reload and the back button returns to the session", async ({
  page,
  audit,
}) => {
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);

  await page.getByRole("button", { name: /view progress dashboard/i }).click();
  await expect(page.getByRole("heading", { name: /progress dashboard/i })).toBeVisible({
    timeout: 60_000,
  });

  // The URL is the claim. Without it the two assertions below cannot hold, so this failing
  // first would say "routing is not wired" rather than "reload is broken".
  await expect(page).toHaveURL(/\/dashboard$/);
  audit.note(`after opening the dashboard: ${new URL(page.url()).pathname}`);

  // **1. Bookmarkable.** A hard reload is the same thing a bookmark does - the app is
  // reconstructed from the URL alone, with no in-memory `view` to fall back on.
  await page.reload();
  await expect(page.getByRole("heading", { name: /progress dashboard/i })).toBeVisible({
    timeout: 60_000,
  });
  await expect(page).toHaveURL(/\/dashboard$/);

  // **2. Back works, and stays inside the app.** Previously Back left the site, because there
  // was only ever one history entry.
  await page.goBack();
  await expect(page).toHaveURL(/\/session$/);
  await expect(page.getByRole("heading", { name: /progress dashboard/i })).toBeHidden();
  audit.note(`after Back: ${new URL(page.url()).pathname}`);
});

test("a deep link straight to /dashboard is served rather than 404ing", async ({ page }) => {
  // The other half of "bookmarkable", and it is an *infrastructure* property rather than an app
  // one: the bundle is static files behind CloudFront, so a path with no object behind it has to
  // resolve to `index.html` or client-side routing cannot work at all. Verified against the real
  // edge before this test was written - `CustomErrorResponses` is empty, yet `/dashboard` returns
  // 200 `text/html` from S3 - so no distribution change was needed. This asserts it stays true,
  // because the failure mode is a bookmark that 404s for a parent and works for everyone who
  // clicked through.
  const response = await page.goto(`${LEARNING_WEB}/dashboard`);

  expect(response?.status(), "a deep link must return the SPA shell, not a 404").toBe(200);
  // Signed out, so the sign-in screen is the correct destination - the assertion is that the
  // *document* was served, not that the dashboard renders without a token.
  await expect(page.locator("#root")).not.toBeEmpty({ timeout: 30_000 });
});
