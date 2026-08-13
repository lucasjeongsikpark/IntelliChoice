import { useCallback, useEffect, useState, type ReactNode } from "react";
import "./App.css";
import * as api from "./api/client";
import { friendlyError } from "./api/errors";
import { useLearningSession } from "./hooks/useLearningSession";
import { useAssistanceCounts } from "./hooks/useAssistanceCounts";
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
import { JourneyBar } from "./components/JourneyBar";

// The phases the journey bar describes. Anything else (login, topic select, blocked,
// error) has no journey to show and gets `null` in the slot - a permanent slot either way,
// for the reconcile-by-position reason the narrative and stream banner already document.
const JOURNEY_PHASES = ["pre_exam", "study", "post_exam", "completed"];

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

  // `sub` is passed so the hook can drop a `sessionStorage` session belonging to a previous
  // sign-in in this tab - see `clearSessionIfOwnedByAnotherSubject`.
  const session = useLearningSession(token, sub);
  // `fetchExamOverview`/`recordItemTime` are pulled out by name rather than read off
  // `session` at the call site: the hook returns a fresh object every render, so a
  // `useCallback` depending on `session` would be re-created every render and reintroduce
  // AUD-F-01. The two functions themselves are memoized on `[token]` (useLearningSession.ts).
  // `rememberStudent`/`forgetStudent` are pulled out for the same reason - the
  // pre-session-resolution effect below lists them as dependencies.
  // `markExamViewed` joins them for the same reason: `ExamScreen` lists it in an effect's
  // dependency array (D-218), and it is memoized on `[token]` in the hook.
  const {
    snapshot,
    fetchExamOverview,
    recordItemTime,
    rememberStudent,
    forgetStudent,
    markExamViewed,
  } = session;

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
  // Persisted per learning session rather than held in React state: a mid-session refresh
  // used to zero these, and the results screen then under-reported how much help the student
  // took while the study-outro narrative - computed server-side - reported the real numbers.
  // See useAssistanceCounts.ts.
  const {
    counts,
    record: recordAssistance,
    reset: resetAssistanceCounts,
  } = useAssistanceCounts(snapshot?.learning_session_id ?? null);
  // D-207: see useTutorChat.ts. Held here rather than inside `TutorChatPanel` because
  // `AssistancePanel` unmounts that panel on every change of intervention state.
  // D-217: scoped to the question the current pause is about, so each question gets its own
  // conversation. `pending_interrupt.question_variant_id` is the same id the chat sends with.
  const { reset: resetChat, ...chat } = useTutorChat(
    snapshot?.pending_interrupt?.question_variant_id ?? null,
  );
  const [interventionDismissed, setInterventionDismissed] = useState(false);
  // D-217's `lastStudyQuestionRef` is gone (D-272). It was a render-time cache of the last
  // study question the client had seen, kept because the intervention snapshots did not
  // carry one - a guess at something the server knew. `snapshot.assistance_question` is
  // that answer, so the guess and its staleness rules are deleted rather than tuned.
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

  // D-216: this effect used to also drive `recordAssistance` and the streak, and both
  // were wrong in the same way - snapshots are not one-per-event. Every action arrives
  // twice (the REST response and its own SSE echo, two distinct parses of the same
  // content), so an object-identity dependency fired twice per hint and the counter
  // this hook exists to keep truthful double-counted; while `is_correct` is a primitive,
  // so two *consecutive* correct answers changed nothing and the streak never passed 1.
  // Both now update at the action site (`onSubmit`/`onChoose` below), which runs exactly
  // once per student action. Un-dismissing on new content is all that legitimately keys
  // off the snapshot.
  useEffect(() => {
    if (snapshot?.intervention) {
      setInterventionDismissed(false);
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
    // D-216: logout previously left the per-session UI state (streak, assistance counts,
    // narrative gate, chat transcript) and the dashboard view behind, so the *next*
    // sign-in on this tab could land straight on a dashboard with someone else's leftovers.
    resetSessionUiState();
    setView("session");
  }

  function resetSessionUiState() {
    setStreak(0);
    resetAssistanceCounts();
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

    // The child's name, for screens a *parent* reads. The candidate list is already fetched
    // for the selection screen, so this is a lookup rather than a request. `null` for a
    // student looking at their own dashboard - they do not need to be told who they are -
    // and `null` while the list is still in flight, which the screens fall back from.
    //
    // Only ever passed to a component that renders it. Names live in MySQL and stay there
    // (CLAUDE.md #1): nothing here writes one to Postgres, a log, or an LLM payload.
    const dashboardStudentName =
      role === "parent"
        ? (childCandidates?.find((c) => c.student_external_id === dashboardStudentId)
            ?.display_name ?? null)
        : null;

    if (view === "dashboard" && dashboardStudentId) {
      return (
        <StudentDashboardScreen
          token={token}
          studentId={dashboardStudentId}
          studentName={dashboardStudentName}
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
          studentName={dashboardStudentName}
        />
      );
    }

    if (!snapshot) {
      // A stream that errors before the first snapshot ever arrives used to leave this
      // screen showing "Connecting…" indefinitely, across reloads, with no way out. That
      // was measured on staging: the stream 403'd and the student saw a spinner sentence
      // forever. `EventSource` does not retry a non-2xx at all, so this is terminal, not
      // slow - and the only honest thing to show is that it failed plus a way to start over.
      if (session.streamState === "error") {
        return (
          <div className="panel">
            <h1>We lost the connection</h1>
            <p>
              Your session could not be reopened. Starting fresh will not lose any work you
              have already submitted.
            </p>
            <button
              onClick={() => {
                session.endSession();
                resetSessionUiState();
              }}
            >
              Back to start
            </button>
          </div>
        );
      }
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
          error={session.error}
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
    // `overlayOpen` is `showNarrative`, computed below and passed in for the same reason
    // `snapshot` is a parameter rather than a closure read: the value it needs is declared
    // after this function and only correct at call time (D-218).
    function renderPhase(snapshot: SessionSnapshot, overlayOpen: boolean): ReactNode {
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

        // D-272: "is there help on screen right now". The server sends
        // `assistance_question` on exactly the snapshots that carry help, so this one flag
        // decides both columns and they cannot disagree.
        //
        // It replaces `ladderOpen` as the layout condition, and that is the whole fix.
        // `ladderOpen` means "the graph is paused", which stops being true at hint 3 of 3
        // and at every solution and video - so the layout collapsed to a lone narrow panel
        // exactly when the student had the most to read. Reproduced locally 2026-08-10.
        const assistanceQuestion = snapshot.assistance_question ?? null;
        const helpOnScreen =
          snapshot.phase === "study" &&
          assistanceQuestion !== null &&
          (ladderOpen || (snapshot.intervention != null && !interventionDismissed));

        const examView = (
          <ExamScreen
            phase={snapshot.phase}
            items={snapshot.items ?? null}
            streak={streak}
            overview={session.examOverview}
            busy={session.busy}
            // D-272: non-null exactly while help is on screen, and then this column shows
            // that question locked instead of the live one. No separate "paused" flag - the
            // question being there *is* the pause, and one source beats two that can drift.
            assistanceQuestion={helpOnScreen ? assistanceQuestion : null}
            overlayOpen={overlayOpen}
            error={session.error}
            onSubmit={(questionVariantId, selectedOption, responseTimeMs) => {
              markInteraction();
              // The streak advances here, once per submission, rather than in a
              // snapshot effect - `is_correct` is masked (null) during exams, so only
              // study answers move it, matching where the chip renders.
              void session
                .submitAnswer(questionVariantId, selectedOption, responseTimeMs)
                .then((result) => {
                  if (result?.is_correct === true) setStreak((s) => s + 1);
                  else if (result?.is_correct === false) setStreak(0);
                });
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
            onExamViewed={markExamViewed}
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
            error={session.error}
            onChoose={(choice) =>
              // Counted on the click that succeeded, not on the snapshot that followed -
              // snapshots arrive twice per action (REST + SSE echo) and double-counted
              // the exact metric `useAssistanceCounts` was built to keep truthful.
              // "continue" is declining help, so it is not a support use.
              void session
                .respond({ interrupt_type: "intervention_choice", choice })
                .then((result) => {
                  if (result === null || choice === "continue") return;
                  // A "video" that found no catalog entry served nothing, and counting it
                  // put "Videos suggested: 1" on the results screen and in the parent
                  // report for a student who was shown only the §5.11.6 "not currently
                  // available" message. The server stopped recording it too (`nodes.
                  // _intervention_served`); this is the same predicate on the copy of the
                  // count the student actually reads. Keyed on the video's presence, not
                  // on the message text, for the same reason the server's is.
                  const help = result.intervention;
                  const served = help?.type !== "video" || Boolean(help?.video_url);
                  if (served) recordAssistance(choice);
                })
            }
            onDismiss={() => setInterventionDismissed(true)}
            // D-272: the *question's* variant id, not the pause's. `pending
            // .question_variant_id` is absent on a `/respond`-resumed ladder round (S21's
            // documented gap), and since this prop is what decides whether the tutor chat
            // renders at all, the chat silently disappeared for every round after the first
            // - confirmed locally 2026-08-10: present on the chooser, gone from hint 1
            // onward. `assistance_question` is set on every one of those rounds.
            questionVariantId={assistanceQuestion?.question_variant_id ?? null}
            onSendChatMessage={session.sendChatMessage}
            chat={chat}
          />
        );

        // Pre/post-exam never have assistance alongside - render the exam full-width.
        if (snapshot.phase !== "study") {
          return examView;
        }

        // D-272: two columns for the *whole* time help is on screen - the chooser, every
        // hint rung, the solution, the video and the chat - with the question the help is
        // about on the left and the help on the right, both full size.
        //
        // The condition used to be `ladderOpen`, which is "the graph is paused". That is
        // false at hint 3 of 3 and for every solution and video, so the layout collapsed to
        // one narrow centred card with no question next to it. D-217's comment here was
        // right that `snapshot.items` had by then moved on to the *next* question and must
        // not be paired with this help - the answer was never to drop the question, it was
        // for the server to say which question the help belongs to. It now does.
        if (helpOnScreen) {
          return (
            <div className="study-columns">
              {examView}
              {assistancePanel}
            </div>
          );
        }
        return examView;
      }

      if (snapshot.phase === "error") {
        // No `snapshot.message` here, deliberately (D-216): error transitions write
        // `last_error` - internals like "attendance check failed: ..." - and `message`
        // maps `last_message`, so this rendered an *empty* error line in front of a
        // student. Fixed copy instead; the raw detail belongs in logs, not on screen.
        return (
          <div className="panel">
            <h1>Something went wrong</h1>
            <p>
              This session hit a problem on our side and cannot continue. Everything you
              already finished is saved, and starting again is safe.
            </p>
            <button
              onClick={() => {
                session.endSession();
                resetSessionUiState();
              }}
            >
              Back to start
            </button>
          </div>
        );
      }

      // Every phase this app knows how to draw is handled above, so reaching here means a
      // transitional or unrecognised one. It used to render `Phase: {snapshot.phase}` - the
      // raw graph enum, in front of a K-12 student. Seen on staging 2026-08-07 as
      // "Phase: created" for the two-odd seconds between starting a session and the topic
      // screen appearing, which is the most common way a student meets this branch.
      //
      // The phase is kept for whoever is debugging, in a `title` the UI never speaks.
      //
      // D-216: the exit exists because this branch is also where an *unrecognised* phase
      // lands, and that used to be a panel with zero controls - a student stranded on it
      // (e.g. `awaiting_child_selection` whose candidates never arrived) had no action
      // but a reload. During a normal start it shows for ~2s; the button is harmless
      // there, and starting over from it loses nothing.
      return (
        <div className="panel" title={`phase: ${snapshot.phase}`}>
          <p>Getting your session ready…</p>
          <button
            onClick={() => {
              session.endSession();
              resetSessionUiState();
            }}
          >
            Back to start
          </button>
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
    const phaseContent = renderPhase(snapshot, showNarrative);
    // D-216: once a snapshot exists, a dead stream used to be *invisible* - the recovery
    // screen above sits inside `if (!snapshot)`, so the last snapshot stayed on screen,
    // stale, with no signal and no way back. REST actions still work in that state (they
    // set the snapshot directly), so this is a banner rather than a takeover; "error"
    // rather than "connecting" because `EventSource` retries transient drops on its own
    // and only a terminal failure (an expired token, a 403) needs the student's hand.
    // A permanent slot (banner or null) for the same reconcile-by-position reason as the
    // narrative below.
    const streamBanner =
      session.streamState === "error" ? (
        <div className="panel stream-banner" role="alert">
          <p>Live updates are disconnected — what you see here may be out of date.</p>
          <button onClick={session.reconnectStream}>Reconnect</button>
        </div>
      ) : null;
    // D-272: a permanent slot, like the two below it. A conditional wrapper here would
    // remount the phase screen on every phase change (AUD-F-24), which is the defect this
    // file already carries two comments about.
    const journey = JOURNEY_PHASES.includes(snapshot.phase) ? (
      <div className={`journey-slot ${snapshot.phase === "study" ? "wide" : ""}`}>
        <JourneyBar phase={snapshot.phase} progress={snapshot.study_progress} />
      </div>
    ) : null;
    return (
      <>
        {streamBanner}
        {journey}
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
