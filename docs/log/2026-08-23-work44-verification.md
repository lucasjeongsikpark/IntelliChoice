# 2026-08-23 — standalone session: `WORK-44-DECIDED-NOT-BUILT` verified closed (D-429)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-429.

## What was done

Generic continue request; `RD-01` (queue row 1) still time-blocked until after Sunday
2026-08-24 18:30 UTC, so the session took row 2, `WORK-44-DECIDED-NOT-BUILT` — the two
read-only verifications of D-322's "decided, not built" items #3 and #9.

- **#3 react-router: verified installed and routing** in learning-web (`react-router-dom`
  7.18.2 declared/locked/present; `BrowserRouter` at `main.tsx:40`; pathname-driven screens
  with D-381's unknown-path normalisation). No `<Routes>` by documented design. SPEC §5.1.2
  scopes the first-visit notice to learning-web only, so chat-web's lack of react-router is
  consistent. The `DISCLOSURES-LEGAL` chain loses its fourth blocker.
- **#9 dependency backlog: read via `gh pr list`.** 14 PRs open — the audited 26-PR backlog
  is cleared except the two 2026-07-24 python 3.12→3.14 base-image majors (rule-consistent:
  majors are read individually), plus a fresh batch of 12 patch/minor dependabot PRs dated
  2026-08-21 that qualifies for D-322 #8's standing batch-merge rule.

## Decisions / state changes

- `WORK-44-DECIDED-NOT-BUILT` deleted from §4.2 and the §4.4 queue (verified closed, D-429).
- New §4.2 row + queue row 2: `DEP-PR-BATCH-2026-08-21` (batch-merge the 12 patch/minors,
  read the two majors individually) — homed in D-429; first §4 key without a register anchor,
  and the §4 intro now says so.
- `ARCH-33-CI-GATE` (§6.3) restated: PR-backlog half read; `gh run list` half remains.
- `WORK-44` #2's shared anonymous rate-limit bucket stays in §6.4's accepted-residual set.
- Deliberately NOT done this session: the batch merge itself (mutates GitHub state, advances
  product HEAD — one task per continue).

## Evidence / verification

- `make lint` and `make typecheck`: green (this session).
- `make test`: green earlier the same session (1778 passed, 2 skipped, 1 xfailed); no code
  changed since — this session's edits are docs-only.
- GitHub read performed 2026-08-23 via `gh pr list` (PRs #347–#358 patch/minor, #1 and #8
  majors).

## Handoff

- Next eligible queue item: `DEP-PR-BATCH-2026-08-21` (row 2) on the next continue before
  Sunday's run; `RD-01` confirmation after 2026-08-24 18:30 UTC.

Commit: see the docs commit landing this file (docs-only; product code stays `1768c9d`).
