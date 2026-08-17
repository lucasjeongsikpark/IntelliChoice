import { useCallback, useEffect, useRef, useState } from "react";
import { friendlyError } from "../api/errors";
import type { ChatMessageResult, ChatViz } from "../api/client";

export interface ChatMessage {
  role: "student" | "tutor";
  text: string;
  // D-217: an optional bounded diagram on a tutor reply; never on a student message.
  viz?: ChatViz | null;
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
 * D-217: the transcript is scoped to the current *question*, not the whole session. Each
 * question is its own problem, so its chat is its own conversation - carrying one question's
 * back-and-forth onto the next was noise. Keyed by `questionVariantId` using the
 * derived-not-synchronised pattern `useNarrativeGate`/`useAssistanceCounts` use: a record
 * left by a different question reads as empty, so a new question starts fresh with no window
 * where the previous transcript is briefly visible. `reset` (session end) still clears it.
 *
 * Still client-only, deliberately - unchanged from S24's D-048 precedent. A refresh loses
 * the visible transcript; the backend's own `tutor_chat_messages` audit rows are written
 * either way, so nothing that matters for review or safety depends on this.
 */
export function useTutorChat(questionVariantId: string | null) {
  const [record, setRecord] = useState<{
    questionVariantId: string | null;
    messages: ChatMessage[];
  }>({ questionVariantId, messages: [] });
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Guards against a reply landing after the student has moved on.
  const activeRef = useRef(true);
  useEffect(() => {
    activeRef.current = true;
    return () => {
      activeRef.current = false;
    };
  }, []);

  // Derived: a transcript belonging to a different question shows as empty rather than
  // being cleared by an effect (which would race the question change).
  const messages = record.questionVariantId === questionVariantId ? record.messages : [];

  const reset = useCallback(() => {
    setRecord({ questionVariantId: null, messages: [] });
    setError(null);
    setSending(false);
  }, []);

  const send = useCallback(
    async (
      text: string,
      call: () => Promise<ChatMessageResult | null>,
    ): Promise<boolean> => {
      if (sending) return false;
      setSending(true);
      setError(null);
      // Optimistic: the student's own words appear immediately, which is what makes the
      // ~3-5 s the tutor call actually takes on staging feel like a conversation rather
      // than a frozen box. Appended to *this question's* transcript, starting fresh if the
      // active question changed since the last message.
      setRecord((prev) => {
        const base = prev.questionVariantId === questionVariantId ? prev.messages : [];
        return { questionVariantId, messages: [...base, { role: "student", text }] };
      });
      try {
        const result = await call();
        if (!activeRef.current) return false;
        if (result) {
          setRecord((prev) =>
            prev.questionVariantId === questionVariantId
              ? {
                  questionVariantId,
                  messages: [
                    ...prev.messages,
                    { role: "tutor", text: result.reply_text, viz: result.viz },
                  ],
                }
              : prev,
          );
        }
        // D-380: `run()` returns null on any failure and sets the page-level error, so a
        // null result is a failed send even though nothing was thrown here. Reporting it as
        // success is how the student's typing was thrown away on the quietest failure path.
        return result !== null;
      } catch (err) {
        if (!activeRef.current) return false;
        // D-380: was a single hard-coded "try again in a moment" for every failure, so a 429
        // (rate-limited), a 401 (signed out) and a 503 read identically - and a student told
        // to try again did, repeatedly, against a limit that would keep refusing or a token
        // that was dead. Every other call site in this app routes through `friendlyError`;
        // this one was the exception, and `friendlyError` is imported nowhere in this file.
        setError(friendlyError(err));
        // D-380: reported so the panel can put the student's text back in the box.
        return false;
      } finally {
        if (activeRef.current) setSending(false);
      }
      return true;
    },
    [sending, questionVariantId],
  );

  return { messages, sending, error, send, reset };
}
