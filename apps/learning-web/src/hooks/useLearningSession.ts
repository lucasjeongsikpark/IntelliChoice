import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../api/client";
import { friendlyError, isSignedOut } from "../api/errors";
import { openSessionStream } from "../api/stream";
import type { RespondBody } from "../api/client";
import type { ExamOverview, SessionSnapshot } from "../types";

const SESSION_ID_KEY = "intellichoice.learning_session_id";
const STUDENT_ID_KEY = "intellichoice.selected_student_id";
const OWNER_KEY = "intellichoice.session_owner_sub";

/**
 * Where an in-flight session lives: `localStorage`, so it outlives the tab (D-381).
 *
 * **This was `sessionStorage`, and closing the tab silently abandoned the session.** Measured
 * live 2026-08-16: a student completed the 10-question pre-exam, reached the study phase,
 * closed the tab, signed back in, and got the topic chooser and the first-time narrative -
 * *"Welcome to math practice! You're starting an exciting journey…"*. The work was not lost,
 * it was **unreachable**: writing the old id back by hand resumed at Skill 2 of 4 instantly.
 * `POST /learning/sessions` always mints a new thread and no endpoint answers "which session
 * is this student part-way through", so the id in this browser is the only handle that
 * exists. A tab close, a browser restart, a crash or a low-memory tab eviction all lose it -
 * and a K-12 student on a shared classroom device does all four.
 *
 * The reason `sessionStorage` was originally chosen - a shared branch device restoring the
 * previous student's session - is already handled by `clearSessionIfOwnedByAnotherSubject`
 * below, which compares the stored owner against the signed-in sub before any render sees the
 * id. That guard was written as belt-and-braces for a per-tab store; it is now the actual
 * mechanism, which is why it runs in the state initialisers rather than an effect.
 *
 * The other consequence is deliberate: two tabs now share one session rather than starting
 * two. That is the better failure - concurrent turns are serialised by the per-thread advisory
 * lock (D-374) into a readable 409, whereas two independent sessions for one student produce
 * two exams and one of them is thrown away.
 */
const sessionStore: Pick<Storage, "getItem" | "setItem" | "removeItem"> = localStorage;

/**
 * Drop a stored session that belongs to somebody else, before anything reads it.
 *
 * Found on staging 2026-08-07 by signing in as one fixture student and then another in the
 * same tab. Identity lives in `localStorage` and this session state lives in
 * `sessionStorage`; sign-in replaced only the former, so the app restored the *previous*
 * student's `learning_session_id` and opened the stream against it. The server refused
 * correctly - `403 "Students may only access their own records"`, fail-closed working as
 * designed - and the client had no handler, so the app sat on "Connecting…" forever and
 * survived every reload. On a branch's shared device that is a permanent wedge for the next
 * student to sit down.
 *
 * Recording the owner is what prevents it, and since D-381 that is load-bearing rather than
 * belt-and-braces: these keys live in `localStorage` now (see `sessionStore`), so they outlive
 * the tab and this comparison is the *only* thing standing between the next student to sit
 * down and the previous one's session. Runs in the hook's state initializers rather than in an
 * effect so no render ever sees the other student's id; the effect beside `endSession` covers
 * the other case, an identity change with no remount.
 */
function clearSessionIfOwnedByAnotherSubject(sub: string | null): void {
  const owner = sessionStore.getItem(OWNER_KEY);
  if (sub !== null && owner === sub) return;
  // **Nobody signed in is not somebody else** (D-381). `sub === null` is the login screen,
  // which is exactly where a student sits after a token expiry - and `handleSignedOut`
  // deliberately keeps the session so signing back in resumes the same question (D-375).
  // Clearing here broke that promise for anyone who reloaded before signing back in, because
  // this function ran with `sub === null`, matched neither early return, and binned a session
  // whose owner had not changed at all. Harmless-looking while the id died with the tab
  // anyway; load-bearing now that it does not. The decision is simply deferred: the next
  // sign-in supplies a real `sub` and this comparison runs properly then.
  if (sub === null) return;
  if (owner === null && sessionStore.getItem(SESSION_ID_KEY) === null) return;
  sessionStore.removeItem(SESSION_ID_KEY);
  sessionStore.removeItem(STUDENT_ID_KEY);
  sessionStore.removeItem(OWNER_KEY);
}

// The whole point of persisting `sessionId` is SPEC Phase 11's "Done when": a page refresh
// must restore exact position. On mount, if a session id is already stored, opening the SSE
// stream alone restores the snapshot - no replay of prior actions needed, since
// `/stream` reads the live LangGraph checkpoint on connect (see D-032). D-381 widened
// "refresh" to "this browser": see `sessionStore` for why a tab close was losing sessions
// that the server had kept all along.
export function useLearningSession(
  token: string | null,
  sub: string | null,
  onSignedOut?: () => void,
) {
  const [sessionId, setSessionId] = useState<string | null>(() => {
    clearSessionIfOwnedByAnotherSubject(sub);
    return sessionStore.getItem(SESSION_ID_KEY);
  });
  const [studentId, setStudentId] = useState<string | null>(() =>
    sessionStore.getItem(STUDENT_ID_KEY),
  );
  // S26 (found via live verification): the checkpoint doesn't exist until
  // `resolve_student` runs (the `/student` call `chooseStudent` makes) - connecting
  // the SSE stream any earlier than that races `/stream` ahead of the checkpoint's
  // first-ever write and 404s. Unlike a drop after a successful connect, `EventSource`
  // does not retry a non-2xx response at all, so a fresh session start would otherwise
  // silently never receive a single live push for that tab's lifetime (every REST
  // action still works and updates `snapshot` directly - only SSE-only content like
  // S26's `pre_intro` narrative was affected). A `sessionId` restored from
  // `sessionStorage` (a page refresh) always has an already-resolved checkpoint behind
  // it, so it starts ready.
  const [checkpointReady, setCheckpointReady] = useState<boolean>(() => sessionId !== null);
  const [snapshot, setSnapshot] = useState<SessionSnapshot | null>(null);
  const [streamState, setStreamState] = useState<"connecting" | "open" | "error">("connecting");
  const [error, setError] = useState<string | null>(null);
  // AUD-F-27: the ref is what `run()` reads synchronously (state would be a render behind,
  // so two clicks in the same tick would both pass the guard); the state is what the UI
  // reads. Both, because they answer different questions - "may this call proceed" and
  // "should the controls be disabled" - and the second one had no answer at all before,
  // which is how the guard came to silently discard the student's work.
  const busyRef = useRef(false);
  const [busy, setBusy] = useState(false);

  // D-375: held in a ref so `run` can stay dependency-free. `run` is memoised with `[]` and
  // is captured by every action callback in this file; adding `onSignedOut` to its deps
  // would rebuild all of them on each render of `App`.
  const signedOutRef = useRef(onSignedOut);
  useEffect(() => {
    signedOutRef.current = onSignedOut;
  }, [onSignedOut]);

  // Action callbacks read `sessionId` through this ref, not the `sessionId` state
  // variable directly - a caller that chains `startSession().then(() => chooseStudent())`
  // invokes `chooseStudent` from a closure created *before* `setSessionId` from
  // `startSession` has re-rendered the component, so the closed-over `sessionId` state
  // would still be `null` there (a stale-closure bug that silently no-op'd
  // `chooseStudent` in practice). The ref always holds the current value.
  const sessionIdRef = useRef(sessionId);
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  // D-216: bumping this re-runs the stream effect, giving a dead stream a manual way
  // back. `EventSource` auto-reconnects only after a *successful* connection drops; a
  // non-2xx response (an expired token, a 403) is terminal, and before this the app had
  // no path to a fresh connection short of a full reload.
  const [streamNonce, setStreamNonce] = useState(0);
  const reconnectStream = useCallback(() => setStreamNonce((n) => n + 1), []);

  useEffect(() => {
    void streamNonce; // dependency-only: a bump means "tear down and reconnect"
    if (!token || !sessionId || !checkpointReady) return;
    setStreamState("connecting");
    const close = openSessionStream(
      sessionId,
      token,
      (snap) => setSnapshot(snap),
      (state) => setStreamState(state),
    );
    return close;
  }, [token, sessionId, checkpointReady, streamNonce]);

  // AUD-F-22: the resolved student is *login-scoped* identity, not session state - it is
  // set at login (App.tsx's pre-session resolution) or by an explicit selection, survives
  // `endSession` (so the start screen's dashboard button does not vanish when a session
  // ends - the finding's "backing out does not help"), and is forgotten only on logout.
  const rememberStudent = useCallback((id: string) => {
    sessionStore.setItem(STUDENT_ID_KEY, id);
    setStudentId(id);
  }, []);

  const forgetStudent = useCallback(() => {
    sessionStore.removeItem(STUDENT_ID_KEY);
    setStudentId(null);
  }, []);

  /**
   * Serializes mutations, and - AUD-F-27 - says so instead of pretending it didn't happen.
   *
   * The bare `return null` this replaced was silent: no request, no error, no retry. On
   * staging, where a `POST /answers` takes ~200-400ms rather than the local ~1ms, that
   * discarded **8 of 10 answers and the finalize** in a single measured run while
   * `ExamScreen` had already advanced the question and displayed "Answer submitted for
   * question N". A lost answer is scored incorrect, which corrupts the pre-exam score, the
   * learning gain computed from it, and the parent report built on that.
   *
   * Two changes, and the second one is the real fix: the drop now surfaces an error, and
   * `busy` is exposed as state so the controls can be disabled and the second click never
   * happens. `ExamScreen` already accepted a `busy` prop and disabled every control on it -
   * `App.tsx` had simply passed `busy={false}` everywhere, so the intended design was
   * present and unreachable.
   *
   * Deliberately still *not* a queue: an answer that arrives after a finalize has nowhere
   * valid to land (that is AUD-F-02's 409), so serializing-and-refusing is the honest
   * behaviour. `recordItemTime` stays outside this guard - it is fire-and-forget telemetry
   * and gating it would be the AUD-F-01 problem again.
   */
  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | null> => {
    if (busyRef.current) {
      setError("Still saving your last action — give it a moment and try again.");
      return null;
    }
    busyRef.current = true;
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (err) {
      // D-207: the API's wire text is not a student-facing message. See api/errors.ts -
      // this used to print things like "question variant 3f2a… is not an item of this
      // session" to a child, measured live on staging.
      setError(friendlyError(err));
      // D-375: a 401 must clear the stored token, and this is the only place that can.
      // Nothing acted on 401 before - the friendly message said "Sign in again to keep
      // going" while no screen in the app offered a sign-in, and the dead token stayed in
      // `localStorage` so even a reload skipped the login screen. See `App.handleSignedOut`.
      if (isSignedOut(err)) signedOutRef.current?.();
      return null;
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }, []);

  const startSession = useCallback(async () => {
    if (!token) return null;
    return run(async () => {
      const snap = await api.createSession(token);
      sessionStore.setItem(SESSION_ID_KEY, snap.learning_session_id);
      // Stamped with the session, never separately, so the pair cannot drift.
      if (sub !== null) sessionStore.setItem(OWNER_KEY, sub);
      sessionIdRef.current = snap.learning_session_id;
      setSessionId(snap.learning_session_id);
      // A brand-new session's checkpoint doesn't exist until `chooseStudent` below
      // runs `resolve_student` - see this hook's `checkpointReady` docstring.
      setCheckpointReady(false);
      setSnapshot(snap);
      return snap;
    });
  }, [token, sub, run]);

  const chooseStudent = useCallback(
    async (explicitStudentId?: string) => {
      const sid = sessionIdRef.current;
      if (!token || !sid) return null;
      return run(async () => {
        const snap = await api.selectStudent(token, sid, explicitStudentId);
        if (explicitStudentId) rememberStudent(explicitStudentId);
        // `resolve_student` has now run at least once - the checkpoint is guaranteed
        // to exist, so it's now safe to open the SSE stream.
        setCheckpointReady(true);
        setSnapshot(snap);
        return snap;
      });
    },
    [token, run, rememberStudent],
  );

  const chooseTopic = useCallback(
    async (topicId: string) => {
      const sid = sessionIdRef.current;
      if (!token || !sid) return null;
      return run(async () => {
        const snap = await api.selectTopic(token, sid, topicId);
        setSnapshot(snap);
        return snap;
      });
    },
    [token, run],
  );

  const resolveAttendance = useCallback(
    async (choice: "acknowledge" | "ask_branch_manager") => {
      const sid = sessionIdRef.current;
      if (!token || !sid) return null;
      return run(async () => {
        const snap = await api.resolveAttendance(token, sid, choice);
        setSnapshot(snap);
        return snap;
      });
    },
    [token, run],
  );

  const [examOverview, setExamOverview] = useState<ExamOverview | null>(null);

  // Read-only, deliberately outside the `run()` busy gate - the nav bar polls this
  // frequently (on mount, after every mutation, on a timer resync tick) and must not be
  // blocked by an in-flight answer submission the way a real mutation would be.
  const fetchExamOverview = useCallback(async () => {
    const sid = sessionIdRef.current;
    if (!token || !sid) return null;
    try {
      const overview = await api.getExamOverview(token, sid);
      setExamOverview(overview);
      return overview;
    } catch {
      // Best-effort - a transient failure just leaves the nav bar showing stale state
      // until the next successful poll.
      return null;
    }
  }, [token]);

  // Declared after `fetchExamOverview` so it can await it: D-218 moved the post-answer
  // refresh here, out of `ExamScreen.handleSubmitClick`, where it fired *alongside* the
  // un-awaited POST and therefore stored a pre-answer overview. Same await-then-refetch
  // shape as `skipExamItem`/`flagExamItem` below.
  const submitAnswer = useCallback(
    async (questionVariantId: string, selectedOption: string, responseTimeMs: number) => {
      const sid = sessionIdRef.current;
      if (!token || !sid) return null;
      const snap = await run(async () => {
        const result = await api.submitAnswer(
          token,
          sid,
          questionVariantId,
          selectedOption,
          responseTimeMs,
        );
        setSnapshot(result);
        return result;
      });
      // Only the exam phases have an overview to refresh; the study phase serves one item at
      // a time and has no nav bar. `snap` is null when `run` swallowed a failure, and a
      // failed answer has nothing to re-read.
      if (snap && (snap.phase === "pre_exam" || snap.phase === "post_exam")) {
        await fetchExamOverview();
      }
      return snap;
    },
    [token, run, fetchExamOverview],
  );

  const markExamViewed = useCallback(async () => {
    const sid = sessionIdRef.current;
    if (!token || !sid) return;
    // D-218. Outside the `run()` busy gate for the same reason `fetchExamOverview` is: this
    // fires on arriving at the exam and must not block or be blocked by the student's first
    // answer. Best-effort - a failure just means the clock keeps its old start, which is the
    // pre-D-218 behaviour rather than a broken exam.
    try {
      setExamOverview(await api.markExamViewed(token, sid));
    } catch {
      // Intentionally silent, as above.
    }
  }, [token]);

  const skipExamItem = useCallback(
    async (assessmentItemId: string) => {
      const sid = sessionIdRef.current;
      if (!token || !sid) return null;
      const result = await run(async () => {
        await api.skipExamItem(token, sid, assessmentItemId);
      });
      await fetchExamOverview();
      return result;
    },
    [token, run, fetchExamOverview],
  );

  const flagExamItem = useCallback(
    async (assessmentItemId: string, flagged: boolean) => {
      const sid = sessionIdRef.current;
      if (!token || !sid) return null;
      const result = await run(async () => {
        await api.flagExamItem(token, sid, assessmentItemId, flagged);
      });
      await fetchExamOverview();
      return result;
    },
    [token, run, fetchExamOverview],
  );

  // Fire-and-forget autosave tick - never surfaces an error to `session.error` (losing a
  // few seconds of timing on a network blip isn't worth interrupting the student).
  const recordItemTime = useCallback(
    (assessmentItemId: string, elapsedMs: number) => {
      const sid = sessionIdRef.current;
      if (!token || !sid || elapsedMs <= 0) return;
      void api.recordItemTime(token, sid, assessmentItemId, elapsedMs).catch(() => {});
    },
    [token],
  );

  const finalizeExam = useCallback(
    async (confirmUnanswered: boolean) => {
      const sid = sessionIdRef.current;
      if (!token || !sid) return null;
      return run(async () => {
        const snap = await api.finalizeExam(token, sid, confirmUnanswered);
        setSnapshot(snap);
        return snap;
      });
    },
    [token, run],
  );

  const respond = useCallback(
    async (body: RespondBody) => {
      const sid = sessionIdRef.current;
      if (!token || !sid) return null;
      return run(async () => {
        const snap = await api.respondToInterrupt(token, sid, body);
        if (body.interrupt_type === "child_selection") rememberStudent(body.student_id);
        setSnapshot(snap);
        return snap;
      });
    },
    [token, run, rememberStudent],
  );

  // S24: chat never touches `snapshot`/the graph checkpoint (see `nodes.run_chat_turn`'s
  // own docstring for why - it must keep working while the graph is paused at
  // `intervention_choice`'s `interrupt()`, which a fresh `ainvoke` would silently
  // discard). Deliberately outside the `run()` busy gate for the same reason
  // `fetchExamOverview` is - `TutorChatPanel` owns its own loading/error state, and a
  // chat call must never be blocked by (or block) an unrelated in-flight action.
  const sendChatMessage = useCallback(
    async (questionVariantId: string, message: string) => {
      const sid = sessionIdRef.current;
      if (!token || !sid) return null;
      return api.sendChatMessage(token, sid, questionVariantId, message);
    },
    [token],
  );

  // Deliberately does NOT forget the resolved student (AUD-F-22): clearing it here was
  // what made the start screen's dashboard button disappear the moment a parent backed
  // out of a session. Logout calls `forgetStudent` explicitly.
  const endSession = useCallback(() => {
    sessionStore.removeItem(SESSION_ID_KEY);
    // The owner stamp is meaningless without a session and would otherwise make the next
    // `clearSessionIfOwnedByAnotherSubject` look at a key with nothing behind it.
    sessionStore.removeItem(OWNER_KEY);
    sessionIdRef.current = null;
    setSessionId(null);
    setCheckpointReady(false);
    setSnapshot(null);
    setExamOverview(null);
  }, []);

  // **The ownership check, repeated when the identity changes without a remount** (D-381).
  //
  // `clearSessionIfOwnedByAnotherSubject` runs in the state initialisers, which is the right
  // place for a page load and blind to a sign-in inside a mounted tree. That gap was survivable
  // while the session lived in `sessionStorage`, because the id died with the tab. It is not
  // survivable now that it lives in `localStorage`: the one path that reaches here is a token
  // expiry (`handleSignedOut` deliberately keeps the session so the *same* student resumes),
  // and if a *different* student then signs in on that device, the stale id would open a
  // stream against the first student's session. The server refuses it correctly with a 403 -
  // and a fail-closed refusal the client cannot recover from is a wedged app, which is the
  // exact incident this function's docstring records from 2026-08-07.
  //
  // A deliberate logout never reaches this: `handleLogout` calls `endSession()` first.
  useEffect(() => {
    if (sub === null) return;
    const owner = sessionStore.getItem(OWNER_KEY);
    if (owner === null || owner === sub) return;
    endSession();
    sessionStore.removeItem(STUDENT_ID_KEY);
    setStudentId(null);
  }, [sub, endSession]);

  return {
    sessionId,
    studentId,
    snapshot,
    streamState,
    reconnectStream,
    error,
    busy,
    startSession,
    rememberStudent,
    forgetStudent,
    chooseStudent,
    chooseTopic,
    resolveAttendance,
    submitAnswer,
    respond,
    endSession,
    examOverview,
    fetchExamOverview,
    markExamViewed,
    skipExamItem,
    flagExamItem,
    recordItemTime,
    finalizeExam,
    sendChatMessage,
  };
}
