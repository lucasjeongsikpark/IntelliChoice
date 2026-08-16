/**
 * Console + network capture, which is what makes a browser run *evidence* rather than
 * a green checkmark.
 *
 * INTEGRATION_PLAN §2.6 criterion 3 asks every launch journey to pass "zero console
 * errors, zero 5xx, zero blank/stuck states". All three are properties of the whole
 * run, not of any one assertion, so they are enforced at teardown over everything the
 * page did - a journey cannot pass by never looking.
 *
 * A test that deliberately drives an error path calls `audit.allow({...})` to narrow
 * the teardown check. That is an explicit, greppable opt-out; the default is strict.
 */

import { test as base, expect, type Page, type TestInfo } from "@playwright/test";
import { appendFileSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

export interface ConsoleRecord {
  type: string;
  text: string;
  location: string;
}

export interface NetworkRecord {
  method: string;
  url: string;
  status: number;
  /** Milliseconds since the log was created. Distinguishes a sustained poll from a burst. */
  at: number;
  /** Present only when E2E_CAPTURE_BODIES=1, or always for non-2xx (see below). */
  body?: string;
}

export interface FailedRequest {
  method: string;
  url: string;
  failure: string;
}

/**
 * A console-error allowance narrowed to the request that produced it.
 *
 * Chromium logs `Failed to load resource: the server responded with a status of 409 ()`
 * for every non-2xx fetch, and **the message text does not name the URL - the location
 * does**. So a bare `"Failed to load resource"` string forgives that error on every path
 * at once. `journey-student.spec.ts` meant to forgive AUD-F-02's post-finalize burst on
 * `exam/overview`, and its comment said "allowed by path here"; what it actually allowed
 * was any failed request anywhere in the walk, including a 409 on `POST /answers` - the
 * one request whose failure that journey exists to detect (D-355).
 */
export interface ScopedConsoleError {
  /** Substring of the console message text, as for a plain string allowance. */
  text: string;
  /** Forgiven only when the failing resource's URL matches. */
  url: RegExp;
}

/** What the teardown check is willing to forgive, set per test via `audit.allow()`. */
export interface Allowances {
  /**
   * A console error matching any entry is not a failure: a plain string matches the
   * message text anywhere, a `ScopedConsoleError` also requires the failing URL to match.
   */
  consoleErrors?: (string | ScopedConsoleError)[];
  /**
   * Status codes that may legitimately appear (e.g. 404 for a deliberate probe).
   *
   * **Reported, not enforced, and that is easy to misread** (D-355). `clientErrors` feeds
   * the artifact summary and *no assertion reads it* - `assertClean` covers page errors,
   * console errors, 5xx and failed requests, because those are what INTEGRATION_PLAN §2.6
   * criterion 3 lists. A 4xx fails a journey only through the console error Chromium logs
   * for it, so `consoleErrors` above is where the gate actually lives and this field
   * changes only what the artifact's `clientErrors` line reads after a run.
   */
  statuses?: number[];
  /** Skip the 5xx check entirely - only for tests whose subject *is* a 500. */
  serverErrors?: boolean;
  /** Skip the failed-request check (a deliberately aborted/blocked request). */
  failedRequests?: boolean;
}

/**
 * Bodies can carry fixture names/emails from the MySQL dev-fake. Artifacts are local
 * and gitignored, but CLAUDE.md rule 1 is about habit as much as storage, so full-body
 * capture is opt-in. Error bodies are always kept: a contract mismatch lives in the
 * 422 detail, and a FastAPI validation error carries no PII.
 */
const CAPTURE_BODIES = process.env.E2E_CAPTURE_BODIES === "1";

/** Whether one allowance forgives one console record. See `ScopedConsoleError`. */
function forgives(allowance: string | ScopedConsoleError, entry: ConsoleRecord): boolean {
  if (typeof allowance === "string") return entry.text.includes(allowance);
  return entry.text.includes(allowance.text) && allowance.url.test(entry.location);
}

export class AuditLog {
  private readonly startedAt = Date.now();
  readonly console: ConsoleRecord[] = [];
  readonly pageErrors: string[] = [];
  readonly network: NetworkRecord[] = [];
  readonly failedRequests: FailedRequest[] = [];
  private allowances: Allowances = {};
  /** Free-form notes a test wants to land in the artifact alongside the evidence. */
  readonly notes: string[] = [];

  /** Milliseconds since this log started - the clock every NetworkRecord is stamped on. */
  elapsed(): number {
    return Date.now() - this.startedAt;
  }

  allow(allowances: Allowances): void {
    this.allowances = { ...this.allowances, ...allowances };
  }

  note(message: string): void {
    this.notes.push(message);
  }

  get consoleErrors(): ConsoleRecord[] {
    const allowed = this.allowances.consoleErrors ?? [];
    return this.console
      .filter((entry) => entry.type === "error")
      .filter((entry) => !allowed.some((allowance) => forgives(allowance, entry)));
  }

  get serverErrors(): NetworkRecord[] {
    return this.network.filter((entry) => entry.status >= 500);
  }

  get clientErrors(): NetworkRecord[] {
    const allowed = this.allowances.statuses ?? [];
    return this.network.filter(
      (entry) => entry.status >= 400 && entry.status < 500 && !allowed.includes(entry.status),
    );
  }

  /** Every API call the journey made, in order - the contract record. */
  apiCalls(): NetworkRecord[] {
    return this.network.filter((entry) => !/\.(js|css|png|svg|woff2?|ico|map)(\?|$)/.test(entry.url));
  }

  assertClean(): void {
    expect(this.pageErrors, `uncaught page errors:\n${this.pageErrors.join("\n")}`).toEqual([]);
    expect(
      this.consoleErrors,
      `console errors:\n${this.consoleErrors.map((e) => `${e.text} @ ${e.location}`).join("\n")}`,
    ).toEqual([]);
    if (!this.allowances.serverErrors) {
      expect(
        this.serverErrors,
        `5xx responses:\n${this.serverErrors.map((e) => `${e.status} ${e.method} ${e.url}`).join("\n")}`,
      ).toEqual([]);
    }
    if (!this.allowances.failedRequests) {
      expect(
        this.failedRequests,
        `failed requests:\n${this.failedRequests.map((e) => `${e.method} ${e.url} - ${e.failure}`).join("\n")}`,
      ).toEqual([]);
    }
  }

  toJSON(): unknown {
    return {
      console: this.console,
      pageErrors: this.pageErrors,
      failedRequests: this.failedRequests,
      apiCalls: this.apiCalls(),
      notes: this.notes,
    };
  }
}

function attach(page: Page, log: AuditLog): void {
  page.on("console", (message) => {
    const location = message.location();
    log.console.push({
      type: message.type(),
      text: message.text(),
      location: `${location.url}:${location.lineNumber}`,
    });
  });

  // A React render crash surfaces here, not in `console` - and it is exactly the class
  // of bug the blank-screen findings (AUD-C-10, S22.5's blank turn) belong to.
  page.on("pageerror", (error) => {
    log.pageErrors.push(`${error.name}: ${error.message}\n${error.stack ?? ""}`);
  });

  page.on("requestfailed", (request) => {
    const failure = request.failure()?.errorText ?? "unknown";
    // An SSE connection that the client deliberately closes surfaces here as
    // `net::ERR_ABORTED`, because it was a request still in flight. Both apps' session
    // hooks close their `EventSource` in the effect's cleanup, so every screen swap
    // produces one - 71 in a single 38-second run, which read as a reconnect storm until
    // it was measured: with the student idle the stream is opened 0 times in 20s
    // (tests/learning/sse-reconnect.spec.ts). Counting these as failures would have made
    // every journey fail for doing exactly what it is supposed to do.
    //
    // `POST /exam/items/{id}/time` is aborted for a related-but-different reason: it is
    // explicitly fire-and-forget in the hook (`void api.recordItemTime(...).catch(() => {})`),
    // so one still in flight when the screen unmounts is aborted by design. Its *volume* is
    // the real finding and is tracked as AUD-F-01, measured properly in
    // tests/learning/time-telemetry.spec.ts - not as a pile of failed requests here.
    const url = request.url();
    if (failure === "net::ERR_ABORTED" && /\/stream(\?|$)|\/exam\/items\/[^/]+\/time$/.test(url)) {
      return;
    }
    log.failedRequests.push({ method: request.method(), url: request.url(), failure });
  });

  page.on("response", (response) => {
    const record: NetworkRecord = {
      method: response.request().method(),
      url: response.url(),
      status: response.status(),
      at: log.elapsed(),
    };
    const wantBody = CAPTURE_BODIES || response.status() >= 400;
    if (wantBody) {
      // Fire-and-forget: `body()` rejects for redirects and for a stream still open
      // (SSE never resolves), and neither is worth failing a journey over.
      void response
        .text()
        .then((text) => {
          record.body = text.slice(0, 4000);
        })
        .catch(() => undefined);
    }
    log.network.push(record);
  });
}

/**
 * One JSONL line per test into `artifacts/journeys.jsonl` plus a per-test JSON blob
 * attached to the Playwright report. The JSONL is what later analysis greps; the
 * attachment is what a human opens after a failure.
 */
function persist(log: AuditLog, testInfo: TestInfo): void {
  const summary = {
    test: testInfo.titlePath.join(" > "),
    status: testInfo.status,
    target: process.env.E2E_TARGET ?? "local",
    consoleErrorCount: log.consoleErrors.length,
    pageErrorCount: log.pageErrors.length,
    serverErrorCount: log.serverErrors.length,
    clientErrors: log.clientErrors.map((e) => `${e.status} ${e.method} ${e.url}`),
    ...(log.toJSON() as Record<string, unknown>),
  };
  const jsonl = new URL("../artifacts/journeys.jsonl", import.meta.url).pathname;
  mkdirSync(dirname(jsonl), { recursive: true });
  appendFileSync(jsonl, `${JSON.stringify(summary)}\n`);

  const perTest = testInfo.outputPath("audit.json");
  writeFileSync(perTest, JSON.stringify(summary, null, 2));
  void testInfo.attach("audit", { path: perTest, contentType: "application/json" });
}

export const test = base.extend<{ audit: AuditLog }>({
  audit: async ({ page }, use, testInfo) => {
    const log = new AuditLog();
    attach(page, log);
    await use(log);
    persist(log, testInfo);
    // Only enforced on a test that otherwise passed: a failed assertion has already
    // said what is wrong, and a teardown failure on top of it buries the real message.
    if (testInfo.status === "passed") log.assertClean();
  },
});

export { expect };
