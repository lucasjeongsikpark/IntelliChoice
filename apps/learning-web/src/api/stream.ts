import { API_BASE } from "./client";
import type { SessionSnapshot } from "../types";

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

  source.onopen = () => onStateChange?.("open");
  source.onerror = () => onStateChange?.("error");
  source.onmessage = (event) => {
    onSnapshot(JSON.parse(event.data) as SessionSnapshot);
  };

  return () => source.close();
}
