---
name: end-session
description: Close out an IntelliChoice working session. Runs verification, updates docs/PROJECT_STATE.md (delete-on-resolve), appends a dated entry to docs/log/, and adds DECISIONS.md entries. Use before ending any working session, including partial ones.
---

# End a working session

Reconciled 2026-08-20 to the post-migration documentation model (user ruling DQ-1):
`docs/PROJECT_STATE.md` owns current/open state; `docs/log/` owns historical narration and
is non-authoritative; `docs/PROGRESS.md` and `docs/ROADMAP.md` are archived and are never
updated.

## Steps

1. Run the full verification available: `make lint && make typecheck && make test` (or the
   project's equivalents). Report results honestly — a partial session with a green suite is
   fine; a "done" claim with a red suite is not.
2. Check the session's goal against what was actually verified. State plainly what is done,
   what is partial, and what was not attempted. "Implemented locally" is never reported as
   "deployed" — carry the build SHA discipline (AUTHORITY_MODEL §3.2).
3. Update `docs/PROJECT_STATE.md`:
   - Delete (do not strike through or annotate) any §4–§7 row this session resolved; the
     register under `docs/reference/reconciliation-2026-08/` keeps the evidence.
   - Add rows for genuinely new open items, keyed and dated.
   - Update the snapshot header's as-of date and, if a deploy happened, the deployed SHA.
   - Follow §10's update protocol, including the fan-out check.
4. Add `docs/DECISIONS.md` entries for any non-obvious choices made this session.
5. Append ONE new file to `docs/log/` named `YYYY-MM-DD-<short-slug>.md`: a concise dated
   entry with what was done, evidence produced, unresolved handoff items, and the relevant
   commit/SHA. Never edit or delete existing log entries; never put current/open state only
   in the log (rules: `docs/log/README.md`).
6. Update `docs/ARCHITECTURE.md` if any architecture-level change shipped (new service,
   database, API, scheduled job) — it is the single as-built authority.
7. Summarize for the user: files changed, verification performed, remaining risks, and a
   suggested next step drawn from `docs/PROJECT_STATE.md` §4.3.
