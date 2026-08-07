import { useCallback, useEffect, useState, type ReactNode } from "react";
import "./App.css";
import * as api from "./api/client";
import { friendlyError } from "./api/errors";
import { useLearningSession } from "./hooks/useLearningSession";
import { useNarrativeGate } from "./hooks/useNarrativeGate";
import { useTutorChat } from "./hooks/useTutorChat";
import type { ChildCandidate, Role, SessionSnapshot, TopicOption } from "./types";
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
  // `rememberStudent`/`forgetStudent` are pulled out for the same reason - the
  // pre-session-resolution effect below lists them as dependencies.
  const { snapshot, fetchExamOverview, recordItemTime, rememberStudent, forgetStudent } = session;

  // AUD-F-22: resolve a parent's child *before* any session, so `dashboardStudentId`
  // below is non-null on the start screen and the existing dashboard button is reachable
  // without sitting through a pre → study → post cycle. One child: resolved silently.
  // Several: the existing ChildSelectionScreen is shown at login, and again on demand once
  // a child is bound (the D-184 switcher below - same screen, dismissable). `null` means the
  // lookup hasn't finished; `[]` doubles as the fetch-failure fallback, which degrades to
  // the old behavior (the in-session `child_selection` interrupt still resolves a child,
  // server-side, whenever no explicit id is passed).
  const [childCandidates, setChildCandidates] = useState<ChildCandidate[] | null>(null);
  // The switcher (D-184). Separate from `childCandidates` because "which children exist"
  // and "is the parent currently choosing between them" are different questions - after
  // AUD-F-22 the first is answered once per login and the second can be re-asked.
  const [switchingChild, setSwitchingChild] = useState(false);

  // Keyed on `[token, role]` only. It used to also bail on `session.studentId`, which meant
  // the candidate list was fetched *only* while unresolved and thrown away the moment a
  // child was bound - so there was nothing left to offer a switcher, and a refresh with a
  // child already in `sessionStorage` never fetched at all. Now the list is always
  // populated for a parent and the auto-resolve is what stays conditional. Costs one extra
  // `GET /learning/parents/me/children` per parent page load (one indexed MySQL read,
  // D-020); re-binding an already-bound single child is a same-value `setState` and a
  // no-op.
  useEffect(() => {
    if (!token || role !== "parent") return;
    let cancelled = false;
    api
      .getMyChildren(token)
      .then((children) => {
        if (cancelled) return;
        setChildCandidates(children);
        if (children.length === 1) {
          rememberStudent(children[0].student_external_id);
        }
      })
      .catch(() => {
        if (!cancelled) setChildCandidates([]);
      });
    return () => {
      cancelled = true;
    };
  }, [token, role, rememberStudent]);

  // D-187: the topic picker's contents, fetched once the session has a bound student
  // (which is exactly when the picker renders). `null` is "not loaded"; a failed fetch
  // leaves it null rather than substituting a guess, because the guess is what this
  // replaced - a stale hard-coded list is how a contentless topic gets offered.
  const [topics, setTopics] = useState<TopicOption[] | null>(null);
  // Tracked separately from `topics` because a failed fetch and an in-flight one are both
  // "no list yet" and must not look the same: leaving the screen on "Loading topics…"
  // forever is a spinner that lies about what is happening.
  const [topicsFailed, setTopicsFailed] = useState(false);
  const topicPhase = snapshot?.phase === "student_selected";
  const topicSessionId = topicPhase ? (snapshot?.learning_session_id ?? null) : null;

  useEffect(() => {
    if (!token || !topicSessionId) return;
    let cancelled = false;
    setTopicsFailed(false);
    api
      .getTopics(token, topicSessionId)
      .then((result) => {
        if (!cancelled) setTopics(result.topics);
      })
      .catch(() => {
        // No hard-coded fallback list on purpose - substituting a guess is what D-187
        // removed, and a stale guess is how a contentless topic gets offered.
        if (!cancelled) {
          setTopics(null);
          setTopicsFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token, topicSessionId]);

  const [streak, setStreak] = useState(0);
  const [counts, setCounts] = useState({ hint: 0, solution: 0, video: 0 });
  // D-207: see useTutorChat.ts. Held here rather than inside `TutorChatPanel` because
  // `AssistancePanel` unmounts that panel on every change of intervention state.
  const { reset: resetChat, ...chat } = useTutorChat();
  const [interventionDismissed, setInterventionDismissed] = useState(false);
  // AUD-F-04: both narrative gates now live in a `sessionStorage`-backed hook so they
  // survive a refresh - see useNarrativeGate.ts for why both of them had to move and why the
  // record is keyed by learning session id. The two properties they had as React state are
  // unchanged and still the reason they are shaped this way:
  //   - `dismissedNarrative` is keyed by the narrative *text* (not a boolean), so a *new*
  //     narrative (a different stage firing later in the same session) shows again even
  //     though an earlier one was already dismissed (S26).
  //   - `interactedPhase` is the phase name rather than a boolean, so it self-clears at
  //     every phase boundary (AUD-F-21). A boolean would need a reset effect, and the reset
  //     would race the narrative it is meant to gate: `nodes.py` writes `phase` and
  //     `stage_narrative` in the *same* state update, so a finalize's outro narrative
  //     arrives on the same snapshot as the new phase. Comparing against the current phase
  //     has no such ordering to get wrong.
  const {
    dismissedNarrative,
    interactedPhase,
    dismissNarrative,
    markInteracted,
    reset: resetNarrativeGate,
  } = useNarrativeGate(snapshot?.learning_session_id ?? null);

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

  async function handleLogin(chosenRole: Role, chosenSub: string, stagingSecret: string) {
    setLoginBusy(true);
    setLoginError(null);
    try {
      const { token: newToken } = await api.devToken(chosenRole, chosenSub, stagingSecret);
      localStorage.setItem(TOKEN_KEY, newToken);
      localStorage.setItem(SUB_KEY, chosenSub);
      localStorage.setItem(ROLE_KEY, chosenRole);
      setToken(newToken);
      setSub(chosenSub);
      setRole(chosenRole);
    } catch (err) {
      setLoginError(friendlyError(err));
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
    // AUD-F-22: the resolved child is login-scoped, so logout is where it is forgotten -
    // `endSession` deliberately no longer clears it (a session ending is not a change of
    // who is signed in, and clearing there is what made the dashboard button vanish).
    forgetStudent();
    setChildCandidates(null);
    setSwitchingChild(false);
  }

  function resetSessionUiState() {
    setStreak(0);
    setCounts({ hint: 0, solution: 0, video: 0 });
    resetNarrativeGate();
    // D-207: the transcript is scoped to a learning session, so it is cleared exactly
    // where the rest of the per-session UI state is - not when `TutorChatPanel` happens
    // to unmount, which is what it used to be and why it kept vanishing mid-session.
    resetChat();
  }

  // AUD-F-27: every screen below is passed `session.busy` where it used to be given a
  // hardcoded `busy={false}`. Each of them drives at least one mutation that goes through
  // the hook's `run()` serializer, and `run()` *refuses* a call that arrives while another
  // is in flight - so without this the student could issue a click the app would discard
  // while telling them it had worked. `ExamScreen` in particular already disabled every
  // control and switched its label to "Submitting…" on this prop; the wiring was the only
  // missing piece. `recordItemTime` is deliberately not gated (fire-and-forget telemetry),
  // so this does not re-open AUD-F-01.

  // AUD-F-21: called from the exam screen's three real interactions (answer, skip, flag).
  // Deliberately *not* from `onRecordTime`, which fires on view rather than on intent -
  // treating "the screen was displayed" as interaction would suppress every narrative,
  // including the ones that arrive before the student has done anything and are the whole
  // point of S26.
  const markInteraction = useCallback(() => {
    // No phase means no snapshot yet, so there is nothing the student could have interacted
    // with - previously this stored `null`, which was the same as not recording anything.
    if (snapshot?.phase) markInteracted(snapshot.phase);
  }, [snapshot?.phase, markInteracted]);

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
      // AUD-F-22: a parent's child is resolved before the start screen. While the
      // children lookup is in flight there is nothing to act on yet; once it lands, a
      // multi-child parent picks once (the same screen the in-session interrupt uses)
      // and the choice holds for the whole login. An empty list is the fetch-failure /
      // no-linked-children fallback and falls through to the start screen unresolved.
      if (role === "parent" && !session.studentId) {
        if (childCandidates === null) {
          return (
            <div className="panel">
              <p>Loading…</p>
            </div>
          );
        }
        if (childCandidates.length > 1) {
          return (
            <ChildSelectionScreen
              candidates={childCandidates}
              busy={false}
              onSelect={(studentId) => rememberStudent(studentId)}
            />
          );
        }
      }

      // D-184: the same screen again, re-opened deliberately by a parent who already has a
      // child bound. Only reachable here, with no session in flight - `bind()` refuses to
      // move an existing session to a different student (AUD-X-01, nodes.py), so switching
      // mid-session is not a thing to support but a thing to keep unreachable. Cancelling
      // leaves the current child bound, which is why this uses `onCancel` rather than
      // routing through `forgetStudent`.
      if (role === "parent" && switchingChild && childCandidates && childCandidates.length > 1) {
        return (
          <ChildSelectionScreen
            candidates={childCandidates}
            busy={false}
            title="Switch child"
            onSelect={(studentId) => {
              rememberStudent(studentId);
              setSwitchingChild(false);
            }}
            onCancel={() => setSwitchingChild(false)}
          />
        );
      }

      return (
        <StartScreen
          sub={sub}
          role={role}
          studentId={dashboardStudentId}
          busy={session.busy}
          error={session.error}
          onStart={() => {
            resetSessionUiState();
            // `/student` must run for every role, not just "student" - it's what
            // resolves SPEC §5.6.1's role-based routing (self, explicit child, or the
            // multi-child interrupt). A student passes their own id (self-select); a
            // parent passes the child resolved at login (AUD-F-22), so the in-session
            // interrupt only fires as the fallback when that resolution failed. The
            // backend re-verifies the link either way (SPEC §5.6.1).
            void session.startSession().then(() => {
              void session.chooseStudent(
                role === "student" ? sub : (session.studentId ?? undefined),
              );
            });
          }}
          onViewDashboard={() => setView("dashboard")}
          onLogout={handleLogout}
          canSwitchChild={role === "parent" && (childCandidates?.length ?? 0) > 1}
          onSwitchChild={() => setSwitchingChild(true)}
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
          busy={session.busy}
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
          busy={session.busy}
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

    // Whatever screen the current phase asks for, with no regard for the narrative. Split
    // out of `renderContent` by AUD-F-21 so a narrative can render *above* this rather
    // than instead of it - see the wrapper below. Declared after the child-selection and
    // blocked guards above so those still return before any of this, which is the
    // ordering S26 established and the narrative must not break: both of them need
    // immediate action and neither should be pushed down the page by a story.
    //
    // Takes `snapshot` as a parameter rather than closing over it: TypeScript drops the
    // `!snapshot` narrowing established above once the read happens inside a nested
    // function, and a parameter is the honest way to say "non-null by the time this runs".
    function renderPhase(snapshot: SessionSnapshot): ReactNode {
      if (snapshot.phase === "student_selected") {
        return (
          <TopicSelectScreen
            topics={topics}
            loadFailed={topicsFailed}
            busy={session.busy}
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
            busy={session.busy}
            error={session.error}
            onSubmit={(questionVariantId, selectedOption, responseTimeMs) => {
              markInteraction();
              void session.submitAnswer(questionVariantId, selectedOption, responseTimeMs);
            }}
            onSkip={(assessmentItemId) => {
              markInteraction();
              void session.skipExamItem(assessmentItemId);
            }}
            onFlag={(assessmentItemId, flagged) => {
              markInteraction();
              void session.flagExamItem(assessmentItemId, flagged);
            }}
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
            busy={session.busy}
            onChoose={(choice) =>
              void session.respond({ interrupt_type: "intervention_choice", choice })
            }
            onDismiss={() => setInterventionDismissed(true)}
            questionVariantId={pending?.question_variant_id ?? null}
            onSendChatMessage={session.sendChatMessage}
            chat={chat}
            // D-213: matched by id rather than assumed to be `items[0]`. During a retry
            // ladder the snapshot can carry the *next* item while the pause is still about
            // the previous one, and showing the wrong question next to the chat is worse
            // than showing none - the student would be asked about a problem they were
            // never given.
            questionText={
              snapshot.items?.find(
                (item) => item.question_variant_id === pending?.question_variant_id,
              )?.rendered_question ?? null
            }
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

    // AUD-F-21 (S43 continuation): the narrative renders *above* the phase screen, in the
    // same `.stack` shape the assistance panel already uses - it used to be a sibling
    // branch that returned `StageTransitionScreen` *instead of* the phase screen.
    //
    // Why that was a P1 and not a cosmetic complaint. `stage_narrative` is an LLM call, so
    // on real Bedrock it lands seconds after the student is already working (the mock
    // returns in ~26ms, which is why every local run looked fine and only staging failed).
    // Replacing the screen therefore *unmounted* `ExamScreen` mid-question, and that had
    // two measured consequences on the primary journey:
    //   - `ExamScreen`'s view-time cleanup fired early, flushing 2116ms of a 15,000ms
    //     dwell. `time_spent_minutes` is what parent reports are built from, and this is
    //     the upstream half of AUD-L-14's "0.0 minutes next to 26 attempts".
    //   - the remount re-ran `useState(0)`, so the student was returned to Question 1 with
    //     their cached batch and selections gone.
    // Rendering above keeps the screen mounted, so neither happens, and it also restores
    // `.phase-chip` to the DOM during a narrative - the absence of which is what stalled
    // the post-finalize journey wait.
    //
    // And once the student has started working in this phase, the narrative is dropped
    // rather than shown: a stage *intro* arriving after three answered questions is not
    // useful, and pushing the question down the page mid-thought is its own defect. The
    // narrative is only ever a summary of state the student can already see elsewhere, so
    // dropping one costs nothing but the Bedrock call that was already spent. Narratives
    // at real phase boundaries - the pre/post-exam outros - always show, because
    // `interactedPhase` no longer matches once `phase` has moved on.
    const narrative = snapshot.stage_narrative;
    const showNarrative =
      narrative != null && narrative !== dismissedNarrative && interactedPhase !== snapshot.phase;

    // A **Fragment with two fixed slots**, always returned, and both halves of that are
    // load-bearing (AUD-F-24 - the first version of this fix got it wrong and staging said
    // so). React reconciles children by position, so a wrapper that appears only when the
    // narrative does moves `phaseContent` from `main`'s child to `main > div`'s child, and
    // React responds by **unmounting and remounting** it. That is the same defect
    // AUD-F-21 was: the exam screen's view-time cleanup fires and `useState(0)` re-runs.
    // The first fix wrapped conditionally in `.stack` and therefore still truncated the
    // dwell on staging - 1578 ms against a 15,000 ms dwell, where the pre-fix number was
    // 2116 ms. A conditional wrapper is a remount.
    //
    // So slot 0 holds the narrative *or `null`*, and slot 1 always holds the phase content
    // at the same index either way. A Fragment rather than a `div` because `.stack` carries
    // `max-width: 480px`, which would have quietly narrowed the exam screen for the
    // duration of every narrative - and because adding no DOM node at all means the
    // no-narrative render is identical to what shipped before this change.
    const phaseContent = renderPhase(snapshot);
    return (
      <>
        {showNarrative ? (
          <StageTransitionScreen
            narrative={narrative}
            evidence={snapshot.stage_narrative_evidence ?? []}
            onContinue={() => dismissNarrative(narrative)}
          />
        ) : null}
        {phaseContent}
      </>
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
