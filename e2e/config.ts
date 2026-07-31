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
 * On staging the app's own dev-login screen cannot work: `POST /dev/token` needs the
 * `X-Staging-Token-Secret` header (D-097) and the frontend never sends one. So the
 * staging path mints tokens out of band (fixtures/session.ts) and seeds localStorage
 * directly, which is also how a *parent* journey skips straight to a dashboard.
 */

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
 * with one cause, which is the most expensive shape a harness can fail in. `make
 * e2e-staging` now fetches both from Secrets Manager; this check is what makes running
 * `npx playwright test` by hand say so instead of lying.
 */
function stagingSecret(app: "learning" | "chat", name: string): string {
  const value = process.env[name] ?? "";
  if (TARGET === "staging" && value === "") {
    throw new Error(
      `${name} is unset, so every authenticated ${app} journey would fail on a 404 from ` +
        `the secret-gated /dev/token (D-097). Run \`make e2e-staging\`, which fetches it.`,
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
  /** One linked child - exercises the auto-select path. */
  parentOneChild: { role: "parent", sub: "parent-ext-1" },
  /** Two linked children - exercises the child_selection interrupt. */
  parentTwoChildren: { role: "parent", sub: "parent-ext-2" },
} as const;

export const TOPIC_ID = "linear_equations";
