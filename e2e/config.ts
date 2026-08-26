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
  /**
   * Present this week, one linked parent.
   *
   * **It stopped being "the only student who clears the gate" long ago** - a dozen students
   * below are present too. What it still is: the *shared* identity, kept for the specs that
   * only mint a token, read a dashboard or probe authorization, and the documented one-parent
   * child `deployed-authorization.spec.ts` uses as its parent-link control. Nothing that
   * creates a learning session signs in as it any more (WORK-13-FIXTURES); if a new spec
   * needs to, give it its own student rather than reopening the sharing.
   */
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
  /**
   * The main `journey-student` walk's own student (D-365 §2), same shape as `studentPresent`
   * (grade 3, present, one linked parent) so only the sharing changes.
   *
   * The walk that *named* the isolation finding above was the last one still sharing
   * `studentPresent` with seventeen other spec files. In isolation it is clean; in a whole
   * run it recorded 7 refused submissions and 2.3 minutes against 15 seconds, because it
   * resumed a session another spec had left mid-study.
   */
  studentJourney: { role: "student", sub: "student-ext-10" },
  /**
   * The terminal walk's own student (V1), same shape as `studentJourney` so the only
   * difference between the two walks is where they stop.
   *
   * **The isolation reason here is stronger than every other student's.** The others can be
   * resumed mid-flight, so sharing one costs time and confusing evidence. This walk drives a
   * session to `completed`, and a finished session cannot be carried on with: a second spec
   * signing in as this student would find a results screen and no way to start.
   */
  studentTerminal: { role: "student", sub: "student-ext-11" },
  /**
   * The email-approval walk's own student (V2): no attendance row, so §5.4.4's gate fires on
   * the routine "not marked yet" path. Separate from `studentUnknownAttendance`, which
   * `journey-attendance.spec.ts` drives to a *decline* - there is one gate per student per
   * week and two specs must not answer it differently.
   */
  studentUnknownEmail: { role: "student", sub: "student-ext-12" },
  /** The exam-expiry walk's own student (V10): it finalizes an exam, which is the one session
   *  state another spec cannot resume past. */
  studentExpiry: { role: "student", sub: "student-ext-13" },
  /**
   * The thirteen session-creating specs that were still sharing `studentPresent`
   * (WORK-13-FIXTURES) - the rest of the isolation finding `studentJourney` above names.
   *
   * Twenty-one spec files referenced `studentPresent`. Thirteen of them **create a learning
   * session** as that identity, and the journeys mutate shared Postgres and MySQL state
   * through one seeded account (`playwright.config.ts`'s `workers: 1` comment), so two of
   * them signing in as the same student are one test wearing two names. The other eight
   * references mint a token, read a dashboard, or probe authorization; each of those spec
   * files now carries a line saying why sharing is safe there.
   *
   * Same grade (3) and attendance (present) as `studentPresent`, **unlinked** rather than
   * one-parent: none of the thirteen drives a parent-facing path, so a parent apiece would
   * be thirteen accounts and thirteen PII needles for no coverage. `studentResume` and the
   * band students are the precedent. Kept in file-name order, which is the order the suite
   * runs them in, so a missing one is easy to see.
   */
  studentAssistance: { role: "student", sub: "student-ext-14" },
  studentExamPosition: { role: "student", sub: "student-ext-15" },
  studentHint: { role: "student", sub: "student-ext-16" },
  studentMutation: { role: "student", sub: "student-ext-17" },
  studentNarrativeDisplacement: { role: "student", sub: "student-ext-18" },
  studentNarrativeRace: { role: "student", sub: "student-ext-19" },
  studentNarrativeRefresh: { role: "student", sub: "student-ext-20" },
  studentTutorChat: { role: "student", sub: "student-ext-21" },
  studentPostFinalize: { role: "student", sub: "student-ext-22" },
  studentSseReconnect: { role: "student", sub: "student-ext-23" },
  studentTimeTelemetry: { role: "student", sub: "student-ext-24" },
  studentVideo: { role: "student", sub: "student-ext-25" },
  studentDoubleSubmit: { role: "student", sub: "student-ext-26" },
  /**
   * `dashboard-chart-labels.spec.ts`'s own, for the *opposite* reason to the thirteen above.
   *
   * That spec writes nothing, so it cannot interfere with anybody - but it needs a student
   * with charted history, and it was getting one by accident: whichever sharer of
   * `studentPresent` ran before it in the same run left the mastery rows its axes are drawn
   * from, and `apps/learning-api/tests/conftest.py` sweeps students 1-4 out of Postgres
   * around every pytest test, so that history never outlived one e2e run. Isolating the
   * sharers removed the supplier and the spec skipped itself - measured, on the first run
   * after the swap. It now walks to the study phase itself before reading the charts.
   */
  studentDashboard: { role: "student", sub: "student-ext-27" },
  /**
   * `solution-terminal-rung.spec.ts`'s own (M3-D370-SOLUTION-RUNG), same grade-3 /
   * present / unlinked shape as the thirteen above.
   *
   * **Its own rather than `studentAssistance`'s, even though both click "Show the
   * solution".** That spec is a screenshot probe: it stops at the panel. This one closes
   * the pause, answers the retry, and then reads the dashboard's own independence figure -
   * so sharing one account would make each walk's precondition the other's leftovers, which
   * is the isolation finding `studentJourney` names. Sharing `studentHint` fails the same
   * way from the other side: a resumed session can arrive with the ladder already part-spent
   * on a *hint*, which is a different rung and a different outcome label.
   */
  studentSolution: { role: "student", sub: "student-ext-28" },
  /**
   * `stream-disconnect-visible.spec.ts`'s own (D-427), same grade-3 / present / unlinked
   * shape as the thirteen above.
   *
   * **Its own rather than `studentSseReconnect`'s, even though both specs are about the
   * SSE stream.** That spec measures how often the app reopens `/stream` on its own over a
   * fixed idle window; this one routes `/stream` and refuses every attempt for the whole
   * test. Sharing would make one spec's subject the other's noise - and worse, the reopen
   * count `sse-reconnect` asserts a ceiling on is the exact quantity this spec distorts by
   * design.
   */
  studentDisconnect: { role: "student", sub: "student-ext-29" },
  /** One linked child - exercises the auto-select path. */
  parentOneChild: { role: "parent", sub: "parent-ext-1" },
  /** Two linked children - exercises the child_selection interrupt. */
  parentTwoChildren: { role: "parent", sub: "parent-ext-2" },
  /** `studentJourney`'s parent. Its own, so `parentOneChild` stays a one-child fixture. */
  parentJourney: { role: "parent", sub: "parent-ext-3" },
  /** `studentTerminal`'s parent, its own for the same AUD-F-22 reason. Not walked yet. */
  parentTerminal: { role: "parent", sub: "parent-ext-4" },
} as const;

export const TOPIC_ID = "linear_equations";
