---
name: end-session
description: Close out an IntelliChoice roadmap session. Runs verification, updates docs/PROGRESS.md and docs/DECISIONS.md, and summarizes state for the next session. Use before ending any working session, including partial ones.
---

# End a roadmap session

## Steps

1. Run the full verification available: `make lint && make typecheck && make test` (or the
   project's equivalents). Report results honestly — a partial session with a green suite is
   fine; a "done" claim with a red suite is not.
2. Check the session's "Done when" criteria in docs/ROADMAP.md one by one; mark the session
   ✅ only if all hold, otherwise ⏸ partial.
3. Update docs/PROGRESS.md:
   - Add a session-log entry using the template (what was built, verification performed,
     carry-over, decision refs).
   - Update the "Current status" block: next session, blockers, carry-over items.
4. Add DECISIONS.md entries for any non-obvious choices made this session.
5. If ROADMAP.md scope for future sessions changed as a result of this session, edit it and
   say so.
6. Summarize for the user: files changed, verification performed, remaining risks, and the
   suggested next session.
7. Update docs/ARCHITECTURE.md if any architecture-level changes were made (e.g., new service, new database, new API).
