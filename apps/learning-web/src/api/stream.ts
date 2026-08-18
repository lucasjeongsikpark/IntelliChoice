import { API_BASE } from "./client";
import type { SessionSnapshot } from "../types";

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

// SPEC §5.14.1: the browser's native `EventSource` is used specifically for its
// built-in auto-reconnect (it retries on its own after a drop, using the same URL) -
// see docs/DECISIONS.md D-032 for why the token travels as `?token=` instead of a
// header (EventSource cannot set custom headers).
export function openSessionStream(
  sessionId: string,
  token: string,
  onSnapshot: (snapshot: SessionSnapshot) => void,
  onStateChange?: (state: "open" | "error") => void,
): () => void {
  const url = `${API_BASE}/learning/sessions/${sessionId}/stream?token=${encodeURIComponent(token)}`;
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
    // D-216: an unparsable frame must not throw inside the event handler - that kills no
    // connection and logs nothing visible, it just silently stops snapshots from ever
    // updating again. Skipping one frame is safe: every frame is a full snapshot, so the
    // next one supersedes whatever this one carried.
    let snapshot: SessionSnapshot;
    try {
      snapshot = JSON.parse(event.data) as SessionSnapshot;
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
