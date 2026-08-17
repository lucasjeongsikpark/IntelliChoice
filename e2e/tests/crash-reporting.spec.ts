/**
 * D-389: a real render crash, in both apps, all the way to the sink.
 *
 * The last of the 2026-08-17 audit's never-walked paths: "the ErrorBoundary → client-error
 * reporting loop". Both apps have the loop — `ErrorBoundary.componentDidCatch` calls
 * `reportClientError`, which POSTs to `/{app}/client-errors` — and **nothing exercised it**.
 * `test_client_errors.py` in each API proves the endpoint works *if something calls it*; no test
 * anywhere proved anything does. A boundary that catches but never reports is indistinguishable
 * from a working one at the browser, and it makes every client crash in production invisible,
 * which is the gap U5/D-328 built the sink to close in the first place.
 *
 * **How the crash is induced, and why this way.** Neither client validates a response before
 * rendering it — `client.ts` casts (`as SessionSnapshot`) — so a well-formed JSON body of the
 * wrong *shape* reaches render and throws there, which is a real failure mode rather than a
 * synthetic one. The alternative — dispatching a synthetic `error` event — would test
 * `window.onerror`, a different path with a different reporter.
 *
 * The two errors quoted in the allowances below are **the ones this actually produces**, not the
 * ones predicted when the stubs were written: `topics.filter is not a function` for a numeric
 * `topics`, and `Cannot read properties of undefined (reading 'filter')` for a turn response
 * missing a field the render path reads without checking. The predictions were `groupTopics`' map
 * and `citations.slice`, and both named the wrong line — so the allowances quote measured strings,
 * the same rule this suite applies to fixture bodies (D-386).
 *
 * **The console error is expected and must not be asserted away.** `componentDidCatch` logs
 * `react_render_crash` *deliberately*: its comment says §2.6 criterion 3 counts console errors and
 * "a crash that destroyed the UI *should* fail that criterion loudly". So this file allows that
 * one string rather than asserting the console is clean — the opposite of
 * `pii-typed-by-a-visitor.spec.ts`, and for a documented reason. Asserting cleanliness here would
 * be asserting against a decision the code states in as many words.
 */

import { CHAT_WEB, FIXTURES, LEARNING_WEB } from "../config";
import { expect, test } from "../fixtures/capture";
import { seedGuest, signInViaUi } from "../fixtures/session";
import { startSession } from "../fixtures/learning-flow";
import { ask } from "../fixtures/stub-chat";

interface Report {
  body: string;
  /** The status the server actually answered with, or null while still in flight. */
  status: number | null;
}

/**
 * Records every POST to the app's crash sink **and what came back**.
 *
 * Counting requests is not enough, and this test found out the hard way: the first version polled
 * `page.on("request")`, passed, and then failed teardown with
 * `POST /learning/client-errors - net::ERR_ABORTED`. A report that is *issued* and never *lands*
 * leaves exactly the blind spot the sink exists to remove, so the assertion has to be the 202.
 * Same lesson as D-288, one layer down: count acknowledgements, not attempts.
 */
function watchTheSink(page: import("@playwright/test").Page, path: string): Report[] {
  const reports: Report[] = [];
  page.on("request", (request) => {
    if (request.url().includes(path) && request.method() === "POST") {
      reports.push({ body: request.postData() ?? "", status: null });
    }
  });
  page.on("response", (response) => {
    const request = response.request();
    if (request.url().includes(path) && request.method() === "POST") {
      const pending = reports.find((r) => r.status === null);
      if (pending) pending.status = response.status();
    }
  });
  return reports;
}

test("learning-web: a render crash shows the fallback and reaches the sink", async ({
  page,
  audit,
}) => {
  audit.allow({
    // The boundary's own deliberate log, React's separate re-throw of the same TypeError, and
    // Chromium's note for the stubbed response. Quoted from a run, not predicted.
    consoleErrors: [
      "react_render_crash",
      "topics.filter is not a function",
      "Failed to load resource",
    ],
    serverErrors: true,
  });
  const reports = watchTheSink(page, "/learning/client-errors");

  await page.route("**/learning/sessions/*/topics", async (route) => {
    // GET only: the POST on this same path is how a topic is *chosen*, and
    // `error-vocabulary.spec.ts` owns that one. Breaking both would crash before the list renders
    // for a different reason than the one under test.
    if (route.request().method() !== "GET") return route.continue();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      // `topics` is typed `TopicOption[]` and cast, never validated. A number reaches
      // `groupTopics` and throws inside render.
      body: JSON.stringify({ learning_session_id: "crash-probe", topics: 42 }),
    });
  });

  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentUnlinked);
  await startSession(page);

  await expect(
    page.getByRole("heading", { name: /something went wrong on this screen/i }),
    "the crash left the student on a blank page instead of the boundary's fallback",
  ).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("button", { name: /reload the page/i })).toBeVisible();

  await expect
    .poll(() => reports.filter((r) => r.status !== null).length, {
      message:
        "the boundary caught the crash but no report was *acknowledged* - every client crash in " +
        "production is invisible if this is the real behaviour",
      timeout: 15_000,
    })
    .toBeGreaterThan(0);

  expect(reports[0].status, "the sink did not accept the report").toBe(202);

  const payload = JSON.parse(reports[0].body) as { message?: string; stack?: string };
  expect(payload.message, "the report carried no message").toBeTruthy();
  expect(
    payload.stack,
    "the report carried no component stack, which is the half that says *where* it broke",
  ).toContain("component stack");
});

test("chat-web: a render crash shows the fallback and reaches the sink", async ({
  page,
  audit,
}) => {
  audit.allow({
    consoleErrors: [
      "react_render_crash",
      "Cannot read properties of undefined (reading 'filter')",
      "Failed to load resource",
    ],
    serverErrors: true,
  });
  const reports = watchTheSink(page, "/chat/client-errors");

  await page.route("**/chat/sessions/*/messages", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      // Deliberately missing the fields the transcript renders without checking, which is what
      // a real shape drift looks like. Measured result: `Cannot read properties of undefined
      // (reading 'filter')` inside render - a TypeError, not a handled API error.
      body: JSON.stringify({
        chat_session_id: "crash-probe",
        answer: "Saturday hours are 9 to 5.",
        citations: 42,
        scope: "public",
        intent: "hours",
      }),
    }),
  );

  await seedGuest(page);
  await page.goto(CHAT_WEB);
  await ask(page, "What are the Saturday hours?");

  await expect(
    page.getByRole("heading", { name: /something went wrong on this screen/i }),
    "the crash left the visitor on a blank page instead of the boundary's fallback",
  ).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("button", { name: /reload the page/i })).toBeVisible();

  await expect
    .poll(() => reports.filter((r) => r.status !== null).length, {
      message: "chat-web's boundary caught the crash but no report was acknowledged",
      timeout: 15_000,
    })
    .toBeGreaterThan(0);

  expect(reports[0].status, "the sink did not accept the report").toBe(202);

  const payload = JSON.parse(reports[0].body) as { message?: string };
  expect(payload.message).toBeTruthy();
});
