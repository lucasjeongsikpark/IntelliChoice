/**
 * Every sentence `learning-web/src/api/errors.ts` can produce, rendered at least once — the
 * third of the 2026-08-17 audit's coverage gaps, for the app that had none of it.
 *
 * chat-web already has `tests/chat/error-states.spec.ts`. learning-web had nothing, and it is
 * the app with the larger table: twelve rules, five of them different 409s, plus a generic
 * fallback and a 5xx line. Not one of them had ever been on a screen in a test, which is how
 * D-378's unmatchable rule survived a month in the sibling file and how the
 * `{status: 400, detail: ["attendance"]}` rule survived here (deleted today - no response this
 * API sends has ever carried that word).
 *
 * **What this spec is and is not.** The failures are injected client-side, so this proves the
 * *client's* mapping renders - it is not evidence that the server produces these bodies. That
 * half is `apps/learning-api/tests/test_error_detail_contract.py`, which drives real requests to
 * real 409s and asserts the substrings this table relies on. Two tests, one claim each; either
 * alone would be the kind of half-check that let D-378 ship.
 *
 * Every `detail` below is **quoted from the raiser**, with its source named, because a fixture
 * body invented to match a rule proves only that the rule matches itself.
 *
 * **Injected on `POST /topics`, and not on `POST /answers`, for a reason worth knowing.**
 * `friendlyError` is a pure function of status and detail, so any failing mutation exercises the
 * whole table - but the exam screen is the one place its output is deliberately *not* what the
 * student reads. `ExamScreen` renders `saveFailure ?? error`, and D-378/D-381 made that
 * precedence on purpose: "Question 5 was not saved. Go back and answer it again." names the
 * question and outlives the request, where the per-status line had once claimed "Your progress is
 * saved" about an answer that had just been rolled back. The first version of this spec injected
 * on `/answers` and read that sentence instead, which is the app behaving correctly and the test
 * asking the wrong screen. The topic screen renders `friendlyError`'s output directly
 * (`TopicSelectScreen.tsx:39`), and re-clicking a topic is a clean retry, so the whole table can
 * be walked from one screen in seconds.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";
import { settleToInteractiveScreen, startSession } from "../../fixtures/learning-flow";

test.describe.configure({ timeout: 240_000 });

interface Case {
  name: string;
  status: number;
  /** The response body, exactly as the server would send it. */
  detail: unknown;
  /** What the student must read. */
  expected: RegExp;
  /** Where the quoted detail comes from. */
  source: string;
}

const CASES: Case[] = [
  {
    name: "409 duplicate submission",
    status: 409,
    detail: "item 7c1e0f9a-1b2c-4d5e-8f90-abcdef123456 has already been answered",
    expected: /already answered this one/i,
    source: "services/grading.py:21 (ItemAlreadyAnsweredError)",
  },
  {
    name: "409 exam time limit",
    status: 409,
    detail: "exam time limit exceeded - finalize to submit",
    expected: /exam time is up/i,
    source: "routers/sessions.py:1265",
  },
  {
    name: "409 item belongs to another session",
    status: 409,
    detail:
      "question variant 7c1e0f9a-1b2c-4d5e-8f90-abcdef123456 is not an item of this session",
    expected: /isn't part of this session any more/i,
    source: "routers/sessions.py:1202",
  },
  {
    name: "409 phase has moved on",
    status: 409,
    detail: "session is not accepting answers in phase study",
    expected: /moved on/i,
    source: "routers/sessions.py:1249",
  },
  {
    name: "409 student not selected",
    status: 409,
    detail: "select a student before a topic",
    expected: /finished starting up/i,
    source: "routers/sessions.py:1003 - and this one really is a /topics 409",
  },
  {
    name: "409 with no rule of its own",
    status: 409,
    detail: "topic already selected for this session",
    expected: /didn't fit where the session is/i,
    source: "routers/sessions.py:1067 (TopicAlreadySelectedError, via str(exc))",
  },
  {
    name: "403 wrong account",
    status: 403,
    detail: "not authorized for this session",
    expected: /isn't available for your account/i,
    source: "the audience/ownership guards",
  },
  {
    name: "404 gone or never theirs",
    status: 404,
    detail: "learning session not found",
    expected: /couldn't find this/i,
    source: "routers/sessions.py (session lookup) - the D-381 rule",
  },
  {
    name: "429 too many requests",
    status: 429,
    detail: "rate limit exceeded",
    expected: /a lot at once/i,
    source: "intellichoice_shared/rate_limit.py's global middleware",
  },
  {
    name: "500 our fault",
    status: 500,
    detail: "Internal Server Error",
    expected: /broke on our side/i,
    source: "any unhandled exception",
  },
  {
    // **The negative control, and the reason the deleted 400 rule was worth a test.** A 400 this
    // API really sends must fall to GENERIC, not to a sentence about attendance: the gate is a
    // *phase*, and any rule that claims otherwise is unmatchable by construction.
    name: "400 unknown topic falls to the generic line",
    status: 400,
    detail: "unknown topic 'no-such-topic'",
    expected: /didn't go through/i,
    source: "routers/sessions.py:1051",
  },
];

test("every error sentence a student can be shown actually renders", async ({ page, audit }) => {
  // Its own student is not needed: every submission below is intercepted before it reaches the
  // server, so this walk mutates nothing past creating a session and being served a pre-exam.
  // `studentUnlinked` is used by no other spec in this suite (checked 2026-08-17), so it is the
  // one existing fixture that carries no D-288 sharing risk.
  // **Every failure in this spec is deliberate, so the suite's "zero console errors / zero 5xx"
  // teardown has to be told** - Chromium logs "Failed to load resource" for each injected 4xx and
  // 5xx. Scoped to the one path this spec intercepts and to the statuses the table actually uses,
  // so a failure anywhere else, or a status nobody asked for, still fails the run. The first
  // version of this spec omitted it and failed teardown with 11 console errors it had created.
  // `serverErrors: true` because one of the eleven cases *is* a 500 - the capture fixture's own
  // stated exemption ("only for tests whose subject is a 500") applies to exactly this file.
  audit.allow({
    statuses: [...new Set(CASES.map((testCase) => testCase.status))],
    consoleErrors: [{ text: "Failed to load resource", url: /\/learning\/sessions\/[^/]+\/topics/ }],
    serverErrors: true,
  });

  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentUnlinked);
  await startSession(page);
  await settleToInteractiveScreen(page);
  const topic = page.getByRole("button", { name: /linear equations/i });
  await expect(topic, "never reached the topic screen").toBeVisible({ timeout: 60_000 });

  // A 401 is deliberately absent from the table: D-375 makes it sign the student out rather than
  // render a sentence, and `expired-token-recovery.spec.ts` covers that path. Asserting the 401
  // *message* here would assert behaviour the app is designed not to have.
  const rendered: string[] = [];
  for (const testCase of CASES) {
    await page.route("**/learning/sessions/*/topics", (route) =>
      route.fulfill({
        status: testCase.status,
        contentType: "application/json",
        body: JSON.stringify({ detail: testCase.detail }),
      }),
    );

    await topic.click();
    const error = page.locator("p.error");
    await expect(
      error,
      `${testCase.name}: the app showed no error at all for a ${testCase.status} whose detail ` +
        `comes from ${testCase.source}`,
    ).toBeVisible({ timeout: 30_000 });
    const text = (await error.innerText()).trim();
    rendered.push(`${testCase.status} -> ${text}`);
    audit.note(`${testCase.name}: ${JSON.stringify(text)}`);

    expect(
      text,
      `${testCase.name}: the student was shown ${JSON.stringify(text)}, which does not match ` +
        `${testCase.expected}. The detail was quoted from ${testCase.source}, so either the rule ` +
        "in errors.ts cannot match what the server sends (D-378's failure mode) or the wording " +
        "changed without this table",
    ).toMatch(testCase.expected);

    // **The raw wire text must never be on screen.** This is the incident the whole file exists
    // for: on staging 2026-08-06 a 409 put "question variant 3f2a… is not an item of this
    // session" in front of a child. A session id in an error message is frightening and useless
    // to them, and `logDetail` is where it belongs.
    if (typeof testCase.detail === "string") {
      const identifier = testCase.detail.match(/[0-9a-f]{8}-[0-9a-f]{4}/)?.[0];
      if (identifier !== undefined) {
        expect(
          text,
          `${testCase.name}: the raw detail leaked an identifier to the student`,
        ).not.toContain(identifier);
      }
    }

    await page.unroute("**/learning/sessions/*/topics");
  }

  audit.note(`rendered ${rendered.length} of ${CASES.length} sentences`);
  expect(rendered).toHaveLength(CASES.length);
});
