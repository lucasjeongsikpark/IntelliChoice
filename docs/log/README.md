# docs/log/ — per-session narration (historical, non-authoritative)

Created 2026-08-20 by user decision (documentation reconciliation, DQ-1). These rules are
the user's ruling, verbatim in substance:

- `docs/log/` is **historical session narration only**.
- It is **NOT a source of current project truth**.
- It must **never override** `docs/PROJECT_STATE.md`, accepted decisions in
  `docs/DECISIONS.md`, `docs/SPEC.md`, primary repository evidence, or deployed/runtime
  evidence.
- **Agents should not read the full log by default.** Read an entry only when you need the
  history of a specific past session.
- Each session may **append one concise dated entry** describing: what was done, evidence
  produced, unresolved handoff items, and the relevant commit/SHA.
- **Current/open state belongs in `docs/PROJECT_STATE.md`, not here.** If an entry names an
  open item, the authoritative copy is the PROJECT_STATE row, not the log line.
- When a log entry becomes stale, **leave it historical rather than rewriting it**. Entries
  are append-only: one new file per session, named `YYYY-MM-DD-<short-slug>.md`; existing
  entries are never edited or deleted.

Precedence: see `docs/reference/AUTHORITY_MODEL.md`. This directory sits below every
document tier named there — it is narration, not evidence and not authority.
