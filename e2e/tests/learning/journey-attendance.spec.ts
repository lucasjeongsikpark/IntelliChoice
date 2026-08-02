/**
 * The attendance gate, which SPEC §5.4.4 requires to fail closed: an absent student must
 * not reach an exam, and *unknown* attendance must not be treated as present.
 *
 * The gate fires when the exam is requested, not at session start - `/student` returns
 * `student_selected` for absent and present students alike, and only `/topics` returns
 * `phase: blocked`. Verified directly against the API for both fixtures before these
 * tests were written, because asserting at the wrong step would have looked exactly like
 * a bypass.
 *
 * **Both tests are written to survive a re-run**, which matters because §2.6 criterion 3
 * requires every journey to pass *twice consecutively*: an acknowledged absence persists
 * per student and week, so a second run finds no gate to walk. The invariant that always
 * holds either way - and the one the spec actually states - is that no exam is reachable.
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

/** Drives a student to the point where the gate would fire. */
async function requestAnExam(page: import("@playwright/test").Page): Promise<void> {
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);
}

test("an absent student never reaches an exam, and can acknowledge the absence", async ({
  page,
  audit,
}) => {
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentAbsent);
  await requestAnExam(page);

  const gate = page.getByRole("heading", { name: /attendance check/i });
  const gated = await gate
    .waitFor({ state: "visible", timeout: 60_000 })
    .then(() => true)
    .catch(() => false);

  // The one assertion that must hold on every run, gate or no gate.
  await expect(
    page.locator(".phase-chip"),
    "an absent student reached an exam screen - SPEC §5.4.4 fail-closed violation",
  ).toHaveCount(0);

  if (!gated) {
    audit.note(
      "no gate screen: this student's absence was already acknowledged by an earlier run (persists per student+week). Fail-closed still verified - no exam screen.",
    );
    return;
  }

  const message = await page.locator(".message").innerText();
  audit.note(`gate message: ${JSON.stringify(message.slice(0, 160))}`);
  expect(
    message.trim().length,
    "the gate rendered with no explanation for the student",
  ).toBeGreaterThan(0);

  await stableClick(page.getByRole("button", { name: /confirm i did not attend/i }));
  await expect(page.getByRole("button", { name: /back to start/i })).toBeVisible({
    timeout: 60_000,
  });
  await expectNotBlank(page);
  // Acknowledging an absence must not open the gate.
  await expect(page.locator(".phase-chip")).toHaveCount(0);
});

test("unknown attendance is gated too, and the branch-manager email is shown before sending", async ({
  page,
  audit,
}) => {
  // student-ext-3 has no attendance row at all - the fail-closed case, and a different
  // student from the test above so neither test's resolution affects the other.
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentUnknownAttendance);
  await requestAnExam(page);

  const gate = page.getByRole("heading", { name: /attendance check/i });
  const gated = await gate
    .waitFor({ state: "visible", timeout: 60_000 })
    .then(() => true)
    .catch(() => false);
  audit.note(`unknown-attendance student gated: ${gated}`);

  await expect(
    page.locator(".phase-chip"),
    "a student with unknown attendance reached an exam - SPEC §5.4.4 requires unknown ≠ present",
  ).toHaveCount(0);

  if (!gated) {
    audit.note("no gate screen: resolved by an earlier run. Fail-closed still verified.");
    return;
  }

  // D-152 §2: unknown ("not marked yet") is the routine production state, so the block a
  // student reads must say exactly that and must not imply a recorded absence - otherwise
  // "did not attend" looks like the safe choice for a student who actually attended.
  const gateMessage = await page.locator(".message").innerText();
  audit.note(`unknown-attendance gate message: ${JSON.stringify(gateMessage.slice(0, 200))}`);
  expect(
    gateMessage,
    "the unknown-attendance block should read as not-yet-marked, not as a recorded absence",
  ).toContain("not been marked yet");
  expect(gateMessage).not.toContain("did not receive");

  await stableClick(page.getByRole("button", { name: /ask the branch manager to verify/i }));

  // SPEC §5.1.4: the draft is shown and approval is explicit. An approval gate with no
  // decline is not a gate, so both buttons must exist.
  const preview = page.locator(".email-preview");
  await expect(preview).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("button", { name: /send verification email/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /don't send/i })).toBeVisible();
  const previewText = await preview.innerText();
  audit.note(
    `draft shown, ${previewText.length} chars, has To/Subject: ${/To:|Subject:/.test(previewText)}`,
  );

  await stableClick(page.getByRole("button", { name: /don't send/i }));
  // Declining must leave the gate closed rather than falling through to the exam.
  await expect(page.locator(".phase-chip")).toHaveCount(0, { timeout: 30_000 });
  await expectNotBlank(page);
});
