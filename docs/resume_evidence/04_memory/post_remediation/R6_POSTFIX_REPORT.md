# R6 — MEMORY-POLARITY-DEFAULT + MEMORY-STALE-FACT-SERVED: fix and $0 re-measurement

**Remediation R6** against D-460's findings #2 and #3 (E4 §4.3 and §3.4), taken 2026-09-23 as
the first eligible row of `PROJECT_STATE` §4.4 after the resume-evidence program closed
(D-466/D-471). Reproduce → smallest deterministic fix → permanent regression tests → re-run of
E4's own zero-cost instruments. **No paid model call was made.** Decision record: D-472.

**Nothing in this directory replaces an E4 artifact.** Every historical file under
`docs/resume_evidence/04_memory/` is byte-for-byte unchanged (`git status` shows only additions
here). This run wrote only under the `polarity_postfix` run label plus a fresh
`scripted_lane_results.json` in this directory (the original lives one level up).

---

## 1. The two defects

**#2 — polarity left at the schema default.** `MemoryFactCandidate.polarity` defaulted to
`"positive"`, and neither the consolidation system prompt nor the field's schema description
mentioned the word. E4's real arm stored 98/120 `weak_skill` facts as *positive*, and since
polarity is the one field the contradiction protocol keys on, `contested` fired 2 times in 20
students where the scripted lane reaches it 40/40.

**#3 — the stale fact served.** `top_fact_for_skill` ordered `active` facts by confidence
alone. `reconfirm_fact` raises confidence on every agreeing window, so an older fact outranked a
newer contradicting one by construction: E4's `polarity_flip` (two weeks of success, then four
regression events across two sessions) wrote and promoted the negative fact in 985/985 students
and served the stale positive one in 985/985.

**A third, found while reproducing #3.** `SemanticMemory.first_observed_at`/`last_confirmed_at`
had only a `now()` server default, which Postgres freezes at *transaction* start, while
`reconfirm_fact` stamps Python's wall clock. Inside one transaction a fact added *after* a
reconfirmation therefore carried an *earlier* timestamp than the reconfirmation — the failing
test shows `13.104988 < 13.128904`. A recency-first read path alone would have left the E4
harness (one transaction per student) and any window-batching caller still serving the stale
fact.

## 2. The fixes (three files, product code)

| File | Change |
|---|---|
| `packages/memory/src/intellichoice_memory/consolidation.py` | `_effective_polarity`: for `strength`/`weak_skill` the polarity is **derived from the fact type** via the existing `_ABILITY_FACT_TYPES` table and the model's value is ignored; other fact types keep the model's value. `_SYSTEM_PROMPT` now defines polarity and says to set it on every fact. |
| `packages/shared/src/intellichoice_shared/bedrock.py` | `MemoryFactCandidate.polarity` carries a schema `description` (the gateway sends `model_json_schema()` as the tool's `inputSchema`, so it reaches the model). |
| `packages/db/src/intellichoice_db/repositories/memory.py` | `top_fact_for_skill` orders by `last_confirmed_at DESC, confidence DESC, first_observed_at DESC`. `add_fact` stamps both timestamps from Python's clock when unset. |

Design boundary honoured: the user chose **recency-first** over "recency + cross-type demotion"
(a `weak_skill` candidate demoting an active `strength` on the same skill). Consequence, stated
in ARCHITECTURE §8: ability-type facts never contradict *themselves* any more (polarity is fixed
per type), so demote/supersede stays reachable only through the ten model-polarity types; a
regression after a strength is a second live fact and the read path picks the newest.

## 3. Reproduce-first evidence

Five new tests, all shown FAILING on unfixed code, then passing:

| Test | Fails before with |
|---|---|
| `test_repositories.py::test_top_fact_for_skill_serves_the_most_recently_confirmed_fact` | `assert 'strength' == 'weak_skill'` |
| `test_repositories.py::test_add_fact_stamps_its_timestamps_from_the_clock_reconfirm_fact_uses` | later fact's timestamp `<` the earlier reconfirmation's |
| `test_consolidation.py::test_ability_fact_polarity_is_derived_from_the_fact_type_not_the_model` | `assert 'positive' == 'negative'` |
| `test_consolidation.py::test_polarity_is_explained_to_the_model_in_prompt_and_schema` | `"polarity" not in _SYSTEM_PROMPT` |
| `test_consolidation.py::test_a_later_regression_is_served_over_an_older_strength` | served `strength` |

One pre-existing test was re-pointed, not weakened:
`test_contradiction_demotes_then_supersedes_on_second_contradiction` scripted its "opposite
polarity" as a `weak_skill` fact flipping to positive — exactly the inconsistent shape the fix
normalises away. It now scripts `hint_dependence` (model-chosen polarity) and asserts the same
demote → supersede path.

## 4. Re-measurement on E4's instruments ($0)

Same generator, same seed, `DEFAULT_CORPUS_START`, N = 1,000, isolated database
`intellichoice_e4_bench` (created, migrated, TRUNCATEd via `--cleanup`, dropped). Build
`398cd6f` + this working tree; E4's mock arm was `a6c80fa`.

| metric | E4 mock (D-460) | R6 postfix |
|---|---|---|
| calls total / failed | 3,135 / 0 | 3,135 / 0 |
| `polarity_flip` **status_correct** | 985/985 | 985/985 |
| `polarity_flip` **served_correct** | **0/985** | **985/985** |
| `repeated_strength` / `repeated_weak` / `under_evidenced` served_correct | 985/985 each | 985/985 each |
| `mastery_conflict_weak` / `mastery_conflict_strength` (no live fact) | 985/985 each | 985/985 each |
| scripted lane (10 checks × 40 students) | 400/400 | 400/400 |

Artifacts: `mock_polarity_postfix_metrics_summary.csv`, `mock_polarity_postfix_summary.json`,
`mock_results_n1000_polarity_postfix.jsonl`, `mock_polarity_postfix_ground_truth_manifest.jsonl`,
`mock_polarity_postfix_raw_vs_consolidated.{json,csv}`, `scripted_lane_results.json`.

**Columns that moved and are NOT this fix.** `raw_history_input_tokens_total` 31,379,901 →
31,940,901 (+1.8%), the compression percentiles (median 15.82× → 16.20×) and
`students_whose_cumulative_history_exceeds_ceiling` 40 → 49 changed between the two build SHAs;
the corpus is identical (same students, calls, and planted outcomes) and this change touches
no event rendering, so the drift is attributed to the D-467 changes that lie between `a6c80fa`
and `398cd6f` — *inferred from the SHA range, not bisected*.
`input_ceiling.windows_with_oversized_existing_fact_payload` 0 → **1,659** is D-467's honest
`MAX_SAFE_EXISTING_FACTS` 21 → 11 now firing at mock scale: the first corpus-wide count of how
often the consolidation payload exceeds the budget the gateway can serialise. It belongs to the
open `MEMORY-CEILING-STILL-SATURATED` item (D-471), not to R6.

## 5. Verification

- `make lint` / `make typecheck`: clean.
- Focused: `packages/db/tests/test_repositories.py` + `packages/memory/tests/test_consolidation.py`
  — 71 passed.
- Full suite: **2231 passed / 2 skipped / 1 xfailed** — baseline 2226 + the 5 new tests, no flake (baseline this session, before any edit: 2226 passed / 2 skipped / 1 xfailed).
- Dev database untouched by the benchmark (separate `bench` database, dropped afterwards).

## 6. Honestly still open (carried on the `PROJECT_STATE` row)

- **#4 `MEMORY-CACHE-WRITE-UNBILLED`** — untouched.
- **`MEMORY-CEILING-STILL-SATURATED`** — untouched; the 1,659-window count above is new evidence.
- The real model's *quality* of polarity on the ten non-ability types is unmeasured post-fix (the
  prompt/schema half of #2 is a $0 change whose effect only a paid arm can measure). E4 arm A's
  `MEMORY_BENCH_REAL_BEDROCK=1 ... --students 10` re-run (~36¢ at D-467's rate) would measure it;
  not run — spend not authorised for this task.
- Deployment: **implemented locally, not deployed** (LB-05). Reaches staging with the next
  manual deploy (D-417).
