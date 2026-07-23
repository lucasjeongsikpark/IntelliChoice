import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../api/client";
import { openSessionStream } from "../api/stream";
import type { RespondBody } from "../api/client";
import type { ChatTurn, TurnSnapshot } from "../types";

const SESSION_ID_KEY = "intellichoice.chat_session_id";
const TRANSCRIPT_KEY = "intellichoice.chat_transcript";

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
export function useChatSession(token: string | null) {
  const [sessionId, setSessionId] = useState<string | null>(() =>
    sessionStorage.getItem(SESSION_ID_KEY),
  );
  const [transcript, setTranscript] = useState<ChatTurn[]>(loadTranscript);
  const [streamState, setStreamState] = useState<"connecting" | "open" | "error">("connecting");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  // A brand-new session has no LangGraph checkpoint until its first `/messages` call
  // completes - opening the SSE stream any earlier 404s once (harmless, self-heals via
  // `EventSource`'s own auto-reconnect, same category as D-032/D-033's caveats) but is
  // easy to just avoid. `loadTranscript()`'s initial value already reflects whether a
  // restored session has a completed turn.
  const [streamReady, setStreamReady] = useState(() => loadTranscript().length > 0);

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
    if (!sessionId || !streamReady) return;
    setStreamState("connecting");
    const close = openSessionStream(
      sessionId,
      token,
      (snapshot) => {
        setTranscript((prev) => {
          if (prev.length === 0) return prev;
          const last = prev[prev.length - 1];
          const updated: ChatTurn = { ...last, response: snapshot };
          return [...prev.slice(0, -1), updated];
        });
      },
      (state) => setStreamState(state),
    );
    return close;
  }, [sessionId, streamReady, token]);

  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | null> => {
    if (busyRef.current) return null;
    busyRef.current = true;
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (err) {
      setError(err instanceof api.ApiError ? String(err.detail) : String(err));
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

  const sendMessage = useCallback(
    async (query: string) => {
      return run(async () => {
        const sid = await ensureSession();
        if (!sid) return null;
        const turnId = crypto.randomUUID();
        setTranscript((prev) => [...prev, { id: turnId, query, response: null }]);
        const response: TurnSnapshot = await api.postMessage(token, sid, query);
        setTranscript((prev) =>
          prev.map((t) => (t.id === turnId ? { ...t, response } : t)),
        );
        setStreamReady(true);
        return response;
      });
    },
    [token, run, ensureSession],
  );

  const respond = useCallback(
    async (body: RespondBody) => {
      const sid = sessionIdRef.current;
      if (!sid) return null;
      return run(async () => {
        const response = await api.respondToInterrupt(token, sid, body);
        setTranscript((prev) => {
          if (prev.length === 0) return prev;
          const last = prev[prev.length - 1];
          return [...prev.slice(0, -1), { ...last, response }];
        });
        return response;
      });
    },
    [token, run],
  );

  const endSession = useCallback(() => {
    sessionStorage.removeItem(SESSION_ID_KEY);
    sessionStorage.removeItem(TRANSCRIPT_KEY);
    sessionIdRef.current = null;
    setSessionId(null);
    setTranscript([]);
    setStreamReady(false);
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
    respond,
    endSession,
  };
}
