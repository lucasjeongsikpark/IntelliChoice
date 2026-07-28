import { useCallback, useEffect, useState, type ReactNode } from "react";
import "./App.css";
import * as api from "./api/client";
import { useLearningSession } from "./hooks/useLearningSession";
import type { Role } from "./types";
import logoUrl from "../../../packages/ui-brand/assets/logo.png";
import { DevLoginScreen } from "./screens/DevLoginScreen";
import { StartScreen } from "./screens/StartScreen";
import { ChildSelectionScreen } from "./screens/ChildSelectionScreen";
import { TopicSelectScreen } from "./screens/TopicSelectScreen";
import { AttendanceScreen } from "./screens/AttendanceScreen";
import { ExamScreen } from "./screens/ExamScreen";
import { AssistancePanel } from "./screens/InterventionScreen";
import { ResultsScreen } from "./screens/ResultsScreen";
import { StageTransitionScreen } from "./screens/StageTransitionScreen";
import { StudentDashboardScreen } from "./screens/StudentDashboardScreen";

const TOKEN_KEY = "intellichoice.token";
const SUB_KEY = "intellichoice.sub";
const ROLE_KEY = "intellichoice.role";

type View = "session" | "dashboard";

function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [sub, setSub] = useState<string | null>(() => localStorage.getItem(SUB_KEY));
  const [role, setRole] = useState<string | null>(() => localStorage.getItem(ROLE_KEY));
  const [loginBusy, setLoginBusy] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [view, setView] = useState<View>("session");

  const session = useLearningSession(token);
  // `fetchExamOverview`/`recordItemTime` are pulled out by name rather than read off
  // `session` at the call site: the hook returns a fresh object every render, so a
  // `useCallback` depending on `session` would be re-created every render and reintroduce
  // AUD-F-01. The two functions themselves are memoized on `[token]` (useLearningSession.ts).
  const { snapshot, fetchExamOverview, recordItemTime } = session;

  const [streak, setStreak] = useState(0);
  const [counts, setCounts] = useState({ hint: 0, solution: 0, video: 0 });
  const [interventionDismissed, setInterventionDismissed] = useState(false);
  // S26: keyed by the narrative text itself (not a boolean) so a *new* narrative
  // (a different stage firing later in the same session) shows again even though an
  // earlier one was already dismissed.
  const [dismissedNarrative, setDismissedNarrative] = useState<string | null>(null);

  useEffect(() => {
    if (snapshot?.is_correct === true) setStreak((s) => s + 1);
    else if (snapshot?.is_correct === false) setStreak(0);
  }, [snapshot?.is_correct, snapshot?.learning_session_id]);

  useEffect(() => {
    if (snapshot?.intervention) {
      setInterventionDismissed(false);
      const type = snapshot.intervention.type;
      setCounts((c) => ({ ...c, [type]: c[type] + 1 }));
    }
  }, [snapshot?.intervention]);

  // AUD-F-01: `ExamScreen` lists both of these in effect dependency arrays (the overview
  // poll and the view-time autosave), so an inline arrow - a new identity on every render -
  // tears both effects down and re-runs them on every SSE snapshot. Measured before the fix,
  // with the student sitting on one question for 15 seconds and touching nothing: 899
  // `POST .../time` reports (longest 68ms) and 903 `GET .../exam/overview` against a declared
  // 20-second poll. `useLearningSession` already memoizes both on `[token]` alone, so the fix
  // is to stop re-wrapping them - see docs/DECISIONS.md D-103 §2.
  const handleFetchOverview = useCallback(() => {
    void fetchExamOverview();
  }, [fetchExamOverview]);

  async function handleLogin(chosenRole: Role, chosenSub: string) {
    setLoginBusy(true);
    setLoginError(null);
    try {
      const { token: newToken } = await api.devToken(chosenRole, chosenSub);
      localStorage.setItem(TOKEN_KEY, newToken);
      localStorage.setItem(SUB_KEY, chosenSub);
      localStorage.setItem(ROLE_KEY, chosenRole);
      setToken(newToken);
      setSub(chosenSub);
      setRole(chosenRole);
    } catch (err) {
      setLoginError(err instanceof api.ApiError ? String(err.detail) : String(err));
    } finally {
      setLoginBusy(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(SUB_KEY);
    localStorage.removeItem(ROLE_KEY);
    setToken(null);
    setSub(null);
    setRole(null);
    session.endSession();
  }

  function resetSessionUiState() {
    setStreak(0);
    setCounts({ hint: 0, solution: 0, video: 0 });
    setDismissedNarrative(null);
  }

  // Every branch below used to be a direct early return from App() itself
  // (each one a full-page element centered by #root flex). Wrapped in this
  // closure so a persistent shell (header/footer) can wrap all of them
  // without touching any branch's own logic (S22.5).
  function renderContent(): ReactNode {
    if (!token || !sub || !role) {
      return <DevLoginScreen onLogin={handleLogin} busy={loginBusy} error={loginError} />;
    }

    // A student's own dashboard is always themselves; a parent's dashboard needs a
    // student to have been resolved first (explicit selection or the child-selection
    // interrupt) - see hooks/useLearningSession.ts's docstring for the auto-select gap.
    const dashboardStudentId = role === "student" ? sub : session.studentId;

    if (view === "dashboard" && dashboardStudentId) {
      return (
        <StudentDashboardScreen
          token={token}
          studentId={dashboardStudentId}
          onBack={() => setView("session")}
        />
      );
    }

    if (!session.sessionId) {
      return (
        <StartScreen
          sub={sub}
          role={role}
          studentId={dashboardStudentId}
          busy={false}
          error={session.error}
          onStart={() => {
            resetSessionUiState();
            // `/student` must run for every role, not just "student" - it's what
            // resolves SPEC §5.6.1's role-based routing (self, auto-selected only
            // child, or the multi-child interrupt). A student passes their own id
            // (self-select); a parent passes none and lets the backend decide.
            void session.startSession().then(() => {
              void session.chooseStudent(role === "student" ? sub : undefined);
            });
          }}
          onViewDashboard={() => setView("dashboard")}
          onLogout={handleLogout}
        />
      );
    }

    if (!snapshot) {
      return (
        <div className="panel">
          <p>Connecting…</p>
        </div>
      );
    }

    const pending = snapshot.pending_interrupt;

    if (pending?.interrupt_type === "child_selection" && pending.child_candidates) {
      return (
        <ChildSelectionScreen
          candidates={pending.child_candidates}
          busy={false}
          onSelect={(studentId) =>
            void session.respond({ interrupt_type: "child_selection", student_id: studentId })
          }
        />
      );
    }

    if (snapshot.phase === "blocked" || pending?.interrupt_type === "email_approval") {
      return (
        <AttendanceScreen
          message={snapshot.message}
          pendingInterrupt={pending}
          resolved={snapshot.attendance_resolution === "absence_acknowledged"}
          busy={false}
          onAcknowledge={() => void session.resolveAttendance("acknowledge")}
          onAskBranchManager={() => void session.resolveAttendance("ask_branch_manager")}
          onApproveEmail={(approved) =>
            void session.respond({ interrupt_type: "email_approval", approved })
          }
          onBackToStart={() => {
            session.endSession();
            resetSessionUiState();
          }}
        />
      );
    }

    // S26: a personalized stage narrative interposes ahead of whatever screen the
    // current phase would otherwise show - same "gate ahead of the phase branches"
    // pattern as the intervention/ladder checks below, just earlier. Never intercepts
    // the child-selection/blocked branches above (those need immediate action) - by
    // construction, `stage_narrative` is never set before a student is resolved.
    if (snapshot.stage_narrative && snapshot.stage_narrative !== dismissedNarrative) {
      return (
        <StageTransitionScreen
          narrative={snapshot.stage_narrative}
          evidence={snapshot.stage_narrative_evidence ?? []}
          onContinue={() => setDismissedNarrative(snapshot.stage_narrative ?? null)}
        />
      );
    }

    if (snapshot.phase === "student_selected") {
      return (
        <TopicSelectScreen
          busy={false}
          error={session.error}
          onSelect={(topicId) => void session.chooseTopic(topicId)}
        />
      );
    }

    if (snapshot.phase === "completed" && snapshot.learning_gain) {
      return (
        <ResultsScreen
          gain={snapshot.learning_gain}
          hintCount={counts.hint}
          solutionCount={counts.solution}
          videoCount={counts.video}
          onDone={() => {
            session.endSession();
            resetSessionUiState();
          }}
          onViewDashboard={() => setView("dashboard")}
        />
      );
    }

    if (["pre_exam", "study", "post_exam"].includes(snapshot.phase)) {
      // S21: the graph re-pauses on `intervention_choice` after a hint below the
      // ladder's final level, so `pending` can be set again even once `snapshot.
      // intervention` already carries this round's content - both are read together.
      const ladderOpen = pending?.interrupt_type === "intervention_choice";

      const examView = (
        <ExamScreen
          phase={snapshot.phase}
          items={snapshot.items ?? null}
          streak={streak}
          overview={session.examOverview}
          busy={false}
          error={session.error}
          onSubmit={(questionVariantId, selectedOption, responseTimeMs) =>
            void session.submitAnswer(questionVariantId, selectedOption, responseTimeMs)
          }
          onSkip={(assessmentItemId) => void session.skipExamItem(assessmentItemId)}
          onFlag={(assessmentItemId, flagged) =>
            void session.flagExamItem(assessmentItemId, flagged)
          }
          onRecordTime={recordItemTime}
          onFetchOverview={handleFetchOverview}
          onFinalize={async (confirmUnanswered) =>
            (await session.finalizeExam(confirmUnanswered)) !== null
          }
        />
      );

      const assistancePanel = (
        <AssistancePanel
          intervention={snapshot.intervention ?? null}
          ladderOpen={ladderOpen}
          busy={false}
          onChoose={(choice) =>
            void session.respond({ interrupt_type: "intervention_choice", choice })
          }
          onDismiss={() => setInterventionDismissed(true)}
          questionVariantId={pending?.question_variant_id ?? null}
          onSendChatMessage={session.sendChatMessage}
        />
      );

      // The very first pause has no content yet - nothing to show alongside the exam
      // question, matching the prior standalone-chooser behavior.
      if (ladderOpen && !snapshot.intervention) {
        return assistancePanel;
      }
      if (snapshot.intervention && !interventionDismissed) {
        return (
          <div className="stack">
            {assistancePanel}
            {examView}
          </div>
        );
      }
      return examView;
    }

    if (snapshot.phase === "error") {
      return (
        <div className="panel">
          <h1>Something went wrong</h1>
          <p className="error">{snapshot.message}</p>
          <button onClick={() => session.endSession()}>Back to start</button>
        </div>
      );
    }

    return (
      <div className="panel">
        <p>Phase: {snapshot.phase}</p>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <img src={logoUrl} alt="IntelliChoice" className="app-logo" />
        <span className="app-product-name">Adaptive Learning</span>
      </header>
      <main className="app-main">{renderContent()}</main>
      <footer className="app-footer">
        <span>© IntelliChoice Inc.</span>
        <a href="https://www.intellichoice.org" target="_blank" rel="noreferrer">
          intellichoice.org
        </a>
      </footer>
    </div>
  );
}

export default App;
