/**
 * U6's last criterion: does a band walk ever see a real video offered? (D-339)
 *
 * **No walk had ever answered this, and the reason was the harness.**
 * `clearInterventionIfPresent` clicks "Get a hint" every time it meets the §5.11.3 menu, so the
 * Video branch had never been exercised by any journey - the criterion was unreachable by
 * construction, not merely unmet. U6 was closed ⏸ on exactly that.
 *
 * **It was also unreachable by content until today.** The catalog held videos for 4 of 112 skills
 * when U6 was written; after D-337's sync it is **102 of 112**, so a study question now has a real
 * chance of landing on a skill with something to offer.
 *
 * **What this asserts, and what it deliberately does not.** SPEC §5.11.6 gives the Video choice
 * two legitimate outcomes: a video card, or a plain "nothing verified for this skill yet" message
 * (D-314 made that path a real answer rather than a dead end). Both are correct product behaviour,
 * so failing on the fallback would make this test a coverage report on the pinned channel. What is
 * asserted is that **the branch runs and resolves to one of its two defined outcomes** - and the
 * outcome is recorded either way, so a run where every skill falls back is visible in the audit
 * trail rather than hidden behind a green tick.
 *
 * The criterion "a band walk sees a real video offered" is therefore reported as a measurement,
 * not enforced as a threshold - D-100's rule, and the same posture `hint-displacement.spec.ts`
 * takes on dwell time.
 */

import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { signInViaUi } from "../../fixtures/session";
import {
  answerCurrentQuestion,
  answerWholeExam,
  chooseTopic,
  currentPhase,
  finalizeExam,
  settleToInteractiveScreen,
  stableClick,
  startSession,
} from "../../fixtures/learning-flow";

test.describe.configure({ timeout: 300_000 });

test("the video intervention resolves to a card or the no-video answer", async ({
  page,
  audit,
}) => {
  // Same known-defect allowance as the sibling ladder spec: finalizing an exam emits a burst of
  // 409s (AUD-F-02). Allowed by path so this journey still enforces zero console errors for
  // everything else.
  audit.allow({ statuses: [409], consoleErrors: ["Failed to load resource"] });

  await signInViaUi(page, LEARNING_WEB, FIXTURES.studentPresent);
  await startSession(page);
  await settleToInteractiveScreen(page);
  await chooseTopic(page);

  await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });
  await answerWholeExam(page);
  await finalizeExam(page);
  await settleToInteractiveScreen(page);

  // Answer until the graph pauses on `intervention_choice`. Identical to the ladder spec's loop
  // on purpose - the difference between the two tests is which button gets clicked, and keeping
  // everything before that identical is what makes the comparison meaningful.
  const menu = page.getByRole("heading", { name: /want a hand/i });
  let reached = false;
  for (let i = 0; i < 30 && !reached; i += 1) {
    await settleToInteractiveScreen(page);
    if ((await menu.count()) > 0) {
      reached = true;
      break;
    }
    const phase = await currentPhase(page);
    if (phase && /post-exam/i.test(phase)) break;
    if (!(await answerCurrentQuestion(page))) await page.waitForTimeout(500);
  }
  // A skip here is honest rather than a pass: the walk answered everything correctly, so no menu
  // ever opened and there was no Video branch to take. Reported as skipped for the same reason
  // D-318 made the ladder assertion skip rather than tick.
  test.skip(!reached, "no intervention menu opened in this run (every answer was correct)");

  // **The click no other journey makes.**
  await stableClick(page.getByRole("button", { name: /watch a video/i }));

  // **Wait for the Video *result*, not for "a panel".**
  //
  // The first version of this test waited on `.intervention-panel` and then branched on whether a
  // `.video-card` was inside it. It passed - and the text it recorded as the "no video" fallback
  // was the intervention **menu**: *"Not quite — want a hand? … GET A HINT / SHOW THE SOLUTION /
  // WATCH A VIDEO"*. The panel it matched was the one that was already on screen, so the
  // assertion held whether or not the Video branch ever ran. A criterion that cannot fail, caught
  // by reading the artifact rather than the green tick.
  //
  // The result screen is identified positively: `<h2>Video</h2>` in `.intervention-head`, which
  // the menu does not render. Now the test fails if the click does nothing.
  const videoHeading = page.getByRole("heading", { name: /^video$/i });
  const resolved = await videoHeading
    .waitFor({ state: "visible", timeout: 30_000 })
    .then(() => true)
    .catch(() => false);
  // **When this fails it is a product defect with a known mechanism (D-356), not a flake.**
  // Measured 2026-08-16 on staging, twice in four attempts, with the server proven correct:
  // `POST /respond` returned 200 carrying `intervention.type="video"` and a real
  // `video_url` in BOTH the passing and the failing run, byte-identical in substance. What
  // differs is what the browser is left holding.
  //
  // `build_deferred_narrative_snapshot` (routers/sessions.py) omits `intervention` AND
  // `assistance_question`, and every SSE frame *replaces* the client's whole snapshot - so
  // a `study_step` narrative arriving ~1.5s later erases the help panel. The client's own
  // condition (`App.tsx`: `ladderOpen || intervention != null`) makes the video and
  // solution branches the exposed ones, because both *close* the pause and therefore have
  // only `intervention` holding the panel up.
  //
  // `stage_narrative_scheduler` already guards this - `hint_ladder_awaiting_choice` skips
  // the publish mid-ladder - and its comment describes this exact wipe for hints. The guard
  // does not cover video or solution, which is where the pause is already closed.
  if (!resolved) {
    audit.note(
      "D-356: the video panel was erased after /respond returned it - check for a " +
        "deferred stage_narrative frame published after the video choice",
    );
  }
  expect(
    resolved,
    "clicking 'Watch a video' never produced the video result screen. If /respond returned " +
      "200 with intervention.type=video, this is D-356: a deferred narrative frame " +
      "replaced the snapshot and dropped the help panel",
  ).toBe(true);

  const panel = page.locator(".intervention-panel");
  // §5.11.6's two legitimate outcomes.
  const card = panel.locator(".video-card");
  const hasCard = (await card.count()) > 0;

  if (hasCard) {
    const title = await card.locator(".video-card-title").innerText();
    const href = await card.getAttribute("href");
    const meta = await card.locator(".video-card-meta").innerText();
    audit.note(`VIDEO OFFERED | title=${JSON.stringify(title)} href=${href} meta=${meta}`);

    // A card with no destination is worse than the fallback: it looks like help and does nothing.
    expect(href, "the video card rendered without a link").toBeTruthy();
    expect(href).toMatch(/^https?:\/\//);
    expect(title.trim().length, "the video card rendered with no title").toBeGreaterThan(0);
    // D-314: the counter must say "suggested", never "watched" - the product cannot know whether
    // a student watched anything, and claiming so in a parent-visible number would be a lie.
    expect(meta).not.toMatch(/watched/i);
  } else {
    const text = (await panel.innerText()).trim();
    audit.note(`NO VIDEO FOR THIS SKILL | fallback=${JSON.stringify(text.slice(0, 160))}`);

    // The §5.11.6 fallback is a real answer and must read as one. An empty panel, or one showing
    // a raw error, is the dead end D-314 fixed and would be a regression of it.
    expect(text.length, "the no-video path rendered an empty panel").toBeGreaterThan(0);
    expect(text).not.toMatch(/error|failed|undefined|null/i);
  }

  // Recorded on every run, so "the criterion was met" is a fact in the artifact rather than an
  // inference from the test having passed.
  audit.note(`U6 CRITERION | a real video was offered: ${hasCard}`);
});
