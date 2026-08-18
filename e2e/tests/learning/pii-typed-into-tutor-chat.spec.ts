/**
 * D-398: the leg V7 deferred — a student types an email and a phone number into the tutor chat.
 *
 * **The deferral's reason was a cost estimate, and the estimate was wrong.** D-387 recorded this
 * as "deliberately not done… the browser leg would cost a full pre-exam walk to reach the study
 * phase where the composer exists". The walk is real — sign in, start, topic, clear ten pre-exam
 * items, finalize, answer one study question wrong — but measured against the last full suite run
 * it costs **4.6 s** (`assistance-panel-probe`), not the minutes the 300 s timeouts imply. Those
 * timeouts are safety margin, not duration.
 *
 * **And one of the two reasons stopped being true after V7.** The other was that "its redaction is
 * already asserted against the persisted row", which is still correct and still not the point: the
 * server test cannot see a carrier that never reaches the server. D-389 then fixed learning-web's
 * crash-report sink, which until that day 404'd against the vite origin in local development — so
 * *"a crash report fired by a render error while the text is in state"*, the exact carrier the
 * chat-side sibling was written to catch, became a **live** path here rather than a theoretical
 * one. This file is the leg that watches it.
 *
 * It is deliberately the same shape as `chat/pii-typed-by-a-visitor.spec.ts`, including the
 * percent-decoding that spec needed after its first version passed an injected
 * `?q=` + `encodeURIComponent(EMAIL)` beacon: `@` arrives as `%40`, so a raw `includes` misses
 * precisely the leak being hunted. Copied rather than shared because the two apps share no code by
 * design (D-347), and a divergence between the two checks should be visible as a diff.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";
import {
  answerCurrentQuestion,
  chooseTopic,
  settleToInteractiveScreen,
  startSession,
} from "../../fixtures/learning-flow";

test.describe.configure({ timeout: 300_000 });

/** Distinctive enough that a match cannot be a coincidence, and shaped so the redactor's own
 *  patterns (`_EMAIL_RE`, `_PHONE_RE`) recognise them. Different literals from the chat spec's,
 *  so a cross-contaminated run cannot pass one file using the other's evidence. */
const EMAIL = "zqxv.student@example.com";
const PHONE = "555-0198";
const QUESTION = `I'm stuck. Email me at ${EMAIL} or call ${PHONE} if that's easier.`;

/**
 * Sign in and walk to the intervention panel, where the tutor composer lives.
 *
 * The same route `assistance-panel-probe` takes, because it is the only one there is: the chat
 * panel is rendered by `InterventionScreen`, and an intervention is offered only after a wrong
 * answer in the study phase (SPEC §5.11.3).
 */
async function reachTheTutorComposer(page: import("@playwright/test").Page): Promise<boolean> {
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);
  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });

  // Clear the pre-exam. Correctness does not matter - the study phase is the destination.
  for (let i = 0; i < 12; i += 1) {
    if (!(await answerCurrentQuestion(page))) break;
    if (await page.locator(".phase-chip").getByText(/study/i).count()) break;
  }
  const submitExam = page.getByRole("button", { name: /^submit exam$/i });
  if (await submitExam.isVisible().catch(() => false)) {
    await submitExam.click();
    await page
      .getByRole("button", { name: /submit|confirm/i })
      .last()
      .click()
      .catch(() => undefined);
  }
  await expect(page.locator(".phase-chip")).toHaveText(/study/i, { timeout: 120_000 });

  // `answerCurrentQuestion` takes the first option, which is wrong nearly every time - but
  // "nearly" is why this has a budget and a boolean rather than an assertion.
  for (let attempt = 0; attempt < 6; attempt += 1) {
    if (await page.getByRole("button", { name: /get a hint/i }).isVisible().catch(() => false)) {
      break;
    }
    if (!(await answerCurrentQuestion(page))) break;
  }
  const chooser = page.getByRole("button", { name: /get a hint/i });
  if (!(await chooser.isVisible().catch(() => false))) return false;

  await chooser.click();
  await expect(page.locator(".intervention-panel")).toBeVisible({ timeout: 60_000 });

  // **The panel opens on the help view, and the chat is behind a mode switch.** The first run of
  // this file stopped here and timed out on a composer that does not exist yet - the failure
  // snapshot showed `tab "Ask your tutor"`, which is the control that renders it
  // (`InterventionScreen`: `showing === "tutor" ? <TutorChatPanel …>`). Worth stating rather than
  // silently clicking, because it means the tutor composer is two interactions deep in a screen
  // that is itself only reachable after a wrong study answer - which is most of why this leg had
  // never been walked.
  //
  // `tab`, not `button`: the control sits in a `tablist "Help or tutor"`, which the same snapshot
  // said and the second run's locator ignored.
  await page.getByRole("tab", { name: /ask your tutor/i }).click();
  return true;
}

test("a typed email and phone number leave the tutor chat exactly once", async ({
  page,
  audit,
}) => {
  // Finalizing an exam emits a burst of 409s (AUD-F-02), the same known defect the sibling
  // journeys allow. **This allowance cannot weaken the check below**: the console listener here is
  // its own `page.on("console")`, independent of the audit teardown, so an allowed "Failed to load
  // resource" cannot also hide a `console.log` carrying the student's email.
  audit.allow({ statuses: [409], consoleErrors: ["Failed to load resource"] });

  const carriers: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    // Percent-decoded as well as raw. See this file's header: the chat sibling's first version
    // passed an injected query-string beacon because `@` travels as `%40`.
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

  const reached = await reachTheTutorComposer(page);
  audit.note(`reached the tutor composer: ${reached}`);
  test.skip(!reached, "never landed on a wrong study answer within the attempt budget");

  const composer = page.getByRole("textbox", { name: /ask your tutor a question/i });
  await expect(composer).toBeEnabled({ timeout: 30_000 });
  await composer.fill(QUESTION);
  await page.getByRole("button", { name: /^send$/i }).click();

  // The reply has to land, or the request that carries the text may not have been sent yet and
  // "exactly once" would be counting an unfinished turn.
  await expect(page.locator(".chat-bubble.tutor").last()).toBeVisible({ timeout: 60_000 });

  audit.note(`requests carrying the typed PII: ${JSON.stringify(carriers)}`);

  expect(
    carriers.length,
    "the email or phone number left the page in more than one request - a beacon, a crash " +
      `report, or a query string built from the input: ${JSON.stringify(carriers)}`,
  ).toBe(1);

  expect(
    carriers[0],
    "the one request carrying the typed PII is not the tutor turn that is supposed to carry it",
  ).toMatch(/^POST \/learning\/sessions\/[^/]+\/chat$/);

  expect(
    consoleHits,
    "the typed email or phone number was written to the browser console, which is a place " +
      "nothing redacts",
  ).toEqual([]);
});

test("the student still sees their own words, not a redacted copy", async ({ page, audit }) => {
  audit.allow({ statuses: [409], consoleErrors: ["Failed to load resource"] });

  const reached = await reachTheTutorComposer(page);
  audit.note(`reached the tutor composer: ${reached}`);
  test.skip(!reached, "never landed on a wrong study answer within the attempt budget");

  const composer = page.getByRole("textbox", { name: /ask your tutor a question/i });
  await composer.fill(QUESTION);
  await page.getByRole("button", { name: /^send$/i }).click();

  // The server redacts `message` at the request boundary and stores only the redacted copy
  // (`test_pii_is_redacted_on_the_wire_and_in_storage`), but the transcript is the client's own
  // state - so the student reads what they typed. Asserted so that a future change which starts
  // echoing the server's copy back, and shows a child `[redacted-email]` where their address was,
  // fails here rather than being discovered by a confused twelve-year-old.
  const asked = page.locator(".chat-bubble.student", { hasText: EMAIL });
  await expect(asked).toBeVisible({ timeout: 60_000 });
  await expect(asked).not.toContainText("[redacted-email]");
});
