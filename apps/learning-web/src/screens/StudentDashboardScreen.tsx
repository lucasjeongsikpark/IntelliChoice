import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import * as api from "../api/client";
import { ReportView } from "../components/ReportView";
import { SkillFocusList } from "../components/SkillFocus";
import { splitByTarget } from "../lib/skillFocus";
import { topicLabel } from "../topics";
import type {
  BlockedSessionSummary,
  DashboardData,
  DifficultyPoint,
  StudentHistory,
  StudentReport,
} from "../types";

interface Props {
  token: string;
  studentId: string;
  /**
   * The child's display name, when a parent is reading this. `null` for a student looking
   * at their own dashboard, and `null` while the parent's children list is still loading -
   * both fall back to the external id.
   *
   * Added because the parent journey showed the id: a parent picked "Ben First" by name on
   * the previous screen and then read "Student: student-ext-2". The name was already in
   * hand, one screen earlier.
   */
  studentName?: string | null;
  onBack: () => void;
}

// Recharts' `Formatter`/label-formatter generics expect a callback whose parameter
// types are a supertype of `ValueType | undefined` / `ReactNode` - `unknown` satisfies
// that structurally without a broad `any`.
function formatPercent(value: unknown): string {
  return `${Math.round(Number(value) * 100)}%`;
}

function formatDateLabel(value: unknown): string {
  return typeof value === "string" ? new Date(value).toLocaleDateString() : "";
}

// Skill names are curriculum-authored free text with no length cap - truncating to a
// single line keeps the Y-axis category labels from wrapping and colliding with their
// neighbors (the full name is still available via the tooltip's series value).
const SKILL_LABEL_MAX_CHARS = 26;

/**
 * Truncates in the **middle**, because a skill name's distinguishing part is its tail.
 *
 * These names are built as "Solve linear equations …", so cutting off the end - which this
 * did - collapsed different skills onto the same label. Measured on staging 2026-08-07, the
 * "Mastery by skill" axis rendered "Solve linear equations wi…" **twice**: once for "…with
 * variables on both sides" and once for "…with negative or fractional coefficients". Two
 * bars, two different masteries (87% and 31%), no way to tell which was which. On a chart
 * whose whole job is to say which skill needs work, that is the chart failing.
 *
 * Keeping a head and a tail costs the same horizontal space and separates every name in the
 * current curriculum. It degrades gracefully rather than uniquely: two skills differing only
 * in the middle would still collide, which the tooltip's full value still resolves.
 */
function truncateSkillLabel(value: unknown): string {
  const label = typeof value === "string" ? value : String(value);
  if (label.length <= SKILL_LABEL_MAX_CHARS) return label;
  const head = Math.ceil((SKILL_LABEL_MAX_CHARS - 1) / 2);
  const tail = SKILL_LABEL_MAX_CHARS - 1 - head;
  return `${label.slice(0, head)}…${label.slice(-tail)}`;
}

interface GroupedBlock {
  key: string;
  week_id: string;
  blocked_reason: string;
  /** Most recent attempt in the group - the one a parent would ask about. */
  latest_blocked_at: string;
  attempts: number;
}

/**
 * One row per blocked **week and reason**, not per blocked attempt.
 *
 * `blocked_sessions` is an attempt log, and rendering it directly meant a student who tried
 * several times in one day produced several identical lines. Measured on staging 2026-08-07
 * on a parent's dashboard: **20 rows, 6 distinct** - "Week 2026-W31 — absent (7/31/2026)"
 * eight times and "(7/29/2026)" six times. Everything above it on that dashboard said "no
 * data yet", so a wall of repeated blocks was the entire page, and 14 of the 20 lines
 * carried no information the line above did not.
 *
 * The attempt count is kept rather than dropped - "tried 8 times and was blocked" is a
 * different situation from "tried once", and it is the parent's cue that the child wanted to
 * work. Grouping is display-only; the rows themselves stay as they are, since they are the
 * evidence for a gate that refused someone.
 */
function groupBlockedSessions(blocked: BlockedSessionSummary[]): GroupedBlock[] {
  const groups = new Map<string, GroupedBlock>();
  for (const b of blocked) {
    const key = `${b.week_id}|${b.blocked_reason}`;
    const existing = groups.get(key);
    if (existing === undefined) {
      groups.set(key, {
        key,
        week_id: b.week_id,
        blocked_reason: b.blocked_reason,
        latest_blocked_at: b.blocked_at,
        attempts: 1,
      });
      continue;
    }
    existing.attempts += 1;
    if (b.blocked_at > existing.latest_blocked_at) existing.latest_blocked_at = b.blocked_at;
  }
  return [...groups.values()].sort((a, b) =>
    b.latest_blocked_at.localeCompare(a.latest_blocked_at),
  );
}

function formatDifficultyTooltip(value: unknown, _name: unknown, item: unknown): [string, string] {
  const payload = (item as { payload?: DifficultyPoint } | undefined)?.payload;
  return [String(value), payload?.skill_name ?? ""];
}

// Fixed chart colors (`--viz-series-*`, declared on `:root` in App.css) - Recharts needs
// resolved values, not CSS var() references, so these are read here rather than passed as
// `var(...)`. Order is fixed across every chart on this screen (dataviz skill: "color
// follows the entity, never its rank").
//
// The `:root` in that sentence is the whole point, and this comment used to say
// `.dashboard-charts`, which is where they really were. Custom properties inherit
// downward, so a declaration on that descendant was invisible to
// `document.documentElement` here: all four lookups returned `""`, every series took the
// fallback below, and the charts rendered monochrome with no error anywhere. If this
// lookup is ever re-pointed at an element, the declaration has to move with it.
function vizColor(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#2a78d6";
}

type RangePreset = "7d" | "30d" | "90d" | "all";

const RANGE_LABELS: Record<RangePreset, string> = {
  "7d": "Last 7 days",
  "30d": "Last 30 days",
  "90d": "Last 90 days",
  all: "All time",
};

function rangeStart(preset: RangePreset): string | null {
  if (preset === "all") return null;
  const days = preset === "7d" ? 7 : preset === "30d" ? 30 : 90;
  const start = new Date();
  start.setDate(start.getDate() - days);
  return start.toISOString();
}

export function StudentDashboardScreen({ token, studentId, studentName = null, onBack }: Props) {
  const [history, setHistory] = useState<StudentHistory | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const [rangePreset, setRangePreset] = useState<RangePreset>("30d");
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);

  const [report, setReport] = useState<StudentReport | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  const start = useMemo(() => rangeStart(rangePreset), [rangePreset]);

  // AUD-X-04: the idempotency key for report generation, and the reason it is built this way
  // rather than minted per click. A fresh key per call (what `submitAnswer` does) would leave
  // the defect exactly as it was - two clicks, two paid Bedrock calls. A key derived only from
  // (student, range) would go the other way and make a report un-regeneratable forever.
  //
  // So: stable for this mounted view of this student at this range, fresh on remount. A double
  // click returns the report the student is already looking at without paying again; changing
  // the range, or coming back to the dashboard later, generates a real new one. Two tabs still
  // get two keys and therefore two reports - bounded by AUD-L-02's per-day ceiling, not by this.
  //
  // D-161: the nonce ROTATES when a response arrives with `generated: false`. Both server
  // fallbacks (cost ceiling, gateway failure) persist their facts-only row under the key, so a
  // stable nonce would pin the degraded report for the lifetime of this view - "Regenerate
  // report" would silently replay it, where before D-159 a second click was a real retry.
  // Rotation happens only on a *received* degraded result: a network error keeps the key,
  // because the outcome is unknown and, if the server committed before the response was lost,
  // the retry must replay rather than pay twice - the exact defect AUD-X-04 closed.
  const [reportNonce, setReportNonce] = useState(() => crypto.randomUUID());
  const reportKey = `${studentId}:${rangePreset}:${reportNonce}`;

  useEffect(() => {
    let cancelled = false;
    api
      .getStudentHistory(token, studentId)
      .then((h) => !cancelled && setHistory(h))
      .catch((err) => !cancelled && setHistoryError(String(err)));
    return () => {
      cancelled = true;
    };
  }, [token, studentId]);

  useEffect(() => {
    let cancelled = false;
    setDashboard(null);
    api
      .getStudentDashboard(token, studentId, start, null)
      .then((d) => !cancelled && setDashboard(d))
      .catch((err) => !cancelled && setDashboardError(String(err)));
    return () => {
      cancelled = true;
    };
  }, [token, studentId, start]);

  async function handleGenerateReport() {
    setReportBusy(true);
    setReportError(null);
    try {
      const result = await api.generateStudentReport(token, studentId, start, null, reportKey);
      setReport(result);
      if (!result.generated) {
        // D-161: this key now names a stored facts-only row; the next explicit click must be
        // a fresh request, not a replay of the degraded report.
        setReportNonce(crypto.randomUUID());
      }
    } catch (err) {
      setReportError(String(err));
    } finally {
      setReportBusy(false);
    }
  }

  // D-213: derived here rather than fetched - every input is already on this screen, so a
  // new endpoint would be a second source of truth for a number the client can compute.
  //
  // `unresolved_skill_names` is per completed session, so a skill that has been left
  // unfinished repeatedly counts once per session. That count is the "and it keeps
  // happening" signal a single mastery percentage cannot carry.
  const skillGroups = useMemo(() => {
    if (!dashboard) return { focus: [], secure: [] };
    const unresolvedCounts = new Map<string, number>();
    for (const session of history?.completed_sessions ?? []) {
      for (const name of session.unresolved_skill_names) {
        unresolvedCounts.set(name, (unresolvedCounts.get(name) ?? 0) + 1);
      }
    }
    return splitByTarget(dashboard.mastery_by_skill, unresolvedCounts);
  }, [dashboard, history]);

  // Independence as a share, not a count. "12 independent correct" is unreadable without
  // the denominator - 12 of 14 and 12 of 90 are different students.
  const independenceRate =
    dashboard && dashboard.usage.total_attempts > 0
      ? Math.round((dashboard.usage.independent_count / dashboard.usage.total_attempts) * 100)
      : null;

  const colors = {
    series1: vizColor("--viz-series-1"),
    series2: vizColor("--viz-series-2"),
    series3: vizColor("--viz-series-3"),
    series4: vizColor("--viz-series-4"),
    ink: vizColor("--viz-ink") || "#333",
    grid: vizColor("--viz-grid") || "#e8e8e8",
  };

  return (
    <div className="panel wide dashboard dashboard-charts">
      {/* D-213: the Back button used to sit full-width between the title and the controls,
          splitting the header in half. It belongs beside the title. */}
      <div className="dashboard-head">
        <div>
          <h1>Progress dashboard</h1>
          <p className="subtitle">Student: {studentName ?? studentId}</p>
        </div>
        <button className="secondary dashboard-back" onClick={onBack}>
          Back
        </button>
      </div>

      <div
        className="date-range-controls"
        role="group"
        aria-label="Select date range for charts and reports"
      >
        {(Object.keys(RANGE_LABELS) as RangePreset[]).map((preset) => (
          <button
            key={preset}
            className={preset === rangePreset ? "selected" : ""}
            aria-pressed={preset === rangePreset}
            onClick={() => setRangePreset(preset)}
          >
            {RANGE_LABELS[preset]}
          </button>
        ))}
      </div>

      {dashboardError && <p className="error">{dashboardError}</p>}
      {!dashboard && !dashboardError && <p>Loading charts…</p>}

      {dashboard && (
        <>
          {/* D-213: each stat now carries the context that makes it mean something. A bare
              "26" answered no question anyone actually has. */}
          <div className="stat-grid">
            <div className="stat">
              <span className="stat-value">{dashboard.attempts_count}</span>
              Questions answered
            </div>
            <div className="stat">
              <span className="stat-value">{dashboard.time_spent_minutes.toFixed(0)}</span>
              Minutes of practice
            </div>
            <div className="stat">
              <span className="stat-value">
                {independenceRate === null ? "—" : `${independenceRate}%`}
              </span>
              Solved without help
            </div>
            <div className="stat">
              <span className="stat-value">{skillGroups.secure.length}</span>
              {skillGroups.secure.length + skillGroups.focus.length > 0
                ? `of ${skillGroups.secure.length + skillGroups.focus.length} skills at target`
                : "skills at target"}
            </div>
          </div>

          {/* D-213: promoted to the top of the screen, because it is the one section that
              says what to do next. It used to be the last column of the session table. */}
          <section className="chart-section" aria-label="Skills to strengthen">
            <h2>Skills to strengthen</h2>
            <p className="chart-caption">{dashboard.mastery_window_label}</p>
            <SkillFocusList focus={skillGroups.focus} secure={skillGroups.secure} />
          </section>

          <section className="chart-section" aria-label="Mastery by skill">
            <h2>Mastery by skill</h2>
            {/* AUD-L-15: this is the one chart on the screen the date-range picker above
                does not apply to, and it excludes the post-exam besides - so a skill can
                read 100% here while "Pre vs. post accuracy" shows it missed. Both are
                correct measurements of different windows; without the caption the pair
                reads as a contradiction. Server-supplied so it cannot drift. */}
            <p className="chart-caption">{dashboard.mastery_window_label}</p>
            {dashboard.mastery_by_skill.length === 0 ? (
              <p className="chart-empty">No mastery data yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height={Math.max(140, dashboard.mastery_by_skill.length * 56)}>
                <BarChart
                  data={dashboard.mastery_by_skill}
                  layout="vertical"
                  margin={{ left: 12, right: 16 }}
                >
                  <CartesianGrid stroke={colors.grid} horizontal={false} />
                  <XAxis type="number" domain={[0, 1]} stroke={colors.ink} fontSize={12} />
                  <YAxis
                    type="category"
                    dataKey="skill_name"
                    stroke={colors.ink}
                    fontSize={12}
                    width={168}
                    tickFormatter={truncateSkillLabel}
                    interval={0}
                  />
                  <Tooltip formatter={formatPercent} />
                  {/* D-213: the dashed line was unlabelled, so it read as decoration. It
                      is the mastery target the "skills to strengthen" split uses. */}
                  <ReferenceLine
                    x={0.8}
                    stroke={colors.ink}
                    strokeDasharray="4 4"
                    label={{ value: "Target", position: "top", fill: colors.ink, fontSize: 11 }}
                  />
                  <Bar
                    dataKey="weighted_score"
                    name="Mastery"
                    fill={colors.series1}
                    radius={[0, 4, 4, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </section>

          <section className="chart-section" aria-label="Pre and post exam accuracy by skill">
            <h2>Pre vs. post accuracy by skill</h2>
            <p className="chart-caption">{dashboard.pre_post_window_label}</p>
            {dashboard.pre_post_by_skill.length === 0 ? (
              <p className="chart-empty">No completed pre/post cycle in this range yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height={Math.max(160, dashboard.pre_post_by_skill.length * 56)}>
                <BarChart data={dashboard.pre_post_by_skill} layout="vertical" margin={{ left: 12, right: 16 }}>
                  <CartesianGrid stroke={colors.grid} horizontal={false} />
                  <XAxis type="number" domain={[0, 1]} stroke={colors.ink} fontSize={12} />
                  <YAxis
                    type="category"
                    dataKey="skill_name"
                    stroke={colors.ink}
                    fontSize={12}
                    width={168}
                    tickFormatter={truncateSkillLabel}
                    interval={0}
                  />
                  <Tooltip formatter={formatPercent} />
                  <Legend />
                  <Bar dataKey="pre_accuracy" name="Pre-exam" fill={colors.series1} radius={[0, 4, 4, 0]} />
                  <Bar dataKey="post_accuracy" name="Post-exam" fill={colors.series2} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </section>

          <section className="chart-section" aria-label="Learning gain over time">
            <h2>Gains over time</h2>
            {dashboard.gains_over_time.length === 0 ? (
              <p className="chart-empty">No completed pre/post cycle in this range yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={dashboard.gains_over_time}>
                  <CartesianGrid stroke={colors.grid} />
                  <XAxis
                    dataKey="date"
                    stroke={colors.ink}
                    fontSize={12}
                    tickFormatter={formatDateLabel}
                  />
                  <YAxis stroke={colors.ink} fontSize={12} />
                  <Tooltip labelFormatter={formatDateLabel} />
                  <Legend />
                  <Line type="monotone" dataKey="raw_gain" name="Raw gain" stroke={colors.series1} strokeWidth={2} dot={{ r: 4 }} />
                  <Line type="monotone" dataKey="weighted_gain" name="Weighted gain" stroke={colors.series2} strokeWidth={2} dot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </section>

          <section className="chart-section" aria-label="Hint, solution, and video usage">
            <h2>Support usage</h2>
            {dashboard.usage.total_attempts === 0 ? (
              <p className="chart-empty">No study attempts in this range yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height={100}>
                <BarChart
                  data={[
                    {
                      name: "Attempts",
                      Independent: dashboard.usage.independent_count,
                      Hint: dashboard.usage.hint_count,
                      Solution: dashboard.usage.solution_count,
                      Video: dashboard.usage.video_count,
                    },
                  ]}
                  layout="vertical"
                  margin={{ left: 12, right: 16 }}
                >
                  <XAxis type="number" stroke={colors.ink} fontSize={12} />
                  <YAxis type="category" dataKey="name" hide />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="Independent" stackId="usage" fill={colors.series4} />
                  <Bar dataKey="Hint" stackId="usage" fill={colors.series1} />
                  <Bar dataKey="Solution" stackId="usage" fill={colors.series2} />
                  <Bar dataKey="Video" stackId="usage" fill={colors.series3} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </section>

          <section className="chart-section" aria-label="Difficulty progression">
            <h2>Difficulty progression</h2>
            {dashboard.difficulty_progression.length === 0 ? (
              <p className="chart-empty">No study attempts in this range yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={dashboard.difficulty_progression}>
                  <CartesianGrid stroke={colors.grid} />
                  <XAxis
                    dataKey="date"
                    stroke={colors.ink}
                    fontSize={12}
                    tickFormatter={formatDateLabel}
                  />
                  <YAxis stroke={colors.ink} fontSize={12} allowDecimals={false} />
                  <Tooltip labelFormatter={formatDateLabel} formatter={formatDifficultyTooltip} />
                  <Line
                    type="stepAfter"
                    dataKey="difficulty"
                    name="Difficulty"
                    stroke={colors.series1}
                    strokeWidth={2}
                    dot={{ r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </section>
        </>
      )}

      <ReportView report={report} busy={reportBusy} error={reportError} onGenerate={handleGenerateReport} />

      {historyError && <p className="error">{historyError}</p>}
      {!history && !historyError && <p>Loading…</p>}

      {history && (
        <>
          <h2>Completed sessions</h2>
          {history.completed_sessions.length === 0 && <p className="dim">None yet.</p>}
          {/* D-213: ten columns became six.
              - Hints/Solutions/Videos collapse into one "Support used" total. The split
                mattered to nobody reading a row; the breakdown is the "Support usage"
                chart above, which is where a reader who wants it will look.
              - "Skills to strengthen" is gone from here entirely - it is the section at the
                top of the screen now, derived from current mastery rather than from one
                session's leftovers.
              - Pre/Post/Gain become one "Pre -> Post" cell, so the improvement reads as a
                movement instead of three numbers to subtract mentally. */}
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Topic</th>
                  <th>Pre → Post</th>
                  <th>Gain</th>
                  <th>Support used</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                {history.completed_sessions.map((s) => (
                  <tr key={s.learning_gain_id}>
                    <td>{new Date(s.completed_at).toLocaleDateString()}</td>
                    <td>{topicLabel(s.topic_id)}</td>
                    <td className="numeric">
                      {s.pre_raw_score} → {s.post_raw_score}
                    </td>
                    <td className={`numeric ${s.raw_gain > 0 ? "gain-up" : s.raw_gain < 0 ? "gain-down" : ""}`}>
                      {s.raw_gain > 0 ? `+${s.raw_gain}` : s.raw_gain}
                    </td>
                    <td className="numeric">{s.hint_count + s.solution_count + s.video_count}</td>
                    <td>
                      {s.tutor_review_flagged ? (
                        <span title="Flagged for tutor review">⚠️ Flagged</span>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2>Blocked (attendance not confirmed)</h2>
          {history.blocked_sessions.length === 0 && <p className="dim">None.</p>}
          <ul>
            {groupBlockedSessions(history.blocked_sessions).map((b) => (
              <li key={b.key}>
                Week {b.week_id} — {b.blocked_reason} (
                {new Date(b.latest_blocked_at).toLocaleDateString()})
                {b.attempts > 1 && <span className="dim"> · {b.attempts} attempts</span>}
              </li>
            ))}
          </ul>

          {/* D-213: the "Skill mastery" bullet list that sat here is removed. It printed the
              same weighted scores as the "Mastery by skill" chart and the "Skills to
              strengthen" section above it - three renderings of one dataset, the last of
              them a bare `<ul>`. Nothing was lost: `history.mastery` and
              `dashboard.mastery_by_skill` carry the same per-skill weighted score, and the
              two surviving views show it against its target rather than alone. */}

          {history.problem_reports.length > 0 && (
            <>
              <h2>Problem reports filed</h2>
              <ul>
                {history.problem_reports.map((r) => (
                  <li key={`${r.question_template_id}-${r.created_at}`}>
                    {r.report_type} — {r.status}
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </div>
  );
}
