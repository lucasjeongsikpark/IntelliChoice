import { useEffect, useRef, useState } from "react";
import type { ChatMeta, ChatTurn, TurnSnapshot } from "../types";
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

/** How many sources sit inline before the rest are collapsed (D-382). Three is the point at
 *  which the chips start wrapping onto a second row in the 720px column. */
const INLINE_CITATIONS = 3;

function citationLabel(c: TurnSnapshot["citations"][number]): string {
  return (
    c.document_title +
    (c.section_title ? ` — ${c.section_title}` : "") +
    (c.page_number ? `, p.${c.page_number}` : "")
  );
}

/**
 * Follow-up chips worth showing: on topic by construction, and not something the visitor has
 * already asked (D-382).
 *
 * The server picks these from a small hand-authored pool by category, and **that pool is 14
 * rows, 7 of them visible to a guest** — so after two or three turns the same generic prompts
 * came back every time, including ones the visitor had just used. Filtering against the
 * transcript is done here rather than server-side for a concrete reason: `QAState` carries
 * only the current turn, so the conversation is something the *client* holds and the server
 * does not. `_suggested_followups` can only exclude the single query it was passed.
 *
 * This makes the chips stop repeating. It does not make them conversation-*aware* — that
 * needs a larger pool or generated candidates validated against what retrieval can actually
 * answer, which is a design decision rather than a filter. Recorded in D-382.
 */
function unaskedFollowups(prompts: string[], transcript: ChatTurn[]): string[] {
  const asked = new Set(transcript.map((t) => t.query.trim().toLowerCase()));
  return prompts.filter((p) => !asked.has(p.trim().toLowerCase()));
}

/**
 * Whether a snapshot describes a turn that has **finished**, as opposed to one the server is
 * still working on (D-379).
 *
 * **The defect this closes.** `resolve_role` clears `answer`, `citations`, `reason` and the
 * rest at turn *start*, while `client_turn_id` is already in the checkpoint. `/stream` emits
 * its initial snapshot on every connect with no "is a turn running?" guard, so a reload two
 * seconds into a 6-11s question restored a turn whose response was present and empty. D-348's
 * matcher found the id, matched confidently, and committed it - and the bubble rendered *"No
 * answer came back for that one. Try asking it again."* Following that instruction produced a
 * 409, and seconds later the real answer overwrote the refusal.
 *
 * In a product where a refusal is a first-class outcome, that **fabricates one** and instructs
 * an action that fails.
 *
 * `reason` is the discriminator and it is server-authored: cleared to null on entry, and set
 * by every terminal node (`ANSWER`, `NO_APPROVED_SOURCE`, `OUT_OF_SCOPE`, `ACCESS_REQUIRED`,
 * `POLICY_RESTRICTED`, `NEEDS_CLARIFICATION`, `HUMAN_ACTION_REQUIRED`, `SYSTEM_ERROR`). So
 * `reason === null` means "not finished" rather than "finished with nothing to say".
 *
 * D-351 added that field describing it as *"the field a client should branch on"* and no
 * component read it. This is the first one.
 *
 * The fallbacks matter for old checkpoints: a session checkpointed before `reason` existed has
 * none, so anything else that renders is also accepted as evidence the turn completed.
 */
function isFinishedTurn(response: TurnSnapshot): boolean {
  return (
    response.reason !== null ||
    Boolean(response.answer) ||
    Boolean(response.access_hint) ||
    response.citations.length > 0 ||
    response.escalation_recommended ||
    Boolean(response.pending_interrupt)
  );
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
  const composerRef = useRef<HTMLTextAreaElement>(null);
  // Before the first turn there is no stream to be connecting to - see the dot's comment.
  const streamDotState = transcript.length === 0 ? "idle" : streamState;

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [transcript]);

  // D-381: put focus back in the composer when the turn finishes. The textarea is `disabled`
  // while busy, and disabling the focused element moves focus to `<body>` - so after every
  // send a keyboard-only visitor had to Tab past "new chat", "sign out" and every follow-up
  // chip in the transcript to ask a second question. Measured live: seven presses on a
  // two-turn conversation, and it grows with the conversation.
  //
  // Guarded on the composer being enabled and nothing else holding focus, so this cannot
  // steal focus from an approval dialog that opened as the turn paused.
  useEffect(() => {
    if (busy) return;
    const active = document.activeElement;
    const focusIsLoose = active === null || active === document.body;
    if (focusIsLoose && composerRef.current?.disabled === false) {
      composerRef.current.focus({ preventScroll: true });
    }
  }, [busy]);

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
          {/* D-381: a guest is not signed in, so "sign out" was both meaningless and
              destructive - `handleLogout` calls `endSession()`, so it silently binned the
              conversation of someone who had never signed in to anything, with no
              confirmation and no undo. "New chat" beside it already does the one thing they
              might have wanted. Signing *in* is the action a guest can actually take, and it
              is the one the access hint offers, so this offers the same. */}
          {who === "guest" ? (
            // "sign in", not "log in" — symmetric with the "sign out" it replaces, and
            // deliberately *not* the same words as `AccessHintBanner`'s "Log in". Two
            // controls with an identical accessible name, doing the same thing, on screen at
            // once is a thing to avoid on its own; it also made
            // `getByRole("button", {name: /^log in$/i})` ambiguous, which is how the
            // duplication announced itself.
            <button className="link" onClick={onSignIn}>
              sign in
            </button>
          ) : (
            <button className="link" onClick={onLogout}>
              sign out
            </button>
          )}
        </div>
      </header>

      {/* D-350: the single biggest gap. An answer arriving changed the DOM with no
          announcement at all, so a screen-reader user had to hunt for it manually. The
          pattern is `learning-web`'s `TutorChatPanel`, which already did this correctly -
          the codebase disagreeing with itself rather than an open question. */}
      {/* D-381: `role="log"` sits on an inner element, not on `<main>`. An explicit role
          *replaces* the implicit one, so putting `log` on `<main>` removed the page's only
          main landmark - the exact thing D-350 added `<main>` for. A screen-reader user's
          "skip to main content" had nothing to skip to. Both properties are real now: the
          landmark is the element, the live region is the list inside it. */}
      <main className="chat-main">
        <div
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
            {turn.response && isFinishedTurn(turn.response) && (
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
                  {/* D-379: reachable only for a turn that genuinely finished with nothing
                      renderable - `isFinishedTurn` above keeps an in-flight snapshot out of
                      this bubble entirely, which is what used to manufacture a refusal.

                      D-381: **except a paused one, which is how the refusal came back.**
                      `isFinishedTurn` counts `pending_interrupt` as finished (line 91) so the
                      bubble renders - but a paused turn has nothing else in it, because
                      `resolve_role` clears `answer`/`reason`/`citations`/`access_hint` at turn
                      entry and a node that pauses on `interrupt()` never returns. So every
                      field this guard tests is empty *by construction* while the consent or
                      approval dialog is still open, and the visitor read "no answer came back,
                      try asking it again" underneath a question the server was mid-way through.
                      Following that instruction spends a second paid turn. Observed live on
                      both the location-consent and email-approval paths, 2026-08-16. */}
                  {!turn.response.answer &&
                    !turn.response.access_hint &&
                    turn.response.citations.length === 0 &&
                    !turn.response.escalation_recommended &&
                    (turn.response.pending_interrupt ? (
                      /* Wording matches errors.ts's 409 rule ("Answer the prompt above first,
                         then you can carry on"), so the transcript and the error the composer
                         would show describe the same situation in the same words. */
                      <span className="dim" role="status">
                        Waiting for your answer to the prompt above.
                      </span>
                    ) : (
                      <span className="dim">
                        No answer came back for that one. Try asking it again.
                      </span>
                    ))}
                  {/* D-241: a citation is a *label*, not an action, and it used to be
                      impossible to tell. Measured on staging: `.citation-chip` and the
                      interactive `.chip` below rendered with the identical background
                      (`--accent-bg`) and the identical 999px pill radius, differing only
                      in text colour and 6px of height - so a source sat next to a
                      follow-up button looking like a second button, and clicking it did
                      nothing. Named and restyled rather than made clickable: these sources
                      are internal approved documents, and several have no URL to open. */}
                  {/* D-382: the first few inline, the rest behind a disclosure. Six sources
                      rendered as six wrapping chips built a block as tall as the answer, so
                      the thing the visitor asked for sat above a wall of document titles.
                      Nothing is hidden from them - the summary states the count and opens
                      with a keypress - but provenance stops outweighing the answer. */}
                  {turn.response.citations.length > 0 && (
                    <>
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
                        {turn.response.citations.slice(0, INLINE_CITATIONS).map((c, i) => (
                          <span className="citation-chip" key={i}>
                            {citationLabel(c)}
                          </span>
                        ))}
                      </div>
                      {turn.response.citations.length > INLINE_CITATIONS && (
                        <details className="citations-more">
                          <summary>
                            {turn.response.citations.length - INLINE_CITATIONS} more source
                            {turn.response.citations.length - INLINE_CITATIONS === 1 ? "" : "s"}
                          </summary>
                          <div className="citations">
                            {turn.response.citations.slice(INLINE_CITATIONS).map((c, i) => (
                              <span className="citation-chip" key={i}>
                                {citationLabel(c)}
                              </span>
                            ))}
                          </div>
                        </details>
                      )}
                    </>
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
                      {/* D-379: the client stopped re-deriving what the server already
                          said. `reason` is the field D-351 added *"to branch on"*, and this
                          banner was the last place still inferring from
                          `escalation_recommended` + `citations.length` - the exact triple
                          AUD-C-19 was about.

                          Two outcomes it got wrong. On `sources_conflict` the server answers
                          "The documents I found disagree with each other on this, so I don't
                          want to guess" **with verified citations attached**, and this line
                          added "I couldn't answer all of that from an approved source"
                          underneath - contradicting the sentence above it, because sources
                          were found and nothing was partly answered. On
                          `no_approved_source` the server's own answer already says it, so
                          the visitor read the same refusal twice in two phrasings.

                          Suppressed whenever the server wrote prose of its own, on the same
                          reasoning D-220 used for the access hint: the API keeps carrying the
                          text for non-browser clients, and the de-duplication is a rendering
                          concern. The fallback line survives for a turn that recommends
                          escalation with nothing written. */}
                      <span>
                        {turn.response.answer
                          ? null
                          : turn.response.citations.length > 0
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
                  {unaskedFollowups(turn.response.suggested_followups, transcript).length > 0 && (
                    <div className="suggestion-chips">
                      {unaskedFollowups(turn.response.suggested_followups, transcript).map((prompt) => (
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
            {(!turn.response || !isFinishedTurn(turn.response)) && !turn.error && !turn.cancelled && (
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
        </div>
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
          ref={composerRef}
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
      {/* D-381: `maxLength` silently swallows anything past the limit - paste a long
          question and the tail vanishes with no notice at all, which is worse than the 422
          it replaced because nothing tells the visitor their question was shortened. Shown
          only as the limit approaches, so it is not permanent clutter on a one-line ask. */}
      {draft.length >= MAX_QUERY_CHARS * 0.9 && (
        <p className="dim composer-count" role="status">
          {draft.length === MAX_QUERY_CHARS
            ? `Maximum length reached (${MAX_QUERY_CHARS} characters). Anything longer will not be included.`
            : `${MAX_QUERY_CHARS - draft.length} characters left.`}
        </p>
      )}
    </div>
  );
}
