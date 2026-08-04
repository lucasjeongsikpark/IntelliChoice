/**
 * AUD-F-04: does a page refresh re-show a stage narrative the student already dismissed?
 *
 * **Finding id corrected 2026-08-04.** This file called the behaviour AUD-F-05 throughout,
 * but AUD-F-05 is the *displacement* finding (a narrative replacing the screen in use, fixed
 * by AUD-F-21 and covered by `narrative-displacement.spec.ts`). Return-after-refresh is
 * AUD-F-04. The two were filed under one heading in AUDIT_FINDINGS.md, which is the likely
 * source of the mix-up.
 *
 * `App.tsx` tracked dismissal in React state (`dismissedNarrative`, keyed by the narrative
 * text) while the backend keeps `stage_narrative` in the snapshot. React state does not
 * survive a reload, so the gate closed again.
 *
 * This matters beyond the annoyance: SPEC Phase 11's own "done when" is that a refresh
 * restores the student's exact position, and `useLearningSession`'s docstring cites that
 * requirement explicitly. Landing on a narrative screen instead of the question is a
 * different position. It stayed P3 because one further click cleared it.
 *
 * **Fixed 2026-08-04**, and the assertion at the end of this test is inverted accordingly -
 * it now states that the narrative does *not* come back. Both gates moved into
 * `useNarrativeGate` (a `sessionStorage` record keyed by learning session id), because
 * `interactedPhase` is a second door to the same defect: a narrative the student had worked
 * past would also return, without ever having been dismissed.
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
 * same text* to return, and (e) asserts directly on whether it did. No `test.fail()`: the
 * assertion states the required behaviour outright. If no narrative ever arrives, the run
 * cannot establish its precondition and `skip`s with that reason rather than reporting a
 * result.
 *
 * The bounded wait in (d) is load-bearing now that the assertion is inverted, and more so
 * than it was before. "The narrative did not come back" is an absence, and an absence is
 * also what a slow snapshot looks like - so `NARRATIVE_RETURN_MS` has to be long enough that
 * expiry means the app decided not to show it, not that this test ran out of patience.
 *
 * The welcome narrative is used rather than a pre-exam one: it is the case the finding
 * itself quotes, it needs no topic selection or exam, and it removes AUD-F-05's
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
      "not be established - this run says nothing about AUD-F-04 either way",
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

  // Distinguishing *which* narrative came back is what keeps a failure here actionable: a
  // different one arriving is a different defect, not AUD-F-04, and without this the message
  // below would misattribute it.
  let textAfter: string | null = null;
  if (returned) {
    textAfter = (await page.locator(".stack p, .panel p, main p").first().innerText())
      .trim()
      .slice(0, 120);
    audit.note(`text after the refresh: ${JSON.stringify(textAfter)}`);
  }

  // (e) The required behaviour, asserted directly. Inverted 2026-08-04 with the fix; before
  // it, this file asserted `toBe(true)` to state the defect.
  expect(
    returned ? `returned: ${textAfter}` : "did not return",
    textAfter === narrativeText
      ? "the dismissed stage narrative came back after a refresh - AUD-F-04 has regressed. " +
        "Both gates live in useNarrativeGate (sessionStorage, keyed by learning session id); " +
        "check that the record is being written and that its session id still matches."
      : "a narrative appeared after the refresh, but not the one that was dismissed - that " +
        "is not AUD-F-04 and needs its own investigation",
  ).toBe("did not return");
});
