import { TutorChatPanel, type ChatTranscript } from "../components/TutorChatPanel";
import type { ChatMessageResult } from "../api/client";
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
  // D-207: the transcript lives in `App`, not in `TutorChatPanel`. This component
  // changes shape between the chooser and the content view, which unmounts the panel and
  // took the conversation with it - a student who asked a question, took a hint, then
  // came back found an empty chat. See `useTutorChat`.
  chat: ChatTranscript;
  // D-213: the stem of the question this pause is about, so the tutor panel can show it
  // alongside the conversation. `null` when the snapshot no longer carries the item.
  questionText: string | null;
  // D-216: a refused/failed choice used to show nothing at all on this panel - the same
  // `session.error` the exam screen renders.
  error: string | null;
}

/**
 * D-207 rewrite. The content was correct before this and read as an undifferentiated
 * wall: a hint's three fields (`hint_text`, `concept_reminder`, `next_step_prompt`) were
 * three bare `<p>`s, two of them `.dim`, so nothing said which one was the hint and which
 * two were context. Solution steps put `explanation` and `expression` in the same run of
 * text. Each part now says what it is.
 */
export function AssistancePanel({
  intervention,
  ladderOpen,
  busy,
  onChoose,
  onDismiss,
  questionVariantId,
  onSendChatMessage,
  chat,
  questionText,
  error,
}: AssistancePanelProps) {
  const chatPanel = questionVariantId && (
    <TutorChatPanel
      questionVariantId={questionVariantId}
      onSendMessage={onSendChatMessage}
      transcript={chat}
      questionText={questionText}
    />
  );

  if (!intervention) {
    return (
      <div className="panel">
        <h1>Not quite — want a hand?</h1>
        <p className="subtitle">Choose how you'd like to work through this one.</p>
        {error && <p className="error">{error}</p>}
        <div className="assistance-choices">
          <button disabled={busy} onClick={() => onChoose("hint")}>
            Get a hint
          </button>
          <button className="secondary" disabled={busy} onClick={() => onChoose("solution")}>
            Show the solution
          </button>
          <button className="secondary" disabled={busy} onClick={() => onChoose("video")}>
            Watch a video
          </button>
          {/* The way out, which this screen did not have. Measured on staging 2026-08-07:
              after a wrong answer the whole page was four assistance buttons and a footer
              link - no back, no dashboard, not even sign-out - and it survived a reload, so
              a student who wanted to carry on unaided was stuck until they accepted help.
              Two costs, not one: it takes the choice away from the student, and every one of
              the other three buttons is a paid Bedrock call, so "no thanks" was the only
              option that was free and the only one missing. `"continue"` was already a valid
              choice server-side (`intervention_choice` routes it straight to
              `flow.advance_study`); nothing needed to be added behind this button. */}
          <button className="secondary" disabled={busy} onClick={() => onChoose("continue")}>
            No thanks — next question
          </button>
        </div>
        {chatPanel}
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
      {intervention.type === "hint" && <HintContent intervention={intervention} />}
      {intervention.type === "solution" && <SolutionContent intervention={intervention} />}
      {intervention.type === "video" && <VideoContent intervention={intervention} />}

      {error && <p className="error">{error}</p>}

      {ladderOpen ? (
        <>
          <div className="assistance-choices">
            {isHint && !atFinalLevel && (
              <button disabled={busy} onClick={() => onChoose("hint")}>
                {/* D-213: names the rung the student is about to get rather than "another",
                    so the choice between one more hint and the full solution is informed.
                    Falls back when the levels are absent, which is the same condition
                    `atFinalLevel` already tolerates. */}
                {intervention.hint_level != null && intervention.max_hint_level != null
                  ? `Next hint (${intervention.hint_level + 1} of ${intervention.max_hint_level})`
                  : "Get another hint"}
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
          </div>
          {chatPanel}
        </>
      ) : (
        <button className="secondary" onClick={onDismiss}>
          Got it — next question
        </button>
      )}
    </div>
  );
}

/**
 * What each rung of the ladder is *for*, in the student's terms.
 *
 * SPEC §5.11.3's hint ladder is three graded levels - a nudge, then the method, then
 * enough to finish - and the UI never said so. Naming them turns "hint 2" from a counter
 * into information: a student who wants the approach rather than a nudge can see that the
 * next one is the approach, and one who is nearly there can see there is a further step.
 *
 * Indexed by level, so a `max_hint_level` other than 3 degrades to "Hint N" rather than
 * mislabelling. The server owns the ladder's length; this only names what it serves.
 */
const HINT_RUNG_LABELS = ["A nudge", "The method", "Almost there"];

/**
 * D-213: the ladder was three dots with an `aria-label`. That showed *position* but not
 * that the ladder had rungs, or what they were, or how much help was left - the user's
 * "make it clearer that there are three hints, and make hints more readable".
 *
 * Now an explicit stepper: numbered rungs, the current one marked, spent ones checked, and
 * the ones still available named. The visual state is duplicated in text for screen
 * readers rather than conveyed by colour and shape alone.
 */
function HintContent({ intervention }: { intervention: InterventionContent }) {
  const level = intervention.hint_level ?? null;
  const max = intervention.max_hint_level ?? null;
  const showLadder = level != null && max != null;
  const remaining = showLadder ? max - level : 0;

  return (
    <>
      <div className="intervention-head">
        <h2>{showLadder ? `Hint ${level} of ${max}` : "Hint"}</h2>
        {showLadder && (
          <span className="hint-remaining">
            {remaining > 0
              ? `${remaining} more ${remaining === 1 ? "hint" : "hints"} if you need ${
                  remaining === 1 ? "it" : "them"
                }`
              : "Last hint"}
          </span>
        )}
      </div>

      {showLadder && (
        <ol className="hint-ladder">
          {Array.from({ length: max }, (_, index) => {
            const rung = index + 1;
            const state = rung < level ? "done" : rung === level ? "current" : "upcoming";
            return (
              <li key={rung} className={`hint-rung ${state}`} aria-current={state === "current"}>
                <span className="hint-rung-marker" aria-hidden="true">
                  {state === "done" ? "✓" : rung}
                </span>
                <span className="hint-rung-label">{HINT_RUNG_LABELS[index] ?? `Hint ${rung}`}</span>
              </li>
            );
          })}
        </ol>
      )}

      <p className="intervention-lead">{intervention.hint_text}</p>
      {intervention.concept_reminder && (
        <div className="intervention-aside">
          <h3>Remember</h3>
          <p>{intervention.concept_reminder}</p>
        </div>
      )}
      {intervention.next_step_prompt && (
        <div className="intervention-aside">
          <h3>Try this next</h3>
          <p>{intervention.next_step_prompt}</p>
        </div>
      )}
    </>
  );
}

/**
 * Steps as cards, each with the working on its own line. The old markup put
 * `<p>{explanation}</p><code>{expression}</code>` inside an `<li>`, so on a six-step
 * solution the reasoning and the algebra interleaved with no visual rhythm at all - and a
 * six-step solution is now the normal case, because D-207 serves the authored bank's own
 * `canonical_solution` instead of a generated two-step fallback.
 */
function SolutionContent({ intervention }: { intervention: InterventionContent }) {
  return (
    <>
      <div className="intervention-head">
        <h2>Solution</h2>
      </div>
      <ol className="solution-steps">
        {intervention.steps?.map((step) => (
          <li key={step.step_number} className="solution-step">
            <p className="step-explanation">{step.explanation}</p>
            {/* Some canonical steps close with an empty expression (the "the answer is 8
                weeks" step). Rendering an empty `<code>` box there is a stray artefact. */}
            {step.expression.trim() && <code className="step-expression">{step.expression}</code>}
            {step.common_mistake && (
              <p className="step-mistake">
                <strong>Watch out:</strong> {step.common_mistake}
              </p>
            )}
          </li>
        ))}
      </ol>
      <p className="solution-answer">
        <span className="solution-answer-label">Answer</span>
        <strong>{intervention.final_answer}</strong>
      </p>
    </>
  );
}

/**
 * A link card, not a bare anchor, and it says where it goes.
 *
 * Deliberately **not** an embedded player. An `<iframe>` would put a third-party frame
 * that can set cookies and autoplay in front of a minor, inside a page that otherwise
 * loads nothing external; that is a privacy decision, not a layout one, and it is not
 * this change's to make. The card carries the title and channel so the student knows what
 * they are about to open.
 */
function VideoContent({ intervention }: { intervention: InterventionContent }) {
  return (
    <>
      <div className="intervention-head">
        <h2>Video</h2>
      </div>
      {intervention.video_url ? (
        <a
          className="video-card"
          href={intervention.video_url}
          target="_blank"
          rel="noreferrer"
        >
          <span className="video-card-title">{intervention.video_title}</span>
          <span className="video-card-meta">
            {intervention.video_source} · opens in a new tab
          </span>
        </a>
      ) : (
        // The §5.11.6 fallback. It is a real answer ("nothing verified for this skill
        // yet"), so it reads as one rather than as an error.
        <p className="intervention-lead">{intervention.message}</p>
      )}
    </>
  );
}
