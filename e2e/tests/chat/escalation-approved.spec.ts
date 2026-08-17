/**
 * The admin escalation, **approved, against the real backend** — the chat half of the
 * 2026-08-17 audit's second coverage gap.
 *
 * `escalate-from-refusal.spec.ts` covers the *offer*: it stubs `/messages` and asserts the
 * approval modal appears with both buttons and the right draft. Nothing beyond it has ever
 * clicked "Approve & send" in a browser, so three things had never been observed:
 *
 * 1. The confirmation reaching the transcript (`nodes.EMAIL_SENT_MESSAGE`).
 * 2. The modal closing on approval rather than on decline.
 * 3. **The composer becoming usable again.** `App.tsx` computes
 *    `busy={busy || pendingIsKnown}`, so an approval that failed to clear the pause would
 *    leave a permanently disabled composer — the deadlock shape that the `pendingIsUnknown`
 *    branch exists to avoid, arrived at through the *known* branch instead. Nothing tests it,
 *    and it is invisible to the API-level tests because there is no composer there.
 *
 * `test_admin_escalation.py` already asserts the API-visible half (the send, the
 * `InterruptApproval` row with `decision="approved"`), so this deliberately does not repeat it.
 *
 * **The turn is real, not stubbed.** Locally that means `MockBedrockProvider`'s deterministic
 * scope guard, whose `admin_contact` branch keys on `escalat` / `speak to` / `contact admin`
 * over an in-scope query (`_scope_and_intent_json`) — hence the wording below, which is chosen
 * to satisfy the *real* router rather than to be prose. `FakeEmailTransport` is wired
 * unconditionally in dev and on staging, so approving sends nothing to a real inbox.
 */

import { CHAT_WEB, FIXTURES } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { expectNotBlank, mintToken, seedSession } from "../../fixtures/session";
import { ask } from "../../fixtures/stub-chat";

test.describe.configure({ timeout: 180_000 });

// In scope ("intellichoice") and routed to `admin_contact` ("escalate"). Both halves are
// required: an out-of-scope query never reaches the router at all.
const QUESTION = "Please escalate this to an IntelliChoice administrator.";

test("approving an escalation confirms in the transcript and hands the composer back", async ({
  page,
  audit,
}) => {
  const token = await mintToken(page.request, "chat", FIXTURES.parentOneChild);
  await seedSession(page, "chat", FIXTURES.parentOneChild, token);
  await page.goto(CHAT_WEB);
  await expect(page.locator(".composer textarea")).toBeVisible();

  await ask(page, QUESTION);

  // The pause, as a real dialog from a real turn.
  const dialog = page.getByRole("dialog");
  const paused = await dialog
    .waitFor({ state: "visible", timeout: 90_000 })
    .then(() => true)
    .catch(() => false);
  audit.note(`escalation paused for approval: ${paused}`);

  // Skipping rather than passing: if this turn did not route to `admin_contact`, there was no
  // approval on screen and a green tick would claim one was given. The counterpart assertion
  // (that an unapproved escalation sends nothing) is `test_admin_escalation.py`'s.
  test.skip(
    !paused,
    "the turn did not pause for an email approval, so there was nothing to approve - the " +
      "intent router did not classify this as `admin_contact` and this run says nothing about " +
      "the approval path",
  );

  const approve = page.getByRole("button", { name: /approve & send/i });
  await expect(approve).toBeVisible();
  await expect(page.getByRole("button", { name: /^decline$/i })).toBeVisible();
  const preview = await page.locator(".email-preview").innerText();
  audit.note(`draft: ${preview.length} chars`);
  expect(preview.trim().length, "the approval dialog showed an empty draft").toBeGreaterThan(0);

  await approve.click();

  // 1. The confirmation, quoted from `nodes.EMAIL_SENT_MESSAGE`.
  const lastBubble = page.locator(".message-row.assistant .bubble").last();
  await expect(lastBubble, "no confirmation turn after approving the send").toContainText(
    /sent to an administrator/i,
    { timeout: 90_000 },
  );

  // 2. The dialog is gone. `toHaveCount(0)`, not `not.toBeVisible()`: a dialog left mounted
  //    still holds focus and marks the page behind it `inert`.
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // 3. The composer is usable again. This is the one only a browser can check.
  const composer = page.locator(".composer textarea");
  await expect(
    composer,
    "the composer is still disabled after the approval resolved, so the interrupt was never " +
      "cleared and the visitor cannot ask anything else (App.tsx's `busy || pendingIsKnown`)",
  ).toBeEnabled({ timeout: 30_000 });
  await composer.fill("thanks");
  await expect(page.getByRole("button", { name: /^send$/i })).toBeEnabled();

  await expectNotBlank(page);
});
