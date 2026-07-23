import { useState } from "react";
import type { ChatMessageResult } from "../api/client";

interface ChatMessage {
  role: "student" | "tutor";
  text: string;
}

interface TutorChatPanelProps {
  // The question the pending `intervention_choice` pause is about (`PendingInterrupt.
  // question_variant_id`) - chat is only ever shown alongside that same pause, so this
  // is always set whenever this component renders.
  questionVariantId: string;
  onSendMessage: (
    questionVariantId: string,
    message: string,
  ) => Promise<ChatMessageResult | null>;
}

// S24: the visible transcript is client-only, same D-048 precedent `chat-web` already
// established for its own chat - a refresh loses it (the backend's own `hint_events`/
// `tutor_chat_messages` audit rows are unaffected either way).
export function TutorChatPanel({ questionVariantId, onSendMessage }: TutorChatPanelProps) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;
    setSending(true);
    setError(null);
    setMessages((prev) => [...prev, { role: "student", text }]);
    setInput("");
    try {
      const result = await onSendMessage(questionVariantId, text);
      if (result) {
        setMessages((prev) => [...prev, { role: "tutor", text: result.reply_text }]);
      }
    } catch {
      setError("Chat is having trouble right now - try again in a moment.");
    } finally {
      setSending(false);
    }
  }

  if (!open) {
    return (
      <button className="secondary" onClick={() => setOpen(true)}>
        Chat with your tutor
      </button>
    );
  }

  return (
    <div className="chat-panel">
      <div className="chat-messages" aria-live="polite">
        {messages.length === 0 && (
          <p className="dim">Ask me anything about this question.</p>
        )}
        {messages.map((message, index) => (
          <p key={index} className={`chat-bubble ${message.role}`}>
            {message.text}
          </p>
        ))}
      </div>
      {error && <p className="error">{error}</p>}
      <div className="chat-input-row">
        <input
          type="text"
          value={input}
          disabled={sending}
          placeholder="Type your question..."
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void handleSend();
          }}
        />
        <button disabled={sending || !input.trim()} onClick={() => void handleSend()}>
          Send
        </button>
      </div>
    </div>
  );
}
