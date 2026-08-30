# R1 — Executor completion evidence

## Files Changed

**Product code (2):**
- `packages/adapters/src/intellichoice_adapters/bedrock/gateway.py` — `_validate_or_repair`: the
  `if truncated:` guard moves **above** `_try_validate`. Truncation is judged by the stop reason,
  never by whether the partial happened to validate. No behavioural change to repair (still none
  for truncation, D-115) or to the circuit breaker (still no `_record_failure`, D-115).
- `packages/shared/src/intellichoice_shared/bedrock.py` — `MemoryUpdateResponse`: new
  `_CONSOLIDATION_NEW_FACT_SLATE_TOKENS = 2560` base (was inline 1280);
  `MAX_SAFE_EXISTING_FACTS` 21 → 11; the sizing docstring rewritten around E4's measurement.
  The `128 × existing_facts` term is unchanged.

**Tests (2 files, +6 tests):**
- `packages/adapters/tests/test_bedrock_gateway.py` — `_ScriptedProvider` gains `truncated_empty`
  (the real `max_tokens` + `{}` shape) and `empty_complete` (the control). Three tests:
  fails closed; does not trip the breaker; a *finished* `{}` is still a valid empty update.
- `packages/memory/tests/test_consolidation.py` — `_TruncatingProvider` (doubles the provider,
  uses the **real** gateway). Three tests: end-to-end no-silent-zero; `OutputTruncatedError`
  counts as `calls_failed`; the budget admits E4's worst-case new-fact slate.

**Harness comments only (1):** `benchmarks/resume_evidence/04_memory/memory_benchmark.py` — two
comments that asserted the now-fixed behaviour ("reported as added=0 with zero failures", "a
floor of 1,280"). No executable change; arm A/B semantics untouched.

**New artifacts (not product):** `docs/resume_evidence/04_memory/post_remediation/` —
`R1_POSTFIX_REPORT.md`, `real_postfix_summary.json`, `real_results_n10_postfix.jsonl`,
`real_postfix_ground_truth_manifest.jsonl`, `real_postfix_metrics_summary.csv`,
`real_postfix_raw_vs_consolidated.{json,csv}`.

**No historical E4 artifact was modified** — `git status docs/resume_evidence/04_memory/`
reports only the new `post_remediation/` directory.

## Verification Performed

1. Reproduction shown failing on unfixed product code (fix stashed, tests present).
2. `make lint` / `make typecheck` / `make test`.
3. Targeted re-run of `packages/{memory,adapters,shared}/tests` after the final edits.
4. The paid n=10 real-model re-validation, env-gated, invocability-probed, 150¢ hard cap.
5. Dev-database residue check.

## Verification Results

**Pre-fix (the reproduction, failing):**
```
FAILED packages/memory/tests/test_consolidation.py::test_the_output_budget_admits_the_e4_worst_case_new_fact_slate
FAILED packages/memory/tests/test_consolidation.py::test_a_truncated_call_through_the_real_gateway_is_never_a_silent_zero
FAILED packages/adapters/tests/test_bedrock_gateway.py::test_a_truncation_that_happens_to_validate_still_fails_closed
FAILED packages/adapters/tests/test_bedrock_gateway.py::test_a_truncated_empty_response_does_not_trip_the_circuit_breaker
4 failed, 5 passed
```
with the defect stated as an assertion: `assert result.calls_failed == 1` → `assert 0 == 1`.

**Post-fix:**
```
make lint      → All checks passed! / 481 files already formatted
make typecheck → 0 errors, 0 warnings, 0 informations
make test      → 2200 passed, 3 skipped, 1 xfailed in 532.92s
```
Baseline was 2195 / 2 / 1 (2,198 collected); now 2,204 collected = 2,198 + my 6 tests. All 6 new
tests pass. The delta reads +5 passed / +1 skipped because one **pre-existing** draw-dependent
test flipped to skipped: `test_learning_flow.py` skips explicitly when the randomized pre-exam
draw serves neither routed skill (its D-212 vacuity guard). It passes standalone; nothing in this
diff touches exam draws. The three skips in the full run are all in files I did not modify
(`test_qa_coverage_eval_real_bedrock.py`, `test_llm_judge.py` — both paid-API gated — and that
draw-dependent one).

**Paid re-validation** — real-model evaluation (Haiku 4.5), local data; build `783aa0a` + this
change, as-of 2026-08-29; probe OK before any spend; **36.30¢ gateway-reported of the 150¢ hard
cap**; not aborted.

| metric | E4 arm A (before) | R1 post-fix (after) |
|---|---|---|
| calls | 30 | 30 |
| calls reported failed | **0** | **11** |
| calls silently truncated | **29** | **0** |
| students with a silent truncation | **10 / 10** | **0 / 10** |
| facts written | **6** | **119** |
| provenance (evidence ids / all resolving to that student) | — | **119/119 / 119/119** |
| facts with no resolving evidence | — | 0 |
| spend (gateway) | 19.97¢ | 36.30¢ |

Exactly one window is now a *genuine* empty update (`calls_failed=0, added=0`) — before the fix
it was indistinguishable from the eleven truncated ones.

**No dev-database residue.** The benchmark ran against a dedicated `intellichoice_r1_bench`
database (the harness refuses any name without "bench"), which was dropped after the run. The dev
database's newest `semantic_memory` row is dated 2026-08-26; nothing was written there today.

## Observed Drift

1. **The E4 report's stated root cause is exactly right**, and code reading confirmed it
   independently before I read that section. No drift.
2. **`MAX_SAFE_EXISTING_FACTS = 21` was arithmetic over a refuted premise** — it promised safety
   at 21 live facts while the real run truncated at *zero*. Corrected to 11, with the reasoning
   recorded in the constant's own comment.
3. **`calls.hit_output_ceiling` is now structurally 0** in any post-fix run. The harness derives
   it from `stop_reason` on a *returned* result, and truncated calls now raise instead of
   returning. Truncation lands in `calls.failed` instead. Both fields kept; the harness comment
   and §4 of the report say so explicitly, because "0 truncations" would otherwise be misread.
4. **11 of 30 calls still truncate at 2,560** — the base raise is necessary but not sufficient
   for this corpus's densest windows, and truncation does not track input size. Reported, not
   silently accepted; bounding the response is the real fix and is a behaviour decision.
5. **Blast radius of the fail-closed change is narrower than expected.** `MemoryUpdateResponse`
   is the only `*Response` model in `intellichoice_shared.bedrock` whose `{}` validates (verified
   by enumerating all of them), so this exact silent-success shape was reachable on one task
   only. The reorder does also change behaviour for any *partially-filled* truncated response
   whose missing fields are optional (e.g. a half-written `StageNarrativeResponse`); that change
   is intended and correct under the fail-closed rule, and the full suite shows no regression.

## Documentation Impact

For the coordinator; I amended no canonical document.

- `docs/DECISIONS.md` — this warrants an entry: the fail-closed ordering, the budget re-derivation
  (and why not 4,000), `MAX_SAFE_EXISTING_FACTS` 21 → 11, and the decision to keep truncation a
  schema-class failure that does not trip the breaker.
- `docs/resume_evidence/04_memory/E4_REPORT.md` — §4.1 and §7 finding 1 describe a defect that is
  now fixed. It is a dated measurement artifact, so I did not edit it; a forward-pointer to
  `post_remediation/R1_POSTFIX_REPORT.md` is the coordinator's call.
- `docs/ARCHITECTURE.md` — no as-built topology, storage or scheduler change; likely nothing.
- `docs/TRACEABILITY.md` — the fail-closed behaviour is now covered by four tests, if that
  criterion is being tracked.

## New Decision Required

**none** — every choice was determined by existing authority: fail-closed (SPEC §5.25.3, rule 5),
no repair / no breaker trip for truncation (D-115), error taxonomy (D-207), not raising the
budget to the flat ceiling (D-233, D-221), input bounds untouched (D-141). The *deferred*
decisions (bounding the consolidation response; retrying at a raised ceiling) are named in the
report as follow-on candidates and were deliberately not made.

## Remaining Uncertainty

1. **11 of 30 calls still truncate.** They are now loud, but consolidation still loses those
   windows. Whether 2,560 is the right base, or the response needs bounding, is answerable only
   with the decision named above.
2. **Quality is unchanged and still poor** — 111 of 119 facts are on non-planted filler skills;
   `repeated_weak` recovers 0/10. That is E4 arm B's pre-existing model-quality finding, not
   something R1 targeted or claims to have moved.
3. **Synthetic corpus.** Whether a real student's week is dense enough to truncate at 2,560 is
   untested; D-152 keeps production out of scope.
4. **One paid run, n=10.** No repeat, so run-to-run variance in the truncation rate is unmeasured.
   The spec capped this at one run; I did not exceed it.
5. The **out-of-scope findings** (MEMORY-POLARITY-DEFAULT, STALE-FACT-SERVED,
   CACHE-WRITE-UNBILLED) were not touched, as instructed.
