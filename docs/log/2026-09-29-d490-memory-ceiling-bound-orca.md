# 2026-09-29 — UD-15 built: the consolidation payload bounded to the 11 most recently confirmed facts (D-490)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-490.

Seventh Orca task (`run_5daaacbf0616`, Opus 5.5 high, receipt matched), Frozen Spec
`tasks/memory-ceiling-bound.md`. The executor returned two findings as questions rather than
absorbing them, both ruled in Revision 1: the spec's premise that `list_facts_for_student` is
recency-ordered was false (it has no `ORDER BY`; D-472's rule is `top_fact_for_skill`'s — the
spec misread D-472) → explicit sort in `consolidation.py`, out-of-order insert test; and the
harness's oversized-window metric re-reads live facts so it cannot move → harness untouched, the
bound proven with an uncommitted driver recording every call's requested budget
(0 / 3,135 over 3,968; max 11 facts sent).

Coordinator review: diff vs spec vs evidence compared; four tests shown failing pre-change;
independent ruff/pyright clean, independent `make test` (result in D-490); one unused import
removed, nothing weakened. Accepted; worker released; evidence report
`BOUNDED_REPORT.md` written beside R6's; the harness's stale comment (old event name, 21)
corrected by the coordinator after the run.

Handoff: `MEMORY-CEILING-STILL-SATURATED` closed; `MEMORY-CONSOLIDATION-DEFECTS` keeps only the
unmeasured real-model arm (UD-2). UD-15 leaves §5. Execution queue still empty. Repository
changes uncommitted at this entry; not deployed (LB-05).
