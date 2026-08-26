import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../api/client";
import { friendlyError, isSignedOut } from "../api/errors";
import { openSessionStream } from "../api/stream";
import { isPendingTurn } from "../lib/turnState";
import type { RespondBody } from "../api/client";
import type { ChatTurn, TurnSnapshot } from "../types";

const SESSION_ID_KEY = "intellichoice.chat_session_id";
const CANCELLED_MESSAGE = "You stopped this question.";
const TRANSCRIPT_KEY = "intellichoice.chat_transcript";
const OWNER_KEY = "intellichoice.chat_owner";

/**
 * D-413 (`AUD-CHAT-07`): what a turn replayed from storage is told when nothing ever finishes it.
 *
 * Deliberately does not say the message failed to send, because it almost certainly did - see
 * `ChatTurn.unresolved`. It states what this tab actually knows: the answer did not come back to
 * *it*. "Ask again" is the offer, the same verb a stopped turn gets, because nothing here is the
 * visitor's fault and nothing needs apologising for.
 */
const UNRESOLVED_MESSAGE = "We lost track of this question when the page reloaded.";

/**
 * How long a replayed turn waits before it is declared unresolved.
 *
 * **Equal to the live request's own timeout on purpose, and that equality is the derivation.**
 * The worst case is a visitor who reloaded the instant their question left the tab, so the server
 * may still have the whole of its `chat_turn_deadline_s` (50s, D-346) to run, plus the relay's
 * publish latency before the snapshot reaches a new stream. `REQUEST_TIMEOUT_MS` is already the
 * constant meaning "even the answer never arrived" and is documented as sitting just above the
 * server's deadline for exactly this reason - so a replayed turn waits precisely as long as it
 * would have if the tab had never reloaded.
 *
 * Anything shorter invents failures: the turn would be marked unresolved while the graph is still
 * working, and the snapshot arriving seconds later would clear the state again - a bubble that
 * flaps between "we lost this" and a real answer, which is worse than the wait it saves.
 */
const REPLAYED_TURN_WAIT_MS = api.REQUEST_TIMEOUT_MS;

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
  // **D-403, ported from learning-web's D-216.** Bumping this re-runs the stream effect,
  // giving a dead stream a manual way back. `EventSource` retries *network* errors on its own
  // backoff, including a connection that never established (measured in the e2e harness
  // 2026-08-26: 1 -> 4 attempts over 12s of idle behind an aborted route - this clause read
  // "only after a *successful* connection drops" until then). What it does not retry is a
  // non-2xx response (an expired token, a 403), which is terminal, and before this chat-web
  // had no path to a fresh connection short of a full reload.
  //
  // learning-web has had this since D-216 and chat-web never received it, which is the D-347
  // "fixed in one direction" shape the 08-16 audit named as the finding behind its findings.
  const [streamNonce, setStreamNonce] = useState(0);
  const reconnectStream = useCallback(() => setStreamNonce((n) => n + 1), []);
  // D-402: which turn the handle above belongs to, so Stop can name it to the server. Kept
  // beside the controller rather than derived from the transcript: the last transcript entry is
  // not necessarily the in-flight one once a retry is involved, and cancelling the wrong turn is
  // the failure this whole feature is scoped to avoid.
  const inFlightTurnRef = useRef<{ sessionId: string; turnId: string } | null>(null);
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

  /**
   * D-413: the turns that were already waiting when this page life began.
   *
   * **Scoped to the replayed ones, not to every pending turn, and that scoping is the fix rather
   * than an optimisation.** A turn sent by *this* tab is already bounded - its `fetch` carries
   * `AbortSignal.timeout(REQUEST_TIMEOUT_MS)` and `postTurn`'s catch turns that into the retryable
   * state. A deadline applied to live turns too would race that catch and report the same failure
   * twice, from two places, with two different wordings.
   *
   * Captured in a `useState` initialiser so it is computed once, at mount, from what storage held
   * *before* any effect has run. It never changes afterwards: a turn sent later in this page life
   * is not a replayed turn, and a reload creates a new hook.
   */
  const [replayedPendingIds] = useState<ReadonlySet<string>>(
    () => new Set(loadTranscript().filter(isPendingTurn).map((turn) => turn.id)),
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

  // **Keep the owner stamp current when the identity changes without a remount** (D-381).
  //
  // `clearSessionIfOwnedByAnotherSubject` runs only in the `useState` initialiser above, which
  // is exactly right for a fresh load and blind to an in-app sign-in. D-353's "Log in" button
  // on an access hint is precisely that: it clears the token keys, keeps the transcript on
  // purpose, and the visitor signs in as somebody else in the same mounted tree. `OWNER_KEY`
  // stayed at the guest value, so the *next* reload saw owner `""` against sub `tutor-ext-1`
  // and deleted the session and the transcript - destroying the conversation D-353 exists to
  // preserve, one reload later than anyone would look. Measured live 2026-08-16.
  //
  // Re-stamping without clearing is safe for every path that reaches here, and there are only
  // two: this one, where keeping the transcript is the entire point, and logout-then-sign-in,
  // where `handleLogout` has already called `endSession()` so there is nothing left to
  // inherit. The cross-identity protection itself is unchanged and still lives in the
  // initialiser, where a genuinely new page load is judged.
  useEffect(() => {
    sessionStorage.setItem(OWNER_KEY, sub ?? "");
  }, [sub]);

  useEffect(() => {
    void streamNonce; // dependency-only: a bump means "tear down and reconnect"
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
          // **A turn the visitor stopped stays stopped** (D-381). `cancelTurn` aborts the
          // client's fetch and nothing else - there is no cancel endpoint, so the graph runs
          // to completion under its 50s deadline and publishes a finished snapshot. That
          // snapshot arrived here and silently replaced "You stopped this question." with an
          // answer to a question the visitor had explicitly withdrawn. Observed live
          // 2026-08-16: Stop, then the refusal-with-escalation-button appeared seconds later.
          // `retryTurn` clears `cancelled`, so "Ask again" still works.
          //
          // **A pause is the exception, and it has to be.** `App` reads `pending_interrupt`
          // off the *last turn's* response to decide whether to render a modal, so dropping a
          // paused snapshot would hide the dialog while the graph stays parked on its
          // `interrupt()` - and every later question would 409 on "pending interrupt" with
          // nothing on screen to resolve. Suppressing an answer the visitor withdrew is
          // honest; suppressing a question the server is asking them deadlocks the session.
          if (prev[index].cancelled && !snapshot.pending_interrupt) return prev;
          // Clearing `error` matters: a turn that failed at the HTTP layer but whose
          // graph run actually completed gets its real answer over SSE, and leaving the
          // error bubble beside it would show a failure next to its own result.
          //
          // **`unresolved` is cleared for the same reason, and unlike `cancelled` it is not
          // protected** (D-413). A late answer to a turn the visitor *stopped* must stay
          // suppressed - they withdrew the question. A turn we merely lost track of is the
          // opposite case: nobody withdrew anything, so an answer that finally arrives is
          // strictly better than the apology, and the flag has to go with it or a future
          // branch reading `unresolved` without `!turn.response` inherits a stale one.
          const updated: ChatTurn = {
            ...prev[index],
            response: snapshot,
            error: null,
            unresolved: false,
          };
          return prev.map((turn, i) => (i === index ? updated : turn));
        });
      },
      (state) => setStreamState(state),
    );
    return close;
  }, [sessionId, streamReadyFor, token, streamNonce]);

  /**
   * **D-413 (`AUD-CHAT-07`): the replayed `Thinking…` gets a deadline.**
   *
   * A turn restored from `sessionStorage` has no request behind it in this page life, so the only
   * thing that can ever finish it is the stream effect above matching a snapshot to its
   * `client_turn_id`. Two ordinary paths never produce one: the question never reached the server
   * (the checkpoint then names a *different* turn, and D-348 drops an unmatched snapshot by
   * design, correctly), and the process died mid-turn (the checkpoint holds an unfinished state,
   * so `isFinishedTurn` stays false and the bubble stays even *with* a response). In both, the
   * visitor waits on a pulsing bubble for the rest of the session.
   *
   * This is `ExamScreen`'s `POSITION_WAIT_MS` shape (D-317): a render state that depends on a
   * message which may never arrive needs a deadline, or the silent case becomes a permanent one.
   *
   * `response: null` is set alongside the flag and is load-bearing, not tidying: the failed-turn
   * bubbles all require `!turn.response`, so leaving an *unfinished* snapshot in place would put
   * the turn in a state that renders nothing at all - a blank gap where the answer should be,
   * which is a worse outcome than the stuck bubble. `postTurn`'s catch clears it for the same
   * reason.
   *
   * `isPendingTurn` is re-checked inside the updater rather than trusted from mount: by the time
   * this fires the turn may have been answered by a snapshot, stopped by the visitor, or retried,
   * and each of those has already put it in a state this must not overwrite.
   */
  useEffect(() => {
    if (replayedPendingIds.size === 0) return;
    const id = window.setTimeout(() => {
      setTranscript((prev) =>
        prev.map((turn) =>
          replayedPendingIds.has(turn.id) && isPendingTurn(turn)
            ? { ...turn, response: null, error: UNRESOLVED_MESSAGE, unresolved: true }
            : turn,
        ),
      );
    }, REPLAYED_TURN_WAIT_MS);
    return () => window.clearTimeout(id);
  }, [replayedPendingIds]);

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
      inFlightTurnRef.current = { sessionId: sid, turnId };
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

  /**
   * D-352: stop the turn the user is waiting on. Safe to call when nothing is in flight.
   *
   * **D-402: it now tells the server as well, and that half is what the visitor feels.** The
   * abort below only ends *this* tab's request - uvicorn does not cancel the handler when a
   * client disconnects, so the graph kept running under its 50s deadline holding the session's
   * advisory lock, and the next question was refused with "This conversation is already working
   * on a question." for up to that long.
   *
   * The server call is fire-and-forget on purpose: the local stop has already taken effect, so
   * awaiting it would delay the UI for no benefit, and a failure has to degrade to the old
   * behaviour rather than report an error for something the visitor just watched succeed.
   *
   * ---
   *
   * **D-413: it now takes the turn it is stopping, and works on a turn this tab never sent.**
   *
   * Two defects came out of reading the previous version, neither of them in `AUD-CHAT-07`'s note:
   *
   * 1. **After a reload it did nothing at all.** Both refs are `null` at mount and only `postTurn`
   *    fills them, so on a replayed turn the abort was a no-op, the `if` body never ran, and no
   *    state changed. The one exit the visitor could see was inert, permanently. Naming the turn
   *    from the transcript is enough to fix it, because D-402's endpoint is addressed by
   *    `(session_id, client_turn_id)` and a replayed turn carries both.
   * 2. **It aborted whatever was in flight, not the turn whose button was clicked.** Every pending
   *    turn renders its own Stop, so a replayed turn plus a live one meant two buttons and one
   *    victim - "cancelling the wrong turn is the failure this whole feature is scoped to avoid",
   *    per `inFlightTurnRef`'s own comment. The abort is now conditional on the named turn being
   *    the in-flight one.
   *
   * The replayed branch has to set the stopped state itself: there is no request, so there is no
   * `postTurn` catch to do it. Telling the server anyway is the point rather than a side effect -
   * the graph from the previous page life may still be running and holding the session's advisory
   * lock, which is exactly what D-402 exists to release. A cancellation for a turn that finished
   * long ago is harmless: it is a row nothing consumes, which `STALE_AFTER` already reaps.
   */
  const cancelTurn = useCallback(
    (turnId: string) => {
      const inFlight = inFlightTurnRef.current;
      if (inFlight && inFlight.turnId === turnId) {
        // The abort is what `postTurn`'s catch turns into the stopped state, so this branch
        // deliberately sets no transcript state of its own.
        inFlightRef.current?.abort();
        inFlightTurnRef.current = null;
        void api.cancelTurn(token, inFlight.sessionId, turnId);
        return;
      }
      setTranscript((prev) =>
        prev.map((turn) =>
          // Guarded like the deadline's updater: between render and click the turn may have been
          // answered, and a stopped state on a turn with an answer would hide the answer.
          turn.id === turnId && isPendingTurn(turn)
            ? { ...turn, response: null, error: CANCELLED_MESSAGE, cancelled: true }
            : turn,
        ),
      );
      const sid = sessionIdRef.current;
      if (sid) void api.cancelTurn(token, sid, turnId);
    },
    [token],
  );

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
        setTranscript((prev) => [
          ...prev,
          // D-378: recorded on the turn so `retryTurn` can reproduce it. Without it a
          // retried escalation silently becomes an ordinary question.
          { id: turnId, query, response: null, error: null, escalate: true },
        ]);
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
            // **Every terminal marker has to be cleared here, not just the one that brought the
            // visitor to this button** (D-413). `isPendingTurn` treats any of them as "ended", so
            // a leftover flag means the retry runs with no `Thinking…` on screen and the previous
            // end-state bubble still showing - the retried turn would still read "We lost track of
            // this question" while its request is in flight. Adding a sixth state means adding a
            // line here; that is the cost of the shape and it is cheaper than overloading `error`.
            t.id === turnId
              ? { ...t, response: null, error: null, cancelled: false, unresolved: false }
              : t,
          ),
        );
        // D-378: `turn.escalate`, not a bare re-send. See `ChatTurn.escalate`.
        return await postTurn(sid, turnId, turn.query, turn.escalate ?? false);
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
    // Same reasoning as `endSession` (D-381): the banner described the session being left.
    // Here the transcript stays, so a stale error above a preserved conversation would be
    // read as a failure of *that* conversation.
    setError(null);
    setStreamReadyFor(null);
  }, []);

  const endSession = useCallback(() => {
    sessionStorage.removeItem(SESSION_ID_KEY);
    sessionStorage.removeItem(TRANSCRIPT_KEY);
    sessionIdRef.current = null;
    setSessionId(null);
    setTranscript([]);
    // D-381: the page-level banner is per-request state that outlived the conversation it
    // described. "New chat" cleared the transcript and left "We can't reach the server right
    // now" sitting above an empty welcome screen, reporting a failure of a session that no
    // longer exists. `run()` only clears this when the *next* request starts, which on a
    // fresh screen may be never.
    setError(null);
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
    reconnectStream,
    resetSessionKeepTranscript,
    endSession,
  };
}
