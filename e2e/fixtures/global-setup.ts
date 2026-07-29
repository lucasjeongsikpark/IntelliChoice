/**
 * AUD-F-16: establish and record what this run is testing, before it tests anything.
 *
 * Runs once, after Playwright's `webServer` entries are up (globalSetup is sequenced
 * after them) and before the first spec. Two outputs:
 *
 * - a `run` line at the head of `artifacts/journeys.jsonl`, so the greppable record
 *   opens with the version of the thing under test rather than leaving it to be inferred;
 * - a thrown error if the local APIs are older than the checkout, which fails the whole
 *   run rather than letting 40 specs report on unknown code.
 *
 * The file is truncated here rather than appended to, which is the other half of the same
 * problem: `journeys.jsonl` used to accumulate across runs, so "the last run's evidence"
 * meant reading backwards and guessing where the boundary was.
 */

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { TARGET } from "../config";
import { collectBuildIdentity } from "./build-identity";

export default async function globalSetup(): Promise<void> {
  const identities = await collectBuildIdentity();

  const jsonl = new URL("../artifacts/journeys.jsonl", import.meta.url).pathname;
  mkdirSync(dirname(jsonl), { recursive: true });
  writeFileSync(
    jsonl,
    `${JSON.stringify({
      record: "run",
      target: TARGET,
      startedAt: new Date().toISOString(),
      apis: identities,
    })}\n`,
  );

  for (const id of identities) {
    // Printed as well as logged: the number that mattered in AUD-F-16 was two days old,
    // and it would have been obvious to anyone who saw it. Local reports boot time (there
    // is no image); staging reports the SHA (there is no readable process).
    const detail =
      id.started_at === "unknown"
        ? `sha=${id.build_sha}`
        : `booted=${id.started_at} uptime=${id.uptime_seconds}s`;
    console.log(`[build-identity] ${id.service} ${detail}`);
  }
}
