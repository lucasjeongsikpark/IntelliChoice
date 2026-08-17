/**
 * The branch-manager email, **approved** — the second of the 2026-08-17 audit's coverage gaps.
 *
 * **The audit's phrasing for this gap was broader than the truth, and the narrower version is
 * the one worth fixing.** "Every approval gate was declined, never approved" is right about
 * every *browser* walk, and wrong about the system: `test_attendance_ask_branch_manager_
 * end_to_end` (learning) and `test_admin_escalation` (chat) both approve at the API level and
 * already assert the things an API can see — one message reaching the transport, the recipient,
 * the `InterruptApproval` row with `decision="approved"`. Duplicating that here would add
 * nothing.
 *
 * What no test has ever done is approve through the UI, so three things had never happened:
 * the confirmation sentence had never rendered, the dialog had never been observed closing on
 * an approval, and **nothing had checked that approving leaves the session blocked.** That last
 * one is the one that matters. SPEC §5.6.4 says "Session remains blocked" — the email asks a
 * manager to check a record, it does not establish attendance — so a build where approval
 * accidentally unblocked the exam would be a fail-closed violation reachable by a student
 * clicking the button the screen recommends, and every existing test would still pass.
 *
 * `FakeEmailTransport` is wired unconditionally in dev and on staging, which is why this is
 * safe to run anywhere and why the previous walks' caution about approving was unnecessary.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { expectNotBlank, signInViaUi } from "../../fixtures/session";
import {
  chooseTopic,
  settleToInteractiveScreen,
  stableClick,
  startSession,
} from "../../fixtures/learning-flow";

test.describe.configure({ timeout: 180_000 });

test("approving the branch-manager email confirms, closes, and leaves the gate closed", async ({
  page,
  audit,
}) => {
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentUnknownEmail);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);

  const gate = page.getByRole("heading", { name: /attendance check/i });
  const gated = await gate
    .waitFor({ state: "visible", timeout: 60_000 })
    .then(() => true)
    .catch(() => false);
  audit.note(`gated: ${gated}`);

  // The invariant that must hold on every run, gate or no gate - the same one
  // `journey-attendance.spec.ts` leads with, and the reason this spec is safe to re-run.
  await expect(
    page.locator(".phase-chip"),
    "a student with unmarked attendance reached an exam - SPEC §5.4.4 requires unknown ≠ present",
  ).toHaveCount(0);

  // Skipping rather than passing: an earlier run in the same ISO week may have left this
  // student's gate resolved, and a green tick would claim an approval was walked when none was
  // on screen to walk.
  test.skip(
    !gated,
    "no gate screen for this student this week, so there was no approval to give and this run " +
      "says nothing about the confirmation path (the fail-closed check above still ran)",
  );

  await stableClick(page.getByRole("button", { name: /ask my branch manager to check/i }));

  // The dialog, as a dialog (D-381). Asserted by role rather than by class, because the fix
  // that made this a dialog is the thing that keeps the decline button on screen.
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 60_000 });
  const approve = page.getByRole("button", { name: /send verification email/i });
  await expect(approve).toBeVisible();
  await expect(page.getByRole("button", { name: /don't send/i })).toBeVisible();

  // What the student is about to authorise. The draft names a minor, their grade and their
  // branch (attendance.py's `build_attendance_email_draft`), which is exactly why §5.1.4 asks
  // a human first - so the preview has to actually contain it, or the approval is uninformed.
  const preview = await page.locator(".email-preview").innerText();
  audit.note(`draft: ${preview.length} chars, To/Subject present: ${/To:|Subject:/.test(preview)}`);
  expect(preview, "the draft did not name the week it is asking about").toMatch(/Week:/);
  expect(preview, "the draft was not addressed to anyone").toMatch(/To:\s*\S+@\S+/);

  await stableClick(approve);

  // 1. The confirmation, quoted from `attendance.EMAIL_SENT_MESSAGE`. Anchored on two
  //    fragments rather than the whole paragraph: the sentence may be reworded, but a
  //    confirmation that does not say a message was sent, or that does not say the practice
  //    stays paused, is a different message and should fail here.
  const message = page.locator(".message");
  await expect(message, "no confirmation after approving the send").toContainText(
    /sent a message to your branch manager/i,
    { timeout: 60_000 },
  );
  await expect(message).toContainText(/stays paused/i);

  // 2. The dialog is gone. `toHaveCount(0)` rather than `not.toBeVisible()`: a dialog left
  //    mounted but hidden still traps focus through `useFocusTrap`'s `inert` marking.
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator(".email-preview")).toHaveCount(0);

  // 3. **The one that matters.** §5.6.4: approving the email does not establish attendance, so
  //    the session must stay blocked. Checked after the confirmation, so a build that unblocks
  //    on approval fails here rather than reading as a copy problem.
  await expect(
    page.locator(".phase-chip"),
    "approving the verification email unblocked the exam - the email asks a manager to check " +
      "a record, it does not confirm attendance (SPEC §5.6.4 'Session remains blocked')",
  ).toHaveCount(0);

  // The way out is still on screen (D-216/D-381): a student who has just sent the request must
  // not be parked on a screen with nothing to do.
  await expect(page.getByRole("button", { name: /back to start/i })).toBeVisible();
  await expectNotBlank(page);
});
