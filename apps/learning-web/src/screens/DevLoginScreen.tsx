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

interface Props {
  onLogin: (role: Role, sub: string) => void;
  busy: boolean;
  error: string | null;
}

export function DevLoginScreen({ onLogin, busy, error }: Props) {
  const [role, setRole] = useState<Role>("student");
  const [sub, setSub] = useState("student-ext-1");

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

      {error && <p className="error">{error}</p>}

      <button disabled={busy || !sub} onClick={() => onLogin(role, sub)}>
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </div>
  );
}
