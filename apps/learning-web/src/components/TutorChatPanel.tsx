import { useEffect, useRef, useState } from "react";
import type { ChatMessageResult } from "../api/client";
import type { ChatMessage } from "../hooks/useTutorChat";
import { useProgressiveReveal } from "../hooks/useProgressiveReveal";
import { ChatViz } from "./ChatViz";
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
  const fullyRevealed = !reveal || revealed >= total;
  return (
    <>
      <p className={`chat-bubble ${message.role}`}>
        <RichText text={message.text} maxChars={reveal ? revealed : undefined} />
      </p>
      {/* D-217: the diagram appears once its reply has finished revealing, so it doesn't
          pop in above still-typing text. */}
      {message.viz && fullyRevealed && <ChatViz viz={message.viz} />}
    </>
  );
}

export interface ChatTranscript {
  messages: ChatMessage[];
  sending: boolean;
  error: string | null;
  send: (text: string, call: () => Promise<ChatMessageResult | null>) => Promise<void>;
}

interface TutorChatPanelProps {
  // The question this conversation is about. `AssistancePanel` only renders this component
  // when it has one (from `snapshot.assistance_question`, D-272).
  questionVariantId: string;
  onSendMessage: (
    questionVariantId: string,
    message: string,
  ) => Promise<ChatMessageResult | null>;
  // D-207: owned by `App` via `useTutorChat`, because this component is unmounted every
  // time `AssistancePanel` switches between its help and tutor views - which used to
  // silently discard the conversation.
  transcript: ChatTranscript;
}

/**
 * D-272: a full-height conversation, not a 220px box.
 *
 * Three things went away in this rewrite and each was a symptom of the panel being a
 * *section* of the help panel rather than a mode of the column:
 *
 * - The **collapse/expand** state and its "Chat with your tutor" button. The column now
 *   has an explicit Help/Tutor switch above it, so a second way to hide the same thing was
 *   one control too many.
 * - The **`max-height: 220px`** scroll box, which showed about three messages.
 * - The **`<details>` copy of the question**. The question is permanently on the left now,
 *   so repeating it here was the split-attention problem being solved twice, badly.
 */
export function TutorChatPanel({
  questionVariantId,
  onSendMessage,
  transcript,
}: TutorChatPanelProps) {
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  // Keep the newest message in view. `block: "nearest"` so this scrolls the transcript
  // box itself and never yanks the whole page while the student is reading the question
  // beside it.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [transcript.messages.length, transcript.sending]);

  async function handleSend() {
    const text = input.trim();
    if (!text || transcript.sending) return;
    setInput("");
    await transcript.send(text, () => onSendMessage(questionVariantId, text));
  }

  return (
    <div className="chat-panel">
      <div className="chat-messages" aria-live="polite">
        {transcript.messages.length === 0 && (
          <div className="chat-empty">
            <p>Ask me anything about this question.</p>
            {/* Openers, because "ask me anything" is the hardest prompt to answer when you
                are stuck - if you knew what to ask you would be less stuck. These fill the
                input rather than sending, so the student still chooses.

                **Worded to classify as help, not as a hint request.** `classify_intent`
                routes `request_hint` into the actual hint ladder, which spends a Bedrock
                call and sets `hint_used` on the attempt - so a suggested opener containing
                "hint" or "stuck" would quietly take a rung of help the student did not ask
                for. Measured locally 2026-08-10: "I don't know where to start" came back
                `off_topic` and got the refusal message, because it has neither a keyword nor
                a question mark. These three each land on `question_help` or `why_wrong`. */}
            <div className="chat-starters">
              {[
                "What is this question actually asking?",
                "Why is my answer wrong?",
                "Can you explain it a different way?",
              ].map((starter) => (
                <button
                  key={starter}
                  type="button"
                  className="secondary chat-starter"
                  onClick={() => setInput(starter)}
                >
                  {starter}
                </button>
              ))}
            </div>
          </div>
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
