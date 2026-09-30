# Bounded — MEMORY-CEILING-STILL-SATURATED: the consolidation payload capped at the 11 most recently confirmed facts, $0 re-measurement

**Remediation against D-471's live finding** (a ~26-fact cohort derived a 5,888-token output
budget, the gateway clamped it to 4,000, 8/8 calls truncated — all surfaced, none silent) and
R6's mock-scale count (1,659/3,135 windows over D-467's honest `MAX_SAFE_EXISTING_FACTS = 11`).
**User decision 2026-09-29 (UD-15):** cap the existing facts sent for reconfirmation to the N
most recently confirmed; older facts age out through retention instead of being re-litigated
every window. Built 2026-09-29 as the seventh Orca coordinator/executor task. **No paid model
call was made.** Decision record: D-490.

**Nothing in this directory replaces an E4 or R6 artifact.** Every historical file under
`docs/resume_evidence/04_memory/` is byte-for-byte unchanged; this run wrote only the
`bounded_*` files in this directory.

---

## 1. The defect

`_consolidate_one_batch` sent **every** live fact of the student as `existing_facts` and derived
`max_output_tokens = 2560 + 128 × n` from that count. Above 11 facts the derived budget exceeds
the gateway's 4,000-token hard ceiling (`_HARD_MAX_OUTPUT_TOKENS`), the gateway clamps it, and
the structured response truncates — D-467 made that truncation fail closed and counted, and
logged `memory_consolidation_payload_oversized` so the decision *which facts to drop* would
arrive with a distribution. D-471 then observed it live; R6 measured it at mock scale.

## 2. The fix (one product file)

| File | Change |
|---|---|
| `packages/memory/src/intellichoice_memory/consolidation.py` | `_most_recently_confirmed` sorts the live facts by `(last_confirmed_at desc, confidence desc, semantic_memory_id desc)` and keeps the first `MAX_SAFE_EXISTING_FACTS` (11). The payload and the derived budget both come from that bounded list, so the budget is at most `max_output_tokens_for(11) = 3,968 < 4,000`. When facts were dropped, one INFO event `memory_consolidation_payload_bounded` carries `existing_fact_count`, `sent_fact_count`, `dropped_fact_count` — counts only. The WARNING `memory_consolidation_payload_oversized` is gone (its condition can no longer occur). One sentence appended to `_SYSTEM_PROMPT`: the existing facts shown are the most recently confirmed and may not be all of them; an unlisted fact must not be assumed absent. |

**Why the sort lives in `consolidation.py`.** The Frozen Spec assumed `list_facts_for_student`
already returned recency-first order; the executor found it has **no `ORDER BY`** — D-472's
recency-first rule is `top_fact_for_skill`'s, and D-472 says exactly that. The repository query
(six other callers) is untouched; the sort key mirrors `top_fact_for_skill` with the id as the
deterministic tiebreak.

**Why bounding cannot lose or duplicate a fact.** Apply time matches every `facts_to_add`
candidate against the **database** (`find_live_fact`), not against the sent list, so a candidate
for an unsent fact still reconfirms, promotes, demotes or supersedes that fact under the polarity
protocol. What the model can no longer do for an unsent fact is name it in `facts_to_update` /
`facts_to_expire`; those facts rely on retention/expiry (UD-7 territory, unchanged).

## 3. Reproduce-first evidence

Five new tests in `packages/memory/tests/test_consolidation.py`; four shown FAILING on the
pre-change code, then passing (the fifth pins "nothing changes at or below the bound" and passes
before and after):

| Test | Fails before with |
|---|---|
| `test_a_26_fact_student_is_sent_only_the_11_most_recently_confirmed` | 26 ids sent, not 11 |
| `test_at_or_below_the_bound_the_payload_is_unchanged_and_nothing_is_logged` | passes before and after (pins the no-op) |
| `test_a_fact_left_out_of_the_bounded_payload_is_still_reconciled_not_duplicated` | the oldest fact was in the sent payload |
| `test_dropping_facts_logs_one_counts_only_info_event` | 0 bounded records (a WARNING `…payload_oversized` was captured instead) |
| `test_the_model_is_told_the_existing_fact_list_is_bounded` | `'most recently confirmed' not in _SYSTEM_PROMPT` |

The first test inserts facts **out of recency order** so a future ordering change in the
repository or in the sort key fails here.

## 4. Re-measurement on E4's instruments ($0)

Same generator, same seed, `DEFAULT_CORPUS_START`, N = 1,000, isolated `bench` database
(created, migrated, dropped); mock provider, scripted lane. Build `4f32f85` + this working tree;
R6 was `398cd6f`.

**The harness's own oversized-window metric cannot move.**
`input_ceiling.windows_with_oversized_existing_fact_payload` is computed from the harness's
re-read of the student's *live* facts, not from the payload the product sent, so it stays
**1,659** by construction — it now measures how often the bound fires, not whether a call is
over budget. The harness was left byte-untouched (its comment was corrected afterwards, with
the run already recorded). The bound itself was proven with an **uncommitted scratchpad driver**
that imports the harness and wraps `MeteringGateway.generate_structured` to record every call's
requested `max_output_tokens` and sent fact count — `bounded_call_budgets.json`:

| metric | value |
|---|---|
| calls with `max_output_tokens` > `max_output_tokens_for(11)` = 3,968 | **0 / 3,135** |
| calls with `max_output_tokens` > 4,000 / calls with > 11 facts sent | 0 / 0 |
| maximum `max_output_tokens` observed / maximum facts sent | 3,968 / 11 |
| calls at the bound (11 facts sent) | 1,997 |

Everything the fix must not change, against R6:

| metric | R6 postfix | bounded |
|---|---|---|
| calls total / failed | 3,135 / 0 | 3,135 / 0 |
| `hit_output_ceiling` | 0 | 0 |
| `polarity_flip` status_correct / served_correct | 985/985 / 985/985 | 985/985 / 985/985 |
| `repeated_strength`, `repeated_weak`, `under_evidenced`, `mastery_conflict_weak`, `mastery_conflict_strength` | 985/985 each | 985/985 each |
| lifecycle provisional / active | 6,386 / 11,043 | 6,386 / 11,043 |
| unplanted extra live facts / facts without resolving evidence | 12,504 / 0 | 12,504 / 0 |
| provenance (facts / with ids / all resolving) | 17,429 each | 17,429 each |
| events total / dropped over the per-student call cap | 346,320 / 63,063 | 346,320 / 63,063 |
| scripted lane (10 checks × 40 students) | 400/400 | 400/400 |

**Columns that moved, and why.** `raw_history_input_tokens_total` 31,940,901 → 32,087,901 is
**exactly +49 tokens × 3,000 windows**; the added prompt sentence measures exactly +49 estimated
tokens (`estimate_input_tokens` of `_SYSTEM_PROMPT` 249 → 298), and the harness's
`payload_tokens` includes the prompt as fixed overhead. The compression median (16.20× → 16.31×)
and `students_whose_cumulative_history_exceeds_ceiling` (49 → 50) follow from that arithmetic.
`live_fact_tokens_total` 1,496,978 → 1,495,880 (−1,098, −0.07%) is the mock provider's response
to a shorter `existing_facts` list; the live-fact *counts* above are identical.

Artifacts: `bounded_call_budgets.json`, `bounded_mock_summary.json`,
`bounded_mock_metrics_summary.csv`, `bounded_mock_results_n1000.jsonl`,
`bounded_mock_ground_truth_manifest.jsonl`, `bounded_mock_raw_vs_consolidated.{json,csv}`,
`bounded_scripted_lane_results.json`.

## 5. Verification

- Executor: `packages/memory/tests` 70 passed; `ruff check` / `ruff format --check` clean;
  `pyright` 0 errors; `make test` **2307 passed / 2 skipped / 1 xfailed** (baseline 2302 + 5).
- Coordinator, independently on the same tree: ruff and pyright clean; `make test`
  **2307 passed / 2 skipped / 1 xfailed** (520 s), identical to the executor's count.
- Dev database untouched by the benchmark (separate `bench` database, dropped afterwards).

## 6. Honestly still open

- The real model's behaviour with a bounded list — whether it re-proposes unlisted facts as new
  more often, spending output tokens that apply-time dedup then discards — is **unmeasured**
  (E4 arm A, ~36¢; UD-2 spend, not authorised). The store is protected either way.
- The real model's polarity quality on the ten non-ability types stays unmeasured post-D-472
  for the same reason.
- Deployment: **implemented locally, not deployed** at the time of writing (LB-05).
