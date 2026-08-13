/**
 * Where this harness points, and how it authenticates.
 *
 * Two targets, selected by `E2E_TARGET`:
 *
 * - `local` (default) - the docker-compose stack plus four dev servers this harness
 *   starts itself (see playwright.config.ts's `webServer`). `MockBedrockProvider`, so
 *   runs are free and deterministic.
 * - `staging` - the real CloudFront distributions. Same-origin routing (D-084) means
 *   the web URL *is* the API URL, so only the two web URLs need setting.
 *
 * On staging the app's own dev-login screen needs the `X-Staging-Token-Secret` header that
 * `POST /dev/token` is gated by (D-097). The screen *does* send one now - it grew a "Staging
 * secret" field - but only if a human types the secret into it, so an automated run still
 * mints tokens out of band (fixtures/session.ts) and seeds localStorage directly. That is
 * also how a *parent* journey skips straight to a dashboard.
 *
 * This paragraph read "the frontend never sends one" until 2026-08-07, which had stopped
 * being true and would have sent the next person looking at the wrong half of the system.
 */

import { execFileSync } from "node:child_process";

export type Target = "local" | "staging";

export const TARGET: Target = (process.env.E2E_TARGET as Target | undefined) ?? "local";

function env(name: string, fallback: string): string {
  const value = process.env[name];
  return value === undefined || value === "" ? fallback : value;
}

/** Trailing slashes make `${base}${path}` produce `//path`, which CloudFront 404s. */
function trimSlash(url: string): string {
  return url.replace(/\/+$/, "");
}

export const LEARNING_WEB = trimSlash(env("LEARNING_WEB_URL", "http://localhost:5173"));
export const CHAT_WEB = trimSlash(env("CHAT_WEB_URL", "http://localhost:5174"));

// Same-origin on staging; separate ports locally.
export const LEARNING_API = trimSlash(
  env("LEARNING_API_URL", TARGET === "staging" ? LEARNING_WEB : "http://localhost:8001"),
);
export const CHAT_API = trimSlash(
  env("CHAT_API_URL", TARGET === "staging" ? CHAT_WEB : "http://localhost:8002"),
);

/**
 * Per-app and deliberately not interchangeable (D-097). Absent locally, where
 * `/dev/token` is open. Never logged, never written to an artifact.
 *
 * On staging an empty secret is fatal *here* rather than seventeen specs later. Both
 * values used to default to `""`, `mintToken` omitted the header, and every
 * authenticated journey failed on its own 404 - a wall of unrelated-looking failures
 * with one cause, which is the most expensive shape a harness can fail in.
 *
 * **D-310: fetched here rather than inherited from the environment, because inheriting it
 * put it in the process table.** `make e2e-staging` used to fetch both and pass them as
 * environment assignments, on the stated grounds that they would "land in the child's envp
 * and never in argv, `ps`, or a shell history". Measured on a live run: **4 process-table
 * lines carried an expanded secret**, because npm's `exec` path and Playwright's workers
 * re-expose the inherited environment in their process titles. Any local process could read
 * both secrets with `ps` for the duration of a staging run.
 *
 * Fetching it here fixes that at the source: the only thing on any command line is the
 * secret's *id*, the value comes back on stdout to this process, and it lives in a
 * module-level constant that no child inherits. `execFileSync` (not `exec`) so there is no
 * shell to quote through, and no new dependency - the `aws` CLI was already a hard
 * requirement of the target that used to do the fetching.
 */
const SECRET_IDS = {
  learning: "intellichoice-staging/learning-api/staging-token-shared-secret",
  chat: "intellichoice-staging/chat-api/staging-token-shared-secret",
} as const;

function stagingSecret(app: "learning" | "chat", name: string): string {
  // An explicitly supplied value still wins, so CI or a one-off can inject one without AWS
  // access. It is no longer how `make e2e-staging` works.
  const supplied = process.env[name] ?? "";
  if (supplied !== "") return supplied;
  if (TARGET !== "staging") return "";

  const profile = process.env.AWS_PROFILE;
  const args = [
    ...(profile ? ["--profile", profile] : []),
    "secretsmanager",
    "get-secret-value",
    "--secret-id",
    SECRET_IDS[app],
    "--query",
    "SecretString",
    "--output",
    "text",
  ];
  let value = "";
  try {
    value = execFileSync("aws", args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] })
      .trim();
  } catch (error) {
    throw new Error(
      `could not read the ${app} /dev/token secret from Secrets Manager, so every ` +
        `authenticated ${app} journey would fail on a 404 (D-097). Check that the AWS CLI is ` +
        `authenticated (\`aws sts get-caller-identity\`) and that AWS_PROFILE names a profile ` +
        `with access. Underlying failure: ${(error as Error).message.split("\n")[0]}`,
    );
  }
  // The same length floor the Makefile used to apply, kept because it is the check that
  // distinguishes "fetched nothing" from "fetched a real secret" without printing either.
  if (value.length < 10) {
    throw new Error(
      `the ${app} /dev/token secret came back shorter than 10 characters - refusing to run ` +
        `rather than fail seventeen journeys on a 404 (D-097).`,
    );
  }
  return value;
}

export const STAGING_TOKEN_SECRET = {
  learning: stagingSecret("learning", "STAGING_TOKEN_SECRET_LEARNING"),
  chat: stagingSecret("chat", "STAGING_TOKEN_SECRET_CHAT"),
};

/**
 * The seeded fixture accounts, mirroring learning-web's own DevLoginScreen list so a
 * journey and the screen it drives cannot disagree about who exists.
 */
export const FIXTURES = {
  /** Present this week, one linked parent - the only student who clears the gate. */
  studentPresent: { role: "student", sub: "student-ext-1" },
  /** Absent this week - drives the attendance-gate journey. */
  studentAbsent: { role: "student", sub: "student-ext-2" },
  /**
   * No attendance row at all. SPEC §5.4.4's fail-closed case: unknown ≠ present, so this
   * student must be gated exactly like an absent one.
   */
  studentUnknownAttendance: { role: "student", sub: "student-ext-3" },
  /** Present, no parent link. */
  studentUnlinked: { role: "student", sub: "student-ext-4" },
  /**
   * The per-band walk students (D-288), one per grade band the bank serves. Each walk gets
   * its own student because staging's sessions persist: two tests signing in as the same
   * student resume each other's exams (the journey-student isolation finding). All present.
   */
  studentBandK2: { role: "student", sub: "student-ext-5" },
  studentBand35: { role: "student", sub: "student-ext-6" },
  studentBand68: { role: "student", sub: "student-ext-7" },
  studentBand912: { role: "student", sub: "student-ext-8" },
  /** The refresh-restores-position test's own student, isolating it from the full walk. */
  studentResume: { role: "student", sub: "student-ext-9" },
  /** One linked child - exercises the auto-select path. */
  parentOneChild: { role: "parent", sub: "parent-ext-1" },
  /** Two linked children - exercises the child_selection interrupt. */
  parentTwoChildren: { role: "parent", sub: "parent-ext-2" },
} as const;

export const TOPIC_ID = "linear_equations";
