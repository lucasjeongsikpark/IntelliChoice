import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../api/client";
import { friendlyError } from "../api/errors";
import { openSessionStream } from "../api/stream";
import type { RespondBody } from "../api/client";
import type { ExamOverview, SessionSnapshot } from "../types";

const SESSION_ID_KEY = "intellichoice.learning_session_id";
const STUDENT_ID_KEY = "intellichoice.selected_student_id";

// The whole point of persisting `sessionId` in `sessionStorage` (survives a refresh,
// cleared when the tab closes) is SPEC Phase 11's "Done when": a page refresh must
// restore exact position. On mount, if a session id is already stored, opening the SSE
// stream alone restores the snapshot - no replay of prior actions needed, since
// `/stream` reads the live LangGraph checkpoint on connect (see D-032).
export function useLearningSession(token: string | null) {
  const [sessionId, setSessionId] = useState<string | null>(() =>
    sessionStorage.getItem(SESSION_ID_KEY),
  );
  const [studentId, setStudentId] = useState<string | null>(() =>
    sessionStorage.getItem(STUDENT_ID_KEY),
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

  useEffect(() => {
    if (!token || !sessionId || !checkpointReady) return;
    setStreamState("connecting");
    const close = openSessionStream(
      sessionId,
      token,
      (snap) => setSnapshot(snap),
      (state) => setStreamState(state),
    );
    return close;
  }, [token, sessionId, checkpointReady]);

  // AUD-F-22: the resolved student is *login-scoped* identity, not session state - it is
  // set at login (App.tsx's pre-session resolution) or by an explicit selection, survives
  // `endSession` (so the start screen's dashboard button does not vanish when a session
  // ends - the finding's "backing out does not help"), and is forgotten only on logout.
  const rememberStudent = useCallback((id: string) => {
    sessionStorage.setItem(STUDENT_ID_KEY, id);
    setStudentId(id);
  }, []);

  const forgetStudent = useCallback(() => {
    sessionStorage.removeItem(STUDENT_ID_KEY);
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
      sessionStorage.setItem(SESSION_ID_KEY, snap.learning_session_id);
      sessionIdRef.current = snap.learning_session_id;
      setSessionId(snap.learning_session_id);
      // A brand-new session's checkpoint doesn't exist until `chooseStudent` below
      // runs `resolve_student` - see this hook's `checkpointReady` docstring.
      setCheckpointReady(false);
      setSnapshot(snap);
      return snap;
    });
  }, [token, run]);

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

  const submitAnswer = useCallback(
    async (questionVariantId: string, selectedOption: string, responseTimeMs: number) => {
      const sid = sessionIdRef.current;
      if (!token || !sid) return null;
      return run(async () => {
        const snap = await api.submitAnswer(
          token,
          sid,
          questionVariantId,
          selectedOption,
          responseTimeMs,
        );
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
    sessionStorage.removeItem(SESSION_ID_KEY);
    sessionIdRef.current = null;
    setSessionId(null);
    setCheckpointReady(false);
    setSnapshot(null);
    setExamOverview(null);
  }, []);

  return {
    sessionId,
    studentId,
    snapshot,
    streamState,
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
    skipExamItem,
    flagExamItem,
    recordItemTime,
    finalizeExam,
    sendChatMessage,
  };
}
