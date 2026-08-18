import { defineConfig, devices } from "@playwright/test";
import { CHAT_WEB, LEARNING_WEB, TARGET } from "./config";

const isLocal = TARGET === "local";

/**
 * S39/AUD-F. Chromium by default: this audits *our* contracts against real APIs, not browser
 * compatibility, and one engine keeps the console/network evidence comparable between runs.
 *
 * **That default has one measured exception, added in D-397.** "Not browser compatibility" was
 * the right scope until V11 showed it hides a class of *our own* bugs: D-352's `downloadIcs`
 * fixes could not be held by any Chromium assertion, because Chromium tolerates exactly what
 * they fixed. The `webkit` project below runs only the specs tagged `@browser`, where browser
 * behaviour is the subject rather than the environment.
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
  projects: [
    // `grepInvert` is not optional: without it a `@mobile` spec runs on *both* projects, and
    // on the desktop one it asserts a phone viewport it does not have.
    {
      name: "chromium",
      grepInvert: /@mobile/,
      use: { ...devices["Desktop Chrome"] },
    },
    // D-350: a second viewport, running only the specs that opt in by name (`@mobile`).
    // Until this existed the suite was Desktop Chrome only, which is why chat-web shipped
    // with **no width media query at all** and nobody saw it: at 360px the header crushed,
    // the calendar dialog's three buttons collapsed, and the composer sat under the iOS home
    // indicator. Scoped by grep rather than run wholesale - the point is to keep the layout
    // honest, not to double a 75-test suite's wall clock.
    {
      name: "mobile",
      grep: /@mobile/,
      use: { ...devices["Pixel 7"] },
    },
    // D-397 (OPEN_DECISIONS #13): a second *engine*, running only the specs where browser
    // behaviour is itself the subject (`@browser`).
    //
    // **Why this exists is a measurement, not a preference.** D-352 fixed two browser-fragility
    // bugs in `downloadIcs` - an anchor never appended to the document, and `revokeObjectURL`
    // called synchronously after `click()`. V11 then wrote `calendar-branches.spec.ts` to hold
    // that fix and found it could not: reverting `downloadIcs` left **both tests passing**,
    // because Chromium tolerates both. A whole class of defect - the one where a browser is
    // lenient - was structurally invisible to a single-engine suite, and no assertion written
    // against Chromium could have been wrong about it.
    //
    // **And then this engine tolerated both bugs as well, which is the honest result.** The
    // recommendation that produced this project said WebKit "is the strictest of the three about
    // detached anchors and revoked object URLs, so it is the engine that would have caught
    // D-352". Measured: with `downloadIcs` reverted to its pre-D-352 form, both specs **pass on
    // WebKit too**. The measurement has a positive control - changing the download filename in
    // the same edit makes the same spec fail with `Received: "PROOF-THE-EDIT-IS-LIVE.ics"` - so
    // this is a real negative, not a dev server serving a stale bundle.
    //
    // A likely reason, untested and therefore stated as a guess: Playwright drives downloads
    // through the automation protocol rather than the browser's ordinary download path, so the
    // strictness that would bite in real Safari may not be reachable from any Playwright engine.
    //
    // **`downloadIcs` is held now, but not by this project** (D-399): `ics-download-dom-contract`
    // patches `click` and `revokeObjectURL` and asserts what the code did rather than how a
    // browser reacted, which is the only thing that discriminated the fix after two attempts that
    // did not. The class where a browser is *lenient* remains structurally invisible to any
    // reaction-based assertion here, on either engine.
    //
    // What this project does buy is real and smaller than advertised: the download and dialog
    // specs run on the engine every iPhone and iPad uses, which for a product whose parents read
    // reports on phones is worth the seconds it costs.
    //
    // Scoped by grep rather than run wholesale, for the same reason as `mobile` above. `@browser`
    // specs keep running on chromium too - this project *adds* an engine, it does not move
    // coverage onto one.
    //
    // The cost is lower than OPEN_DECISIONS #13 estimated, and that estimate was wrong about its
    // premise too: CI type-checks this harness (`e2e-typecheck`) and never runs it, so there is
    // no second browser download in CI to pay for.
    {
      name: "webkit",
      grep: /@browser/,
      use: { ...devices["Desktop Safari"] },
    },
  ],

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
