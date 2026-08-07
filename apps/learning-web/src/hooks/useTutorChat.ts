import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessageResult } from "../api/client";

export interface ChatMessage {
  role: "student" | "tutor";
  text: string;
}

/**
 * The tutor conversation, owned above the panel that renders it (D-207).
 *
 * It used to be `useState` inside `TutorChatPanel`, and that was a real defect rather
 * than a structural preference. `AssistancePanel` returns two different trees - a chooser
 * when there is no intervention yet, and the content view once there is - so React
 * unmounts the panel at the moment the student's first choice lands. Ask a question, take
 * a hint, come back: the conversation is gone. It disappeared again on every subsequent
 * ladder round for the same reason.
 *
 * Keeping it here also gives the transcript a lifetime that means something: it is the
 * conversation *for this learning session*, and `reset` is called from the same place the
 * rest of the per-session UI state is cleared.
 *
 * Still client-only, deliberately - unchanged from S24's D-048 precedent. A refresh loses
 * the visible transcript; the backend's own `tutor_chat_messages` audit rows are written
 * either way, so nothing that matters for review or safety depends on this.
 */
export function useTutorChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Guards against a reply landing after the student has moved on to another session.
  const activeRef = useRef(true);
  useEffect(() => {
    activeRef.current = true;
    return () => {
      activeRef.current = false;
    };
  }, []);

  const reset = useCallback(() => {
    setMessages([]);
    setError(null);
    setSending(false);
  }, []);

  const send = useCallback(
    async (
      text: string,
      call: () => Promise<ChatMessageResult | null>,
    ): Promise<void> => {
      if (sending) return;
      setSending(true);
      setError(null);
      // Optimistic: the student's own words appear immediately, which is what makes the
      // ~3-5 s the tutor call actually takes on staging feel like a conversation rather
      // than a frozen box.
      setMessages((prev) => [...prev, { role: "student", text }]);
      try {
        const result = await call();
        if (!activeRef.current) return;
        if (result) {
          setMessages((prev) => [...prev, { role: "tutor", text: result.reply_text }]);
        }
      } catch {
        if (!activeRef.current) return;
        setError("Chat is having trouble right now — try again in a moment.");
      } finally {
        if (activeRef.current) setSending(false);
      }
    },
    [sending],
  );

  return { messages, sending, error, send, reset };
}
