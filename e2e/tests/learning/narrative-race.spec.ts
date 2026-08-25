/**
 * AUD-F-05's measurement (the id was assigned after this file was written, and filled in
 * 2026-08-04 by D-174's sweep - four other citations pointed here while naming AUD-F-01,
 * which is the unrelated refetch-burst finding).
 *
 * The probe: the stage narrative arrives over SSE *after* the topic-select screen has
 * rendered, and `App.tsx` gates the narrative ahead of the phase branches - so the
 * narrative screen replaces a screen the student is already using.
 *
 * Found by the journey walk failing with Playwright's "element was detached from the DOM"
 * on the topic card, which is precisely what a student's click hitting the swap looks
 * like. This file measures the window rather than asserting a threshold, because no
 * threshold was known before the first measurement (D-100's rule).
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";
import { startSession } from "../../fixtures/learning-flow";

test("measure the window between the topic screen rendering and the narrative displacing it", async ({
  page,
  audit,
}) => {
  // Its own student, not `studentPresent` (WORK-13-FIXTURES). This spec creates a
  // learning session, and the journeys mutate shared per-student Postgres and MySQL
  // state through one seeded account - so a spec sharing that account picks up
  // whatever the previous one left behind. `FIXTURES` in config.ts has the
  // measurement: 7 refused submissions and 2.3 minutes against 15 seconds.
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentNarrativeRace);
  await startSession(page);

  // Whichever appears first wins the race; both outcomes are recorded.
  const topicList = page.locator(".card-list");
  const narrativeContinue = page.getByRole("button", { name: /^continue$/i });

  await expect(topicList.or(narrativeContinue).first()).toBeVisible({ timeout: 60_000 });
  const topicVisibleFirst = (await topicList.count()) > 0;
  const started = Date.now();
  audit.note(`first screen after start: ${topicVisibleFirst ? "topic list" : "stage narrative"}`);

  if (!topicVisibleFirst) {
    audit.note("narrative won the race this run - no displacement to measure");
    test.skip(true, "narrative rendered before the topic list on this run");
  }

  // Wait for the displacement, bounded. If it never comes, that is also a result.
  const displaced = await narrativeContinue
    .waitFor({ state: "visible", timeout: 20_000 })
    .then(() => true)
    .catch(() => false);
  const elapsed = Date.now() - started;

  audit.note(
    displaced
      ? `topic list was displaced by the stage narrative after ~${elapsed}ms of being interactive`
      : `topic list was not displaced within 20s`,
  );

  // Recorded, not asserted, for the same reason as the click probe below: this measures a
  // race. The measurement that matters (~26ms of interactivity) is in the note above.
  if (!displaced) audit.note("no displacement this run - the narrative arrived before the topic list");
});

test("a click landing in that window is discarded (the student loses the interaction)", async ({
  page,
  audit,
}) => {
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentNarrativeRace);
  await startSession(page);

  const topicList = page.locator(".card-list");
  const narrativeContinue = page.getByRole("button", { name: /^continue$/i });
  await expect(topicList.or(narrativeContinue).first()).toBeVisible({ timeout: 60_000 });
  test.skip((await topicList.count()) === 0, "narrative rendered first on this run");

  // Click the topic and immediately look at where the app ends up. `/topics` is what a
  // successful click sends; its absence proves the click never reached the API.
  // Matched on the method too since D-187: the same path now serves a GET that populates
  // the picker, and it fires *before* this line runs (`.card-list` renders only once that
  // GET resolves). A path-only predicate would therefore have gone on matching - on the
  // wrong request - and reported "the click reached the API" for a click that never landed.
  const topicsCall = page
    .waitForRequest(
      (request) => request.method() === "POST" && request.url().includes("/topics"),
      { timeout: 8000 },
    )
    .then(() => true)
    .catch(() => false);
  // The click is allowed to fail. Playwright throws "element was detached from the DOM" when
  // the narrative replaces the topic list mid-click - which is not an accident of the harness,
  // it *is* the event this test exists to observe, and letting it throw made the probe fail the
  // suite on its own subject (one whole-suite run in S41, having passed the run before). So the
  // outcome is captured, in keeping with the "recorded, not asserted" note below.
  const clickLanded = await page
    .locator(".card-list button")
    .first()
    .click({ timeout: 5000, force: true })
    .then(() => true)
    .catch(() => false);
  const reached = await topicsCall;
  audit.note(
    clickLanded
      ? "the click completed against a stable element"
      : "the element was detached mid-click - the narrative displaced the topic list inside the window",
  );
  audit.note(`POST /topics reached the API: ${reached}`);
  // Deliberately not asserted: the window is ~26ms, so whether a scripted click lands
  // inside it varies per run. What this probe contributes is the recorded outcome, and an
  // assertion here would make the suite flaky rather than informative.

  if (await narrativeContinue.isVisible()) {
    await narrativeContinue.click();
    // After dismissing, the student is either on the exam (click survived) or back on the
    // topic list (click lost). Both are recorded; the second is the defect.
    const backOnTopics = await topicList
      .waitFor({ state: "visible", timeout: 10_000 })
      .then(() => true)
      .catch(() => false);
    audit.note(
      backOnTopics
        ? "after dismissing the narrative the student is back on the topic list - the click was lost"
        : "after dismissing the narrative the session advanced - the click survived",
    );
  }
});
