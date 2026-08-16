import { useEffect, useRef, useState } from "react";
import type { ChatMeta, ChatTurn } from "../types";
import { MAX_QUERY_CHARS } from "../api/errors";
import logoUrl from "../../../../packages/ui-brand/assets/logo.png";
import { AccessHintBanner } from "./AccessHintBanner";
import { RichText } from "../components/RichText";
import { WelcomeCard } from "./WelcomeCard";

/**
 * D-352: two browser-fragility fixes in four lines.
 *
 * The anchor was never appended to the document, and `revokeObjectURL` ran on the line after
 * `click()` - synchronously, before the browser had necessarily started reading the blob.
 * Chromium tolerates both, which is why the e2e suite (Chromium-only) has been asserting the
 * button is *visible* and never that a download happens. Appending the anchor and revoking on
 * a later tick is the shape that works everywhere.
 */
const STREAM_LABELS: Record<string, string> = {
  idle: "Not connected yet",
  connecting: "Connecting to live updates",
  open: "Live updates connected",
  error: "Live updates disconnected",
};

function downloadIcs(icsContent: string) {
  const blob = new Blob([icsContent], { type: "text/calendar" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "intellichoice-event.ics";
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

interface Props {
  who: string;
  transcript: ChatTurn[];
  meta: ChatMeta | null;
  busy: boolean;
  streamState: "connecting" | "open" | "error";
  error: string | null;
  /** D-347: an interrupt type this build has no dialog for. See `App.tsx`. */
  unknownInterrupt: string | null;
  onSend: (query: string) => void;
  onRetry: (turnId: string) => void;
  /** D-352: stop the turn currently in flight. */
  onCancel: () => void;
  onEscalate: (query: string) => void;
  onLogout: () => void;
  /** D-353: sign in from an access hint, keeping the conversation. */
  onSignIn: () => void;
  onNewSession: () => void;
}

export function ChatScreen({
  who,
  transcript,
  meta,
  busy,
  streamState,
  error,
  unknownInterrupt,
  onSend,
  onRetry,
  onCancel,
  onEscalate,
  onLogout,
  onSignIn,
  onNewSession,
}: Props) {
  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  // Before the first turn there is no stream to be connecting to - see the dot's comment.
  const streamDotState = transcript.length === 0 ? "idle" : streamState;

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [transcript]);

  function submit() {
    const query = draft.trim();
    if (!query || busy) return;
    onSend(query);
    setDraft("");
  }

  return (
    <div className="chat-page">
      {/* D-350: `<header>`/`<main>` because chat-web had no landmark element anywhere - a
          screen-reader user had an `h1` and then an undifferentiated run of text. */}
      <header className="chat-header">
        <div className="chat-header-title">
          <img src={logoUrl} alt="IntelliChoice" className="app-logo" />
          <h1>IntelliChoice Q&amp;A</h1>
        </div>
        <div className="who">
          {/* D-350: the dot was an empty `<span>` whose only signal was colour - invisible
              to a screen reader and to a colour-blind reader alike. `idle` is a new state
              rather than a style: `streamState` initialises to "connecting" while the effect
              that opens the stream deliberately returns early until the first turn exists,
              so a fresh session showed an indefinite "connecting" dot for a connection that
              had never been attempted. Verified live before the fix (D-343). */}
          <span className={`stream-dot ${streamDotState}`} aria-hidden="true" />
          <span className="sr-only">{STREAM_LABELS[streamDotState]}</span>
          {who}
          {" · "}
          <button className="link" onClick={onNewSession}>
            new chat
          </button>
          {" · "}
          <button className="link" onClick={onLogout}>
            sign out
          </button>
        </div>
      </header>

      {/* D-350: the single biggest gap. An answer arriving changed the DOM with no
          announcement at all, so a screen-reader user had to hunt for it manually. The
          pattern is `learning-web`'s `TutorChatPanel`, which already did this correctly -
          the codebase disagreeing with itself rather than an open question. */}
      <main
        className="message-list"
        ref={listRef}
        role="log"
        aria-live="polite"
        aria-label="Conversation"
      >
        {transcript.length === 0 && (
          <>
            <p className="dim">
              Ask about branches, schedules, volunteering, student learning, parent
              information, or tutor/branch procedures.
            </p>
            <WelcomeCard meta={meta} onPromptClick={(prompt) => onSend(prompt)} />
          </>
        )}
        {transcript.map((turn) => (
          <div key={turn.id}>
            <div className="message-row user">
              <div className="bubble">{turn.query}</div>
            </div>
            {/* D-347: gated on `turn.response`, not `turn.response.answer`.
                The old gate produced a **completely blank assistant turn** whenever a
                response arrived with a null answer and no pending interrupt - the whole
                bubble vanished, including the citations, the escalation banner, the access
                hint and the follow-up chips that all live inside it, while `Thinking…`
                below was simultaneously suppressed because `turn.response` was non-null.
                Reachable in ordinary use: reload during a first turn restores a turn with
                `response: null`, the SSE initial snapshot lands with the checkpointed
                answer still unset, and the visitor is left with their own question and
                nothing under it. */}
            {turn.response && (
              <div className="message-row assistant">
                <div className="bubble">
                  {/* D-219: was raw text, so `**bold**` showed its asterisks and the
                      branch locator's "- " lines collapsed into one run. */}
                  {/* D-220: suppressed when the banner below is already saying it.
                      `explain_access` sets `answer = hint.message`, so an access-hint turn
                      rendered the same sentence twice - once here, once in
                      `AccessHintBanner` - which is what a logged-out parent actually saw
                      the first time this path was walked live. The API contract is left
                      alone deliberately: `answer` is what an SSE or non-browser client
                      reads, so it must keep carrying the text, and the duplication is a
                      rendering concern. Compared rather than assumed equal, so a backend
                      that ever writes a *different* answer alongside a hint still shows
                      both. */}
                  {turn.response.answer &&
                    turn.response.answer !== turn.response.access_hint?.message && (
                      <RichText text={turn.response.answer} />
                    )}
                  {/* The other half of the blank-turn fix: when the response carries no
                      answer *and* nothing else in this bubble would render, say so. Checked
                      against the same fields the bubble actually shows rather than against
                      `answer` alone, so a turn that has citations or a hint but no prose
                      keeps showing them instead of this line. */}
                  {!turn.response.answer &&
                    !turn.response.access_hint &&
                    turn.response.citations.length === 0 &&
                    !turn.response.escalation_recommended && (
                      <span className="dim">
                        No answer came back for that one. Try asking it again.
                      </span>
                    )}
                  {/* D-241: a citation is a *label*, not an action, and it used to be
                      impossible to tell. Measured on staging: `.citation-chip` and the
                      interactive `.chip` below rendered with the identical background
                      (`--accent-bg`) and the identical 999px pill radius, differing only
                      in text colour and 6px of height - so a source sat next to a
                      follow-up button looking like a second button, and clicking it did
                      nothing. Named and restyled rather than made clickable: these sources
                      are internal approved documents, and several have no URL to open. */}
                  {turn.response.citations.length > 0 && (
                    <div
                      className="citations"
                      aria-label={
                        turn.response.citations.length === 1
                          ? "Source for this answer"
                          : "Sources for this answer"
                      }
                    >
                      <span className="citations-label">
                        {turn.response.citations.length === 1 ? "Source" : "Sources"}
                      </span>
                      {turn.response.citations.map((c, i) => (
                        <span className="citation-chip" key={i}>
                          {c.document_title}
                          {c.section_title ? ` — ${c.section_title}` : ""}
                          {c.page_number ? `, p.${c.page_number}` : ""}
                        </span>
                      ))}
                    </div>
                  )}
                  {/* D-164: this used to read "try asking to contact an administrator",
                      which put the work back on the user and depended on the scope guard
                      classifying whatever they typed next as `admin_contact`. The answer
                      text already promises "I can pass this on to a branch manager if
                      you'd like"; the button is what makes that promise true. Gated on
                      `escalation_recommended`, which the backend sets False whenever it
                      returned an access hint instead - so "log in to see it" never comes
                      with an offer to email a human about content that already exists. */}
                  {turn.response.escalation_recommended && (
                    <div className="escalation-banner">
                      {/* D-219: one wording for two different outcomes. `escalation_
                          recommended` comes straight from the model, which sets it when it
                          could not answer *any part* of the question - so a half-answered
                          compound question got a cited answer with "I couldn't answer that
                          from an approved source" directly beneath it. Walked on staging
                          2026-08-08: a tutor-onboarding answer citing the Volunteer Guide,
                          sitting above a flat claim that nothing had been answered.
                          Citations are the honest discriminator here: the model can only
                          produce one by quoting a real approved passage. */}
                      <span>
                        {turn.response.citations.length > 0
                          ? "I couldn't answer all of that from an approved source."
                          : "I couldn't answer that from an approved source."}
                      </span>
                      <button
                        className="secondary escalate"
                        disabled={busy}
                        onClick={() => onEscalate(turn.query)}
                      >
                        Ask an administrator
                      </button>
                    </div>
                  )}
                  {turn.response.access_hint && (
                    <AccessHintBanner
                      hint={turn.response.access_hint}
                      onLogin={onSignIn}
                    />
                  )}
                  {turn.response.ics_content && (
                    <button
                      className="secondary ics-download"
                      onClick={() => downloadIcs(turn.response!.ics_content!)}
                    >
                      Download .ics
                    </button>
                  )}
                  {turn.response.suggested_followups.length > 0 && (
                    <div className="suggestion-chips">
                      {turn.response.suggested_followups.map((prompt) => (
                        <button
                          key={prompt}
                          className="chip"
                          type="button"
                          disabled={busy}
                          onClick={() => onSend(prompt)}
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
            {/* AUD-C-10: `Thinking…` is now gated on the turn *not* having failed.
                Before, `!turn.response` covered both in-flight and failed, so any 500,
                409, 401 or dropped connection left this bubble on screen permanently -
                a §2.6 criterion-3 stuck state reachable from the most ordinary failure
                there is. */}
            {!turn.response && !turn.error && (
              <div className="message-row assistant">
                <div className="bubble dim" role="status">
                  Thinking…
                  {/* D-352: an answer takes 6-11s (measured live, D-343) with the composer
                      disabled throughout, and until now there was no way out of that but a
                      page reload - which then landed on the blank-turn path. */}
                  <button
                    className="link cancel-turn"
                    type="button"
                    onClick={onCancel}
                  >
                    Stop
                  </button>
                </div>
              </div>
            )}
            {/* A stopped turn is not a failed one: no `role="alert"`, no apology, and the
                action is "ask again" rather than "try again". */}
            {!turn.response && turn.cancelled && (
              <div className="message-row assistant">
                <div className="bubble dim">
                  {turn.error}
                  <button
                    className="secondary retry"
                    type="button"
                    disabled={busy}
                    onClick={() => onRetry(turn.id)}
                  >
                    Ask again
                  </button>
                </div>
              </div>
            )}
            {!turn.response && turn.error && !turn.cancelled && (
              <div className="message-row assistant">
                <div className="bubble turn-error" role="alert">
                  That message couldn't be sent. {turn.error}
                  <button
                    className="secondary retry"
                    type="button"
                    disabled={busy}
                    onClick={() => onRetry(turn.id)}
                  >
                    Try again
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </main>

      {unknownInterrupt && (
        <div className="escalation-banner" role="alert">
          <span>
            This conversation is waiting on something this version of the app can't show you.
            Start a new chat to carry on.
          </span>
          <button className="secondary" type="button" onClick={onNewSession}>
            Start a new chat
          </button>
        </div>
      )}

      {error && <p className="error">{error}</p>}

      <div className="composer">
        {/* D-350: no label, no `aria-label`, no `id` - Chrome DevTools flagged it live as
            "a form field element should have an id or name attribute". Every other input in
            this app is wrapped in `label.field`; the one people actually type into was not. */}
        <label className="sr-only" htmlFor="chat-composer">
          Ask a question
        </label>
        <textarea
          id="chat-composer"
          name="chat-composer"
          value={draft}
          // D-378: the browser stops this before the server has to. The 422 rule in
          // `errors.ts` stays as the backstop for anything that bypasses the control -
          // this is the half that means a visitor never reaches an error they cannot act on.
          maxLength={MAX_QUERY_CHARS}
          placeholder="Ask a question…"
          disabled={busy}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <button disabled={busy || !draft.trim()} onClick={submit}>
          Send
        </button>
      </div>
    </div>
  );
}
