/**
 * AUD-F-16: what version of the API did this run actually test?
 *
 * The finding was that nobody could say. `playwright.config.ts` sets
 * `reuseExistingServer: true`, and the two `uvicorn` processes had been up since two days
 * before the run - started before four authorization fixes merged. The vite dev servers
 * are torn down and restarted every run, so the *frontends* were current while the *APIs*
 * were frozen: nothing looked stale, and every S39/S40 `local` result is of an unknown
 * application version.
 *
 * So a run records the identity, and asserts it. The two environments go stale
 * differently and - the part that took a wrong turn first - they are not even readable
 * the same way:
 *
 * - `local` - there is no image and no SHA, so the identity is boot time, read from
 *   `/healthz`, and the assertion is that the API booted *after* the newest Python source
 *   file. A server older than the code it claims to run is the finding, stated directly.
 *   This is what `reuseExistingServer: true` could not notice.
 * - `staging` - **`/healthz` is not reachable, on purpose.** `terraform/environments/
 *   staging/main.tf` excludes it and `/metrics` from CloudFront's API path patterns:
 *   "internal-only, never meant to be publicly reachable". The first version of this file
 *   fetched it anyway and would have failed every staging run against the SPA's
 *   index.html. Widening a public surface to satisfy a test harness is the wrong trade, so
 *   staging reads the identity from **ECS itself** - the image tag on the task definition
 *   the service is actually running.
 *
 * The ECS route is strictly better evidence than the HTTP one it replaced: it reports what
 * the cluster is running rather than what a process says about itself, and it cannot be
 * satisfied by a stale task that is still answering. `make e2e-staging` already needs an
 * AWS session to mint tokens (D-097), so this adds no new requirement.
 *
 * Fails the run rather than warning. A warning in a test log is a thing nobody reads,
 * which is the same failure mode as the original defect.
 */

import { execFileSync } from "node:child_process";
import { statSync } from "node:fs";
import { CHAT_API, LEARNING_API, TARGET } from "../config";

/**
 * No `--profile` by default: the AWS CLI's own resolution order already handles a named
 * profile (`AWS_PROFILE`), exported credentials, and an assumed role in CI. Hardcoding a
 * developer's profile name would work on one laptop and fail everywhere else, including
 * CI, where no such profile exists. `E2E_AWS_PROFILE` forces one when that is wanted.
 */
const AWS_PROFILE = process.env.E2E_AWS_PROFILE;
const ECS_CLUSTER = process.env.ECS_CLUSTER ?? "intellichoice-staging";

export interface BuildIdentity {
  service: string;
  /** Where the identity was read from - a `/healthz` URL locally, an ECS ARN on staging. */
  source: string;
  build_sha: string;
  /** Process boot time. Only the local path can know this; "unknown" on staging. */
  started_at: string;
  uptime_seconds: number;
}

/**
 * Newest mtime across the Python sources the two APIs import, as epoch ms.
 *
 * `git ls-files` rather than a directory walk: it is the same set of files a commit would
 * carry, so it cannot be thrown off by `__pycache__`, a stray virtualenv, or an editor
 * swap file - any of which would make this check either useless or permanently red.
 */
function newestSourceMtimeMs(): number {
  const out = execFileSync(
    "git",
    ["ls-files", "-z", "apps/*/src/**/*.py", "packages/*/src/**/*.py"],
    { cwd: new URL("../..", import.meta.url).pathname, encoding: "utf8" },
  );
  const files = out.split("\0").filter(Boolean);
  if (files.length === 0) throw new Error("no Python sources found - is this a git checkout?");
  const root = new URL("../..", import.meta.url).pathname;
  return Math.max(...files.map((f) => statSync(`${root}/${f}`).mtimeMs));
}

async function fetchIdentityOverHttp(service: string, base: string): Promise<BuildIdentity> {
  const url = `${base}/healthz`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${service} /healthz returned ${res.status}`);
  const body = (await res.json()) as Partial<BuildIdentity>;
  if (typeof body.started_at !== "string") {
    // An API too old to carry the identity is itself the stale-server case this exists
    // to catch, so say that rather than reporting a missing field.
    throw new Error(
      `${service} /healthz has no started_at - it predates AUD-F-16's fix, which means it is exactly the stale server this check is for (${url})`,
    );
  }
  return {
    service,
    source: url,
    build_sha: body.build_sha ?? "unknown",
    started_at: body.started_at,
    uptime_seconds: body.uptime_seconds ?? -1,
  };
}

function aws(args: string[]): string {
  const profileArgs = AWS_PROFILE ? ["--profile", AWS_PROFILE] : [];
  return execFileSync("aws", [...profileArgs, ...args], { encoding: "utf8" }).trim();
}

/**
 * The image tag ECS is running for `service`, as a git SHA prefix.
 *
 * `deploy-staging.yml` tags every image `gha-${GITHUB_SHA::12}`, so the tag *is* the
 * identity and no cooperation from the application is needed.
 */
function readIdentityFromEcs(service: string): BuildIdentity {
  const taskDefArn = aws([
    "ecs", "describe-services",
    "--cluster", ECS_CLUSTER,
    "--services", `${ECS_CLUSTER}-${service}`,
    "--query", "services[0].taskDefinition",
    "--output", "text",
  ]);
  if (!taskDefArn || taskDefArn === "None") {
    throw new Error(`no task definition for ${service} in cluster ${ECS_CLUSTER}`);
  }
  // The sidecar shares the task definition, so select this service's own container
  // rather than taking the first image (D-104's collector rides alongside both apps).
  const image = aws([
    "ecs", "describe-task-definition",
    "--task-definition", taskDefArn,
    "--query", `taskDefinition.containerDefinitions[?name=='${service}'].image | [0]`,
    "--output", "text",
  ]);
  const tag = image.split(":").pop() ?? "";
  const match = /^gha-([0-9a-f]+)$/.exec(tag);
  return {
    service,
    source: taskDefArn,
    // A tag that is not `gha-<sha>` is worth surfacing verbatim rather than normalising
    // away: it means something other than this pipeline set the image.
    build_sha: match ? match[1] : `unrecognised-tag:${tag}`,
    started_at: "unknown",
    uptime_seconds: -1,
  };
}

/**
 * Read both APIs' identity, assert freshness, and return the records for the run log.
 * Called once per run from `globalSetup`, not per test - the answer cannot change
 * mid-run, and a per-test check would be 40 identical HTTP calls.
 */
export async function collectBuildIdentity(): Promise<BuildIdentity[]> {
  if (TARGET === "local") {
    const identities = await Promise.all([
      fetchIdentityOverHttp("learning-api", LEARNING_API),
      fetchIdentityOverHttp("chat-api", CHAT_API),
    ]);
    const newest = newestSourceMtimeMs();
    for (const id of identities) {
      const bootedMs = Date.parse(id.started_at);
      if (bootedMs < newest) {
        const staleBy = Math.round((newest - bootedMs) / 1000);
        throw new Error(
          `${id.service} booted at ${id.started_at}, which is ${staleBy}s BEFORE the newest Python source file. ` +
            `It is running code older than this checkout, so any result from this run is of an unknown version (AUD-F-16). ` +
            `Restart it, or unset reuseExistingServer.`,
        );
      }
    }
    return identities;
  }

  const identities = ["learning-api", "chat-api"].map(readIdentityFromEcs);

  // Asserted only on request: only the caller knows which SHA it meant to test. Compared
  // as a prefix because the image tag carries 12 characters of a 40-character SHA, so a
  // pasted full SHA and a copied tag both work.
  const expected = process.env.EXPECT_BUILD_SHA?.trim().toLowerCase();
  if (expected) {
    for (const id of identities) {
      const matches =
        expected.startsWith(id.build_sha) || id.build_sha.startsWith(expected);
      if (!matches) {
        throw new Error(
          `${id.service} is running ${id.build_sha}, expected ${expected}. ` +
            `The deployed code is not the code under test (AUD-F-16). Source: ${id.source}`,
        );
      }
    }
  }

  return identities;
}
