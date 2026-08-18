import { API_BASE } from "./client";
import type { TurnSnapshot } from "../types";

/**
 * D-405: how long without a frame before the stream is presumed dead.
 *
 * The server sends a keepalive every 15s (`KEEPALIVE_INTERVAL_S`, both APIs). 40s tolerates one
 * lost keepalive plus jitter and is well under any edge idle timeout, so a healthy-but-quiet
 * stream is never reported - which is the failure mode that mattered: an indicator that cries
 * disconnect during a normal pause is worse than one that stays silent, because the visitor
 * learns to ignore it.
 *
 * **This only became possible in W12a (D-404).** The keepalive used to be an SSE *comment*, which
 * fires no client event, so there was nothing to time against: any timer would have expired on
 * every quiet stream. It is now `event: keepalive`, which is what `addEventListener` below reads.
 */
export const STALE_AFTER_MS = 40_000;

// SPEC §5.14.1 pattern applied to chat (mirrors apps/learning-web/src/api/stream.ts) -
// the browser's native `EventSource` for its built-in auto-reconnect. Unlike learning,
// a token here is optional: SPEC §5.19.1 allows fully anonymous Q&A sessions, and
// `chat_api.routers.stream` only requires a token when the session has a resolved
// owner (see docs/DECISIONS.md D-032/D-040).
export function openSessionStream(
  chatSessionId: string,
  token: string | null,
  onSnapshot: (snapshot: TurnSnapshot) => void,
  onStateChange?: (state: "open" | "error") => void,
): () => void {
  const query = token ? `?token=${encodeURIComponent(token)}` : "";
  const url = `${API_BASE}/chat/sessions/${chatSessionId}/stream${query}`;
  const source = new EventSource(url);

  // D-405: the liveness timer. `EventSource` reports `onerror` when the browser *notices* a drop,
  // and a silent partition can leave it believing the connection is fine - which is EDGE-CHAT-02.
  // Started at creation rather than on `onopen`, deliberately: a connect that hangs with no
  // response at all produces neither event, and a stream that has not opened in 40s is dead too.
  let staleTimer: ReturnType<typeof setTimeout> | undefined;
  const markAlive = () => {
    if (staleTimer !== undefined) clearTimeout(staleTimer);
    staleTimer = setTimeout(() => onStateChange?.("error"), STALE_AFTER_MS);
  };
  markAlive();
  // The keepalive is a *named* event, so it never reaches `onmessage` (which receives only
  // unnamed events) - that separation is why D-404 named it rather than sending a bare `data:`.
  source.addEventListener("keepalive", markAlive);

  source.onopen = () => {
    onStateChange?.("open");
    markAlive();
  };
  source.onerror = () => onStateChange?.("error");
  source.onmessage = (event) => {
    markAlive();
    // D-216, ported from learning-web (D-347): an unparsable frame must not throw inside
    // the event handler. Doing so kills no connection and logs nothing visible - it just
    // silently stops snapshots from ever updating again, which in this app means a
    // reloaded tab's `Thinking…` never resolves. Skipping one frame is safe: every frame
    // is a full snapshot, so the next one supersedes whatever this one carried.
    let snapshot: TurnSnapshot;
    try {
      snapshot = JSON.parse(event.data) as TurnSnapshot;
    } catch {
      return;
    }
    onSnapshot(snapshot);
  };

  return () => {
    // Clearing before closing matters: a pending timer would fire `onStateChange("error")`
    // after the caller has torn the stream down, setting state on an unmounted consumer and
    // showing a disconnect banner for a stream nobody is watching.
    if (staleTimer !== undefined) clearTimeout(staleTimer);
    source.close();
  };
}
