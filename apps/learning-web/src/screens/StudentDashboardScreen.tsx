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
import { topicLabel } from "../topics";
import type { DashboardData, DifficultyPoint, StudentHistory, StudentReport } from "../types";

interface Props {
  token: string;
  studentId: string;
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

function truncateSkillLabel(value: unknown): string {
  const label = typeof value === "string" ? value : String(value);
  return label.length > SKILL_LABEL_MAX_CHARS
    ? `${label.slice(0, SKILL_LABEL_MAX_CHARS - 1)}…`
    : label;
}

function formatDifficultyTooltip(value: unknown, _name: unknown, item: unknown): [string, string] {
  const payload = (item as { payload?: DifficultyPoint } | undefined)?.payload;
  return [String(value), payload?.skill_name ?? ""];
}

// Fixed chart colors (`--viz-series-*`, defined on `.dashboard-charts` in App.css) -
// Recharts needs resolved values, not CSS var() references, so these are read once at
// module load. Order is fixed across every chart on this screen (dataviz skill: "color
// follows the entity, never its rank").
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

export function StudentDashboardScreen({ token, studentId, onBack }: Props) {
  const [history, setHistory] = useState<StudentHistory | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const [rangePreset, setRangePreset] = useState<RangePreset>("30d");
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);

  const [report, setReport] = useState<StudentReport | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  const start = useMemo(() => rangeStart(rangePreset), [rangePreset]);

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
      const result = await api.generateStudentReport(token, studentId, start, null);
      setReport(result);
    } catch (err) {
      setReportError(String(err));
    } finally {
      setReportBusy(false);
    }
  }

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
      <h1>Progress dashboard</h1>
      <p className="subtitle">Student: {studentId}</p>
      <button className="secondary" onClick={onBack}>
        Back
      </button>

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
          <div className="stat-grid">
            <div className="stat">
              <span className="stat-value">{dashboard.attempts_count}</span>
              Attempts
            </div>
            <div className="stat">
              <span className="stat-value">{dashboard.time_spent_minutes.toFixed(0)}</span>
              Minutes spent
            </div>
            <div className="stat">
              <span className="stat-value">{dashboard.usage.independent_count}</span>
              Independent correct
            </div>
          </div>

          <section className="chart-section" aria-label="Mastery by skill">
            <h2>Mastery by skill</h2>
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
                  <ReferenceLine x={0.8} stroke={colors.ink} strokeDasharray="4 4" />
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
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Topic</th>
                <th>Pre</th>
                <th>Post</th>
                <th>Gain</th>
                <th>Hints</th>
                <th>Solutions</th>
                <th>Videos</th>
                <th>Review flag</th>
                <th>Skills to strengthen</th>
              </tr>
            </thead>
            <tbody>
              {history.completed_sessions.map((s) => (
                <tr key={s.learning_gain_id}>
                  <td>{new Date(s.completed_at).toLocaleDateString()}</td>
                  <td>{topicLabel(s.topic_id)}</td>
                  <td>{s.pre_raw_score}</td>
                  <td>{s.post_raw_score}</td>
                  <td>{s.raw_gain}</td>
                  <td>{s.hint_count}</td>
                  <td>{s.solution_count}</td>
                  <td>{s.video_count}</td>
                  <td>{s.tutor_review_flagged ? "⚠️" : ""}</td>
                  <td>{s.unresolved_skill_names.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h2>Blocked (attendance not confirmed)</h2>
          {history.blocked_sessions.length === 0 && <p className="dim">None.</p>}
          <ul>
            {history.blocked_sessions.map((b) => (
              <li key={`${b.week_id}-${b.blocked_at}`}>
                Week {b.week_id} — {b.blocked_reason} (
                {new Date(b.blocked_at).toLocaleDateString()})
              </li>
            ))}
          </ul>

          <h2>Skill mastery</h2>
          {history.mastery.length === 0 && <p className="dim">No mastery data yet.</p>}
          <ul>
            {history.mastery.map((m) => (
              <li key={m.skill_name}>
                {m.skill_name}: {Math.round(m.weighted_score * 100)}%
              </li>
            ))}
          </ul>

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
