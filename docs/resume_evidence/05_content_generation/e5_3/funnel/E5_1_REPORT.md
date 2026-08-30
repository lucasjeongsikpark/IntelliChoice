# E5.1 - Content-pipeline per-stage defect-containment funnel

> Experiment: **E5.1** of `docs/resume_evidence/MEASUREMENT_PLAN.md` (Theme 5).
> Generated: **2026-08-30T02:02:18+00:00** at repository `dd624d84bdc5ba0c43e02d25605b5b5d45524485`.
> Environment: **local development database - complete offline generation history**.
> Cost of this measurement: **$0** - no model call, no network, read-only SQL.
> Harness: `benchmarks/resume_evidence/05_content_generation/stage_funnel_analysis.py`.
> Filter: `pipeline_run_id = 0e111b3f-bd93-410e-a16c-6ee2b8e753a6`.

## 1. What this measures, and what it does not

`question_validation_runs` is an append-only row per candidate attempt of the offline authoring pipeline (D-195, D-294, D-295). The generator has only ever run from this machine against this database, so the table is the complete recorded history of that pipeline.

**This is the automated pipeline only.** A candidate that clears every machine stage is written `outcome='pending'` and then goes to human review, which writes no row here. "Accepted" below means *accepted by the machine*, never *approved by a person*.

## 2. Headline

- Candidate attempts recorded: **204**
- Accepted by the machine: **174/204 (85.3%)**
- Rejected: **30/204 (14.7%)**
- Window: 2026-08-29T23:34:54.878786+00:00 -> 2026-08-30T01:56:50.471990+00:00; 1 identified `pipeline_run_id`s, 0 rows predate that column
- Total recorded spend: **722.55¢**, of which **99.21¢** (13.7%) was spent on candidates that were rejected
- Cost per machine-accepted candidate: **4.15¢**

## 3. The funnel

Stages run in this order and a candidate is ended by exactly one of them, so `reached` is derived: a candidate reached stage *k* exactly when no earlier stage ended it. The columns close arithmetically against the row count.

| stage | reached | rejected here | rejection rate (n/N) | spend attributed (¢) |
|---|---:|---:|---|---:|
| `design` | 204 | 0 | 0/204 (0.0%) | 0.00 |
| `generator` | 204 | 2 | 2/204 (1.0%) | 2.44 |
| `validation` | 202 | 22 | 22/202 (10.9%) | 74.16 |
| `dedup` | 180 | 0 | 0/180 (0.0%) | 0.00 |
| `solver` | 180 | 2 | 2/180 (1.1%) | 7.14 |
| `judge` | 178 | 4 | 4/178 (2.2%) | 15.47 |
| `difficulty` | 174 | 0 | 0/174 (0.0%) | 0.00 |

**One caveat on the first row.** The equation-design pre-stage is optional (`--design-attempts`), and only **204** rows carry its record at all, so `design`'s 4.2% is a whole-history rate rather than a per-eligible-candidate one. Among the rows that demonstrably ran it, design ended **0/204 (0.0%)** - the stage is far more decisive than the whole-history column suggests, and it is also the cheapest exit in the table.

Plus non-verdict exits, which end a candidate without any stage judging it - kept out of the rates above on purpose (D-192: "the solvers disagreed" and "we ran out of money before calling anything" must not be one number):

- `budget`: **0**
- `circuit_open`: **0**

Closure check: 30 stage rejections + 0 skips + 0 unattributed + 174 accepted = **204** = 204 rows.

### 3.1 How each stage was attributed

Evidence first: the pipeline stops at the first stage that fails and writes that stage's failure into `stage_results`, so the first key recording a failure *is* the stage that ended the candidate. Reason prose is the fallback for the rows written before those keys existed.

| basis | rows |
|---|---:|
| `accepted` | 174 |
| `stage_evidence` | 30 |

### 3.2 Failure families per stage

Buckets are matched against the pipeline's own prose, first match wins, sharing `scripts/measure_gate_census.py`'s vocabulary. Counts are *reasons*, not candidates - one rejection can carry several. The vocabulary was built for the deterministic gate's failure strings, so it is most meaningful on `validation`; for `design`, `dedup`, `budget` and `circuit_open` the prose is provider-error text and lands in `other` by design.

**`generator`** - other 2
**`validation`** - answer key: derived answer disagrees 18, readability 3, equation unusable 1
**`solver`** - options 2, answer key: derived answer disagrees 1
**`judge`** - math notation 3, options 2, answer leakage 1

## 4. The free-gate overlap counterfactual

For every rejection carrying a `candidate_snapshot`, the item is rebuilt and today's free deterministic stage (the D-201/D-249 hint-leak pre-check plus `validate_authored_item`) is re-run over it. No model is called.

- Rejections carrying a snapshot that could be re-gated: **28**
- Of those, rejected by a **paid** stage (dedup / solver / judge / difficulty): **6**
- The free deterministic gate would **also** have rejected: **0/6 (0.0%)** (overlap)
- Only the paid stage caught it: **6/6 (100.0%)** (unique catch)

| paid stage | snapshots re-gated | free gate also rejects | unique catch | overlap |
|---|---:|---:|---:|---|
| `dedup` | 0 | 0 | 0 | 0/0 (n/a) |
| `solver` | 2 | 0 | 2 | 0/2 (0.0%) |
| `judge` | 4 | 0 | 4 | 0/4 (0.0%) |
| `difficulty` | 0 | 0 | 0 | 0/0 (n/a) |

**The direction that cannot be computed.** Whether the paid stages (dedup/solver/judge/difficulty) would have caught the candidates the deterministic gate rejected CANNOT be computed from this data: those stages never ran on those candidates by design, and running them now costs real money on discarded content. The nearest existing evidence is D-276, which points the other way - with the gate off, 5 wrong answer keys passed both blind solvers and the judge.

### 4.1 The deterministic stage against itself

Re-running today's gate over the candidates the gate itself rejected is a drift check on the measurement, not a claim about the content.

- Validation-stage rejections with a snapshot: **22**
- Today's gate still rejects: **22/22 (100.0%)**
- Today's gate now passes (checks relaxed or the failure was era-specific): **0**

**Most of that gap has a name.** Re-running the identical gate with `answer_form="any"` - what every skill got before D-308 introduced the per-skill canonical-form tie-break - reproduces **22/22 (100.0%)** instead. So **0** of the 0 are the D-308 relaxation working as designed, and **0** are residual drift from other checks that have changed since (D-276's restoration of the answer-key checks, D-288's notation check). Neither number is a defect in the content; both are why section 4's overlap is an upper bound.

Recorded failure families at the time: answer key: derived answer disagrees 18, readability 3, equation unusable 1.

Families today's gate raises on the same items: answer key: derived answer disagrees 18, readability 3, equation unusable 1.

## 5. Spend containment

| bucket | cents | share |
|---|---:|---|
| spent on machine-accepted candidates | 623.33 | 86.3% |
| spent on rejected candidates | 99.21 | 13.7% |
| **total** | **722.55** | 100% |

Per-stage spend attribution is in the funnel table above. Note that a row's `cost_cents` is what the *slot* had spent when the row was written (D-294), so stage spend is "money on candidates this stage ended", not "money this stage's own call cost".

## 6. Strata

| requested tier | candidates | machine-accepted | acceptance rate |
|---|---:|---:|---|
| d1 | 22 | 21 | 21/22 (95.5%) |
| d2 | 70 | 68 | 68/70 (97.1%) |
| d3 | 66 | 55 | 55/66 (83.3%) |
| d4 | 29 | 20 | 20/29 (69.0%) |
| d5 | 17 | 10 | 10/17 (58.8%) |

| topic | candidates | machine-accepted | acceptance rate |
|---|---:|---:|---|
| `algebra_1` | 18 | 0 | 0/18 (0.0%) |
| `g1_addition` | 12 | 12 | 12/12 (100.0%) |
| `g2_subtraction` | 18 | 18 | 18/18 (100.0%) |
| `g3_word_problems` | 24 | 23 | 23/24 (95.8%) |
| `g4_multiplication_division` | 18 | 18 | 18/18 (100.0%) |
| `g5_word_problems` | 18 | 18 | 18/18 (100.0%) |
| `g6_word_problems` | 24 | 24 | 24/24 (100.0%) |
| `linear_equations` | 18 | 16 | 16/18 (88.9%) |
| `pre_algebra` | 24 | 18 | 18/24 (75.0%) |
| `trigonometry` | 30 | 27 | 27/30 (90.0%) |

Rows carrying neither a topic nor a tier anywhere: **0** - by attributed stage, . These are the exits that happen before any item exists to describe (design and the breaker), plus the 2026-08-05/06 rows whose evidence is reason prose alone. They are counted in the `(unknown)` row above rather than dropped, so the strata denominators still sum to the row count.

## 7. The warm-up toll (D-296's structure, re-measured)

Counted over the **1** runs that carry a real `pipeline_run_id` (**204** candidates); **0** rows predate the column and are excluded rather than clustered by timestamp - D-295 measured that reconstruction at ~90.8% fidelity and refused to present it as evidence.

| position in run | candidates | rejected | rejection rate | rejected at `difficulty` | difficulty-rejection rate |
|---|---:|---:|---|---:|---|
| 1 | 1 | 1 | 1/1 (100.0%) | 0 | 0/1 (0.0%) |
| 2 | 1 | 1 | 1/1 (100.0%) | 0 | 0/1 (0.0%) |
| 3 | 1 | 1 | 1/1 (100.0%) | 0 | 0/1 (0.0%) |
| 4 | 1 | 1 | 1/1 (100.0%) | 0 | 0/1 (0.0%) |
| 5 | 1 | 1 | 1/1 (100.0%) | 0 | 0/1 (0.0%) |
| 6 | 1 | 1 | 1/1 (100.0%) | 0 | 0/1 (0.0%) |
| 7-10 | 4 | 4 | 4/4 (100.0%) | 0 | 0/4 (0.0%) |
| 11+ | 194 | 20 | 20/194 (10.3%) | 0 | 0/194 (0.0%) |

Aggregated, the D-296 shape is present: difficulty rejections run **0/6 (0.0%)** over positions 1-6 against **0/194 (0.0%)** at position 11+. It is a weak version of it - only 204 candidates across 1 runs carry a run id, and most of those runs are small - so this reproduces the *direction* of D-295/D-296 and not their magnitudes. The mechanism itself (the `may_retier` guard blocking while the judge histogram warms up) is replayed against the real `JudgeDispersion` in `scripts/measure_retier_guard.py`; this experiment does not re-derive it.

## 8. Per-run breakdown

Full table in `per_run_breakdown.csv`. Acceptance rate by identified run:

| pipeline_run_id | candidates | accepted | acceptance rate | ¢ | ¢/accepted |
|---|---:|---:|---|---:|---|
| `0e111b3f-bd93-410e-a16c-6ee2b8e753a6` | 204 | 174 | 174/204 (85.3%) | 722.55 | 4.15 |

## 8.1 Schema eras present in the data

The table spans several pipeline generations and the evidence keys differ across them. Reported rather than smoothed over - a parser that silently dropped an era would understate exactly the stages that were added last.

| era marker | rows | what it means |
|---|---:|---|
| `candidate_snapshot` present | 28 | D-195 onward, and only on rejections after the Generator returned - the population section 4 can re-gate |
| `equation_design` present | 204 | D-200/D-294 onward; absent means the design pre-stage was off or unreached |
| `difficulty` present | 174 | D-194 onward; 0 accepted rows lack it because they predate difficulty being its own stage |
| `generator_request` present | 2 | D-243 onward; earlier generator failures recorded reason prose and nothing else |
| `stage_results` empty | 0 | 2026-08-05/06 rows, attributed from reason prose alone; 16 of them name a since-removed "narrative dressing" stage |
| `pipeline_run_id` present | 204 | D-295 onward, deliberately not backfilled |

## 9. Reconciliation against the decision record

The table now holds **204** rows and **174** difficulty decisions - both larger than the decision record's figures, which is expected of an append-only table that kept being written to.

- The selected rows (204) are fewer than D-294's 1,184, so the row-count reconciliation does not apply to this slice.
- **D-296's 63%-yield run.** Its shape is visible in the per-run table above rather than re-asserted here; see section 8.
- **D-289's criterion 5, 4.7¢ per accepted item** ($24.97 over 529 serving generated items). Computed over this whole history instead: **4.15¢** (722.55¢ / 174 machine-accepted candidates). The denominators are not the same one - D-289 counted *serving* items after human review, this counts every candidate the machine accepted - so the agreement is corroboration rather than a re-derivation.

## 10. Limitations

- **Automated pipeline only.** Human review writes no row in this table, so no number here is a statement about content a person approved. `outcome='pending'` includes candidates later approved *and* candidates later rejected by review.
- **The re-gate uses today's gate.** Checks have been added since the oldest rows were written (D-288's readable-notation check, D-308's canonical-form tie-break, D-276's restoration of the answer-key checks), so the overlap in section 4 is an **upper bound** on what the gate of the day would have caught. It answers "how much of what we pay for is free *today*", which is the forward-looking question.
- **Snapshot coverage is partial and era-dependent.** A rejection only carries the candidate from D-195 onward and only after the Generator returned; design-stage and generator-stage failures have nothing to re-gate. Two snapshot shapes exist (the earlier one lacks `attempt`/`repaired_defects`); both carry every field the Generator contract needs, so both re-gate.
- **`pipeline_run_id` is NULL before D-295** and was deliberately not backfilled - inferring it would bake a ~10%-wrong guess into the data as recorded fact. Per-run and warm-up numbers therefore cover the identified runs only, and say so.
- **Stage spend is attributed, not itemised.** `cost_cents` is the slot's running total at the moment the row was written (D-294), so a stage's column means "money on candidates this stage ended", not "the cost of this stage's own call".
- **Failure families are pattern-matched prose.** The pipeline writes rejection reasons for a human reader; bucketing is regex, first match wins, with an explicit `other`.
- **Reasons are counted per reason, not per candidate** in section 3.2 - one rejection can raise several objections.
- **A retired stage is in the history.** 16 rows from 2026-08-06 name a "narrative dressing" call that no longer exists in the pipeline; they are attributed to `budget` because that is what their prose records refusing the call.
- **The uncomputable direction stays uncomputed.** Whether the paid stages would have caught the gate's rejections is not measured and is not estimated here; see section 4.

## 11. Artifacts

- `funnel_summary.json` - every number in sections 2-7, machine-readable.
- `stage_attribution.csv` - one row per candidate attempt with its attribution.
- `overlap_analysis.json` - section 4 in full, including per-stage families.
- `per_run_breakdown.csv` - section 8 in full.
- This report.
