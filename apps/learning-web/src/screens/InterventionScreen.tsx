import type { ChatMessageResult } from "../api/client";
import { TutorChatPanel } from "../components/TutorChatPanel";
import type { InterventionContent } from "../types";

type Choice = "hint" | "solution" | "video" | "continue";

interface AssistancePanelProps {
  // `null` for the very first pause, before any choice has produced content yet -
  // renders the plain hint/solution/video chooser with nothing to show alongside.
  intervention: InterventionContent | null;
  // S21: true while the graph is still paused on `intervention_choice` after this
  // content was generated (a "hint" below the ladder's final level) - offers another
  // round instead of the terminal dismiss.
  ladderOpen: boolean;
  busy: boolean;
  onChoose: (choice: Choice) => void;
  onDismiss: () => void;
  // S24: the question this pause is about (`PendingInterrupt.question_variant_id`).
  // `TutorChatPanel` is the 4th `AssistancePanel` option (Hint / Solution / Video /
  // Chat, per ROADMAP S24) - omitted (not shown) when `null`, which happens on a
  // `/respond`-resumed ladder round (S21's pre-existing, documented gap: `ctx.
  // question_variant_id` isn't guaranteed set on that call path, so `PendingInterrupt.
  // question_variant_id` can be missing then too) - the hint/solution/video buttons
  // this panel already offers are unaffected either way.
  questionVariantId: string | null;
  onSendChatMessage: (
    questionVariantId: string,
    message: string,
  ) => Promise<ChatMessageResult | null>;
}

export function AssistancePanel({
  intervention,
  ladderOpen,
  busy,
  onChoose,
  onDismiss,
  questionVariantId,
  onSendChatMessage,
}: AssistancePanelProps) {
  if (!intervention) {
    return (
      <div className="panel">
        <h1>Not quite — want a hand?</h1>
        <p className="subtitle">Choose how you'd like to work through this one.</p>
        <button disabled={busy} onClick={() => onChoose("hint")}>
          Get a hint
        </button>
        <button className="secondary" disabled={busy} onClick={() => onChoose("solution")}>
          Show the solution
        </button>
        <button className="secondary" disabled={busy} onClick={() => onChoose("video")}>
          Watch a video
        </button>
        {questionVariantId && (
          <TutorChatPanel
            questionVariantId={questionVariantId}
            onSendMessage={onSendChatMessage}
          />
        )}
      </div>
    );
  }

  const isHint = intervention.type === "hint";
  const atFinalLevel =
    intervention.hint_level != null &&
    intervention.max_hint_level != null &&
    intervention.hint_level >= intervention.max_hint_level;

  return (
    <div className="intervention-panel">
      {intervention.type === "hint" && (
        <>
          <h2>
            Hint
            {intervention.hint_level != null && intervention.max_hint_level != null && (
              <span className="dim">
                {" "}
                (hint {intervention.hint_level} of {intervention.max_hint_level})
              </span>
            )}
          </h2>
          <p>{intervention.hint_text}</p>
          {intervention.concept_reminder && <p className="dim">{intervention.concept_reminder}</p>}
          {intervention.next_step_prompt && <p className="dim">{intervention.next_step_prompt}</p>}
        </>
      )}
      {intervention.type === "solution" && (
        <>
          <h2>Solution</h2>
          <ol>
            {intervention.steps?.map((step) => (
              <li key={step.step_number}>
                <p>{step.explanation}</p>
                <code>{step.expression}</code>
                {step.common_mistake && <p className="dim">Watch out: {step.common_mistake}</p>}
              </li>
            ))}
          </ol>
          <p>
            <strong>Answer:</strong> {intervention.final_answer}
          </p>
        </>
      )}
      {intervention.type === "video" && (
        <>
          <h2>Video</h2>
          {intervention.video_url ? (
            <p>
              <a href={intervention.video_url} target="_blank" rel="noreferrer">
                {intervention.video_title} ({intervention.video_source})
              </a>
            </p>
          ) : (
            <p>{intervention.message}</p>
          )}
        </>
      )}
      {ladderOpen ? (
        <>
          {isHint && !atFinalLevel && (
            <button disabled={busy} onClick={() => onChoose("hint")}>
              Get another hint
            </button>
          )}
          <button className="secondary" disabled={busy} onClick={() => onChoose("solution")}>
            Show the solution
          </button>
          <button className="secondary" disabled={busy} onClick={() => onChoose("video")}>
            Watch a video
          </button>
          <button className="secondary" disabled={busy} onClick={() => onChoose("continue")}>
            I'll try again now
          </button>
          {questionVariantId && (
            <TutorChatPanel
              questionVariantId={questionVariantId}
              onSendMessage={onSendChatMessage}
            />
          )}
        </>
      ) : (
        <button className="secondary" onClick={onDismiss}>
          Got it — next question
        </button>
      )}
    </div>
  );
}
