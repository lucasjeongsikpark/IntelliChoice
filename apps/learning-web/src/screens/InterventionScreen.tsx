import { useState } from "react";
import { RichText } from "../components/RichText";
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
  // D-272: the id of the question this help is about, from `snapshot.assistance_question`.
  // It used to be `pending.question_variant_id`, which is absent on a `/respond`-resumed
  // ladder round (S21's documented gap) - and since this prop decides whether the chat
  // renders at all, the tutor silently vanished from every round after the first.
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
  // D-216: a refused/failed choice used to show nothing at all on this panel - the same
  // `session.error` the exam screen renders.
  error: string | null;
}

/**
 * The right-hand column of the study screen: the help, and the tutor.
 *
 * ### D-272: two modes, not one stack
 *
 * The chat used to sit at the *bottom* of this panel, under the hint text and four
 * buttons, inside a 220px scroll box. On a real conversation that is three visible
 * messages, below the fold, on a panel that already had a hint on it.
 *
 * It is now a mode of the column rather than a section of it: a segmented control at the
 * top switches between **Help** and **Tutor**, and the chat gets the column's full height.
 *
 * **Deliberately not a tab strip over Hint / Solution / Video.** Those are not views. Each
 * one spends a Bedrock call, and "Show the solution" permanently changes the attempt's
 * outcome label (SPEC §5.11.5: a later correct answer becomes `correct_after_solution`).
 * Making an irreversible, paid, graded action look like switching tabs would be a lie about
 * what a click does. Switching to the tutor costs nothing, so that one *is* a view.
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
  error,
}: AssistancePanelProps) {
  // Local because it is about this render of this column, not about the session. It
  // survives the ladder (the panel keeps its position in the grid while help is open) and
  // resets when help closes, which is what should happen - a new question starts on Help.
  const [view, setView] = useState<"help" | "tutor">("help");
  const chatAvailable = questionVariantId !== null;
  const showing = chatAvailable ? view : "help";

  return (
    <div className="intervention-panel">
      {chatAvailable && (
        <div className="assistance-modes" role="tablist" aria-label="Help or tutor">
          <button
            role="tab"
            aria-selected={showing === "help"}
            className={`assistance-mode ${showing === "help" ? "active" : ""}`}
            onClick={() => setView("help")}
          >
            Help
          </button>
          <button
            role="tab"
            aria-selected={showing === "tutor"}
            className={`assistance-mode ${showing === "tutor" ? "active" : ""}`}
            onClick={() => setView("tutor")}
          >
            Ask your tutor
            {/* So a student who switched away can see a reply landed without switching back. */}
            {chat.messages.length > 0 && (
              <span className="assistance-mode-count">{chat.messages.length}</span>
            )}
          </button>
        </div>
      )}

      {showing === "tutor" && questionVariantId ? (
        <TutorChatPanel
          questionVariantId={questionVariantId}
          onSendMessage={onSendChatMessage}
          transcript={chat}
        />
      ) : (
        <HelpView
          intervention={intervention}
          ladderOpen={ladderOpen}
          busy={busy}
          error={error}
          onChoose={onChoose}
          onDismiss={onDismiss}
        />
      )}
    </div>
  );
}

function HelpView({
  intervention,
  ladderOpen,
  busy,
  error,
  onChoose,
  onDismiss,
}: {
  intervention: InterventionContent | null;
  ladderOpen: boolean;
  busy: boolean;
  error: string | null;
  onChoose: (choice: Choice) => void;
  onDismiss: () => void;
}) {
  if (!intervention) {
    return (
      <>
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
      </>
    );
  }

  const isHint = intervention.type === "hint";
  const atFinalLevel =
    intervention.hint_level != null &&
    intervention.max_hint_level != null &&
    intervention.hint_level >= intervention.max_hint_level;

  return (
    <>
      {intervention.type === "hint" && <HintContent intervention={intervention} />}
      {intervention.type === "solution" && <SolutionContent intervention={intervention} />}
      {intervention.type === "video" && <VideoContent intervention={intervention} />}

      {error && <p className="error">{error}</p>}

      {ladderOpen ? (
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
          {/* The pause can now be open on content that is *not* a hint: §5.11.6's "no video
              for this skill" panel reopens it (`nodes.intervention_choice`) so that the two
              options its own message names stay reachable. Without this branch the reopened
              panel offered the solution and not the hint, so the sentence "You may choose a
              hint or step-by-step solution instead" was still half wrong - which is how the
              first version of this fix looked correct in a screenshot and was not.
              No level arithmetic here on purpose: this panel does not know the ladder
              position (the server keeps it in `assistance_level_by_variant`), and
              `_hint_round` clamps the requested level to the ladder's length, so the worst
              case is the deepest rung served again rather than a rung that does not exist. */}
          {!isHint && (
            <button disabled={busy} onClick={() => onChoose("hint")}>
              Get a hint
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
      ) : (
        <button className="secondary" onClick={onDismiss}>
          Got it — next question
        </button>
      )}
    </>
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

      {/* D-217: through RichText so the model's bold/inline-code/line-breaks render as
          formatting rather than literal characters, and so a multi-line hint keeps its
          breaks (these `<p>`s had no `white-space: pre-line`, unlike the chat bubble). */}
      <p className="intervention-lead">
        <RichText text={intervention.hint_text ?? ""} />
      </p>
      {intervention.concept_reminder && (
        <div className="intervention-aside">
          <h3>Remember</h3>
          <p>
            <RichText text={intervention.concept_reminder} />
          </p>
        </div>
      )}
      {intervention.next_step_prompt && (
        <div className="intervention-aside">
          <h3>Try this next</h3>
          <p>
            <RichText text={intervention.next_step_prompt} />
          </p>
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
            <p className="step-explanation">
              <RichText text={step.explanation} />
            </p>
            {/* Some canonical steps close with an empty expression (the "the answer is 8
                weeks" step). Rendering an empty `<code>` box there is a stray artefact. */}
            {step.expression.trim() && <code className="step-expression">{step.expression}</code>}
            {step.common_mistake && (
              <p className="step-mistake">
                <strong>Watch out:</strong> <RichText text={step.common_mistake} />
              </p>
            )}
          </li>
        ))}
      </ol>
      <p className="solution-answer">
        <span className="solution-answer-label">Answer</span>
        <strong>{intervention.final_answer}</strong>
      </p>
      {/* D-272: one self-explanation prompt after the worked solution. Rendered client-side,
          so it costs nothing and cannot say anything wrong - and asking a student to put the
          method in their own words is the single best-evidenced thing you can do with a
          worked example (Chi et al.'s self-explanation effect). No input box: the value is
          in the pause and the attempt, and a text field here would look like something that
          gets graded. */}
      <p className="self-explain">
        Before you move on — how would you explain this one to a friend?
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
