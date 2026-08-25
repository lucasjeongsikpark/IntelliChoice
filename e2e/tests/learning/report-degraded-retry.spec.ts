/**
 * D-161: the report idempotency key must not pin a degraded report.
 *
 * AUD-X-04's fix (D-159) keys report generation on a per-mount nonce so a replay is served
 * from the stored row without a second paid Bedrock call. The regression that opened: both
 * fallback paths (cost ceiling, gateway failure) persist their facts-only row *under the
 * key*, so after a transient outage the "Regenerate report" button silently replayed the
 * degraded row for the lifetime of the view - before D-159 a second click was a real retry.
 *
 * The client contract, asserted here by intercepting the POST and reading the
 * `Idempotency-Key` header across clicks:
 *
 *  - a response with `generated: false` rotates the nonce, so the next explicit click is a
 *    fresh request (the fix; watched failing before it);
 *  - a response with `generated: true` keeps the key, so a replay still costs nothing
 *    (D-159's documented property - this arm fails if someone "fixes" the above by rotating
 *    on every response);
 *  - a network error keeps the key, because the outcome is unknown: if the server committed
 *    before the response was lost, the retry must replay the stored row rather than pay
 *    again. This is the case the per-mount key exists for.
 *
 * All three arms intercept at the network layer, so no Postgres seeding and no dependency
 * on the mock gateway's behaviour - the contract under test is entirely the client's.
 */

import type { Page, Route } from "@playwright/test";

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";

test.describe.configure({ timeout: 120_000 });

function reportBody(generated: boolean): string {
  return JSON.stringify({
    audience: "student",
    interpretation_text: generated ? "A generated interpretation." : "Facts only.",
    recommendations_text: generated ? "A generated recommendation." : "Keep practicing.",
    generated,
    verified_facts: { attempts_count: 3, date_range_label: "all time" },
    created_at: new Date().toISOString(),
  });
}

/** Collects the Idempotency-Key of every intercepted report POST; `respond` decides each call. */
async function interceptReportPosts(
  page: Page,
  keys: string[],
  respond: (route: Route, call: number) => Promise<void>,
): Promise<void> {
  let call = 0;
  await page.route("**/learning/students/*/report*", async (route) => {
    if (route.request().method() !== "POST") {
      await route.fallback();
      return;
    }
    keys.push(route.request().headers()["idempotency-key"] ?? "");
    await respond(route, call++);
  });
}

async function openDashboard(page: Page): Promise<void> {
  // **Deliberately shares `studentPresent`** (WORK-13-FIXTURES). No session is started, and
  // the report POSTs are intercepted at the network layer (see the header) - the server
  // never sees them, so there is no per-student state to collide over.
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await page.getByRole("button", { name: /view progress dashboard/i }).click();
  await expect(page.getByRole("heading", { name: /progress dashboard/i })).toBeVisible({
    timeout: 30_000,
  });
}

test("a degraded report rotates the key, so an explicit retry is a fresh request", async ({
  page,
  audit,
}) => {
  const keys: string[] = [];
  await interceptReportPosts(page, keys, (route) =>
    route.fulfill({ contentType: "application/json", body: reportBody(false) }),
  );
  await openDashboard(page);

  await page.getByRole("button", { name: /^generate report$/i }).click();
  // The facts-only styling is the visible half of `generated: false`.
  await expect(page.locator(".report-block.facts-only")).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: /regenerate report/i }).click();
  await expect
    .poll(() => keys.length, { timeout: 15_000 })
    .toBe(2);

  audit.note(`degraded arm keys: ${keys[0]} -> ${keys[1]}`);
  expect(keys[0], "the first request must carry a key").not.toBe("");
  expect(
    keys[1],
    "after a degraded (generated=false) response, Regenerate must send a NEW key - " +
      "the same key would silently replay the degraded row (D-161's defect)",
  ).not.toBe(keys[0]);
});

test("a generated report keeps the key, so a replay still pays nothing", async ({
  page,
  audit,
}) => {
  const keys: string[] = [];
  await interceptReportPosts(page, keys, (route) =>
    route.fulfill({ contentType: "application/json", body: reportBody(true) }),
  );
  await openDashboard(page);

  await page.getByRole("button", { name: /^generate report$/i }).click();
  await expect(page.locator(".report-block:not(.facts-only)").first()).toBeVisible({
    timeout: 15_000,
  });

  await page.getByRole("button", { name: /regenerate report/i }).click();
  await expect
    .poll(() => keys.length, { timeout: 15_000 })
    .toBe(2);

  audit.note(`generated arm keys: ${keys[0]} -> ${keys[1]}`);
  expect(
    keys[1],
    "a successful report must keep the key: within one view a repeat is a replay of the " +
      "stored row, not a second paid call (D-159's documented property)",
  ).toBe(keys[0]);
});

test("a network error keeps the key, so a retry can replay a committed-but-lost report", async ({
  page,
  audit,
}) => {
  // This arm aborts the first POST on purpose, and the browser logs the failed fetch.
  audit.allow({ failedRequests: true, consoleErrors: ["Failed to fetch", "ERR_CONNECTION"] });
  const keys: string[] = [];
  await interceptReportPosts(page, keys, (route, call) =>
    call === 0
      ? route.abort("connectionreset")
      : route.fulfill({ contentType: "application/json", body: reportBody(true) }),
  );
  await openDashboard(page);

  await page.getByRole("button", { name: /^generate report$/i }).click();
  await expect(page.locator(".report-section .error")).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: /^generate report$/i }).click();
  await expect
    .poll(() => keys.length, { timeout: 15_000 })
    .toBe(2);

  audit.note(`error arm keys: ${keys[0]} -> ${keys[1]}`);
  expect(
    keys[1],
    "an error is an UNKNOWN outcome: the retry must reuse the key, because if the server " +
      "committed before the response was lost, a new key would pay twice - the exact " +
      "AUD-X-04 defect",
  ).toBe(keys[0]);
});
