import { useEffect, useRef, useState } from "react";
import type { ChatMeta, ChatTurn } from "../types";
import logoUrl from "../../../../packages/ui-brand/assets/logo.png";
import { AccessHintBanner } from "./AccessHintBanner";
import { RichText } from "../components/RichText";
import { WelcomeCard } from "./WelcomeCard";

function downloadIcs(icsContent: string) {
  const blob = new Blob([icsContent], { type: "text/calendar" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "intellichoice-event.ics";
  link.click();
  URL.revokeObjectURL(url);
}

interface Props {
  who: string;
  transcript: ChatTurn[];
  meta: ChatMeta | null;
  busy: boolean;
  streamState: "connecting" | "open" | "error";
  error: string | null;
  onSend: (query: string) => void;
  onRetry: (turnId: string) => void;
  onEscalate: (query: string) => void;
  onLogout: () => void;
  onNewSession: () => void;
}

export function ChatScreen({
  who,
  transcript,
  meta,
  busy,
  streamState,
  error,
  onSend,
  onRetry,
  onEscalate,
  onLogout,
  onNewSession,
}: Props) {
  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

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
      <div className="chat-header">
        <div className="chat-header-title">
          <img src={logoUrl} alt="IntelliChoice" className="app-logo" />
          <h1>IntelliChoice Q&amp;A</h1>
        </div>
        <div className="who">
          <span className={`stream-dot ${streamState}`} />
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
      </div>

      <div className="message-list" ref={listRef}>
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
            {turn.response?.answer && (
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
                  {turn.response.answer !== turn.response.access_hint?.message && (
                    <RichText text={turn.response.answer} />
                  )}
                  {turn.response.citations.length > 0 && (
                    <div className="citations">
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
                      onLogin={onLogout}
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
                <div className="bubble dim">Thinking…</div>
              </div>
            )}
            {!turn.response && turn.error && (
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

      {error && <p className="error">{error}</p>}

      <div className="composer">
        <textarea
          value={draft}
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
