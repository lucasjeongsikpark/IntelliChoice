import { defineConfig, devices } from "@playwright/test";
import { CHAT_WEB, LEARNING_WEB, TARGET } from "./config";

const isLocal = TARGET === "local";

/**
 * S39/AUD-F. Chromium only: this audits *our* contracts against real APIs, not browser
 * compatibility, and a single engine keeps the console/network evidence comparable
 * between runs.
 *
 * `workers: 1` is not a performance concession - the journeys mutate shared Postgres
 * and MySQL state (one seeded student per fixture account), so parallel workers would
 * race each other into findings that are artifacts of the harness.
 *
 * `retries: 0` for the same reason S37/S38 kept probes out of the test suite: an audit
 * wants the first result, and a retry that passes hides exactly the flake §2.6
 * criterion 4 asks to eliminate.
 *
 * S43 (AUD-F-16): `reuseExistingServer: true` below is kept - restarting the APIs on
 * every run would make the local loop much slower, and the reuse is not the defect. The
 * defect was that reuse was *unverifiable*. `globalSetup` now reads both APIs' identity
 * and fails the run if either booted before the newest source file, which is the check
 * that makes the reuse safe rather than merely convenient.
 */
export default defineConfig({
  testDir: "./tests",
  globalSetup: "./fixtures/global-setup.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "artifacts/report" }],
    ["json", { outputFile: "artifacts/results.json" }],
  ],
  outputDir: "artifacts/test-results",
  use: {
    ...devices["Desktop Chrome"],
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    // Staging goes through CloudFront; a cold cache behind an invalidation is slow.
    actionTimeout: isLocal ? 15_000 : 30_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],

  // Locally the harness owns the whole stack, so a run needs only `make up` first
  // (Postgres + MySQL). Against staging it starts nothing.
  webServer: isLocal
    ? [
        {
          command: "uv run uvicorn learning_api.main:app --port 8001",
          cwd: "..",
          url: "http://localhost:8001/healthz",
          reuseExistingServer: true,
          timeout: 120_000,
        },
        {
          command: "uv run uvicorn chat_api.main:app --port 8002",
          cwd: "..",
          url: "http://localhost:8002/healthz",
          reuseExistingServer: true,
          timeout: 120_000,
        },
        {
          command: "npm run dev -- --port 5173 --strictPort",
          cwd: "../apps/learning-web",
          url: LEARNING_WEB,
          reuseExistingServer: true,
          timeout: 120_000,
        },
        {
          command: "npm run dev -- --port 5174 --strictPort",
          cwd: "../apps/chat-web",
          url: CHAT_WEB,
          reuseExistingServer: true,
          timeout: 120_000,
        },
      ]
    : undefined,
});
