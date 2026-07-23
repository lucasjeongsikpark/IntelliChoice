import type { AccessHint } from "../types";

interface Props {
  hint: AccessHint;
  onLogin: () => void;
}

// SPEC §18-C3: the backend-authored access-hint message, never the content itself
// (`chat_api.services.role_access.build_access_hint`) - a "log in" shortcut back to
// `DevLoginScreen` is the closest local equivalent to SPEC's "requires X login" example
// since this dev build has no real `go.intellichoice.org` login redirect to link to.
export function AccessHintBanner({ hint, onLogin }: Props) {
  return (
    <div className="access-hint-banner">
      <span>{hint.message}</span>
      <button className="link" type="button" onClick={onLogin}>
        Log in
      </button>
    </div>
  );
}
