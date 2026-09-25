# 2026-09-23 — queue reconciled after the program closed; memory polarity + recency fix (D-472)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-472.

Session opened on a stale execution queue: §4.4 row 1 was still the resume-evidence program,
which D-466/D-471 had closed; the §4.4 footnote also still said everything else waited on the
user. Reconciled first (program row deleted from §4.2, queue re-derived from the five §4.1
remediation rows by D-466's severity ranking, dated reordering log added), then took the new
row 1: `MEMORY-CONSOLIDATION-DEFECTS` #2/#3. Housekeeping en route: an uncommitted editor
reformat of `CLAUDE.md` (escaped underscores, `&amp;`, dedented continuation lines) reverted at
the user's choice; the leftover `tasks/resume-evidence-e5-3-completion-evidence.md` deleted per
the Frozen Spec contract; Docker was down and was started.

Baseline before any edit: lint/typecheck clean, 2226/2/1. Five reproduce-first tests written
and shown failing — one of them exposed a third defect (server-default `now()` vs Python-clock
timestamps inside one transaction) that would have neutralised recency ranking in the E4
harness. Three product files changed; one pre-existing test re-pointed from a self-contradicting
`weak_skill` flip to `hint_dependence`. E4's mock arm and scripted lane re-run at $0 on an
isolated bench database: `polarity_flip` served-correct 0/985 → 985/985, everything else
unchanged, lane 400/400. Full suite: **2231 passed / 2 skipped / 1 xfailed** — baseline 2226 + the 5 new tests, no flake.

Handoff: the row stays in §4.1 restated (#4 cost accounting + the ceiling bound + unmeasured
real-model polarity quality on non-ability types); queue re-ordered with a dated reason. Nothing
committed or deployed this session (LB-05: implemented locally). UD-14 note: the RDS rotation due
~2026-09-04 has passed and staging connections were not checked (no AWS read this session).
