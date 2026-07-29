# Browser-driven journey audit (S39 / AUD-F)

Playwright harness for INTEGRATION_PLAN §2.3's browser half and §2.6 criterion 3. Built in
S39 because no browser automation existed here, which is what kept both S36 and S37 at ⏸.

```bash
make e2e-install     # once: npm install + chromium (~95 MB)
make up              # Postgres + MySQL (plus db-upgrade / seed / curriculum-load)
make e2e             # the suite; starts both APIs and both vite servers itself
make e2e-typecheck
```

Against real staging (same-origin CloudFront, so only the web URLs are needed):

```bash
export STAGING_TOKEN_SECRET_LEARNING=...   # never echo these
export STAGING_TOKEN_SECRET_CHAT=...
LEARNING_WEB_URL=https://<d1>.cloudfront.net \
CHAT_WEB_URL=https://<d2>.cloudfront.net \
make e2e-staging
```

`/dev/token` is secret-gated on staging (D-097) and the frontends never send that header, so
the harness mints tokens out of band and seeds `localStorage` before the app's first render.

## What makes a run evidence rather than a checkmark

`fixtures/capture.ts` attaches console + network capture to every page and enforces criterion
3's three properties **at teardown, over the whole run** — zero console errors, zero 5xx, zero
blank/stuck states — so a journey cannot pass by never looking. A test that deliberately drives
an error path narrows the check with an explicit `audit.allow({...})`; the default is strict.
Every run appends one JSON line per test to `artifacts/journeys.jsonl` (gitignored): notes,
console errors, and the full API call sequence with millisecond timestamps. That timestamping is
what separated a leaked interval from a remount burst in AUD-F-02.

**And the run says what it tested (S43 continuation, AUD-F-16).** `fixtures/global-setup.ts`
establishes both APIs' identity before the first spec, writes a `record: "run"` line at the head of
`journeys.jsonl`, and truncates the file so one run's evidence is one file rather than an
accumulating pile. The two targets are read differently, because they go stale differently and are
not even reachable the same way:

- **local** — `GET /healthz` for boot time, and the run **fails** if either API booted before the
  newest git-tracked Python source. That is the exact condition AUD-F-16 found: two `uvicorn`
  processes two days older than the checkout served an entire audit while the vite dev servers
  were current, so nothing looked stale. `reuseExistingServer: true` stays — reuse was never the
  defect, unverifiability was.
- **staging** — `/healthz` is **deliberately unreachable** there (`terraform/environments/staging/
  main.tf` excludes it and `/metrics` from CloudFront: "internal-only, never meant to be publicly
  reachable"), so the identity comes from **ECS** — the `gha-<sha>` image tag on the task
  definition the service is actually running. That is better evidence than an HTTP self-report: it
  says what the cluster runs, not what a process claims. Set `EXPECT_BUILD_SHA=<sha>` to assert the
  deployed code is the code under test. Needs an AWS session, which `make e2e-staging` already
  requires for token minting; `E2E_AWS_PROFILE` forces a named profile if you need one.

`tests/smoke.spec.ts` is the harness's own **positive control**: it produces a console error and
a failed request on purpose and asserts the fixture saw them. D-101 §5 and D-102 both record why
— a probe that can only return "clean" is not a measurement.

## Conventions worth keeping

- **chromium only, one worker, zero retries.** The journeys mutate shared Postgres/MySQL state,
  so parallel workers race into findings that are artifacts of the harness; and a retry that
  passes hides exactly the flake §2.6 criterion 4 exists to eliminate.
- **`test.fail()` marks a confirmed defect**, inside the test body (at file scope it would mark
  every test in the file). The suite stays green while the probe keeps measuring; when Phase 0B
  fixes the defect the test passes unexpectedly, fails the run, and that is the signal to drop
  the marker and promote it to a regression test.
- **`stableClick`** absorbs the app's re-render churn (AUD-F-05). Without it every journey
  inherits that race and a different defect would present as this one.
- **Measure before concluding.** Three plausible findings died this way — see D-103 §4.

## Known limitations (carry-over)

- The student walk stops at the study phase. It always picks the first option to stay
  deterministic, so it answers wrong and the study phase never reaches the mastery bar that ends
  it. Closing it means reading the answer off the ladder's "Show the solution" panel.
- A whole-suite run lands at 49–50 of 51, with 1–2 intermittent failures that move between runs
  — shared-state coupling between journeys, not the app. Criterion 3 wants two consecutive clean
  runs, so this needs fixing before the gate.
