import { useCallback, useEffect, useState } from "react";
import "./App.css";
import * as api from "./api/client";
import { friendlyError } from "./api/errors";
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

/**
 * D-347: a token and the guest flag must not both be set, and nothing enforced that.
 *
 * `handleLogin` and `handleLogout` keep them consistent, but neither is involved when the
 * keys are written from outside the app - which the e2e fixtures do on every run
 * (`seedSession` writes the three token keys, `seedGuest` writes only the flag) and which a
 * human debugging on staging does by hand. With both present, `App` skipped the login screen
 * *and* passed the stale token to every request, so a session that looked like a guest
 * 401'd on every turn with no way to see why.
 *
 * The token wins: it is the more specific state, and a stale one now self-clears on its
 * first 401 (`handleSignedOut`) rather than looping.
 */
function reconcileStoredIdentity(): void {
  if (localStorage.getItem(TOKEN_KEY) && localStorage.getItem(GUEST_KEY)) {
    localStorage.removeItem(GUEST_KEY);
  }
}

// At import time, which is after the e2e fixtures' `addInitScript` has written storage and
// before any `useState` initialiser below reads it.
reconcileStoredIdentity();

function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [sub, setSub] = useState<string | null>(() => localStorage.getItem(SUB_KEY));
  const [role, setRole] = useState<string | null>(() => localStorage.getItem(ROLE_KEY));
  const [isGuest, setIsGuest] = useState(() => localStorage.getItem(GUEST_KEY) === "1");
  const [loginBusy, setLoginBusy] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [meta, setMeta] = useState<ChatMeta | null>(null);

  // D-347: what a 401 does. The four keys go, so the next request is anonymous instead of
  // repeating an invalid token forever, and the login screen comes back. The *transcript*
  // deliberately survives: `endSession()` is not called here, because losing the
  // conversation is a second punishment for an expiry the visitor did not cause. The session
  // id survives too and that is safe - it was created under the expired token, so the server
  // will 403 an anonymous caller on it, and `ensureSession` mints a new one for the next
  // question. (D-353 replaces that quiet 403 with a deliberate reset.)
  const handleSignedOut = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(SUB_KEY);
    localStorage.removeItem(ROLE_KEY);
    localStorage.removeItem(GUEST_KEY);
    setToken(null);
    setSub(null);
    setRole(null);
    setIsGuest(false);
  }, []);

  const session = useChatSession(token, sub, handleSignedOut);
  const {
    transcript,
    lastResponse,
    streamState,
    reconnectStream,
    error,
    busy,
    sendMessage,
    escalateTurn,
    retryTurn,
    respond,
    cancelTurn,
    resetSessionKeepTranscript,
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
      // The one place that keeps the raw detail alongside the friendly line, because
      // `DevLoginScreen` matches on "Not Found" to show the `aws secretsmanager` recovery
      // hint - a staging-operator affordance, not a visitor-facing message.
      setLoginError(
        err instanceof api.ApiError && err.status === 404
          ? String(err.detail)
          : friendlyError(err),
      );
    } finally {
      setLoginBusy(false);
    }
  }

  // D-353: what "Log in" on an access hint does now. Deliberately *not* `handleLogout`,
  // which was wired here and destroyed the conversation the hint was about.
  function handleSignInFromHint() {
    localStorage.removeItem(GUEST_KEY);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(SUB_KEY);
    localStorage.removeItem(ROLE_KEY);
    setToken(null);
    setSub(null);
    setRole(null);
    setIsGuest(false);
    resetSessionKeepTranscript();
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

  // D-219: the external id used to ride along - "branch_manager (branch_manager-ext-1)".
  // That is an internal identifier printed at the person it identifies, the same thing
  // D-218 removed from the learning app's start screen and dashboard. The role is the part
  // that means something to the reader: it is what decides which documents they can see.
  const who = token && role ? role.replace(/_/g, " ") : "guest";
  const pending = lastResponse?.pending_interrupt ?? null;
  // D-347: the composer used to be disabled for *any* non-null `pending_interrupt`, while
  // only these three types have a dialog. A fourth interrupt type added server-side would
  // therefore lock the composer with no modal, no prompt and no way to answer the thing
  // being waited on - a hard deadlock whose only exits are "new chat" (which discards the
  // conversation) and "sign out". `response-shapes.spec.ts` records that it tests the known
  // types only, so nothing would have caught it. Locking on *known* types keeps the
  // interlock exactly as strict where a dialog exists, and degrades to a visible notice
  // where one does not.
  const KNOWN_INTERRUPTS = ["email_approval", "calendar_action", "location_consent"];
  const pendingIsKnown = pending !== null && KNOWN_INTERRUPTS.includes(pending.interrupt_type);
  const pendingIsUnknown = pending !== null && !pendingIsKnown;

  return (
    <>
      <ChatScreen
        who={who}
        transcript={transcript}
        meta={meta}
        busy={busy || pendingIsKnown}
        streamState={streamState}
        onReconnect={reconnectStream}
        error={error}
        unknownInterrupt={pendingIsUnknown ? pending.interrupt_type : null}
        onSend={(query) => void sendMessage(query)}
        onRetry={(turnId) => void retryTurn(turnId)}
        onCancel={cancelTurn}
        onEscalate={(query) => void escalateTurn(query)}
        onLogout={handleLogout}
        onSignIn={handleSignInFromHint}
        onNewSession={() => endSession()}
      />

      {pending?.interrupt_type === "email_approval" && (
        <EmailApprovalModal
          pending={pending}
          busy={busy}
          error={error}
          onApprove={(approved, note) =>
            void respond({ interrupt_type: "email_approval", approved, note })
          }
        />
      )}

      {pending?.interrupt_type === "calendar_action" && (
        <CalendarActionModal
          pending={pending}
          busy={busy}
          error={error}
          onChoose={(choice) => void respond({ interrupt_type: "calendar_action", choice })}
        />
      )}

      {pending?.interrupt_type === "location_consent" && (
        <LocationConsentModal
          pending={pending}
          busy={busy}
          error={error}
          onRespond={(body) => void respond(body)}
        />
      )}
    </>
  );
}

export default App;
