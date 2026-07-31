/**
 * AUD-F-05: does a page refresh re-show a stage narrative the student already dismissed?
 *
 * `App.tsx` tracks dismissal in React state (`dismissedNarrative`, keyed by the narrative
 * text) while the backend keeps `stage_narrative` in the snapshot. React state does not
 * survive a reload, so the gate closes again.
 *
 * This matters beyond the annoyance: SPEC Phase 11's own "done when" is that a refresh
 * restores the student's exact position, and `useLearningSession`'s docstring cites that
 * requirement explicitly. Landing on a narrative screen instead of the question is a
 * different position. It stays P3 because one further click clears it.
 *
 * ---
 *
 * **Rewritten 2026-07-31 because it was flaky on staging and the flake was this file.**
 * It failed on one attempt and passed on a retry, which under `test.fail()` reads as
 * "the defect intermittently disappeared". It did not. Two design faults, both of which
 * made the outcome depend on how fast Bedrock answered rather than on the app:
 *
 * 1. **The precondition was an absence, so it was satisfied by two opposite states.** The
 *    old version reached `pre_exam` and asserted `Continue` had count 0, meaning "no
 *    narrative is in the way". That is true when a narrative was shown and dismissed - and
 *    equally true when the narrative *has not arrived yet*. `stage_narrative` is an LLM
 *    call: ~26 ms behind the mock provider, seconds behind real Bedrock. Locally the
 *    narrative had always landed, so the probe ran; on staging it sometimes had not, and
 *    then the reload had no dismissed narrative to restore, nothing came back, and the
 *    assertion inverted. The test never established the state it was testing.
 * 2. **`test.fail()` made every cause of failure look like the defect.** A missing
 *    precondition, a timeout, a harness bug and the real finding all report identically.
 *    A probe that cannot fail for the wrong reason visibly is not evidence, which is the
 *    same lesson `test_health_endpoint_tracing.py` records: assert on what you can count,
 *    not on the absence of the mechanism you happen to have in mind.
 *
 * So this now (a) waits for a narrative to actually appear and captures its text, (b)
 * dismisses it and confirms it is gone, (c) reloads, (d) waits a bounded time for *that
 * same text* to return, and (e) asserts directly that it does. No `test.fail()`: the
 * assertion states today's behaviour, so **when AUD-F-05 is fixed this test fails and is
 * meant to** - update it with the fix. If no narrative ever arrives, the run cannot
 * establish its precondition and `skip`s with that reason rather than reporting a result.
 *
 * The welcome narrative is used rather than a pre-exam one: it is the case the finding
 * itself quotes, it needs no topic selection or exam, and it removes AUD-F-01's
 * topic-card race from a test that is not about it.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";
import { dismissNarrativeIfPresent, startSession } from "../../fixtures/learning-flow";

test.describe.configure({ timeout: 180_000 });

/** Generous: a real-Bedrock narrative is seconds, and the point is not to race it. */
const NARRATIVE_ARRIVAL_MS = 60_000;
/**
 * After the reload the narrative has already been generated and is sitting in the
 * snapshot, so its return needs one fetch and one render - not another model call. Long
 * enough to absorb a slow snapshot, short enough that "it did not come back" is a real
 * observation rather than an impatient one.
 */
const NARRATIVE_RETURN_MS = 30_000;

test("a dismissed stage narrative stays dismissed across a refresh", async ({ page, audit }) => {
  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await startSession(page);

  const continueButton = page.getByRole("button", { name: /^continue$/i });

  // (a) A narrative must actually appear, or there is nothing to dismiss and no probe to
  // run. `skip` rather than pass or fail: an inconclusive run must not be readable as
  // either result.
  const appeared = await continueButton
    .first()
    .waitFor({ state: "visible", timeout: NARRATIVE_ARRIVAL_MS })
    .then(() => true)
    .catch(() => false);
  test.skip(
    !appeared,
    `no stage narrative appeared within ${NARRATIVE_ARRIVAL_MS} ms, so a dismissal could ` +
      "not be established - this run says nothing about AUD-F-05 either way",
  );

  const narrativeText = (await page.locator(".stack p, .panel p, main p").first().innerText())
    .trim()
    .slice(0, 120);
  audit.note(`narrative shown before the refresh: ${JSON.stringify(narrativeText)}`);
  expect(
    narrativeText.length,
    "the narrative screen rendered no text to identify it by",
  ).toBeGreaterThan(0);

  // (b) Dismiss it, and confirm the dismissal took effect before reloading - otherwise a
  // narrative still on screen after the reload proves nothing about persistence.
  expect(await dismissNarrativeIfPresent(page), "the Continue click did not land").toBe(true);
  await expect(
    continueButton,
    "the narrative was still up after Continue, so nothing was dismissed",
  ).toHaveCount(0);

  // (c) and (d): reload, then give the narrative a real chance to come back. The old
  // version read `count()` at whatever instant one of two locators first appeared, and
  // since AUD-F-21 the exam's `.phase-chip` renders *underneath* a narrative rather than
  // instead of it, so that race offered no synchronisation at all.
  await page.reload();
  const returned = await continueButton
    .first()
    .waitFor({ state: "visible", timeout: NARRATIVE_RETURN_MS })
    .then(() => true)
    .catch(() => false);
  audit.note(`narrative returned after the refresh: ${returned}`);

  if (returned) {
    const textAfter = (await page.locator(".stack p, .panel p, main p").first().innerText())
      .trim()
      .slice(0, 120);
    audit.note(`text after the refresh: ${JSON.stringify(textAfter)}`);
    // The same narrative, not merely some narrative - a *different* one arriving would be
    // a different finding, and one this test would otherwise silently report as AUD-F-05.
    expect(
      textAfter,
      "a narrative returned after the refresh, but not the one that was dismissed - that is " +
        "not AUD-F-05 and needs its own investigation",
    ).toBe(narrativeText);
    // And it is genuinely re-dismissable rather than a stuck state, which is the whole of
    // why this is P3 and not a blocking defect.
    expect(
      await dismissNarrativeIfPresent(page),
      "the returned narrative could not be dismissed again - this is no longer P3",
    ).toBe(true);
  }

  // (e) Today's behaviour, asserted directly. This is the defect: when it is fixed, this
  // line fails and should be inverted along with the fix.
  expect(
    returned,
    "AUD-F-05 appears to be fixed: a refresh no longer re-shows the dismissed narrative. " +
      "That is the desired behaviour - invert this assertion and update the finding.",
  ).toBe(true);
});
