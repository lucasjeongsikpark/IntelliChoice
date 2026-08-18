/**
 * D-409 (`AUD-L-10`): the report's 39-skill run-on, grouped into the two bands the server already
 * classifies.
 *
 * The assertion that matters most is the last one: **no threshold appears in the module under
 * test.** The partition is set membership against `weak_skill_names`, which the server computes
 * from `WEAK_SKILL_THRESHOLD`. A `0.7` in TypeScript would be the cross-language copy
 * `intellichoice_shared.mastery_policy` was written to prevent, in the one place no test could
 * catch it drifting.
 */

import { describe, expect, it } from "vitest";
import { groupSkillsByBand, joinSkillNames } from "./masteryBands";

describe("groupSkillsByBand", () => {
  it("puts the server's weak skills in the practising band and the rest in confident", () => {
    const bands = groupSkillsByBand(
      { addition: 0.9, fractions: 0.4, geometry: 0.75, ratios: 0.2 },
      ["fractions", "ratios"],
    );
    expect(bands.confident).toEqual(["addition", "geometry"]);
    expect(bands.practising).toEqual(["fractions", "ratios"]);
  });

  it("preserves the order the server sent rather than sorting", () => {
    // The dashboard and the report must list a child's skills in one order - re-sorting here would
    // make the same data read as two different things on two screens.
    const bands = groupSkillsByBand({ zeta: 0.9, alpha: 0.9, mu: 0.9 }, []);
    expect(bands.confident).toEqual(["zeta", "alpha", "mu"]);
  });

  it("handles a report with nothing weak, and one with nothing confident", () => {
    expect(groupSkillsByBand({ a: 0.9 }, []).practising).toEqual([]);
    expect(groupSkillsByBand({ a: 0.1 }, ["a"]).confident).toEqual([]);
  });

  it("ignores a weak name the mastery table does not have", () => {
    // The report's own facts are the subject. Inventing a row for a name with no score would put a
    // skill on a parent's report that the mastery table does not contain.
    const bands = groupSkillsByBand({ addition: 0.9 }, ["addition", "a_skill_not_in_the_table"]);
    expect(bands.practising).toEqual(["addition"]);
    expect(bands.confident).toEqual([]);
    expect([...bands.confident, ...bands.practising]).toHaveLength(1);
  });

  it("is empty for an empty report rather than throwing", () => {
    expect(groupSkillsByBand({}, [])).toEqual({ confident: [], practising: [] });
  });

  it("never partitions on a score, so there is no threshold to drift", () => {
    // **The structural assertion.** Two definitions of a classification cut is how the same skill
    // becomes "weak" to one subsystem and "proficient" to another (AUD-L-13/D-156), and a copy in
    // another language is the version no test can see. So: the scores are ignored entirely - a
    // skill absent from `weak_skill_names` is confident even when its score says otherwise.
    const bands = groupSkillsByBand({ misleading: 0.01 }, []);
    expect(bands.confident).toEqual(["misleading"]);

    // **A source-reading version of this was written and removed, and the behavioural assertion
    // above is why it was redundant.** It read the module's text and asserted no `0.<digit>`
    // appeared in it - which needed `node:fs`, which this app has no types for, which
    // `npm run build` caught (`tsc --noEmit` did not: the build's project references are the real
    // gate, the same lesson as D-405's vite config).
    //
    // Adding `@types/node` for it would have bought nothing. A future edit that partitioned on a
    // score instead of on `weak_skill_names` fails the assertion above by construction: a skill
    // scoring 0.01 and absent from the weak list can only land in `confident` if the scores are
    // being ignored. Behaviour is a stronger guard than grepping for a literal anyway - a
    // threshold spelled `7 / 10` would have slipped straight past the regex.
  });
});

describe("joinSkillNames", () => {
  it("joins names and reports an empty band as null so a caller can omit it", () => {
    expect(joinSkillNames(["a", "b"])).toBe("a, b");
    expect(joinSkillNames([])).toBeNull();
  });
});
