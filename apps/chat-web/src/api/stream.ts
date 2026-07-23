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
    onSnapshot(JSON.parse(event.data) as TurnSnapshot);
  };

  return () => source.close();
}
