# E5.3 — Raw generation vs validated pipeline, on the same 204 candidates

> **Experiment:** E5.3 of `docs/resume_evidence/MEASUREMENT_PLAN.md` (Theme 5).
> **Environment:** real-model generation (D-447 roster), **isolated local benchmark
> database** — never staging, never production, never the dev database.
> **Repo:** `dd624d8`. **Run:** `pipeline_run_id = 0e111b3f-bd93-410e-a16c-6ee2b8e753a6`.
> **Dates:** run 2026-08-29 23:34:54 UTC → 2026-08-30 01:57:08 UTC; scored 2026-08-30.
> **Spend:** **722.55¢ ($7.23)** against a 1000¢ hard cap. One `run_plan` invocation.
> **Account/region:** 320503430250 / us-east-1.
>
> ### D-342 — what this run is and is not
>
> This is a **quality measurement**, not content production. Everything it generated lives
> in a disposable database. **Nothing was approved, exported, written to `curriculum/`, or
> counted toward any coverage target**; `review_cli` and `export_cli` were never run, and
> `git status curriculum/` is empty. The 174 "machine-accepted" items are measurement
> subjects — *machine-accepted* means **cleared the automated pipeline**, and never means
> *approved by a person*. No statement in this report is a claim about bank growth or
> coverage.

---

## 1. Headline

**Shipping raw generation would ship a defect in 1 item of every 7. The validated pipeline
ships zero of every defect family it checks — and one it does not.**

| | raw generation | validated pipeline |
|---|---|---|
| what it is | every schema-valid generator output, scored as if it shipped with no gate, no solvers, no judge | the machine-accepted subset of the *same* candidates |
| n | **202** | **174** |
| items carrying ≥1 deterministic defect | **30 / 202 = 14.85%** | **8 / 174 = 4.60%** |
| items carrying a **gate-checkable** defect | **22 / 202 = 10.89%** | **0 / 174 = 0.00%** |

Per defect family, numerator and denominator throughout (`defect_families.csv`):

| defect family | raw n/N | raw rate | validated n/N | validated rate |
|---|---|---|---|---|
| answer key: derived answer disagrees with the declared key | 19/202 | **9.41%** | 0/174 | **0.00%** |
| duplicate scenario (skeleton collision within the run) | 14/202 | **6.93%** | 8/174 | **4.60%** |
| age-appropriate wording / readability ceiling | 3/202 | **1.49%** | 0/174 | **0.00%** |
| answer leakage, hint-ladder monotonicity, hint/solution disagreement, option structure, schema/markdown, meta-commentary, notation | 0/202 | 0.00% | 0/174 | 0.00% |

The **0.00%** column for every gate-checkable family is true **by construction** — those
checks are exactly what the pipeline runs before accepting — and it is reported anyway,
because a re-scored 0 is what proves the instrument and the gate agree. They do, exactly:
this experiment's independent re-score of the raw arm found 19 answer-key + 3 readability
defects, and the pipeline's own gate rejected 19 + 3 = **22** candidates at the validation
stage. Two different code paths over the same 202 items, same number, same items.

**The one family that survives acceptance is duplication**, at 4.60% — and §5 shows the
true repetition rate is higher still.

## 2. What was run

One `run_plan` invocation, repair loop off (so the raw arm is a clean one-shot sample):

| | |
|---|---|
| slot plan | 10 skills × the tiers each declares, filtered to tiers 1–5 = **34 (skill, tier) pairs × 6 candidates = 204** |
| skills | `g1_add_within_10`, `g2_sub_two_digit`, `g3_wp_mixed`, `g4_div_by_one_digit`, `g5_wp_ratios_mixed`, `g6_wp_rate_speed`, `prealg_exponents`, `linear_two_step`, `alg1_quadratics`, `trig_functions` |
| topics spanned | 10 (g1 → trigonometry), grade 1 through high-school algebra/trig |
| tier distribution | d1 ×6, d2 ×8, d3 ×9, d4 ×6, d5 ×5 pairs |
| seed offset | **20 000 000** — above every historical run offset (max seed seen: 9 500 002) and far below the 990 000 000+ range the preflight tests reserve. 204 planned ids claimed, **0 already used** |
| budget | `--run-budget-cents 1000`, equal to the configured hard cap; **0 budget skips** |
| roster (D-447) | generator + equation design + solver B = `us.anthropic.claude-sonnet-4-5-20250929-v1:0`; solver A + judge = `us.anthropic.claude-haiku-4-5-20251001-v1:0`; embedding `amazon.titan-embed-text-v2:0` |

**Why this slot plan.** D-296's 63%-yield run spanned 8 topics at tiers 1–4 with ~2
candidates per slot; this mirrors its shape (multi-topic, full grade range) while widening
to all five tiers and deepening to 6 candidates per slot, because the two arms are compared
*within* the run and a thin slot gives duplication nowhere to show up. The CLI filters are a
cross-product (`--skill-id` × `--difficulty`), so the 34 pairs were reached by choosing
skills whose declared tier lists sum to 34 across tiers 1–5 — one skill per topic, spread
across grade bands.

**Invocability was re-measured before spending** (`model_invocability.json`). D-273's rule
is that `agreementAvailability = AVAILABLE` is not a promise you can call the model, and
the recorded 2026-08-11 stratum expired by its own terms. A 1-token `converse` per distinct
roster id on 2026-08-29 returned **invocable** for both Haiku 4.5 and Sonnet 4.5. Preflight
then passed on solver diversity, id availability and model access (`preflight.txt`).

## 3. The run

```
174 accepted of 204 processed (85%, of which retiered=26), 204 scheduled, 722.55 cents spent.
  rejected: generator=2 design=0 validation=22 dedup=0 solver=2 judge=4 difficulty=0
  skipped: budget=0 circuit_open=0 duplicate_id=0
```

| metric | value |
|---|---|
| candidates processed | **204 / 204** scheduled (no early stop) |
| machine-accepted | **174** = 85.29% of attempts, 86.14% of the 202 that returned an item |
| total spend | **722.55¢** = 72.3% of the 1000¢ cap |
| cost per attempt | **3.54¢** |
| cost per machine-accepted candidate | **4.15¢** |
| share of spend on rejected candidates | **13.7%** (99.21¢ of 722.55¢) |
| wall clock | **141.9 min** first candidate → last |
| throughput | **1.44 candidates/min** |

Throughput landed just under the ~1.5/min the project has recorded, with no throttling: the
account cap behaved as documented, and the early-stop rule (stop at ≥120 if throughput
collapses) was never triggered.

Two candidates never returned an item — `authored generator call failed: Bedrock call
failed:` — and are **excluded from the raw arm's denominator**, not counted as quality
defects (D-230: a call that never returned says nothing about content). That is why the raw
arm is n=202 and the run is n=204.

### 3.1 Per-stage funnel (E5.1 harness, reused unchanged)

`funnel/` holds `stage_funnel_analysis.py`'s own output for this `pipeline_run_id`. The
harness was not forked or modified; it was pointed at this run with `--pipeline-run-id` and
a separate `--out-dir`.

| stage | reached | rejected | rejection rate | ¢ ended here |
|---|---|---|---|---|
| design | 204 | 0 | 0.0% | 0.00 |
| generator | 204 | 2 | 1.0% | 2.44 |
| **validation (free deterministic gate)** | 202 | **22** | **10.9%** | 74.16 |
| dedup | 180 | **0** | 0.0% | 0.00 |
| solver panel | 180 | 2 | 1.1% | 7.14 |
| judge | 178 | 4 | 2.2% | 15.47 |
| difficulty | 174 | 0 | 0.0% | 0.00 |

(The ¢ column is the cost of the candidates that *ended* at each stage, not the cost of
running that stage — the E5.1 harness's own convention.)

**The overlap counterfactual, run over this run: of the 6 paid-stage rejections, the free
deterministic gate would have caught 0. All 6 were unique catches.** That is the other half
of D-276. D-276 showed that with the gate off, five wrong answer keys passed both blind
solvers and the judge — SymPy catches what the models miss. This run shows the reverse
edge with equal clarity: the solvers and the judge caught six defects the arithmetic
cannot express, and §5.3 names them.

### 3.2 The judge warm-up toll cost this run nothing

`_MIN_JUDGE_OBSERVATIONS = 5` blocks re-tiering while the judge's rating histogram warms
up, and D-296 measured the toll as difficulty rejections concentrated in a run's first
positions. Here `rejected_difficulty = 0`. The reason is an accident of ordering worth
recording: the plan is walked alphabetically by topic, so positions 1–18 were all
`alg1_quadratics`, every one of which was rejected at the free gate *before* reaching the
judge. The warm-up window was spent on candidates the judge never saw.

## 4. The one skill that produced nothing, and why

| skill | machine-accepted / attempted | rate |
|---|---|---|
| `g6_wp_rate_speed` | 24/24 | 100.0% |
| `g3_wp_mixed` | 23/23 | 100.0% |
| `g2_sub_two_digit` | 18/18 | 100.0% |
| `g4_div_by_one_digit` | 18/18 | 100.0% |
| `g5_wp_ratios_mixed` | 18/18 | 100.0% |
| `g1_add_within_10` | 12/12 | 100.0% |
| `linear_two_step` | 16/17 | 94.1% |
| `trig_functions` | 27/30 | 90.0% |
| `prealg_exponents` | 18/24 | 75.0% |
| **`alg1_quadratics`** | **0/18** | **0.0%** |

The pipeline's own summary flagged it without being asked: *"ACCEPTED NOTHING:
alg1_quadratics (0 of 18) — a skill at zero is a structural failure, not a low yield —
re-running will not change it."* The hand audit identifies the mechanism: the generator
writes the quadratic in standard form as a **bare expression** (`x**2 + 4*x - 60`) rather
than as an equation (`Eq(x**2 + 4*x - 60, 0)`), so `derive_answer` cannot solve it and the
gate rejects — 17 of the 18. The 18th declared a single key for a genuinely two-root
quadratic (`{8, -5}` vs `'5'`).

**This matters for how the headline is read.** The 19 `answer key: derived answer disagrees`
rows in the raw arm decompose as **17 unsolvable-expression + 1 multi-root vs single key +
1 absent equation**. Reading the items (§5.2 of `hand_audit.md`), the questions, the keys
and the worked solutions are *mathematically correct*. So the raw arm's 9.41% is a
**verifiability** failure, not an arithmetic-error rate. Both are disqualifying for
shipping — an answer nobody can derive is exactly as unshippable as a wrong one, which is
the whole design of rule 5 (fail closed) — but the report will not claim 19 wrong answers
when it measured 19 unverifiable ones.

Excluding `alg1_quadratics`, the run accepted **174 / 184 = 94.6%**.

Acceptance falls monotonically with requested tier — d1 97.2% (35/36), d2 97.9% (46/47),
d3 81.1% (43/53), d4 75.0% (27/36), d5 76.7% (23/30) — and `alg1_quadratics` sits entirely
at d3–d5, which accounts for most of the drop.

## 5. What survived acceptance

### 5.1 Duplication is the only deterministic defect that passes

8 of 174 machine-accepted items (**4.60%**) sit in a within-run skeleton collision: the same
sentence with different numbers. The pipeline's dedup stage rejected **0**, and it is not
misconfigured — it is scoped:

- `rendered_question_exists` is an **exact text** match; different digits defeat it.
- `stem_skeleton_exists_in_another_topic` is the D-286 skeleton check, and by its own name
  fires only **across topics**.
- `stem_near_duplicate_exists` is an embedding cosine check **within a topic**, and did not
  fire at the configured threshold.

**All 7 collision groups in this run are same-topic, same-skill, different-tier pairs** —
precisely the gap between those three predicates. Example: `g6_wp_rate_speed` produced "A
freight train travels 180 miles in 4 hours…" (requested d4, stored d1) and "A freight train
travels 135 miles in 9 hours…" (requested d3, stored d2). Both accepted, and the pair is the
same sentence twice — a student working through this skill's ladder would meet it at two
different tiers.

### 5.2 The thresholded signal, and what the hand audit adds

The knobless skeleton signal is the headline; the thresholded one is reported separately so
the headline keeps no tuning in it. At Jaccard ≥ 0.75 over content words there are **29
near-duplicate pairs covering 35 candidates**. Of the **17** pairs in which both members
were machine-accepted, **6 (35.3%) are stored at different difficulty tiers** — including a
d5/d3 pair of structurally identical "garden centre receives N flats × M plants" items.

The hand audit found a three-item version the *knobless* signal misses entirely, because
the verbs differ ("orders/receives/receives", "lends/distributes/sells"): three
`g3_wp_mixed` items that are all "N boxes × M items, then K removed", all accepted, stored
at **d3, d5, d5**. So 4.60% is a **floor** on repetition, not an estimate of it.

### 5.3 Defects only the paid stages caught

Six candidates were rejected by the solver panel or the judge, and the free gate would have
caught **none** of them. Reading them (`hand_audit.md` §3b), they are all
**scenario-fidelity** defects — the equation is internally consistent with the declared key,
so SymPy agrees, but the scenario the equation is attached to is not the one it models:

- a ramp that "rises 1 metre for every 2 metres of horizontal distance" with
  `equation = Eq(x, sin(pi/6))` and key `1/2`. The stated geometry gives sin θ = 1/√5.
  Gate: pass. Solver A: caught.
- a surveyor's *angle of elevation* of 5π/6 radians (150°), physically impossible. Judge.
- `(−3)⁴` presented as the "total effect" of four consecutive 3-degree temperature drops —
  exponentiation modelling repeated addition. Judge.

**This is the counterpart to D-276 and it belongs beside it.** D-276: with the deterministic
gate off, five wrong answer keys passed both blind solvers *and* the judge — the models
cannot replace SymPy. E5.3: the free gate checks *equation ↔ key*, never *scenario ↔
equation*, and a generator that writes both fields to agree with each other passes it every
time — the solvers and judge cannot be replaced by SymPy either. Both stages earn their
place, against different defect classes, and this run measured each direction on the same
204 candidates.

### 5.4 Hand audit, 30 items, drawn before reading

Seed 20260829, 15 machine-rejected + 15 machine-accepted, stratified proportionally over
requested tier. Full write-up: `hand_audit.md`.

| | machine-rejected (n=15) | machine-accepted (n=15) |
|---|---|---|
| wrong answer key / wrong arithmetic | 0/15 | **0/15 (0.0%)** |
| ≥1 defect the deterministic scorer cannot see | 4/15 (26.7%) | **4/15 (26.7%)** |
| rejection judged correct on reading | 15/15 (100%) | — |

Among accepted items: scenario repetition 3/15 (20.0%), unstable tier between near-identical
items 3/15 (20.0%), a scenario that cannot host its own arithmetic 1/15 (6.7%) — a microbe
population that "multiplies by −2 each cycle", whose twin defect the judge *rejected* in the
same run. Zero wrong answers or wrong keys, agreeing with the deterministic arm's 0/174.

**The number to carry:** the deterministic scorer says the accepted arm is 0.00% defective
on everything it can check, and it is right; a human reading 15 of those items rejected
**4**. Machine acceptance is not human approval, and this quantifies the distance.

### 5.5 Tier storage, stated precisely

Of the 174 accepted items, the judge's difficulty verdict was `accepted` for 69, `flagged`
for 79 and `retiered` for 26. **104 of 174 (59.8%) are stored at a tier other than the one
the slot requested** — because D-302 stores the judge's tier on `flagged` as well as on
`retiered`, deliberately. The `RunSummary`'s `retiered=26` counts only the `retiered`
decision, so it must not be read as "tier moved 26 times". Any tier claim about this
pipeline has to be made against `stored_difficulty` (D-302), and the hand audit shows why:
read at the *requested* label the g1 addition ladder looks inverted; read at the *stored*
label it is correct, because the adjudicator fixed it.

## 6. Isolation

Proof and exact setup commands: `isolation_proof.md`.

| dev database (`intellichoice`) | `question_templates` | `question_validation_runs` |
|---|---|---|
| before the run (2026-08-29 23:33 UTC) | 1077 | 1827 |
| after the run and all scoring (2026-08-30 02:02 UTC) | **1077** | **1827** |

Unchanged. The run used a second database, `intellichoice_e53`, created empty, migrated by
`alembic upgrade head` replaying the full chain, and loaded with the committed taxonomy and
bank (33 topics / 112 skills / 958 templates) so the dedup stage saw the corpus a real run
would. `DATABASE_URL` selected it for every command. `git status curriculum/` is empty; no
export ran; no approval path was opened; no staging or production system was contacted.

## 7. Limitations

1. **One run, one roster, one seed offset.** Every rate here is a property of this run's
   204 candidates under the D-447 roster on 2026-08-29. It is not a bank-wide or
   pipeline-wide constant, and a different model in the generator slot could move all of it.
2. **The slot plan was chosen, not sampled.** 10 skills of the 99 authorable, 34 of 272
   (skill, tier) pairs. It spans the grade range deliberately, but it is a designed sample
   and `alg1_quadratics` alone moves the headline by ~9 points.
3. **Machine acceptance ≠ human approval**, and §5.4 measures the gap at 4 of 15 on a hand
   read. Nothing here says an accepted item is publishable; **D-342** says none of them will
   be published.
4. **The deterministic scorer is blind to prose.** It cannot see plausibility, ambiguity,
   distractor quality, or whether the equation models the story. The hand audit is the bound
   on that blindness and is n=30 — roughly ±12 points at 95% confidence, one reader, not
   blinded to the machine verdict (the D-285 limitation, unchanged).
5. **The raw arm's accepted half is reconstructed, not snapshotted.** A rejection carries
   `candidate_snapshot`; an acceptance does not, so accepted items were rebuilt from the
   persisted `question_templates` + canonical `question_variants` rows. Four generator
   fields have no column; three are recovered from the row's own difficulty and prerequisite
   evidence and the fourth (`reasoning`) is substituted. **None of the four is read by any
   deterministic check** — asserted by test
   (`test_reconstruction_preserves_every_field_the_gate_reads`), not assumed.
6. **The 0.00% validated-arm rate for gate-checkable families is true by construction** and
   is reported as a consistency check on the instrument, not as a discovery.
7. **`answer_form` is `'any'` for all 10 skills**, so D-308's canonical-form tie-break was
   never exercised in either arm.
8. **The duplicate signals measure within-run repetition only**, as specified; repetition
   against the 958-item committed bank was left to the pipeline's own dedup stage and is not
   independently scored here.

## 8. Artifacts

| file | what it is |
|---|---|
| `run_summary.json` | run configuration, models, plan, timings, the pipeline's own `RunSummary` |
| `raw_arm_scores.jsonl` | 202 rows — one per generator-returned candidate, with item text, defect families, failures, pipeline reasons |
| `validated_arm_scores.jsonl` | the 174 machine-accepted rows, same schema |
| `defect_families.csv` | the §1 table, machine-readable, with both denominators |
| `scoring_summary.json` | arm summaries, acceptance, economics, duplicate detail |
| `funnel/` | `stage_funnel_analysis.py` (E5.1 harness, unmodified) over this `pipeline_run_id` |
| `hand_audit.md`, `hand_audit_worksheet.md`, `hand_audit_sample.json` | the 30-item audit, its worksheet, and the seeded draw |
| `model_invocability.json` | dated per-model 1-token invocability probe |
| `preflight.txt`, `run_stdout.log` | the free preflight and the full run log |
| `isolation_proof.md` | setup commands and the dev-DB before/after counts |

Harness code: `benchmarks/resume_evidence/05_content_generation/raw_vs_validated_scoring.py`,
`model_invocability_probe.py`, `hand_audit_sample.py`. Tests:
`packages/curriculum/tests/test_raw_vs_validated_scoring.py`,
`test_model_invocability_probe.py`.

## 9. Reproduce

```bash
docker compose exec -T postgres psql -U intellichoice -d postgres \
  -c "CREATE DATABASE intellichoice_e53 OWNER intellichoice;"
docker compose exec -T postgres psql -U intellichoice -d intellichoice_e53 \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
export DATABASE_URL="postgresql+asyncpg://intellichoice:intellichoice@localhost:5432/intellichoice_e53"
(cd packages/db && uv run alembic upgrade head)
uv run python -m intellichoice_curriculum.loader

export CURRICULUM_BEDROCK_PROVIDER=bedrock AWS_PROFILE=<profile>
uv run python benchmarks/resume_evidence/05_content_generation/model_invocability_probe.py \
  --out docs/resume_evidence/05_content_generation/e5_3/model_invocability.json

uv run python -m intellichoice_curriculum.pipeline_cli --preflight \
  --skill-id g1_add_within_10 --skill-id g2_sub_two_digit --skill-id g3_wp_mixed \
  --skill-id g4_div_by_one_digit --skill-id g5_wp_ratios_mixed --skill-id g6_wp_rate_speed \
  --skill-id prealg_exponents --skill-id linear_two_step --skill-id alg1_quadratics \
  --skill-id trig_functions \
  --difficulty 1 --difficulty 2 --difficulty 3 --difficulty 4 --difficulty 5 \
  --candidates-per-slot 6 --seed-offset 20000000 --run-budget-cents 1000
# drop --preflight to spend; a fresh --seed-offset is required for a repeat

uv run python benchmarks/resume_evidence/05_content_generation/raw_vs_validated_scoring.py \
  --pipeline-run-id <id> --out-dir docs/resume_evidence/05_content_generation/e5_3
uv run python benchmarks/resume_evidence/05_content_generation/stage_funnel_analysis.py \
  --pipeline-run-id <id> --out-dir docs/resume_evidence/05_content_generation/e5_3/funnel
uv run python benchmarks/resume_evidence/05_content_generation/hand_audit_sample.py \
  --scores docs/resume_evidence/05_content_generation/e5_3/raw_arm_scores.jsonl \
  --out-dir docs/resume_evidence/05_content_generation/e5_3 --seed 20260829
```
