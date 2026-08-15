import type { FigureSpec } from "./components/QuestionFigure";

// Mirrors the Pydantic response/request models in
// apps/learning-api/src/learning_api/routers/{sessions,students}.py and main.py's
// DevTokenRequest/Response. Kept as plain hand-written types (no codegen) - the backend
// is the source of truth; update both sides together when a shape changes.

export type Role = "student" | "parent" | "tutor" | "branch_manager";

export interface ChildCandidate {
  student_external_id: string;
  display_name: string;
  grade: string;
  branch_name: string;
}

/**
 * D-187: what the *backend* says may be studied, replacing the hard-coded `available`
 * flags this file's sibling `topics.ts` used to carry. `available` means the template bank
 * can build an exam right now; `recommended_for_grade` is §5.7.3's grade candidate and is
 * only ever true when `available` is too.
 */
export interface TopicOption {
  topic_id: string;
  name: string;
  grade_band: string;
  available: boolean;
  recommended_for_grade: boolean;
}

export interface EmailPreview {
  recipient: string;
  subject: string;
  body: string;
}

export interface PendingInterrupt {
  interrupt_type: "child_selection" | "email_approval" | "intervention_choice";
  child_candidates?: ChildCandidate[] | null;
  email_preview?: EmailPreview | null;
  question_variant_id?: string | null;
}

export interface QuestionItem {
  figure_spec?: FigureSpec | null;
  question_variant_id: string;
  display_order: number;
  rendered_question: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
}

/**
 * D-272: the question the current hint/solution/video/chat is about, sent by the server
 * alongside the help itself (`routers/sessions.py`'s `AssistanceQuestionResponse`).
 *
 * `items` could not answer this. At the intervention menu it is `null` (the incorrect-answer
 * turn serves no new item), and once the ladder closes it is the *next* question - so the
 * study screen had nothing correct to put on the left and collapsed to a single narrow panel.
 * This field is bound to the attempt the help was generated for, so the pairing cannot drift.
 *
 * `selected_option` is what the student actually picked, shown back to them on the locked card.
 */
export interface AssistanceQuestion {
  figure_spec?: FigureSpec | null;
  question_variant_id: string;
  rendered_question: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  selected_option?: string | null;
}

/**
 * D-272: how far through the study phase the student is.
 *
 * Two bounded counters, because only one honest denominator exists. The *question* total is
 * genuinely unknown until the session ends - the retry ladder adds items as they are needed -
 * but `target_skill_ids` is fixed at plan time, so "skill 3 of 5" is a fact and "try 2 of 4"
 * is another. See `services/study_progress.py`.
 */
export interface StudyProgress {
  skills_total: number;
  skills_resolved: number;
  current_skill_name?: string | null;
  current_skill_position?: number | null;
  attempt_in_line: number;
  max_attempts: number;
}

export interface LearningGain {
  pre_raw_score: number;
  post_raw_score: number;
  raw_gain: number;
  weighted_gain: number;
  normalized_gain: number | null;
  normalized_gain_status: string | null;
  skill_level_gain: Record<string, unknown>;
  difficulty_transition: Record<string, unknown>;
  independent_correct_rate: number;
  hint_dependency: number;
  solution_dependency: number;
  unresolved_skills: string[];
  response_time_change_ms: number;
}

export interface SolutionStep {
  step_number: number;
  explanation: string;
  expression: string;
  common_mistake?: string | null;
}

export interface InterventionContent {
  type: "hint" | "solution" | "video";
  hint_text?: string | null;
  concept_reminder?: string | null;
  next_step_prompt?: string | null;
  answer_revealed?: boolean | null;
  difficulty?: number | null;
  // S21 within-question hint ladder position ("hint 2 of 3"), set on type "hint" only.
  hint_level?: number | null;
  max_hint_level?: number | null;
  steps?: SolutionStep[] | null;
  final_answer?: string | null;
  message?: string | null;
  video_title?: string | null;
  video_url?: string | null;
  video_source?: string | null;
}

// The shape shared by every action response and the SSE stream (see
// `routers/sessions.py`'s `SessionSnapshotEvent`) - one canonical "where is this
// session right now" view.
export interface SessionSnapshot {
  event?: "session_update";
  learning_session_id: string;
  phase: string;
  message?: string | null;
  is_correct?: boolean | null;
  items?: QuestionItem[] | null;
  learning_gain?: LearningGain | null;
  pending_interrupt?: PendingInterrupt | null;
  intervention?: InterventionContent | null;
  // D-272: present exactly when this snapshot carries help - an `intervention_choice`
  // pause or an `intervention`. See `AssistanceQuestion`.
  assistance_question?: AssistanceQuestion | null;
  // D-272: present on every study-phase snapshot, absent everywhere else.
  study_progress?: StudyProgress | null;
  // SPEC §5.6.5: "absence_acknowledged" is terminal (session ended, nothing more to
  // do); "email_requested" still allows trying a different choice next; `null`/absent
  // means the gate just blocked and no choice has been made yet.
  attendance_resolution?: string | null;
  // S26: a personalized narrative for the stage the session just entered/left
  // (pre_intro/pre_outro/study_step/study_outro/post_outro) - shown by
  // `StageTransitionScreen`, cleared client-side once the student continues past it.
  stage_narrative?: string | null;
  // Plain-language "How we personalized this" lines accompanying stage_narrative.
  stage_narrative_evidence?: string[] | null;
  // U3/D-325: which of the five narrative moments produced the text - `pre_intro`,
  // `pre_outro`, `study_step`, `study_outro`, `post_outro`. Optional both ways: an older
  // server never sends it, and the header falls back to a stage-neutral wording rather than
  // claiming a stage it was not told.
  stage_narrative_stage?: string | null;
}

// Mirrors `routers/sessions.py`'s `ExamItemStatusResponse`/`ExamOverviewResponse` (S23).
// `display_order` is the join key against a locally-cached `QuestionItem[]` batch (both
// shapes already carry it) - the overview endpoint deliberately doesn't re-send question
// content, since the client already has it from the phase-entry batch fetch.
export interface ExamItemStatus {
  assessment_item_id: string;
  question_variant_id: string;
  display_order: number;
  status: "unseen" | "answered" | "skipped" | "flagged";
  difficulty: number;
  time_spent_ms: number;
}

export interface ExamOverview {
  learning_session_id: string;
  phase: string;
  items: ExamItemStatus[];
  remaining_seconds: number | null;
}

export interface CompletedSessionSummary {
  learning_gain_id: string;
  topic_id: string | null;
  pre_raw_score: number;
  post_raw_score: number;
  raw_gain: number;
  weighted_gain: number;
  normalized_gain: number | null;
  normalized_gain_status: string | null;
  unresolved_skill_names: string[];
  hint_count: number;
  solution_count: number;
  video_count: number;
  tutor_review_flagged: boolean;
  completed_at: string;
}

export interface BlockedSessionSummary {
  week_id: string;
  blocked_reason: string;
  blocked_at: string;
}

export interface ProblemReportSummary {
  question_template_id: string;
  report_type: string;
  status: string;
  created_at: string;
}

export interface MasterySummary {
  skill_name: string;
  weighted_score: number;
  recommended_difficulty: number | null;
}

export interface StudentHistory {
  student_external_id: string;
  completed_sessions: CompletedSessionSummary[];
  blocked_sessions: BlockedSessionSummary[];
  problem_reports: ProblemReportSummary[];
  mastery: MasterySummary[];
}

// S28 (SPEC §5.14.2-§5.14.4, plan §18-L9) - mirrors routers/students.py's dashboard/
// report response models.

export interface MasterySkillPoint {
  skill_name: string;
  weighted_score: number;
  target_band: number;
}

export interface PrePostSkillPoint {
  skill_name: string;
  pre_accuracy: number;
  post_accuracy: number;
}

export interface GainPoint {
  date: string;
  raw_gain: number;
  weighted_gain: number;
}

export interface AccuracyPoint {
  date: string;
  accuracy: number;
  attempts: number;
}

export interface DifficultyPoint {
  date: string;
  skill_name: string;
  difficulty: number;
}

export interface UsageBreakdown {
  hint_count: number;
  solution_count: number;
  video_count: number;
  independent_count: number;
  total_attempts: number;
}

export interface DashboardData {
  student_external_id: string;
  mastery_by_skill: MasterySkillPoint[];
  pre_post_by_skill: PrePostSkillPoint[];
  gains_over_time: GainPoint[];
  accuracy_trend: AccuracyPoint[];
  difficulty_progression: DifficultyPoint[];
  usage: UsageBreakdown;
  attempts_count: number;
  time_spent_minutes: number;
  // AUD-L-15: the date-range picker on this screen does not apply to every chart.
  // The server sends each caption so the wording cannot drift from the computation.
  mastery_window_label: string;
  pre_post_window_label: string;
  // D-324: the IANA zone every date on this payload must be *displayed* in. Served rather
  // than held here, so `ORG_TIMEZONE` stays one switch for both apps and this cannot skew
  // from the zone the server buckets by. Optional because a client can meet an older
  // server mid-deploy; the render then falls back to `UTC`, matching the server's own
  // default. Deliberately **not** a hard-coded `America/Chicago` fallback: a second copy
  // of the zone in the client is the skew this field exists to remove, and UTC is an
  // honest "not told" rather than a claim about the org. Either way the label no longer
  // depends on where the *viewer* is, which is the defect being fixed.
  org_time_zone?: string;
}

export interface StudentReport {
  audience: Role;
  interpretation_text: string;
  recommendations_text: string;
  generated: boolean;
  verified_facts: Record<string, unknown>;
  created_at: string;
}

/** U4/D-338: `GET /learning/sessions/{id}/results` - a completed cycle, readable by id. */
export interface SessionResults {
  learning_session_id: string;
  topic_id: string | null;
  learning_gain: LearningGain;
  hint_count: number;
  solution_count: number;
  video_count: number;
  completed_at: string;
}
