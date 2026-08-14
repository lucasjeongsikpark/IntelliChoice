/**
 * One full walk per grade band (D-288, C1 Phase 6).
 *
 * Until these existed, the only band any e2e walk touched was 6-7, via one topic, as a
 * grade-3 student - so the 620-item bank shipped with its 6-8 and 9-12 content never once
 * rendered in front of anyone, and that is exactly where the raw-SymPy option defect sat.
 * Each walk is a real student journey through the real picker: sign-in → start → topic →
 * the full 10-item pre-exam → finalize → study entry, with the capture fixture enforcing
 * zero console errors over the whole thing (§2.6 criterion 3).
 *
 * Each band signs in as its own fixture student, never a shared one: staging sessions
 * persist, and two tests signing in as the same student resume each other's exams (the
 * journey-student isolation finding).
 *
 * The K-2 walk doubles as the figure walk: `telling_time` is a family-C topic, so every
 * question it serves carries a clock spec, and the walk asserts the SVG actually rendered
 * - the one link the D-279 chain could not prove from inside pytest.
 */

import type { Page } from "@playwright/test";
import { FIXTURES, LEARNING_WEB } from "../../config";
import { expect, test } from "../../fixtures/capture";
import { expectNotBlank, expectNotStuck, signInViaUi } from "../../fixtures/session";
import {
  answerCurrentQuestion,
  chooseTopic,
  clearInterventionIfPresent,
  currentPhase,
  finalizeExam,
  settleToInteractiveScreen,
  startSession,
} from "../../fixtures/learning-flow";

// Each walk is a 10-item graded exam against a real graph, plus study entry.
test.describe.configure({ timeout: 300_000 });

const BANDS = [
  {
    band: "K-2 (figure walk)",
    student: FIXTURES.studentBandK2,
    topic: /telling the time/i,
    expectFigure: "clock",
  },
  {
    band: "3-5",
    student: FIXTURES.studentBand35,
    // The full phrase, not /multi-digit/i: "Word Problems: Multi-Digit and Decimal
    // Quantities" also matches the short form, and two matches is a strict-mode violation
    // that stableClick's catch silently converts into "could not select a topic".
    topic: /multiplication and division: multi-digit/i,
    expectFigure: null,
  },
  {
    band: "6-8",
    student: FIXTURES.studentBand68,
    topic: /pre-algebra/i,
    expectFigure: null,
  },
  {
    band: "9-12",
    student: FIXTURES.studentBand912,
    topic: /calculus/i,
    expectFigure: null,
  },
] as const;

/**
 * The rendered question and options must read as mathematics, not as SymPy. `)*(` and
 * digit-star-letter are the two shapes the 64-field notation fix removed; a walk that
 * met one would mean unfixed content reached serving, or a new wave re-shipped it.
 */
async function expectStudentReadableMath(page: Page): Promise<void> {
  const stem = await page.locator("h1").innerText().catch(() => "");
  const options = await page
    .locator(".option-text")
    .allInnerTexts()
    .catch(() => [] as string[]);
  for (const text of [stem, ...options]) {
    expect(text, `programmer notation reached a student: ${text}`).not.toMatch(
      /\)\s*\*\s*\(|\d\s*\*\s*[a-z]/i,
    );
  }
}

for (const { band, student, topic, expectFigure } of BANDS) {
  test(`a ${band} student walks their band's topic end to end`, async ({ page, audit }) => {
    // AUD-F-02: finalize produces a burst of 409s on overview/time polls, each a console
    // error. Allowed so the walk still enforces zero console errors for everything else.
    audit.allow({ statuses: [409], consoleErrors: ["Failed to load resource"] });

    await signInViaUi(page, LEARNING_WEB, student);
    await expectNotBlank(page);
    await startSession(page);
    await expectNotStuck(page, "Connecting…");
    await settleToInteractiveScreen(page);
    await chooseTopic(page, topic);

    await expect(page.locator(".phase-chip")).toHaveText(/pre-exam/i, { timeout: 60_000 });

    // The walk answers the exam itself rather than through answerWholeExam, because each
    // served question is also an assertion surface: notation on every band, the figure on
    // the family-C one.
    let answered = 0;
    for (let i = 0; i < 14 && answered < 10; i += 1) {
      await settleToInteractiveScreen(page);
      if (expectFigure) {
        const figure = page.locator(`.question-figure[data-figure-kind="${expectFigure}"]`);
        await expect(figure, "a family-C question rendered without its figure").toBeVisible();
        await expect(figure.locator("svg[role='img']")).toBeVisible();
      }
      await expectStudentReadableMath(page);
      if (!(await answerCurrentQuestion(page))) {
        await page.waitForTimeout(500);
        continue;
      }
      answered += 1;
    }
    audit.note(`${band}: answered ${answered} pre-exam items`);
    expect(answered, "the pre-exam is SPEC §5.9.2's fixed 10-item set").toBe(10);
    await finalizeExam(page);

    // Study entry proves the band's content serves past the exam builder: the phase
    // advances and a question (or its retry ladder) renders without a console error.
    await settleToInteractiveScreen(page);
    await expect
      .poll(async () => currentPhase(page), { timeout: 60_000 })
      .toMatch(/study|post-exam/i);
    for (let i = 0; i < 4; i += 1) {
      await settleToInteractiveScreen(page);
      if (await clearInterventionIfPresent(page, (m) => audit.note(`${band}: ${m}`))) continue;
      await expectStudentReadableMath(page);
      if (await answerCurrentQuestion(page)) break;
      await page.waitForTimeout(500);
    }
    await expectNotBlank(page);
  });
}
