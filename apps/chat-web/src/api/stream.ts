import { API_BASE } from "./client";
import type { TurnSnapshot } from "../types";

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

  source.onopen = () => onStateChange?.("open");
  source.onerror = () => onStateChange?.("error");
  source.onmessage = (event) => {
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

  return () => source.close();
}
