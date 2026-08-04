import { useState } from "react";
import type { Role } from "../types";
import logoUrl from "../../../../packages/ui-brand/assets/logo.png";

const FIXTURE_IDS: { label: string; role: Role; sub: string }[] = [
  { label: "Student — Ava Only", role: "student", sub: "student-ext-1" },
  { label: "Parent — Priya One (1 linked child)", role: "parent", sub: "parent-ext-1" },
  { label: "Parent — Paul Two (2 linked children)", role: "parent", sub: "parent-ext-2" },
  { label: "Tutor", role: "tutor", sub: "tutor-ext-1" },
  { label: "Branch Manager", role: "branch_manager", sub: "branch_manager-ext-1" },
];

/**
 * `localStorage`, not `sessionStorage` - see the twin comment in
 * `apps/learning-web/src/screens/DevLoginScreen.tsx` for the full reasoning behind the
 * reversal and the threat model it accepts. Short version: per-tab expiry deterred nobody
 * (the value gets typed back in from Secrets Manager anyway) and taxed every manual staging
 * check, and the exposure that matters is the D-097 gate, which stays intact.
 *
 * Per-app by design (D-097) - chat's secret is a different value from learning's, so the two
 * keys must not be shared. Same-origin storage makes that concrete: pasting learning's secret
 * here yields a 404 indistinguishable from having pasted nothing.
 */
const STAGING_SECRET_KEY = "intellichoice.chat_staging_token_secret";

interface Props {
  onLogin: (role: Role, sub: string, stagingSecret: string) => void;
  onContinueAsGuest: () => void;
  busy: boolean;
  error: string | null;
}

export function DevLoginScreen({ onLogin, onContinueAsGuest, busy, error }: Props) {
  const [role, setRole] = useState<Role>("parent");
  const [sub, setSub] = useState("parent-ext-1");
  const [stagingSecret, setStagingSecret] = useState(
    () => localStorage.getItem(STAGING_SECRET_KEY) ?? "",
  );

  function submit() {
    // Remembered only on an actual attempt, so a half-typed value is not persisted.
    // Clearing the field and submitting is also the way to erase a stored secret.
    if (stagingSecret) localStorage.setItem(STAGING_SECRET_KEY, stagingSecret);
    else localStorage.removeItem(STAGING_SECRET_KEY);
    onLogin(role, sub, stagingSecret);
  }

  return (
    <div className="panel">
      <img src={logoUrl} alt="IntelliChoice" className="login-logo" />
      <h1>IntelliChoice Q&amp;A</h1>
      <p className="subtitle">
        SPEC §5.19.1: anonymous access covers FAQ, branch locator, calendar, and admin
        contact. Sign in for role-gated documents (parent/student handbooks, tutor
        procedures, branch-manager manuals). Dev sign-in mints a token via{" "}
        <code>POST /dev/token</code>, standing in for the real go.intellichoice.org auth.
      </p>

      <label className="field">
        <span>Fixture account</span>
        <select
          onChange={(e) => {
            const fixture = FIXTURE_IDS[Number(e.target.value)];
            if (fixture) {
              setRole(fixture.role);
              setSub(fixture.sub);
            }
          }}
          defaultValue=""
        >
          <option value="" disabled>
            Choose a seeded fixture…
          </option>
          {FIXTURE_IDS.map((f, i) => (
            <option key={f.sub} value={i}>
              {f.label}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span>Role</span>
        <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
          <option value="student">student</option>
          <option value="parent">parent</option>
          <option value="tutor">tutor</option>
          <option value="branch_manager">branch_manager</option>
        </select>
      </label>

      <label className="field">
        <span>External id</span>
        <input value={sub} onChange={(e) => setSub(e.target.value)} />
      </label>

      {/* Only needed on a deployed environment (D-097). Left blank locally, where
          `/dev/token` takes its `environment=="dev"` path and ignores the header - so
          there is nothing to configure and nothing that can silently point the wrong way.
          `type="password"` because this screen is screenshotted by the e2e harness on
          failure, and a secret in an artifact is AUD-F-13's shape. */}
      <label className="field">
        <span>Staging secret (leave blank locally)</span>
        <input
          type="password"
          autoComplete="off"
          placeholder="X-Staging-Token-Secret"
          value={stagingSecret}
          onChange={(e) => setStagingSecret(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && sub && !busy) submit();
          }}
        />
      </label>

      {error && <p className="error">{error}</p>}
      {/* A 404 here means the secret is missing or wrong - D-097 returns 404 for both on
          purpose, so a caller learns nothing about whether the endpoint is configured. */}
      {error?.includes("Not Found") && (
        <p className="subtitle">
          On staging this means the secret above is missing or wrong. Retrieve it with:{" "}
          <code>
            aws secretsmanager get-secret-value --secret-id
            intellichoice-staging/chat-api/staging-token-shared-secret --query SecretString
            --output text
          </code>
        </p>
      )}

      <button disabled={busy || !sub} onClick={submit}>
        {busy ? "Signing in…" : "Sign in"}
      </button>
      <button className="secondary" disabled={busy} onClick={onContinueAsGuest}>
        Continue as guest
      </button>
    </div>
  );
}
