# E5.1 - Content-pipeline per-stage defect-containment funnel

> Experiment: **E5.1** of `docs/resume_evidence/MEASUREMENT_PLAN.md` (Theme 5).
> Generated: **2026-08-29T02:44:59+00:00** at repository `7a486a9d8ad6a3affb93c14830b58ff4aa353d26`.
> Environment: **local development database - complete offline generation history**.
> Cost of this measurement: **$0** - no model call, no network, read-only SQL.
> Harness: `benchmarks/resume_evidence/05_content_generation/stage_funnel_analysis.py`.

## 1. What this measures, and what it does not

`question_validation_runs` is an append-only row per candidate attempt of the offline authoring pipeline (D-195, D-294, D-295). The generator has only ever run from this machine against this database, so the table is the complete recorded history of that pipeline.

**This is the automated pipeline only.** A candidate that clears every machine stage is written `outcome='pending'` and then goes to human review, which writes no row here. "Accepted" below means *accepted by the machine*, never *approved by a person*.

## 2. Headline

- Candidate attempts recorded: **1827**
- Accepted by the machine: **878/1827 (48.1%)**
- Rejected: **949/1827 (51.9%)**
- Window: 2026-08-05T21:58:09.263460+00:00 -> 2026-08-13T17:36:51.776408+00:00; 14 identified `pipeline_run_id`s, 1535 rows predate that column
- Total recorded spend: **4074.61¢**, of which **1652.64¢** (40.6%) was spent on candidates that were rejected
- Cost per machine-accepted candidate: **4.64¢**

## 3. The funnel

Stages run in this order and a candidate is ended by exactly one of them, so `reached` is derived: a candidate reached stage *k* exactly when no earlier stage ended it. The columns close arithmetically against the row count.

| stage | reached | rejected here | rejection rate (n/N) | spend attributed (¢) |
|---|---:|---:|---|---:|
| `design` | 1827 | 77 | 77/1827 (4.2%) | 192.86 |
| `generator` | 1750 | 78 | 78/1750 (4.5%) | 36.97 |
| `validation` | 1572 | 409 | 409/1572 (26.0%) | 642.90 |
| `dedup` | 1163 | 16 | 16/1163 (1.4%) | 16.50 |
| `solver` | 1147 | 84 | 84/1147 (7.3%) | 203.82 |
| `judge` | 1063 | 59 | 59/1063 (5.6%) | 185.67 |
| `difficulty` | 1004 | 126 | 126/1004 (12.5%) | 370.29 |

**One caveat on the first row.** The equation-design pre-stage is optional (`--design-attempts`), and only **350** rows carry its record at all, so `design`'s 4.2% is a whole-history rate rather than a per-eligible-candidate one. Among the rows that demonstrably ran it, design ended **149/350 (42.6%)** - the stage is far more decisive than the whole-history column suggests, and it is also the cheapest exit in the table.

Plus non-verdict exits, which end a candidate without any stage judging it - kept out of the rates above on purpose (D-192: "the solvers disagreed" and "we ran out of money before calling anything" must not be one number):

- `budget`: **16**
- `circuit_open`: **84**

Closure check: 849 stage rejections + 100 skips + 0 unattributed + 878 accepted = **1827** = 1827 rows.

### 3.1 How each stage was attributed

Evidence first: the pipeline stops at the first stage that fails and writes that stage's failure into `stage_results`, so the first key recording a failure *is* the stage that ended the candidate. Reason prose is the fallback for the rows written before those keys existed.

| basis | rows |
|---|---:|
| `stage_evidence` | 889 |
| `accepted` | 878 |
| `reason_text` | 60 |

### 3.2 Failure families per stage

Buckets are matched against the pipeline's own prose, first match wins, sharing `scripts/measure_gate_census.py`'s vocabulary. Counts are *reasons*, not candidates - one rejection can carry several. The vocabulary was built for the deterministic gate's failure strings, so it is most meaningful on `validation`; for `design`, `dedup`, `budget` and `circuit_open` the prose is provider-error text and lands in `other` by design.

**`design`** - other 77
**`generator`** - other 68, options 9, hint ladder 1
**`validation`** - answer key: derived answer disagrees 186, answer key: several options match 116, math notation 67, readability 66, answer leakage 51, equation unusable 21, other 9, hint ladder 3, options 2
**`dedup`** - other 16
**`solver`** - answer key: derived answer disagrees 53, other 28, options 19
**`judge`** - hint ladder 34, options 24, other 7, answer leakage 7, meta commentary 6, math notation 3
**`difficulty`** - difficulty rubric 133
**`budget`** - other 16
**`circuit_open`** - other 84

## 4. The free-gate overlap counterfactual

For every rejection carrying a `candidate_snapshot`, the item is rebuilt and today's free deterministic stage (the D-201/D-249 hint-leak pre-check plus `validate_authored_item`) is re-run over it. No model is called.

- Rejections carrying a snapshot that could be re-gated: **641**
- Of those, rejected by a **paid** stage (dedup / solver / judge / difficulty): **250**
- The free deterministic gate would **also** have rejected: **25/250 (10.0%)** (overlap)
- Only the paid stage caught it: **225/250 (90.0%)** (unique catch)

| paid stage | snapshots re-gated | free gate also rejects | unique catch | overlap |
|---|---:|---:|---:|---|
| `dedup` | 10 | 0 | 10 | 0/10 (0.0%) |
| `solver` | 60 | 16 | 44 | 16/60 (26.7%) |
| `judge` | 55 | 5 | 50 | 5/55 (9.1%) |
| `difficulty` | 125 | 4 | 121 | 4/125 (3.2%) |

**The direction that cannot be computed.** Whether the paid stages (dedup/solver/judge/difficulty) would have caught the candidates the deterministic gate rejected CANNOT be computed from this data: those stages never ran on those candidates by design, and running them now costs real money on discarded content. The nearest existing evidence is D-276, which points the other way - with the gate off, 5 wrong answer keys passed both blind solvers and the judge.

### 4.1 The deterministic stage against itself

Re-running today's gate over the candidates the gate itself rejected is a drift check on the measurement, not a claim about the content.

- Validation-stage rejections with a snapshot: **391**
- Today's gate still rejects: **262/391 (67.0%)**
- Today's gate now passes (checks relaxed or the failure was era-specific): **129**

**Most of that gap has a name.** Re-running the identical gate with `answer_form="any"` - what every skill got before D-308 introduced the per-skill canonical-form tie-break - reproduces **333/391 (85.2%)** instead. So **71** of the 129 are the D-308 relaxation working as designed, and **58** are residual drift from other checks that have changed since (D-276's restoration of the answer-key checks, D-288's notation check). Neither number is a defect in the content; both are why section 4's overlap is an upper bound.

Recorded failure families at the time: answer key: derived answer disagrees 174, answer key: several options match 116, math notation 67, readability 64, answer leakage 45, equation unusable 21, other 6, options 2.

Families today's gate raises on the same items: answer key: derived answer disagrees 89, readability 64, math notation 50, answer leakage 34, answer key: several options match 34, equation unusable 21, other 7, options 1.

## 5. Spend containment

| bucket | cents | share |
|---|---:|---|
| spent on machine-accepted candidates | 2421.96 | 59.4% |
| spent on rejected candidates | 1652.64 | 40.6% |
| **total** | **4074.61** | 100% |

Per-stage spend attribution is in the funnel table above. Note that a row's `cost_cents` is what the *slot* had spent when the row was written (D-294), so stage spend is "money on candidates this stage ended", not "money this stage's own call cost".

## 6. Strata

| requested tier | candidates | machine-accepted | acceptance rate |
|---|---:|---:|---|
| (unknown) | 234 | 0 | 0/234 (0.0%) |
| d1 | 239 | 132 | 132/239 (55.2%) |
| d2 | 456 | 343 | 343/456 (75.2%) |
| d3 | 313 | 180 | 180/313 (57.5%) |
| d4 | 388 | 160 | 160/388 (41.2%) |
| d5 | 197 | 63 | 63/197 (32.0%) |

| topic | candidates | machine-accepted | acceptance rate |
|---|---:|---:|---|
| `(unknown)` | 234 | 0 | 0/234 (0.0%) |
| `algebra_1` | 126 | 25 | 25/126 (19.8%) |
| `algebra_2` | 206 | 74 | 74/206 (35.9%) |
| `algebra_foundations` | 87 | 24 | 24/87 (27.6%) |
| `calculus` | 86 | 36 | 36/86 (41.9%) |
| `decimals` | 44 | 42 | 42/44 (95.5%) |
| `g1_addition` | 33 | 28 | 28/33 (84.8%) |
| `g1_subtraction` | 20 | 20 | 20/20 (100.0%) |
| `g1_word_problems` | 27 | 25 | 25/27 (92.6%) |
| `g2_addition` | 26 | 21 | 21/26 (80.8%) |
| `g2_subtraction` | 26 | 19 | 19/26 (73.1%) |
| `g2_word_problems` | 35 | 21 | 21/35 (60.0%) |
| `g3_word_problems` | 29 | 26 | 26/29 (89.7%) |
| `g4_multiplication_division` | 40 | 38 | 38/40 (95.0%) |
| `g4_word_problems` | 35 | 26 | 26/35 (74.3%) |
| `g5_word_problems` | 41 | 32 | 32/41 (78.0%) |
| `g68_word_problems` | 42 | 28 | 28/42 (66.7%) |
| `g6_fractions` | 117 | 35 | 35/117 (29.9%) |
| `g6_geometry_measurement` | 26 | 22 | 22/26 (84.6%) |
| `g6_word_problems` | 49 | 37 | 37/49 (75.5%) |
| `geometry_measures` | 44 | 33 | 33/44 (75.0%) |
| `linear_equations` | 205 | 88 | 88/205 (42.9%) |
| `measurement` | 49 | 45 | 45/49 (91.8%) |
| `number_sense` | 31 | 25 | 25/31 (80.6%) |
| `pre_algebra` | 44 | 39 | 39/44 (88.6%) |
| `statistics_advanced` | 65 | 33 | 33/65 (50.8%) |
| `trigonometry` | 60 | 36 | 36/60 (60.0%) |

Rows carrying neither a topic nor a tier anywhere: **234** - by attributed stage, `design` 77, `circuit_open` 74, `solver` 24, `validation` 18, `budget` 16, `generator` 14, `dedup` 6, `judge` 4, `difficulty` 1. These are the exits that happen before any item exists to describe (design and the breaker), plus the 2026-08-05/06 rows whose evidence is reason prose alone. They are counted in the `(unknown)` row above rather than dropped, so the strata denominators still sum to the row count.

## 7. The warm-up toll (D-296's structure, re-measured)

Counted over the **14** runs that carry a real `pipeline_run_id` (**292** candidates); **1535** rows predate the column and are excluded rather than clustered by timestamp - D-295 measured that reconstruction at ~90.8% fidelity and refused to present it as evidence.

| position in run | candidates | rejected | rejection rate | rejected at `difficulty` | difficulty-rejection rate |
|---|---:|---:|---|---:|---|
| 1 | 14 | 9 | 9/14 (64.3%) | 1 | 1/14 (7.1%) |
| 2 | 14 | 11 | 11/14 (78.6%) | 1 | 1/14 (7.1%) |
| 3 | 14 | 9 | 9/14 (64.3%) | 0 | 0/14 (0.0%) |
| 4 | 14 | 11 | 11/14 (78.6%) | 0 | 0/14 (0.0%) |
| 5 | 14 | 6 | 6/14 (42.9%) | 1 | 1/14 (7.1%) |
| 6 | 14 | 9 | 9/14 (64.3%) | 2 | 2/14 (14.3%) |
| 7-10 | 52 | 41 | 41/52 (78.8%) | 3 | 3/52 (5.8%) |
| 11+ | 156 | 87 | 87/156 (55.8%) | 1 | 1/156 (0.6%) |

Aggregated, the D-296 shape is present: difficulty rejections run **5/84 (6.0%)** over positions 1-6 against **1/156 (0.6%)** at position 11+. It is a weak version of it - only 292 candidates across 14 runs carry a run id, and most of those runs are small - so this reproduces the *direction* of D-295/D-296 and not their magnitudes. The mechanism itself (the `may_retier` guard blocking while the judge histogram warms up) is replayed against the real `JudgeDispersion` in `scripts/measure_retier_guard.py`; this experiment does not re-derive it.

## 8. Per-run breakdown

Full table in `per_run_breakdown.csv`. Acceptance rate by identified run:

| pipeline_run_id | candidates | accepted | acceptance rate | ¢ | ¢/accepted |
|---|---:|---:|---|---:|---|
| `(unidentified)` | 1535 | 769 | 769/1535 (50.1%) | 3381.21 | 4.40 |
| `3973e552-4cee-4b4d-852c-6fb081cf8ab3` | 68 | 43 | 43/68 (63.2%) | 169.93 | 3.95 |
| `704624f4-d643-44d7-bf57-79964e1592b1` | 24 | 10 | 10/24 (41.7%) | 68.40 | 6.84 |
| `0e68de97-5f2b-4a0d-a860-51fda2929a86` | 18 | 7 | 7/18 (38.9%) | 58.29 | 8.33 |
| `37cb300f-3f66-472d-bae6-721154e7404f` | 18 | 5 | 5/18 (27.8%) | 46.28 | 9.26 |
| `b3980d10-d50a-43fe-b083-6931e63191bc` | 42 | 16 | 16/42 (38.1%) | 71.27 | 4.45 |
| `b6935999-e18f-435a-805b-250928017604` | 30 | 3 | 3/30 (10.0%) | 27.02 | 9.01 |
| `81715795-e4d3-4b6b-b080-858a3bcb8f8f` | 8 | 8 | 8/8 (100.0%) | 21.23 | 2.65 |
| `42ae87cc-2fd3-4b61-8714-78dea2e42811` | 8 | 8 | 8/8 (100.0%) | 32.41 | 4.05 |
| `e88566a0-5834-433f-901d-90307c695975` | 16 | 0 | 0/16 (0.0%) | 53.26 | n/a |
| `6865c91e-66b1-483b-8a27-f740c8883f5f` | 20 | 3 | 3/20 (15.0%) | 54.29 | 18.10 |
| `8b2fadbb-9865-453d-8911-060b556d8ad7` | 10 | 0 | 0/10 (0.0%) | 25.25 | n/a |
| `ca44711a-dbb5-4cee-982c-d50813b2922f` | 10 | 0 | 0/10 (0.0%) | 14.46 | n/a |
| `f1b927ff-d7ca-4f36-ab41-8249d6911127` | 10 | 0 | 0/10 (0.0%) | 23.97 | n/a |
| `c806a111-ba52-47de-bb63-9b33aa234fbf` | 10 | 6 | 6/10 (60.0%) | 27.37 | 4.56 |

## 8.1 Schema eras present in the data

The table spans several pipeline generations and the evidence keys differ across them. Reported rather than smoothed over - a parser that silently dropped an era would understate exactly the stages that were added last.

| era marker | rows | what it means |
|---|---:|---|
| `candidate_snapshot` present | 641 | D-195 onward, and only on rejections after the Generator returned - the population section 4 can re-gate |
| `equation_design` present | 350 | D-200/D-294 onward; absent means the design pre-stage was off or unreached |
| `difficulty` present | 976 | D-194 onward; 28 accepted rows lack it because they predate difficulty being its own stage |
| `generator_request` present | 74 | D-243 onward; earlier generator failures recorded reason prose and nothing else |
| `stage_results` empty | 32 | 2026-08-05/06 rows, attributed from reason prose alone; 16 of them name a since-removed "narrative dressing" stage |
| `pipeline_run_id` present | 292 | D-295 onward, deliberately not backfilled |

## 9. Reconciliation against the decision record

The table now holds **1827** rows and **976** difficulty decisions - both larger than the decision record's figures, which is expected of an append-only table that kept being written to.

- **D-294's 1,184 rows.** Row 1,184 in `created_at` order was written at `2026-08-12T17:03:08.781709+00:00`, inside the 2026-08-12 session D-294 records. **Reconciles.**
- **D-295's 858 difficulty decisions.** At the 1,184-row instant only **614** difficulty decisions existed; the 858th was written at row **1535**. The two recorded numbers are therefore snapshots of the same append-only history taken at **different instants within 2026-08-12**, not of one instant. **Reconciles, with that correction** - neither figure is wrong, and quoting them as one pair would be.
- **D-296's 63%-yield run.** Its shape is visible in the per-run table above rather than re-asserted here; see section 8.
- **D-289's criterion 5, 4.7¢ per accepted item** ($24.97 over 529 serving generated items). Computed over this whole history instead: **4.64¢** (4074.61¢ / 878 machine-accepted candidates). The denominators are not the same one - D-289 counted *serving* items after human review, this counts every candidate the machine accepted - so the agreement is corroboration rather than a re-derivation.

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
