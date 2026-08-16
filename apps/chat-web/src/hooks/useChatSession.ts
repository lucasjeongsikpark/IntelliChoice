import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../api/client";
import { friendlyError, isSignedOut } from "../api/errors";
import { openSessionStream } from "../api/stream";
import type { RespondBody } from "../api/client";
import type { ChatTurn, TurnSnapshot } from "../types";

const SESSION_ID_KEY = "intellichoice.chat_session_id";
const CANCELLED_MESSAGE = "You stopped this question.";
const TRANSCRIPT_KEY = "intellichoice.chat_transcript";
const OWNER_KEY = "intellichoice.chat_owner";

/**
 * D-353, ported from `useLearningSession.clearSessionIfOwnedByAnotherSubject`.
 *
 * A session id and a transcript in `sessionStorage` belong to whoever was signed in when they
 * were written. Sign out and back in as somebody else in the same tab and both survive - so
 * the new identity inherits the previous one's conversation on screen, and its next request
 * carries a session id the server will refuse as someone else's (`_assert_session_access`).
 * chat-web had no equivalent of this at all; the one in-app path that could reach it happened
 * to call `endSession()` first, so it was unreachable by accident rather than by design.
 *
 * Anonymous is a real identity here, not the absence of one (SPEC §5.19.1), so `null` is
 * stored and compared like any other owner - a guest returning after a signed-in session must
 * not inherit that session either.
 *
 * Runs in the hook's `useState` initialisers rather than an effect, so no render ever shows
 * the other identity's conversation.
 */
function clearSessionIfOwnedByAnotherSubject(sub: string | null): void {
  const owner = sessionStorage.getItem(OWNER_KEY);
  const current = sub ?? "";
  if (owner === current) return;
  sessionStorage.setItem(OWNER_KEY, current);
  if (owner === null) return; // First run in this tab: adopt whatever is here rather than bin it.
  sessionStorage.removeItem(SESSION_ID_KEY);
  sessionStorage.removeItem(TRANSCRIPT_KEY);
}

function loadTranscript(): ChatTurn[] {
  const raw = sessionStorage.getItem(TRANSCRIPT_KEY);
  if (!raw) return [];
  try {
    return JSON.parse(raw) as ChatTurn[];
  } catch {
    return [];
  }
}

// Mirrors apps/learning-web/src/hooks/useLearningSession.ts's shape (sessionStorage-
// persisted session id + SSE reconnect on mount restores the live snapshot). Unlike
// learning, `QAState` carries only the current turn (no server-side transcript), so the
// visible conversation is built up client-side and persisted alongside the session id -
// a refresh replays it instantly, then the SSE reconnect's initial snapshot reconciles
// the last turn in case anything changed server-side while the tab was away.
export function useChatSession(
  token: string | null,
  sub: string | null,
  onSignedOut?: () => void,
) {
  const [sessionId, setSessionId] = useState<string | null>(() => {
    clearSessionIfOwnedByAnotherSubject(sub);
    return sessionStorage.getItem(SESSION_ID_KEY);
  });
  const [transcript, setTranscript] = useState<ChatTurn[]>(loadTranscript);
  const [streamState, setStreamState] = useState<"connecting" | "open" | "error">("connecting");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  // D-352: the in-flight turn's abort handle. One at a time, because `run`'s mutex already
  // allows only one action at a time - a map keyed by turn would be state with no second
  // case to justify it.
  const inFlightRef = useRef<AbortController | null>(null);
  // A brand-new session has no LangGraph checkpoint until its first `/messages` call
  // completes, so opening the SSE stream any earlier 404s.
  //
  // **This holds the session id it is ready *for*, not a boolean, and that is the fix for a
  // real defect rather than a stylistic preference (D-350).** As a boolean it recorded "some
  // session has answered a turn", which stops being true the moment the session changes:
  // "new chat" cleared it, but a `setStreamReady(true)` still in flight from the previous
  // session's turn could land afterwards, and the next session id to arrive then satisfied
  // the effect immediately - opening a stream against a session whose first message had not
  // been sent. Measured locally: 6 runs of the new-chat journey, 6 x `404 /stream`, against 0
  // before. An id cannot be stale in that way: a value naming session A never enables a
  // stream for session B.
  const [streamReadyFor, setStreamReadyFor] = useState<string | null>(() =>
    loadTranscript().length > 0 ? sessionStorage.getItem(SESSION_ID_KEY) : null,
  );

  // See useLearningSession's own comment on why action callbacks read the session id
  // through a ref rather than the `sessionId` state directly - a caller that chains
  // `startSession().then(() => sendMessage(...))` would otherwise close over a stale
  // `null` from before the state update re-rendered.
  const sessionIdRef = useRef(sessionId);
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  useEffect(() => {
    sessionStorage.setItem(TRANSCRIPT_KEY, JSON.stringify(transcript));
  }, [transcript]);

  useEffect(() => {
    if (!sessionId || streamReadyFor !== sessionId) return;
    setStreamState("connecting");
    const close = openSessionStream(
      sessionId,
      token,
      (snapshot) => {
        setTranscript((prev) => {
          if (prev.length === 0) return prev;
          // D-348: apply the snapshot to the turn it actually describes.
          //
          // This used to overwrite `prev[prev.length - 1]` unconditionally, and `/stream`
          // emits its initial snapshot on *every* (re)connect - so any reconnect during an
          // in-flight turn painted the *previous* turn's answer and citations under the new
          // question. On reload mid-turn that was not even transient: the restored turn had
          // no response of its own, so the stale one stayed until something else arrived.
          //
          // An unmatched snapshot is dropped rather than applied to the last turn as a
          // fallback, because "apply it to the last turn" is precisely the behaviour being
          // fixed. The one case that legitimately has no id is a session checkpointed before
          // this field existed; there the last turn is the best available answer and the
          // stream still self-corrects, so it is matched positionally.
          const id = snapshot.client_turn_id;
          const index = id
            ? prev.findLastIndex((turn) => turn.id === id)
            : prev.length - 1;
          if (index < 0) return prev;
          // Clearing `error` matters: a turn that failed at the HTTP layer but whose
          // graph run actually completed gets its real answer over SSE, and leaving the
          // error bubble beside it would show a failure next to its own result.
          const updated: ChatTurn = { ...prev[index], response: snapshot, error: null };
          return prev.map((turn, i) => (i === index ? updated : turn));
        });
      },
      (state) => setStreamState(state),
    );
    return close;
  }, [sessionId, streamReadyFor, token]);

  // D-347: the stored token is the thing a 401 invalidates, and clearing it is the only exit
  // from the loop it otherwise creates - `get_optional_claims` 401s a *present but invalid*
  // token rather than downgrading to anonymous (deliberately, so an expired session is not a
  // silent access-scope drop), so every retry failed identically and `EventSource` reconnected
  // against the same 401 forever. `onSignedOut` is `App`'s clearing of the four localStorage
  // keys; the transcript is deliberately *not* cleared, because losing the conversation is a
  // second punishment for an expiry the visitor did not cause.
  const signedOutRef = useRef(onSignedOut);
  // Set by `postTurn` when the abort came from `cancelTurn` rather than from the deadline or
  // a transport failure, and read by `run` on the way out.
  const wasCancelledRef = useRef(false);
  useEffect(() => {
    signedOutRef.current = onSignedOut;
  }, [onSignedOut]);

  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | null> => {
    if (busyRef.current) return null;
    busyRef.current = true;
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (err) {
      // D-352: a user-initiated cancel is already stated on the turn itself; a red page
      // banner on top of it would read as a failure the user did not cause.
      if (!wasCancelledRef.current) {
        setError(friendlyError(err));
        if (isSignedOut(err)) signedOutRef.current?.();
      }
      wasCancelledRef.current = false;
      return null;
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }, []);

  const ensureSession = useCallback(async (): Promise<string | null> => {
    if (sessionIdRef.current) return sessionIdRef.current;
    const created = await api.createSession(token);
    sessionStorage.setItem(SESSION_ID_KEY, created.chat_session_id);
    sessionIdRef.current = created.chat_session_id;
    setSessionId(created.chat_session_id);
    return created.chat_session_id;
  }, [token]);

  // AUD-C-10: `run`'s catch sets the page-level error banner but knows nothing about
  // which turn failed, so the failed turn kept `response: null` and rendered `Thinking…`
  // forever. Marking the turn itself is what resolves it - the banner is a page-level
  // signal and cannot clear a per-turn bubble.
  const postTurn = useCallback(
    async (
      sid: string,
      turnId: string,
      query: string,
      escalate = false,
    ): Promise<TurnSnapshot> => {
      const controller = new AbortController();
      inFlightRef.current = controller;
      try {
        const response: TurnSnapshot = await api.postMessage(
          token,
          sid,
          query,
          escalate,
          turnId,
          controller.signal,
        );
        setTranscript((prev) =>
          prev.map((t) => (t.id === turnId ? { ...t, response, error: null } : t)),
        );
        setStreamReadyFor(sid);
        return response;
      } catch (err) {
        // D-352: a turn the user stopped is not a turn that failed, and must not be reported
        // as one. `AbortSignal.timeout` also surfaces as an abort, so the two are told apart
        // by *who* aborted: `controller.signal.aborted` is only true when `cancelTurn` fired.
        const cancelled = controller.signal.aborted;
        wasCancelledRef.current = cancelled;
        setTranscript((prev) =>
          prev.map((t) =>
            t.id === turnId
              ? {
                  ...t,
                  response: null,
                  error: cancelled ? CANCELLED_MESSAGE : friendlyError(err),
                  cancelled,
                }
              : t,
          ),
        );
        // Rethrown on purpose: `run` still owns the banner and the busy flag, so the
        // page-level behaviour is unchanged and only the per-turn state is added.
        throw err;
      } finally {
        if (inFlightRef.current === controller) inFlightRef.current = null;
      }
    },
    [token],
  );

  /** D-352: stop the turn the user is waiting on. Safe to call when nothing is in flight. */
  const cancelTurn = useCallback(() => {
    inFlightRef.current?.abort();
  }, []);

  const sendMessage = useCallback(
    async (query: string) => {
      return run(async () => {
        const sid = await ensureSession();
        if (!sid) return null;
        const turnId = crypto.randomUUID();
        setTranscript((prev) => [...prev, { id: turnId, query, response: null, error: null }]);
        return await postTurn(sid, turnId, query);
      });
    },
    [run, ensureSession, postTurn],
  );

  // D-164: the refusal already offers to "pass this on to a branch manager"; this is what
  // makes the offer real. A new transcript turn is appended rather than mutating the
  // refusal, because the escalation *is* a separate action the user took and the paused
  // approval prompt attaches to the latest turn (`App.tsx` reads `lastResponse`).
  const escalateTurn = useCallback(
    async (query: string) => {
      return run(async () => {
        const sid = await ensureSession();
        if (!sid) return null;
        const turnId = crypto.randomUUID();
        setTranscript((prev) => [...prev, { id: turnId, query, response: null, error: null }]);
        return await postTurn(sid, turnId, query, true);
      });
    },
    [run, ensureSession, postTurn],
  );

  // AUD-C-10's other half: a stuck turn that can only be abandoned is still a dead end.
  // Retrying in place (same turn id) rather than appending a new turn keeps the
  // transcript honest - the user asked once.
  const retryTurn = useCallback(
    async (turnId: string) => {
      const turn = transcript.find((t) => t.id === turnId);
      if (!turn) return null;
      return run(async () => {
        const sid = await ensureSession();
        if (!sid) return null;
        setTranscript((prev) =>
          prev.map((t) =>
            t.id === turnId ? { ...t, response: null, error: null, cancelled: false } : t,
          ),
        );
        return await postTurn(sid, turnId, turn.query);
      });
    },
    [run, ensureSession, postTurn, transcript],
  );

  const respond = useCallback(
    async (body: RespondBody) => {
      const sid = sessionIdRef.current;
      if (!sid) return null;
      return run(async () => {
        const response = await api.respondToInterrupt(token, sid, body);
        setTranscript((prev) => {
          if (prev.length === 0) return prev;
          // D-348: same matching rule as the SSE handler. `/respond` resumes the paused
          // turn, so the server echoes that turn's own `client_turn_id` back - which is
          // the turn this result belongs to, whether or not it is still the last one.
          const id = response.client_turn_id;
          const index = id ? prev.findLastIndex((turn) => turn.id === id) : prev.length - 1;
          if (index < 0) return prev;
          return prev.map((turn, i) => (i === index ? { ...turn, response } : turn));
        });
        return response;
      });
    },
    [token, run],
  );

  /**
   * D-353: start a fresh server session while keeping the conversation on screen.
   *
   * The "Log in" button on an access hint called `onLogout`, which calls `endSession()` -
   * so a guest who asked a parent-gated question and took the offer to sign in lost the
   * question they had just asked, along with everything before it. That is the worst
   * possible moment to clear a transcript: the hint exists precisely because the answer they
   * wanted is behind the sign-in they are being sent to.
   *
   * The **session id** must still go. It was created anonymously, so reusing it under a token
   * hits the server's ownership check and 403s (`_assert_session_access`) - which is correct
   * server behaviour and a dead end for the client. Dropping it means the next question mints
   * a session under the new identity, which is what signing in was for.
   */
  const resetSessionKeepTranscript = useCallback(() => {
    sessionStorage.removeItem(SESSION_ID_KEY);
    sessionIdRef.current = null;
    setSessionId(null);
    setStreamReadyFor(null);
  }, []);

  const endSession = useCallback(() => {
    sessionStorage.removeItem(SESSION_ID_KEY);
    sessionStorage.removeItem(TRANSCRIPT_KEY);
    sessionIdRef.current = null;
    setSessionId(null);
    setTranscript([]);
    setStreamReadyFor(null);
  }, []);

  const lastResponse = transcript.length > 0 ? transcript[transcript.length - 1].response : null;

  return {
    sessionId,
    transcript,
    lastResponse,
    streamState,
    error,
    busy,
    sendMessage,
    escalateTurn,
    retryTurn,
    respond,
    cancelTurn,
    resetSessionKeepTranscript,
    endSession,
  };
}
