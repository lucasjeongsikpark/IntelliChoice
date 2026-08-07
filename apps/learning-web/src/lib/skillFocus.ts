import type { MasterySkillPoint } from "../types";

/**
 * Splitting the mastery rows into "still to strengthen" and "secure".
 *
 * Pure, and kept out of the component file so it is directly testable and so that file
 * exports only components (the Fast Refresh rule oxlint enforces).
 *
 * The split is on each skill's **own** `target_band` rather than a single global
 * threshold, so it agrees with the target line the mastery chart draws and cannot drift
 * from the server's idea of "at target".
 */

export interface FocusSkill {
  name: string;
  /** Weighted mastery, 0-1. */
  score: number;
  /** The server's target for this skill, 0-1. */
  target: number;
  /** How many completed sessions in range ended with this skill unresolved. */
  unresolvedSessions: number;
}

export function splitByTarget(
  mastery: MasterySkillPoint[],
  unresolvedCounts: Map<string, number>,
): { focus: FocusSkill[]; secure: FocusSkill[] } {
  const rows: FocusSkill[] = mastery.map((m) => ({
    name: m.skill_name,
    score: m.weighted_score,
    target: m.target_band,
    unresolvedSessions: unresolvedCounts.get(m.skill_name) ?? 0,
  }));
  return {
    // Weakest first: that is the order a student should work in, so it is the order the
    // list reads in.
    focus: rows.filter((r) => r.score < r.target).sort((a, b) => a.score - b.score),
    secure: rows.filter((r) => r.score >= r.target).sort((a, b) => b.score - a.score),
  };
}
