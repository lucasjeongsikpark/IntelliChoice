/**
 * D-164: the no-source refusal's offer to "pass this on to a branch manager" is now an
 * action, not a suggestion.
 *
 * Before this, `escalation_recommended` rendered the text "try asking to contact an
 * administrator for more help" — which put the work back on the user and depended on the
 * scope guard classifying whatever they typed next as `admin_contact`. A unit test cannot
 * show that a button reaches the approval modal, so the whole point of this fix is only
 * observable in a browser.
 *
 * Asserts on the outgoing request the way `report-degraded-retry.spec.ts` (D-161) does:
 * no database seeding and no mock-gateway dependency, just interception, so what the
 * button actually posts is checked rather than inferred from what came back.
 */

import { expect, test } from "../../fixtures/capture";
import { CHAT_WEB } from "../../config";
import { SESSION_ID, SHAPES } from "../../fixtures/chat-shapes";
import { ask } from "../../fixtures/stub-chat";
import { seedGuest } from "../../fixtures/session";

const QUESTION = "Do you offer transport from the middle school to the Dallas branch?";

interface Posted {
  query: string;
  escalate?: boolean;
}

/**
 * Stubs the chat surface, answering `/messages` from the request itself: a plain turn gets
 * the no-source refusal, an `escalate: true` turn gets the paused email approval. Records
 * every posted body so the test can assert on what the button sent.
 */
async function stubEscalationFlow(page: import("@playwright/test").Page): Promise<Posted[]> {
  const posted: Posted[] = [];

  await page.route("**/chat/meta", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ welcome_text: "Ask about branches.", suggested_prompts: [] }),
    }),
  );
  await page.route("**/chat/sessions", (route) =>
    route.request().method() === "POST"
      ? route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ chat_session_id: SESSION_ID }),
        })
      : route.fallback(),
  );
  await page.route("**/chat/sessions/*/stream**", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
      body: ": stubbed\n\n",
    }),
  );
  await page.route("**/chat/sessions/*/messages", (route) => {
    const body = JSON.parse(route.request().postData() ?? "{}") as Posted;
    posted.push(body);
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        body.escalate ? SHAPES["email_approval interrupt"] : SHAPES["no-source refusal"],
      ),
    });
  });

  return posted;
}

test.beforeEach(async ({ page }) => {
  await seedGuest(page);
});

test("a no-source refusal offers a real escalation, and it reaches the approval modal", async ({
  page,
}) => {
  const posted = await stubEscalationFlow(page);
  await page.goto(CHAT_WEB);
  await ask(page, QUESTION);

  const escalate = page.getByRole("button", { name: /ask an administrator/i });
  await expect(escalate).toBeVisible();
  await escalate.click();

  // The approval modal is the fix's whole purpose: no email exists until a human sees the
  // draft and approves it (CLAUDE.md #4 / SPEC §5.1.4).
  await expect(page.getByRole("heading", { name: /send to an administrator\?/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /approve & send/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /^decline$/i })).toBeVisible();

  // D-221: the modal asks a person to approve a message written about them, so what it
  // shows has to be the message. The fixture now carries the real `build_escalation_draft`
  // output rather than invented prose, which makes these two assertions meaningful: the
  // user's own question is quoted back, and the opening states the reason this escalation
  // exists - the reason D-219 got wrong and shipped unreachable.
  // Scoped to `.email-preview` on purpose: the question is also on screen in the user's own
  // message bubble, so an unscoped locator resolves to two elements and fails strict mode
  // with a message about duplication rather than about the draft (D-220's exact trap).
  const preview = page.locator(".email-preview");
  await expect(preview.getByText(QUESTION, { exact: false })).toBeVisible();
  await expect(
    preview.getByText(/asked a question the assistant could not answer/i),
    "the draft no longer says why this escalation was raised",
  ).toBeVisible();

  // What the button actually sent: the *original* question, flagged as an escalation.
  // Posting a new/empty query here would email the administrator the wrong text, and
  // omitting the flag would send it back through the scope guard as a fresh question.
  expect(posted).toHaveLength(2);

  // **D-412 (`AUD-CHAT-08`): the two identical questions are told apart.** `escalateTurn` appends
  // a new turn carrying the same `query`, so before this the transcript showed the question twice
  // with nothing distinguishing them - it read as though the visitor had asked again rather than
  // forwarded it to a person. Asserted here rather than in a new file because this spec already
  // performs the escalation; the count above is what makes the label meaningful.
  const userBubbles = page.locator(".message-row.user");
  await expect(userBubbles).toHaveCount(2);
  await expect(
    userBubbles.last().getByText(/sent to an administrator/i),
    "the forwarded question is not labelled, so the transcript reads as the same question asked twice",
  ).toBeVisible();
  // And the original is *not* labelled - otherwise the label says nothing.
  await expect(userBubbles.first().getByText(/sent to an administrator/i)).toHaveCount(0);
  expect(posted[0]).toMatchObject({ query: QUESTION, escalate: false });
  expect(posted[1]).toMatchObject({ query: QUESTION, escalate: true });

  // D-348 added `client_turn_id`, which this assertion caught by being an exact-shape check -
  // so it is asserted rather than loosened away. The two ids must *differ*: the escalation
  // appends a new transcript turn rather than mutating the refusal (the escalation is a
  // separate action the user took), and reusing the first turn's id would make every later
  // snapshot for it land on the wrong bubble.
  const ids = posted.map((body) => (body as { client_turn_id?: string }).client_turn_id);
  expect(ids[0], "the first turn sent no client turn id").toBeTruthy();
  expect(ids[1], "the escalation sent no client turn id").toBeTruthy();
  expect(ids[0]).not.toEqual(ids[1]);
});

test("an access hint offers no escalation (D-164's precedence rule)", async ({ page }) => {
  // When the answer exists but is behind a login, "sign in as a tutor" must not come with
  // an offer to email a human about content that already exists. The backend encodes this
  // by leaving `escalation_recommended` false on a hint; this is the rendered half.
  await page.route("**/chat/meta", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ welcome_text: "Ask about branches.", suggested_prompts: [] }),
    }),
  );
  await page.route("**/chat/sessions", (route) =>
    route.request().method() === "POST"
      ? route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ chat_session_id: SESSION_ID }),
        })
      : route.fallback(),
  );
  await page.route("**/chat/sessions/*/stream**", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
      body: ": stubbed\n\n",
    }),
  );
  await page.route("**/chat/sessions/*/messages", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SHAPES["access hint"]),
    }),
  );

  await page.goto(CHAT_WEB);
  await ask(page, "What is the branch escalation procedure?");

  // D-220: read from the fixture rather than repeating its wording. This used to assert
  // /sign in as a tutor/i, which was the shape file's own invented sentence - when the
  // fixture was corrected to the message `explain_access` really emits, the assertion
  // broke while the property it guards had not changed at all.
  await expect(page.getByText(SHAPES["access hint"].access_hint!.message)).toBeVisible();
  await expect(page.getByRole("button", { name: /ask an administrator/i })).toHaveCount(0);
});
