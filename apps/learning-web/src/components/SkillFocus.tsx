import type { FocusSkill } from "../lib/skillFocus";

/**
 * "Skills to strengthen", as the thing the screen is *for* rather than the tenth column of
 * a ten-column table.
 *
 * It used to be `unresolved_skill_names.join(", ")` in the last cell of the completed-
 * sessions table - the widest column, holding the longest text, in the position most likely
 * to be scrolled off. That is the readability complaint, and moving the same string
 * somewhere roomier would not have fixed it: a comma-joined list of skill names says which
 * skills, and nothing about how far off they are or whether they are improving.
 *
 * This is derived from mastery rather than from the session log, so it answers "where am I
 * now" instead of "what went wrong once". `target_band` is the server's own per-skill
 * target, so a skill leaves this list by the same rule the mastery chart draws.
 *
 * Language is growth-oriented per SPEC §5.10.3 - "to strengthen" and "secure", never "weak"
 * or "failing", and internal skill ids never appear.
 */

function percent(value: number): number {
  return Math.round(value * 100);
}

export function SkillFocusList({ focus, secure }: { focus: FocusSkill[]; secure: FocusSkill[] }) {
  if (focus.length === 0 && secure.length === 0) {
    return <p className="chart-empty">No skill data yet — finish a session to see this.</p>;
  }

  return (
    <div className="skill-focus">
      {focus.length > 0 && (
        <ul className="skill-focus-list">
          {focus.map((skill) => (
            <li key={skill.name} className="skill-focus-item">
              <div className="skill-focus-head">
                {/* Not truncated. The chart's Y axis truncates because axis labels collide;
                    there is no such constraint here, and this is the place a student
                    actually reads the name. */}
                <span className="skill-focus-name">{skill.name}</span>
                <span className="skill-focus-score">{percent(skill.score)}%</span>
              </div>
              {/* The bar carries the same number as the text beside it, so it is a visual
                  aid rather than the only way to read the value. */}
              <div className="skill-focus-bar" aria-hidden="true">
                <span className="skill-focus-fill" style={{ width: `${percent(skill.score)}%` }} />
                <span className="skill-focus-target" style={{ left: `${percent(skill.target)}%` }} />
              </div>
              <p className="skill-focus-note">
                {percent(skill.target - skill.score)} points from the {percent(skill.target)}%
                target
                {skill.unresolvedSessions > 0 &&
                  ` · unfinished in ${skill.unresolvedSessions} ${
                    skill.unresolvedSessions === 1 ? "session" : "sessions"
                  }`}
              </p>
            </li>
          ))}
        </ul>
      )}

      {focus.length === 0 && (
        <p className="skill-focus-clear">
          Every skill is at its target right now. Nice work.
        </p>
      )}

      {secure.length > 0 && (
        <div className="skill-secure">
          <h3 className="skill-secure-title">Secure</h3>
          <ul className="skill-secure-list">
            {secure.map((skill) => (
              <li key={skill.name}>
                <span className="skill-secure-check" aria-hidden="true">
                  ✓
                </span>
                {skill.name} <span className="skill-secure-score">{percent(skill.score)}%</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
