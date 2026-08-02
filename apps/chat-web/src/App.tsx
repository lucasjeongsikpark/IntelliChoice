import { useEffect, useState } from "react";
import "./App.css";
import * as api from "./api/client";
import { useChatSession } from "./hooks/useChatSession";
import type { ChatMeta, Role } from "./types";
import { DevLoginScreen } from "./screens/DevLoginScreen";
import { ChatScreen } from "./screens/ChatScreen";
import { EmailApprovalModal } from "./screens/EmailApprovalModal";
import { CalendarActionModal } from "./screens/CalendarActionModal";
import { LocationConsentModal } from "./screens/LocationConsentModal";

const TOKEN_KEY = "intellichoice.chat_token";
const SUB_KEY = "intellichoice.chat_sub";
const ROLE_KEY = "intellichoice.chat_role";
const GUEST_KEY = "intellichoice.chat_guest";

function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [sub, setSub] = useState<string | null>(() => localStorage.getItem(SUB_KEY));
  const [role, setRole] = useState<string | null>(() => localStorage.getItem(ROLE_KEY));
  const [isGuest, setIsGuest] = useState(() => localStorage.getItem(GUEST_KEY) === "1");
  const [loginBusy, setLoginBusy] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [meta, setMeta] = useState<ChatMeta | null>(null);

  const session = useChatSession(token);
  const {
    transcript,
    lastResponse,
    streamState,
    error,
    busy,
    sendMessage,
    retryTurn,
    respond,
    endSession,
  } = session;

  async function handleLogin(chosenRole: Role, chosenSub: string, stagingSecret: string) {
    setLoginBusy(true);
    setLoginError(null);
    try {
      const { token: newToken } = await api.devToken(chosenRole, chosenSub, stagingSecret);
      localStorage.setItem(TOKEN_KEY, newToken);
      localStorage.setItem(SUB_KEY, chosenSub);
      localStorage.setItem(ROLE_KEY, chosenRole);
      localStorage.removeItem(GUEST_KEY);
      setToken(newToken);
      setSub(chosenSub);
      setRole(chosenRole);
      setIsGuest(false);
    } catch (err) {
      setLoginError(err instanceof api.ApiError ? String(err.detail) : String(err));
    } finally {
      setLoginBusy(false);
    }
  }

  function handleContinueAsGuest() {
    localStorage.setItem(GUEST_KEY, "1");
    setIsGuest(true);
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(SUB_KEY);
    localStorage.removeItem(ROLE_KEY);
    localStorage.removeItem(GUEST_KEY);
    setToken(null);
    setSub(null);
    setRole(null);
    setIsGuest(false);
    endSession();
  }

  // SPEC §18-C3: `/chat/meta` is anonymous-OK, but there's nothing useful to show on
  // the dev-login screen itself - fetch once the caller is past it (guest or signed
  // in), refetching on role change since suggestions are role-aware. A fetch failure
  // just means no welcome card - never a user-facing error.
  useEffect(() => {
    if (!isGuest && !token) return;
    let cancelled = false;
    void api
      .getChatMeta(token)
      .then((result) => {
        if (!cancelled) setMeta(result);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [token, isGuest]);

  if (!isGuest && (!token || !sub || !role)) {
    return (
      <DevLoginScreen
        onLogin={handleLogin}
        onContinueAsGuest={handleContinueAsGuest}
        busy={loginBusy}
        error={loginError}
      />
    );
  }

  const who = token && role && sub ? `${role} (${sub})` : "guest";
  const pending = lastResponse?.pending_interrupt ?? null;

  return (
    <>
      <ChatScreen
        who={who}
        transcript={transcript}
        meta={meta}
        busy={busy || pending !== null}
        streamState={streamState}
        error={error}
        onSend={(query) => void sendMessage(query)}
        onRetry={(turnId) => void retryTurn(turnId)}
        onLogout={handleLogout}
        onNewSession={() => endSession()}
      />

      {pending?.interrupt_type === "email_approval" && (
        <EmailApprovalModal
          pending={pending}
          busy={busy}
          onApprove={(approved) =>
            void respond({ interrupt_type: "email_approval", approved })
          }
        />
      )}

      {pending?.interrupt_type === "calendar_action" && (
        <CalendarActionModal
          pending={pending}
          busy={busy}
          onChoose={(choice) => void respond({ interrupt_type: "calendar_action", choice })}
        />
      )}

      {pending?.interrupt_type === "location_consent" && (
        <LocationConsentModal
          pending={pending}
          busy={busy}
          onRespond={(body) => void respond(body)}
        />
      )}
    </>
  );
}

export default App;
