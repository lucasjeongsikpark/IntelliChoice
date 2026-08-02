import { useEffect, useRef, useState } from "react";
import type { ChatMeta, ChatTurn } from "../types";
import logoUrl from "../../../../packages/ui-brand/assets/logo.png";
import { AccessHintBanner } from "./AccessHintBanner";
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
                  {turn.response.answer}
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
                  {turn.response.escalation_recommended && (
                    <div className="escalation-banner">
                      I couldn't fully answer that - try asking to contact an
                      administrator for more help.
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
