import { useEffect, useRef, useState } from "react";
import type { ChatMessageResult } from "../api/client";
import type { ChatMessage } from "../hooks/useTutorChat";
import { useProgressiveReveal } from "../hooks/useProgressiveReveal";
import { RichText } from "./RichText";
import { renderedLength } from "../lib/markdown";

/**
 * One message. The newest tutor reply reveals progressively; everything else renders
 * complete, because re-revealing the whole transcript on every new message would be a
 * distraction rather than a flourish.
 */
function ChatBubble({ message, reveal }: { message: ChatMessage; reveal: boolean }) {
  const total = renderedLength(message.text);
  const revealed = useProgressiveReveal(total, reveal);
  return (
    <p className={`chat-bubble ${message.role}`}>
      <RichText text={message.text} maxChars={reveal ? revealed : undefined} />
    </p>
  );
}

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
  // D-213: the question this conversation is about, shown inside the panel.
  //
  // The chat opens from the intervention screen, which does not render the question - so a
  // student was asked to type a question about something no longer on screen, and had to
  // remember it. `null` when the current snapshot no longer carries the item (a
  // `/respond`-resumed ladder round can arrive without it), in which case the block is
  // omitted rather than rendered empty.
  questionText: string | null;
}

export function TutorChatPanel({
  questionVariantId,
  onSendMessage,
  transcript,
  questionText,
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
      {questionText && (
        <details className="chat-question" open>
          <summary>The question you're working on</summary>
          <p>{questionText}</p>
        </details>
      )}
      <div className="chat-messages" aria-live="polite">
        {transcript.messages.length === 0 && (
          <p className="dim">Ask me anything about this question.</p>
        )}
        {transcript.messages.map((message, index) => (
          <ChatBubble
            key={index}
            message={message}
            // Only the newest tutor reply reveals, and only while it is the newest. A
            // student scrolling back should not watch old replies re-type themselves.
            reveal={message.role === "tutor" && index === transcript.messages.length - 1}
          />
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
