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
  question_variant_id: string;
  display_order: number;
  rendered_question: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
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
}

export interface StudentReport {
  audience: Role;
  interpretation_text: string;
  recommendations_text: string;
  generated: boolean;
  verified_facts: Record<string, unknown>;
  created_at: string;
}
