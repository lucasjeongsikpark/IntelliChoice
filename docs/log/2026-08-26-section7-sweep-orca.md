# 2026-08-26 — the §7 sweep: three unknowns closed by reading; the roster defaults fixed (D-446, D-447)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgments:
> D-446, D-447.

## What was done

A continue request found the execution queue still empty of unblocked items, so the session
executed §7's own protocol: the three read-resolvable known unknowns.

- **`K5-HINT-INSTRUMENTS`** — D-264 read: status tag stands, no in-place correction existed;
  the owed dated annotation now points at D-265 (28 → 27), D-266/268 (the diagnosis), and
  D-271 (the refuted "automated repair cannot reach" conclusion).
  `HINT_SOLUTION_REVIEW.md` §5 states the falsification frame correctly — no edit owed.
- **`D288-D317-CLOSURE`** — both bodies read: D-317 + addendum **closes** D-288's named
  product defect (staging-verified 10/10 vs 2/6). Annotations at D-288's stale ⏸ status line
  and at D-317's addendum-contradicted "What is not yet known" section; nothing else retired.
- **`DRIFT-49-MODEL-ROSTER`** — settled from DECISIONS + git history alone (the ask-the-user
  half never fired): the intended roster is D-273's 2026-08-11 stratum, actually run by
  Phase 1; `.env.example`'s mirror was staleness (slots last touched at D-230, `6988ee6`).

## The implementation (sixteenth Orca run)

The decision-free half of DRIFT-49 went to an Opus executor (`run_f8d852490cd5`,
claude/opus/high, receipt requested == effective, heartbeat-confirmed): `settings.py`'s four
AccessDenied `claude-sonnet-5` defaults → the stratum roster; `.env.example`'s Generator slot
corrected off the mirror; `test_pipeline_settings_defaults.py` pins solver diversity via
`underlying_model` plus the dated ids. Landed as `7983154` (PR #410).

## Verification

Executor: lint clean, typecheck 0 errors, suite 1870/2/1-xpassed (baseline 1867 + 3 new);
2 of 3 new tests fail on revert. Coordinator: independent diff review, standalone re-run of
the new tests (3 passed), and the xpass verified as `test_learning_flow.py`'s documented
non-strict D-238 coin flip — baseline intact, not off it.

## State changes

- §7 shrinks 5 → 2 rows (the survivors are irreducible/method-bounded: `D192-PHANTOM`,
  `ARCH-34`'s tfvars half); §10's "closed by reading" rule updated to match.
- The execution queue remains **empty of unblocked items** — the sweep consumed the last
  agent-actionable reads.
- QUESTION_GENERATION.md: Appendix A's shipped-default annotation dated closed; the stratum
  roster table now notes it is also the code default (D-447).

## Handoff — unchanged from D-444/D-445

UD-2 (the read-only DB session + staging e2e spend), a manual deploy (D-417 §C9), UD-13,
UD-5's EMF promotion, D310 (a), and the dated 2026-08-31 07:17 UTC cron check.
