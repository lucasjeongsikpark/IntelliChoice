import { useEffect, useRef, useState } from "react";
import type { ChatMessageResult } from "../api/client";
import type { ChatMessage } from "../hooks/useTutorChat";

export interface ChatTranscript {
  messages: ChatMessage[];
  sending: boolean;
  error: string | null;
  send: (text: string, call: () => Promise<ChatMessageResult | null>) => Promise<void>;
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
  // D-207: owned by `App` via `useTutorChat`, because this component is unmounted every
  // time `AssistancePanel` switches between its chooser and content views - which used to
  // silently discard the conversation.
  transcript: ChatTranscript;
}

export function TutorChatPanel({
  questionVariantId,
  onSendMessage,
  transcript,
}: TutorChatPanelProps) {
  // Whether the panel is *expanded* is genuinely local - it is about this render of this
  // screen, not about the conversation. It opens itself once there is something to read,
  // so a student returning from a hint sees their earlier exchange rather than a button
  // that hides it.
  const [open, setOpen] = useState(transcript.messages.length > 0);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (transcript.messages.length > 0) setOpen(true);
  }, [transcript.messages.length]);

  // Keep the newest message in view. `block: "nearest"` so this scrolls the transcript
  // box itself and never yanks the whole page while the student is reading the question
  // above it.
  useEffect(() => {
    if (!open) return;
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [open, transcript.messages.length, transcript.sending]);

  async function handleSend() {
    const text = input.trim();
    if (!text || transcript.sending) return;
    setInput("");
    await transcript.send(text, () => onSendMessage(questionVariantId, text));
  }

  if (!open) {
    return (
      <button className="secondary chat-open" onClick={() => setOpen(true)}>
        Chat with your tutor
      </button>
    );
  }

  return (
    <div className="chat-panel">
      <div className="chat-head">
        <h3>Your tutor</h3>
        <button className="link chat-collapse" onClick={() => setOpen(false)}>
          Hide
        </button>
      </div>
      <div className="chat-messages" aria-live="polite">
        {transcript.messages.length === 0 && (
          <p className="dim">Ask me anything about this question.</p>
        )}
        {transcript.messages.map((message, index) => (
          <p key={index} className={`chat-bubble ${message.role}`}>
            {message.text}
          </p>
        ))}
        {/* A tutor turn takes ~3-5 s against real Bedrock (measured on staging: 4050 ms
            for the reply, 5695 ms for the whole round trip including intent
            classification). Without this the student's own message just sat there and
            nothing indicated anything was happening. */}
        {transcript.sending && (
          <p className="chat-bubble tutor typing" aria-label="Your tutor is typing">
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-dot" />
          </p>
        )}
        <div ref={endRef} />
      </div>
      {transcript.error && <p className="error">{transcript.error}</p>}
      <div className="chat-input-row">
        <input
          type="text"
          value={input}
          disabled={transcript.sending}
          placeholder="Type your question..."
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void handleSend();
          }}
        />
        <button disabled={transcript.sending || !input.trim()} onClick={() => void handleSend()}>
          Send
        </button>
      </div>
    </div>
  );
}
