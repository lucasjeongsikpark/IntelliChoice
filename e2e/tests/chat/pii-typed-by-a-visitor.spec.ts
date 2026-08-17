/**
 * D-387: a visitor types an email address and a phone number, and the browser is watched.
 *
 * The 2026-08-17 audit listed "PII redaction (no walk typed an email address or a phone
 * number)" as never exercised. Measuring that first narrowed it a long way, and the narrowing
 * is why this file is small:
 *
 *  - `redact_free_text` is unit-tested (`test_pii_redaction.py`).
 *  - Every Bedrock payload is structurally floored — field allowlist, no PII-named fields, no
 *    extras (`test_bedrock_payload_pii_floor.py`, 59 tests).
 *  - All four free-text entry points redact at the request boundary: chat's `query`
 *    (`sessions.py:588`), learning's tutor `message` (`sessions.py:1820`) and both crash sinks.
 *  - learning's tutor chat asserts the **stored row** is redacted
 *    (`test_pii_is_redacted_on_the_wire_and_in_storage`).
 *  - Neither app serves a transcript back — chat-api has `create_session`, `post_message` and
 *    `respond_to_interrupt` and no history route, and chat-web's `localStorage` holds only
 *    `sub`/`role`/`isGuest`. So the visitor's raw words live in the tab and nowhere else, and
 *    the "your own message came back mangled" failure this walk was expected to find cannot
 *    happen.
 *
 * What is left is the part only a browser can see, and it is worth one test: **the typed PII
 * must leave the page exactly once**, in the one request that is supposed to carry it. A
 * beacon, a crash report fired by a render error while the text is in state, a query string
 * built from the input, or a `console.log` of the composer's value would each put a child's
 * email somewhere nobody is redacting — and none of them are visible from a server test.
 *
 * The console assertion is not redundant with the suite's zero-console-errors teardown: that
 * checks for errors, and a `console.log` or `console.warn` carrying the text is neither an
 * error nor a failure. It is still a leak into a place the browser keeps.
 *
 * Deliberately not here: learning-web's tutor chat. Its redaction is already asserted against
 * the persisted row, and the browser leg would cost a full pre-exam walk to reach the study
 * phase where the composer exists. Recorded rather than silently skipped.
 */

import { expect, test } from "../../fixtures/capture";
import { CHAT_WEB } from "../../config";
import { ask } from "../../fixtures/stub-chat";
import { seedGuest } from "../../fixtures/session";

/** Distinctive enough that a match cannot be a coincidence, and shaped so the redactor's own
 *  patterns (`_EMAIL_RE`, `_PHONE_RE`) recognise them. */
const EMAIL = "zqxv.parent@example.com";
const PHONE = "555-0142";
const QUESTION = `What are the Saturday hours? Email me at ${EMAIL} or call ${PHONE}.`;

test("a typed email and phone number leave the page exactly once", async ({ page, audit }) => {
  const carriers: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    // **Percent-decoded as well as raw, and the first version of this test was wrong without
    // it.** A leak through a query string arrives as `zqxv.parent%40example.com`, so a plain
    // `includes(EMAIL)` misses exactly the case this test exists to catch - found by injecting
    // a `fetch('/chat/beacon?q=' + encodeURIComponent(EMAIL))` and watching the test pass. It
    // is the same shape as the audit probe that matched `CAST(blob AS text)` and missed
    // msgpack floats, recorded in `test_chat_endpoints.py`'s coordinates test.
    let decoded = url;
    try {
      decoded = decodeURIComponent(url);
    } catch {
      // A malformed escape sequence - keep the raw form rather than dropping the request.
    }
    const haystack = `${url} ${decoded} ${request.postData() ?? ""}`;
    if (haystack.includes(EMAIL) || haystack.includes(PHONE)) {
      carriers.push(`${request.method()} ${new URL(url).pathname}`);
    }
  });

  const consoleHits: string[] = [];
  page.on("console", (message) => {
    const text = message.text();
    if (text.includes(EMAIL) || text.includes(PHONE)) {
      consoleHits.push(`${message.type()}: ${text.slice(0, 120)}`);
    }
  });

  await seedGuest(page);
  await page.goto(CHAT_WEB);
  await ask(page, QUESTION);

  // Whatever the answer is - a cited answer, a refusal, an access hint - the turn has to
  // finish, or nothing below has been exercised.
  await expect(page.locator(".bubble").last()).toBeVisible({ timeout: 60_000 });
  await expect(page.locator("textarea")).toBeEnabled({ timeout: 60_000 });

  audit.note(`requests carrying the typed PII: ${JSON.stringify(carriers)}`);

  expect(
    carriers.length,
    "the email or phone number left the page in more than one request - a beacon, a crash " +
      `report, or a query string built from the input: ${JSON.stringify(carriers)}`,
  ).toBe(1);

  expect(
    carriers[0],
    "the one request carrying the typed PII is not the turn that is supposed to carry it",
  ).toMatch(/^POST \/chat\/sessions\/[^/]+\/messages$/);

  expect(
    consoleHits,
    "the typed email or phone number was written to the browser console, which is a place " +
      "nothing redacts",
  ).toEqual([]);
});

test("the visitor still sees their own words, not a redacted copy", async ({ page }) => {
  await seedGuest(page);
  await page.goto(CHAT_WEB);
  await ask(page, QUESTION);

  // The product answer to the question this walk was written to ask. The server redacts
  // `query` at the boundary and keeps only the redacted copy, but the transcript is the
  // client's own state, so the visitor reads what they typed. Asserted so that a future change
  // which starts echoing the server's copy back - and shows a parent `[redacted-email]` where
  // their address was - fails here instead of being discovered by a confused user.
  const asked = page.locator(".bubble", { hasText: EMAIL });
  await expect(asked).toBeVisible({ timeout: 60_000 });
  await expect(asked).not.toContainText("[redacted-email]");
});
