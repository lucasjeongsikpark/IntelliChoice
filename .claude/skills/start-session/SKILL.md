---
name: start-session
description: Begin a roadmap session for IntelliChoice. Loads progress state and the session's scope from docs/ROADMAP.md, verifies prerequisites, and proposes a concrete plan before any code is written. Use at the start of every working session, optionally with a session id like "S3".
---

# Start a roadmap session

Argument (optional): a session id like `S3`. If omitted, use the "Next session" line in
docs/PROGRESS.md.

## Steps

1. Read docs/PROGRESS.md — note current status, carry-over items, and anything blocked.
2. Read only the target session's block in docs/ROADMAP.md, plus the spec sections it lists
   from docs/SPEC.md. Do not load the whole spec.
3. Read docs/DECISIONS.md entries referenced by or relevant to this session.
4. Verify prerequisites:
   - The sessions this one depends on (see "Dependency notes" in ROADMAP.md) are marked ✅.
   - The environment still works: run `make lint && make typecheck && make test` if a Makefile
     exists. If the baseline is red, fixing it becomes the first task of the session.
5. Fold any carry-over items from PROGRESS.md into the plan.
6. Propose a short plan: files to create/change, order of work, and how each "Done when"
   criterion will be verified. Ask the user to confirm before editing (per their global
   workflow rules for multi-file changes).

## Rules for the session

- Stay inside the session's scope. If something adjacent is discovered, add it to PROGRESS.md
  carry-over instead of doing it now, unless it blocks the current work.
- Small, testable increments; run the test suite as you go, not only at the end.
- Never write PII fields into Postgres models, logs, or LLM payloads (SPEC §5.30).
- Any call to a paid API needs a timeout, bounded retry, and a token/spend cap.
- New non-obvious choices get a DECISIONS.md entry.
