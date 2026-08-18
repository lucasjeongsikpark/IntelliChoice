/**
 * D-409 (`AUD-L-10`): the report listed every skill as one joined run-on.
 *
 * Measured on the live build: 39 skills rendered as `name: 80%; name: 60%; …` in a single
 * paragraph on the artefact a parent trusts. Half of that finding was already fixed - `_RATE_FACTS`
 * and `formatRate` turned proportions into percentages (see `ReportView`'s own comment about
 * `Overall accuracy: 0.24`) - so what was left is that a parent cannot see the *shape* of 39
 * numbers in a sentence.
 *
 * **Two bands, not three, and that is a constraint rather than a preference.** The obvious design is
 * "Strong / Developing / Needs work", which needs two cutoffs. This system defines exactly **one**:
 * `WEAK_SKILL_THRESHOLD = 0.7`, and `intellichoice_shared.mastery_policy` exists specifically
 * because *"two definitions of a classification threshold is how the same skill ends up 'weak' to
 * one subsystem and 'proficient' to another"* (AUD-L-13/D-156). Inventing a middle cut here would
 * put a third definition on a parent-facing report, disagreeing with what the study plan actually
 * targets.
 *
 * **And no threshold appears in this file at all**, which is the point. The server already ships
 * `weak_skill_names`, computed from that one constant (`report.py`), so the partition is a set
 * membership test rather than a number this language has to keep in step. A `0.7` in TypeScript
 * would be exactly the cross-language copy `mastery_policy` warns about, in the one place no test
 * could catch it drifting.
 */

export interface MasteryBands {
  /** At or above the weak-skill cut, per the server. */
  confident: string[];
  /** Below it. Named for SPEC §5.10.3's growth-oriented framing - a skill being practised is not
   *  a skill failed, and this is a document a child may read. */
  practising: string[];
}

/**
 * Partition `mastery_by_skill` into the two bands the server already classifies.
 *
 * Order is preserved from `mastery_by_skill` rather than sorted: the dashboard and the report
 * should list a child's skills in one order, and re-sorting here would make the same data read as
 * two different things on two screens.
 *
 * A skill named in `weakSkillNames` but absent from `masteryBySkill` is ignored - the report's own
 * facts are the subject, and inventing a row for a name with no score would put a skill on a
 * parent's report that the mastery table does not have.
 */
export function groupSkillsByBand(
  masteryBySkill: Record<string, unknown>,
  weakSkillNames: readonly string[],
): MasteryBands {
  const weak = new Set(weakSkillNames);
  const bands: MasteryBands = { confident: [], practising: [] };
  for (const name of Object.keys(masteryBySkill)) {
    (weak.has(name) ? bands.practising : bands.confident).push(name);
  }
  return bands;
}

/** `["a","b"]` → `"a, b"`, and `[]` → `null` so a caller can omit an empty band entirely. */
export function joinSkillNames(names: readonly string[]): string | null {
  return names.length > 0 ? names.join(", ") : null;
}
