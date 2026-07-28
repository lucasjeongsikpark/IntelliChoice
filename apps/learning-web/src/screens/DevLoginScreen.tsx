import { useState } from "react";
import type { Role } from "../types";
import logoUrl from "../../../../packages/ui-brand/assets/logo.png";

const FIXTURE_IDS: { label: string; role: Role; sub: string }[] = [
  { label: "Student — Ava Only (present, 1 parent)", role: "student", sub: "student-ext-1" },
  { label: "Student — Ben First (absent this week)", role: "student", sub: "student-ext-2" },
  { label: "Student — Drew Unlinked (present, no parent)", role: "student", sub: "student-ext-4" },
  { label: "Parent — Priya One (1 linked child)", role: "parent", sub: "parent-ext-1" },
  { label: "Parent — Paul Two (2 linked children)", role: "parent", sub: "parent-ext-2" },
];

/**
 * Kept in `sessionStorage`, not `localStorage`: this secret mints a token for **any** role
 * on a deployed environment, so it should not outlive the tab. Surviving a refresh is the
 * whole point (the screen is the first thing a reload lands on); surviving a closed browser
 * is not worth it.
 */
const STAGING_SECRET_KEY = "intellichoice.staging_token_secret";

interface Props {
  onLogin: (role: Role, sub: string, stagingSecret: string) => void;
  busy: boolean;
  error: string | null;
}

export function DevLoginScreen({ onLogin, busy, error }: Props) {
  const [role, setRole] = useState<Role>("student");
  const [sub, setSub] = useState("student-ext-1");
  const [stagingSecret, setStagingSecret] = useState(
    () => sessionStorage.getItem(STAGING_SECRET_KEY) ?? "",
  );

  function submit() {
    // Remembered only on an actual attempt, so a half-typed value is not persisted.
    if (stagingSecret) sessionStorage.setItem(STAGING_SECRET_KEY, stagingSecret);
    else sessionStorage.removeItem(STAGING_SECRET_KEY);
    onLogin(role, sub, stagingSecret);
  }

  return (
    <div className="panel">
      <img src={logoUrl} alt="IntelliChoice" className="login-logo" />
      <h1>IntelliChoice Adaptive Learning</h1>
      <p className="subtitle">
        Dev sign-in — mints a token via <code>POST /dev/token</code>, standing in for
        the real go.intellichoice.org auth (out of scope here).
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
            intellichoice-staging/learning-api/staging-token-shared-secret --query SecretString
            --output text
          </code>
        </p>
      )}

      <button disabled={busy || !sub} onClick={submit}>
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </div>
  );
}
