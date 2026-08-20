---
name: start-session
description: Begin an IntelliChoice working session. Loads current state from docs/PROJECT_STATE.md, verifies prerequisites, and proposes a concrete plan before any code is written. Use at the start of every working session, optionally with a work-item key.
---

# Start a working session

Argument (optional): a work-item key from `docs/PROJECT_STATE.md` §4 (e.g. a register key).
If omitted, pick from §4.3 (the items an agent can act on now).

Reconciled 2026-08-20 to the post-migration documentation model: `docs/PROJECT_STATE.md` is
the entry point; `docs/PROGRESS.md` and `docs/ROADMAP.md` are archived history — do not
read them for current state. Frozen integration sessions live in
`docs/reference/integration/ROADMAP_FROZEN_SESSIONS.md` behind the D-152 freeze banner.

## Steps

1. Read `docs/PROJECT_STATE.md` — the snapshot header (repository vs deployed SHA), §4
   (active work), §5 (open user decisions — never answer one), §6 (blocked/deferred/parked,
   including the D-152 freeze in §6.1).
2. For the chosen item, follow its register-key link into
   `docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md` for evidence, and
   read only the SPEC sections and DECISIONS entries the item names. Do not load the whole
   spec.
3. Verify prerequisites:
   - The item is not blocked (§6.2), parked (§6.4), or waiting on a user decision (§5).
   - The environment still works: run `make lint && make typecheck && make test` if a
     Makefile exists. If the baseline is red, fixing it becomes the first task of the
     session.
4. Propose a short plan: files to create/change, order of work, and how the outcome will be
   verified. Ask the user to confirm before editing (per their global workflow rules for
   multi-file changes).

## Rules for the session

- Stay inside the chosen item's scope. New discoveries become new `PROJECT_STATE` rows (or
  register notes), not detours.
- Small, testable increments; run the test suite as you go, not only at the end.
- Never write PII fields into Postgres models, logs, or LLM payloads (SPEC §5.30).
- Any call to a paid API needs a timeout, bounded retry, and a token/spend cap.
- New non-obvious choices get a DECISIONS.md entry.
- At close, run /end-session (PROJECT_STATE update + docs/log/ entry).
