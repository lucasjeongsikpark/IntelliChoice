import { useState } from "react";
import type { Role } from "../types";
import logoUrl from "../../../../packages/ui-brand/assets/logo.png";

// Kept in step with `e2e/config.ts`'s FIXTURES, which documents itself as mirroring this
// list "so a journey and the screen it drives cannot disagree about who exists". It had
// drifted: `student-ext-3` was in the harness and missing here, so the one fixture that
// exercises SPEC §5.4.4's fail-closed case - attendance *unknown*, not absent - was
// unreachable by hand. D-152 §2 established that `signups.attended = null` is the *routine*
// production state rather than a rare one, which makes this the most important of the three
// attendance fixtures to be able to click.
const FIXTURE_IDS: { label: string; role: Role; sub: string }[] = [
  { label: "Student — Ava Only (present, 1 parent)", role: "student", sub: "student-ext-1" },
  { label: "Student — Ben First (absent this week)", role: "student", sub: "student-ext-2" },
  {
    label: "Student — Cleo Second (attendance not yet marked)",
    role: "student",
    sub: "student-ext-3",
  },
  { label: "Student — Drew Unlinked (present, no parent)", role: "student", sub: "student-ext-4" },
  // The per-band walk students (D-288) - grades 1/4/7/10, all present, so every band the
  // bank serves can be walked by hand as well as by the e2e suite.
  { label: "Student — Finn FirstGrader (grade 1, present)", role: "student", sub: "student-ext-5" },
  { label: "Student — Gia Fourth (grade 4, present)", role: "student", sub: "student-ext-6" },
  { label: "Student — Hana Seventh (grade 7, present)", role: "student", sub: "student-ext-7" },
  { label: "Student — Iris Tenth (grade 10, present)", role: "student", sub: "student-ext-8" },
  { label: "Student — Jae Resume (grade 3, present)", role: "student", sub: "student-ext-9" },
  // The main journey walk's own student and parent (D-365). Kept in step with `e2e/config.ts`
  // deliberately: the comment at the top of this list is about exactly this drift.
  { label: "Student — Kai Journey (grade 3, present)", role: "student", sub: "student-ext-10" },
  // The terminal walk's own student and parent (V1). This is the one student whose sessions
  // reach `completed`, so signing in as them by hand will usually land on a results screen
  // rather than the start screen - that is the fixture working, not a fault.
  { label: "Student — Lena Terminal (grade 3, present)", role: "student", sub: "student-ext-11" },
  {
    label: "Student — Milo Unmarked (grade 3, not marked yet)",
    role: "student",
    sub: "student-ext-12",
  },
  { label: "Parent — Priya One (1 linked child)", role: "parent", sub: "parent-ext-1" },
  { label: "Parent — Paul Two (2 linked children)", role: "parent", sub: "parent-ext-2" },
  { label: "Parent — Pia Three (1 linked child, Kai)", role: "parent", sub: "parent-ext-3" },
  { label: "Parent — Rae Four (1 linked child, Lena)", role: "parent", sub: "parent-ext-4" },
];

/**
 * `localStorage`, not `sessionStorage` - a deliberate reversal of the original choice, which
 * kept this out of `localStorage` on the reasoning that a secret minting a token for **any**
 * role should not outlive the tab. What that actually bought is smaller than it looks: the
 * value is typed back in from Secrets Manager on the next tab anyway, so per-tab expiry
 * deterred nobody and taxed every manual staging check. Persisting it trades disk exposure
 * on the operator's own machine for keeping the D-097 gate intact, which is the exposure
 * that matters - the alternative under consideration was opening `/dev/token` outright.
 *
 * So the threat model this accepts: anything running on this origin, or anyone holding the
 * unlocked laptop, can read the staging secret. It does NOT widen what the internet can
 * reach. Rotate the Secrets Manager value if a machine holding it is lost, and note the
 * secret is deleted entirely at S44 when a real issuer replaces `/dev/token`.
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
