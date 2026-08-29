# E5.2 - Seeded-defect detection benchmark: precision, recall and F1 across six defect classes

> Experiment: **E5.2** of `docs/resume_evidence/MEASUREMENT_PLAN.md` (Theme 5).
> Generated: **2026-08-29T21:44:06Z** (corpus rebuilt and one item re-scored at 22:05:29Z) at
> repository `469bb5638cd69ed829d20cb5daa4dfe7f8f5f10e`.
> Environment: **real-model evaluation (blind solver panel) + deterministic gate, local.**
> No database write, no staging, no production, no bank write - every corpus item exists only
> in memory and in the artifacts listed in §12.
> Models: Solver A `us.anthropic.claude-haiku-4-5-20251001-v1:0`, Solver B
> `us.anthropic.claude-sonnet-4-5-20250929-v1:0`, embeddings `amazon.titan-embed-text-v2:0`
> (the D-273 roster; invocability re-probed at the start of each run - §3).
> Cost of this measurement: **131.23 cents** against a hard ceiling of 200.
> Harness: `benchmarks/resume_evidence/05_content_generation/build_defect_corpus.py` and
> `run_defect_detection.py`. Corpus seed `520000`; every mutation is reproducible from it.

## 1. What this replaces

The recorded negative controls for the authoring pipeline are `audit_authored_bank.py
--self-test` (move every declared answer to a wrong option, count the objections: **12/12**,
D-229) and the hint-leak control (**32/32**, D-246). Both are real evidence and both share
three limits: one defect class each, n small enough that one miss moves the figure eight
points, and - the structural one - **no clean items at all**.

No clean items means no precision. A detector that flags everything scores 12/12 on that
control and so does a detector that works. This experiment supplies the missing half (102
unmutated approved items, blocked so every class has a matched negative set) and widens the
first to six classes at n = 102, chosen so that a *different* stage of the pipeline is the only
thing that can catch each one. A benchmark whose defects all die at the same check measures
that check six times.

## 2. Headline

Over **102 labeled defects across 6 classes** and **102 clean controls** from the same
approved bank, all drawn from 29 topics, 87 skills and all five difficulty tiers:

| | value |
|---|---|
| Pipeline as a whole (gate ∪ dedup ∪ solver panel) | recall **72/100 (72.0%)**, precision **1.000**, F1 **0.837** |
| False positives on the 102 clean controls | **0/102 (0.0%)** for the gate, the solver panel, the dedup check and the union |
| Deterministic gate alone (free) | recall **51/102 (50.0%)**, 0/102 clean FP |
| SymPy re-derivation alone (free) | recall **34/102 (33.3%)**, 0/102 clean FP |
| Blind solver panel alone (paid) | recall **47/100 (47.0%)**, 0/102 clean FP |
| Cost | **0.32 cents/call**, 408 solver calls, **131.23 cents** total |

Denominators of 100 rather than 102 where two items' solver calls failed and are therefore
excluded from every solver-dependent figure (D-230 - §7.5).

Three results carry more than the headline does:

1. **One defect class is caught by nothing.** `mismatched_hint_ladder` scores **0/17 on every
   detector in the pipeline**, and is 17 of the 28 total misses. Excluding it, combined recall
   is 72/83 (86.7%).
2. **The deterministic gate and the solver panel are close to disjoint, not redundant.** Each
   alone is ~50%; together with dedup they reach 72%. The class the gate cannot see
   (`contradictory_constraints`, 0/17 gate) is the one the solvers catch best (13/15), and it
   is exactly the failure `check_sympy_independent_solve`'s own docstring warns about.
3. **The near-duplicate threshold is sharper than the defect.** Cosine distance 0.05 catches a
   typography-only clone every time (6/6, distances 0.006-0.014) and a renamed clone twice in
   six (0.041-0.246); a clone with a renamed protagonist *and* a renamed object is missed 5/5
   (0.365-0.502) while being the same question. The free `arithmetic_identity` check catches
   all 17.

## 3. Environment, models and spend

The paid arm refuses to start without `CURRICULUM_BENCH_REAL_BEDROCK=1` and
`CURRICULUM_BEDROCK_PROVIDER=bedrock`, and refuses if Solver A and Solver B resolve to the same
underlying model (their agreement would be one opinion counted twice). It then re-probes both
slots before spending, because **AVAILABLE is not invocable** (D-273) and the recorded
2026-08-11 invocability stratum expired by its own rule:

```
invocability probe solver_a (us.anthropic.claude-haiku-4-5-20251001-v1:0): OK - selected 'b'
invocability probe solver_b (us.anthropic.claude-sonnet-4-5-20250929-v1:0): OK - selected 'b'
```

The probe is the smallest *legal* structured call rather than literally one token - the gateway
speaks only structured output, so a probe has to be a schema-valid `SolverResponse`; it is a
one-line arithmetic question at a 200-token ceiling.

Spend accounting, all from the artifacts:

| | cents |
|---|---:|
| Main pass - 204 items × 2 solver calls | 129.34 |
| Main pass - invocability probes (2 slots) + embeddings (204 stems) | 0.53 |
| Re-score pass - 1 item (see §4.1), probes and embeddings again | 1.36 |
| Corpus construction, deterministic gate, SymPy, identity and exact-text dedup | 0.00 |
| **Total actually spent, against a 200-cent hard ceiling** | **131.23** |
| *of which superseded:* the main pass's row for `e52-no_correct_option-012` | *0.58* |
| Sum of the per-item costs in the committed artifact (203 + 1 rows) | 129.60 |

Cost per solver call **0.32¢** - consistent with D-229's recorded 0.34¢/call at 278 calls.
Recorded run window for the 204-item pass: 21:44:06Z → 22:04:07Z. The budget guard is
abort-not-truncate: before every item the harness prices the two calls it is about to make with
the gateway's own `worst_case_cost_cents` and stops if that would cross the ceiling; it never
fired, because the projection at 10 calibration items (0.70¢/item) already put the full run at
~143¢.

Every row is persisted the moment it completes, so a stopped run keeps what it paid for, and
the run order round-robins over the seven groups so a stopped run is a *balanced* sample rather
than seventeen complete `wrong_numeric_answer` rows and nothing else.

## 4. The corpus

`defect_corpus.jsonl` - 204 records plus a header, 560 KiB, committed. Every record carries its
source bank item id, class, seed and the exact mutation applied.

**Source pool.** 918 of the bank's 958 approved items. 40 excluded and recorded with reasons:
22 carry a `figure_spec` (their gate verdict depends on a figure the corpus record cannot carry
readably) and 18 carry a `figure_reading`, which by design *replaces* the equation as the
source of truth, so `check_sympy_independent_solve` never runs on them and three of the six
mutations would have nothing to act on. **Zero items were excluded for already failing the
gate**, which is itself a check: every item in this bank was approved through this gate, so a
failure there would have meant the bank and the gate had drifted apart.

**Sampling.** Round-robin over (topic, difficulty) cells, then a per-topic cycle of six control
slots and one slot per mutation class, then a topic-and-tier rotation before any prefix is
taken. The last step was added twice, both times after measuring a real defect: a plain prefix
of the cell round-robin is the alphabetically-first two thirds of the topics (the controls held
no `place_value`, `trigonometry` or `statistics_advanced` item at all, and the dedup detector -
which compares only within a topic - had no reference set for a third of the corpus), and
fixing that alone made every topic's pool ascend by difficulty, putting tier 5 at 8 of 204. The
shipped corpus covers 29/29 topics and all five tiers **on both sides**:

| | topics | skills | d1 | d2 | d3 | d4 | d5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 102 defects | 29 | - | 13 | 41 | 23 | 18 | 7 |
| 102 clean controls | 29 | - | 18 | 33 | 17 | 23 | 11 |
| corpus | 29 | 87 | 31 | 74 | 40 | 41 | 18 |

(The bank's own tier distribution is 15/37/22/18/8 percent, so the corpus is close to
proportional rather than balanced - tier 5 is genuinely scarce in the bank.)

**Disjointness.** Every mutation source is disjoint from every clean control, and each
near-duplicate clone is a clone *of* a clean control. Both are load-bearing: the controls are
the dedup detector's reference set standing in for "the approved bank", so a mutated item whose
source were also a control would register as a duplicate of itself, and a clone of anything
else would have nothing to be a duplicate of. Asserted by
`test_committed_corpus_meets_the_measurement_plan_shape`.

### 4.1 The six classes, and how each mutation was verified

Nothing is admitted to the corpus on the strength of "the edit was applied". Each mutation is
run against the real gate, or against `route_answer`, before it is accepted.

| class | n | the mutation | admitted only if |
|---|---:|---|---|
| `wrong_numeric_answer` | 17 | `correct_option` re-pointed at a distractor (seed-chosen letter) | the gate fails with *"does not match declared correct option"* |
| `no_correct_option` | 17 | every option's first numeral shifted by one delta | `resolved_matches` finds **no** option stating the derived answer |
| `mismatched_solution` | 17 | `canonical_solution` replaced by another item's, whole | the gate fails on `check_hint_solution_answer_agreement` |
| `mismatched_hint_ladder` | 17 | `hint_ladder` replaced by a **numeral-disjoint** donor's | the donor shares no numeral with this question or its equation |
| `contradictory_constraints` | 17 | one stem numeral shifted; equation, options and key untouched | the **shadow equation** (same shift, applied to the equation) derives a *different* answer |
| `near_duplicate` | 17 | a clean control cloned with cosmetic edits at three graded severities | the clone still **passes** the gate and keeps its `arithmetic_identity` |

Two of those admission tests were written after they caught something.

- **`no_correct_option` had a real hole.** The obvious test - "the gate now rejects the declared
  key" - admits an item where the uniform shift moved a *distractor* onto the true answer:
  options 9/6/5/11 with a derived answer of 9 become 12/9/8/14, the declared option no longer
  matches, and the answer is still on the page under a different letter. That is a
  `wrong_numeric_answer` item wearing a `no_correct_option` label. Measured on the first build:
  **1 of 17** items (`e52-no_correct_option-012`, options `15/25, 9, 6, 11/75` with a derived
  answer of 6). The admission test is now `resolved_matches` returning nothing - the pipeline's
  own reading sequence, asked whether *any* option states the answer - and the delta loop
  advances until it does. That one item was rebuilt at delta 7 and re-scored; the other 16 are
  byte-identical to the first build.
- **`contradictory_constraints` needs the shadow equation.** "Perturbed the stem" could mean
  "perturbed it into an equivalent problem", and such an item would be filed as an undetected
  defect while not being a defect at all. The corpus records both answers per item, e.g.
  declared `(4,)` vs stem-implied `(34/7,)`.

63 mutation attempts were skipped and recorded: 62 near-duplicate candidates with no first name
the name-swap tiers recognise, 1 with no swappable story noun. That is a **sampling bias worth
naming**: the two name-based severity tiers can only clone word problems with a named
protagonist, so those 11 items are word-problem-heavy relative to the corpus as a whole.

**Deliberately not included: hint answer leakage.** D-246 already measured that class at 32/32
against this same, unchanged, free gate check. Re-buying solver calls for the least uncertain
class in the subsystem would have spent this experiment's budget on a number already recorded.

## 5. The detectors

Four free, two paid, one union. All six are the pipeline's own code, imported rather than
restated (the AUD-C-25 lesson: a benchmark that reimplements the check it is scoring measures
its own copy).

| detector | what it is | cost |
|---|---|---|
| `deterministic_gate` | `validate_authored_item` - the whole §5.8.5 suite, called exactly as `loader._gate` calls it, with the skill's own `answer_form` | free |
| `sympy_rederivation` | `check_sympy_independent_solve` alone, reported separately because D-276 is the strongest single result in this subsystem | free |
| `exact_text_dedup` | the cheap check the pipeline runs first: is this exact rendered question already in the reference set | free |
| `arithmetic_identity` | D-273's "same calculation, different story" check. **Present in the codebase and deliberately not wired into the pipeline** (`ai_pipeline` §2b) | free |
| `dedup_embedding` | the production near-duplicate check: embed `item.stem`, cosine-compare against reference items **in the same topic**, flag below `NEAR_DUPLICATE_COSINE_DISTANCE_THRESHOLD = 0.05` | ~0.05¢ for the corpus |
| `solver_panel` | Solver A + Solver B through the two distinct task slots, verdicts through `solver_objections`; payload built the way `ai_pipeline` builds it, including D-196's `rendered_for_model()` | 0.32¢/call |
| `combined_pipeline` | gate ∪ dedup ∪ solvers - the three machine stages of `run_authored_candidate` this corpus can exercise, unioned fail-closed as the pipeline unions them | - |

The judge stage is **not** measured. Its ±1-tier noise is documented (D-238/D-239) and
difficulty is not a defect class here.

## 6. Results

### 6.1 Recall per class × detector (n/N)

| detector | wrong answer | no correct option | mismatched solution | mismatched hints | contradictory constraints | near-duplicate | ALL |
|---|---:|---:|---:|---:|---:|---:|---:|
| `deterministic_gate` | 17/17 | 17/17 | 17/17 | 0/17 | 0/17 | 0/17 | **51/102** |
| `sympy_rederivation` | 17/17 | 17/17 | 0/17 | 0/17 | 0/17 | 0/17 | 34/102 |
| `exact_text_dedup` | 0/17 | 0/17 | 0/17 | 0/17 | 0/17 | 0/17 | 0/102 |
| `arithmetic_identity` | 2/17 | 0/17 | 0/17 | 1/17 | 1/17 | 17/17 | 21/102 |
| `dedup_embedding` | 0/17 | 0/17 | 0/17 | 0/17 | 0/17 | 8/17 | 8/102 |
| `solver_panel` | 17/17 | 17/17 | 0/17 | 0/17 | 13/15 | 0/17 | **47/100** |
| `combined_pipeline` | 17/17 | 17/17 | 17/17 | 0/17 | 13/15 | 8/17 | **72/100** |

`arithmetic_identity`'s flags outside `near_duplicate` are not detections of the labeled
defect - they are the same phenomenon as its clean-set flags, and §7.4 shows what they are.

### 6.2 Pooled: precision, recall, F1, clean-set false-positive rate

102 defects against 102 clean controls.

| detector | TP | FN | FP | TN | unscored | precision | recall | F1 | clean FP rate |
|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| `deterministic_gate` | 51 | 51 | 0 | 102 | 0 | 1.000 | 0.500 (51/102) | 0.667 | 0.000 (0/102) |
| `sympy_rederivation` | 34 | 68 | 0 | 102 | 0 | 1.000 | 0.333 (34/102) | 0.500 | 0.000 (0/102) |
| `exact_text_dedup` | 0 | 102 | 0 | 102 | 0 | - | 0.000 (0/102) | - | 0.000 (0/102) |
| `arithmetic_identity` | 21 | 81 | 4 | 98 | 0 | 0.840 | 0.206 (21/102) | 0.331 | 0.039 (4/102) |
| `dedup_embedding` | 8 | 94 | 0 | 102 | 0 | 1.000 | 0.078 (8/102) | 0.145 | 0.000 (0/102) |
| `solver_panel` | 47 | 53 | 0 | 102 | 2 | 1.000 | 0.470 (47/100) | 0.639 | 0.000 (0/102) |
| `combined_pipeline` | 72 | 28 | 0 | 102 | 2 | 1.000 | 0.720 (72/100) | 0.837 | 0.000 (0/102) |

Per-class precision needs a matched negative set, which is why the 102 controls are blocked
into six groups of 17 - one per class - rather than pooled. The full per-class quadrant table
(TP/FN/FP/TN, precision, recall, F1, clean FP for every class × detector cell, plus the three
near-duplicate severities) is `detection_metrics.csv` - 70 rows, one per detector × scope.

## 7. What the numbers say

### 7.1 A defect class nothing catches

`mismatched_hint_ladder` - three rungs lifted wholesale from a different item, chosen so they
share no numeral with the question they are attached to - is **0/17 for every detector**, and
accounts for 17 of the pipeline's 28 misses.

This is a structural hole, not a tuning problem, and both halves of it are visible in the
source. `hint_ladder_monotonicity_violations` is verbatim substring containment and its own
docstring says so ("**Do not read the name and conclude monotonicity is handled**"); the only
other hint check is answer leakage, which asks whether a rung states *this* item's answer. And
`SolverPayload` carries the rendered question and four options - the solvers are never shown a
hint. So no stage of the pipeline this corpus exercises ever compares a hint with its stem.

That is not the same as "no coverage exists": `HINT_SOLUTION_REVIEW.md` §3 is the instrument for
hint quality, it is an LLM reviewer, and it is not part of the generation gate path. What is
measured here is that **the generation path itself contains nothing that would stop a
mismatched hint ladder from being served**, and this is the first number attached to that.

`test_mismatched_hint_ladder_is_a_defect_the_gate_cannot_see` fails if the gate ever grows such
a check - the row above is then stale and must be re-measured, not re-worded.

### 7.2 The gate and the solver panel are complementary, and the split is exactly where the docstrings said it would be

Neither detector is a subset of the other:

- the gate catches 17/17 `mismatched_solution` and the solvers catch 0/17 - the solution is
  never in the solver payload;
- the solvers catch 13/15 `contradictory_constraints` and the gate catches 0/17 - the equation
  still derives its declared answer, so there is nothing for SymPy to object to.

The second is `check_sympy_independent_solve`'s own warning turned into a measurement: *"it
verifies equation -> answer, never situation -> equation. A model that equates two robots'
rates instead of their totals gets a faithfully-solved wrong answer."* Every one of these 17
items is that sentence: a stem numeral moved, the equation and answer key left alone.

It is also the mirror of D-276. There, with the deterministic gate switched off, five wrong
answer keys passed both blind solvers and the judge - SymPy is irreplaceable. Here, with SymPy
running and correct, 13 of 15 scoreable stem/equation contradictions are caught by the solvers
and none by SymPy - the panel is irreplaceable too. Each result is the other one's converse,
and together they are the argument for keeping both stages.

How the panel objects is itself informative. Across the corpus the solvers raised 77
objections: 47 `no_option_matches`, 28 disagreements, 2 ambiguity flags. On
`contradictory_constraints` the dominant signal is `no_option_matches` (14 of 21 objections) -
the field D-193 added precisely because a closed `selected_option` literal forced a solver that
had computed an absent answer to express it as a vote. Without that field this class would have
produced two solvers agreeing on the same wrong option and been recorded as agreement.

### 7.3 The near-duplicate threshold is sharper than the defect

Recall by cosmetic severity, with the observed cosine distances to the cloned control:

| severity | edit | `dedup_embedding` (0.05) | `arithmetic_identity` | observed distances |
|---|---|---:|---:|---|
| `typography_only` | one double space / typographic apostrophe | **6/6** | 6/6 | 0.0059-0.0141 |
| `name_swap` | protagonist renamed, everywhere | **2/6** | 6/6 | 0.0407-0.2457 |
| `name_and_noun_swap` | protagonist **and** story object renamed, everywhere | **0/5** | 5/5 | 0.3653-0.5018 |

Every one of these is the same question with the same numbers - the arithmetic identity is
preserved by construction and asserted per item. The third tier is the shape D-273 actually
measured in production output ("27 of the 55 shared their number set... four separate items
were `9 + 9`"), and the embedding check misses all of it.

For scale, the clean controls' nearest same-topic neighbour sits at median 0.762 (min 0.184),
so the threshold is nowhere near the noise floor - it is simply calibrated for
near-verbatim copies, and a renamed story is not one. `exact_text_dedup` catches **0/17**,
which is what the embedding check exists to backstop; the gap between 0/17 and 8/17 is what it
currently buys.

**This is a finding, not a recommendation.** Raising 0.05 would trade against a false-positive
rate this corpus cannot measure, because 102 controls in 29 topics is a thin reference set
compared with a real topic's bank. The cheap alternative is in the next section.

### 7.4 `arithmetic_identity` finds real duplicates in the shipped bank, and is not wired

`arithmetic_identity` catches **17/17** near-duplicates at every severity, for free, because it
compares `(sorted numeric literals, sorted operators)` and ignores the story entirely. It also
flagged **4 of the 102 clean controls**, which the table above scores as false positives.

All four were read by hand, and none of them is a false positive:

| pair | topic | equation |
|---|---|---|
| `e52-clean-006` "Liam has 9 red marbles and 9 blue marbles" ↔ `e52-clean-093` "A child has 9 marbles in one pocket and finds 9 more" | `g1_addition` | `Eq(x, 9 + 9)` both |
| `e52-clean-009` "Emma collects 30 stickers in January and 40 in February" ↔ `e52-clean-096` "A library has 30 books on one shelf and 40 on another" | `g2_addition` | `Eq(x, 30 + 40)` both |

Two genuine duplicate pairs, in the approved bank, in the same topic, differing only in the
story - D-273's pathology, still present. A further four *defect* items were flagged
off-class for the same reason - their unmutated source items already share an arithmetic
identity with a control: `9 + 9` again in `g1_addition`, `9 - 7` in `g1_subtraction`,
`7 + 6` in `g1_addition`, and `2 × 3.14 × 25` twice in `g6_geometry_measurement`. Six distinct
duplicate pairs, none of them injected by this experiment.

So `arithmetic_identity`'s measured 0.039 clean-set false-positive rate is an **upper bound**:
against its actual claim ("this arithmetic already exists in this topic") it made **0 false
positives in 102**, and it surfaced 6 duplicate pairs the shipped bank contains. Its cost is
one regex over an equation string.

The reason it is not wired is recorded honestly in `ai_pipeline` §2b - the cause was fixed
upstream (`avoid_equations`), and wiring the backstop still fails four pipeline tests whose
fixtures call `generate_authored_candidate` directly and so legitimately design the same
equation twice. This experiment adds the number that was missing from that decision: on a
102-item sample of the bank the backstop would have flagged 4 items, and by hand all 4 are real.

### 7.5 The production solver ceiling truncates, and the accounting must not call that a catch

Two of the 17 `contradictory_constraints` items failed:

```
e52-contradictory_constraints-010  solver A: model hit max_output_tokens=1200 before completing the SolverResponse response; not retrying under the same ceiling
e52-contradictory_constraints-011  solver B: model hit max_output_tokens=1200 before completing the SolverResponse response; not retrying under the same ceiling
```

1200 is `_AUTHORED_SOLVER_MAX_TOKENS`, the production value, and it was **not** raised for this
run - raising it would have measured a different pipeline. That both truncations landed on the
same class is consistent rather than coincidental: a stem that contradicts its own equation is
exactly the item a solver reasons longest about, and the two records show the solvers
recomputing and second-guessing before running out of room.

Both are excluded from every solver-dependent figure and reported in their own column. That is
D-230 mechanised, and D-230 exists because this exact conflation shipped once:
`ItemVerdict.agrees` was false for an objection and for an error alike, so a Solver B that
failed every call scored a perfect negative control.
`test_a_panel_whose_every_call_failed_scores_nothing_rather_than_everything` is that property as
an executable assertion.

**In the pipeline, these two would still be contained.** `run_authored_candidate` calls
`_reject([f"solver A call failed: ..."], stage_results, "solver")` - a solver call failure is a
rejection, fail-closed. So the pipeline-effective containment of this corpus is **74/102
(72.5%)** rather than 72/100, with the caveat that the same path rejects a *valid* item whose
solver merely wrote too much - a false-positive channel none of the 102 clean controls
exercised, and one this benchmark therefore does not size.

## 8. The clean controls (D-221)

The controls are the half of this experiment that can falsify it, so they are reported first
rather than last:

- **`deterministic_gate`: 0/102.** Expected - every control is an item this same gate approved -
  and asserted independently by `test_the_gate_flags_no_clean_control`, which would fail if the
  corpus and the gate had drifted apart. A non-zero number here would have invalidated every
  false-positive rate in this report before a model was called.
- **`solver_panel`: 0/102.** Not expected, and the more interesting of the two. These 102 items
  include hand-authored ones that never faced a solver panel (D-211's open risk), and this run
  is effectively a 102-item re-measurement of D-229's 127/127 agreement on a differently drawn
  sample. It agrees: **102/102, zero objections, zero ambiguity flags.**
- **`dedup_embedding`: 0/102**, with the nearest same-topic neighbour at median cosine distance
  0.762.
- **`arithmetic_identity`: 4/102**, all four hand-verified as genuine duplicate pairs (§7.4).

## 9. Three hand-checked items

Verified against the raw verdicts in `detection_results.jsonl`, not against the summary.

**A true positive the free detectors miss — `e52-contradictory_constraints-000`**
(source `authored-geometry_measures-d3-1207302`). The stem's `14` was shifted to `17`; the
equation `x = (14 * 10) / (7 * 5)`, the options `2 / 4 / 8 / 105` and the key `b` are untouched.
Gate: **passes** (flags all false, `gate_failures: []`) - correctly, since the equation still
derives 4 and 4 is option b. Solver A and Solver B both computed 17 × 10 / (7 × 5) = 34/7 ≈
4.857, both set `no_option_matches=true`, both named `b` as closest. The corpus's shadow
equation records the same value, `(34/7,)`, so the label and the solvers agree about what the
stem now asks. Cost 0.98¢.

**A false negative — `e52-near_duplicate-012`** (a `name_and_noun_swap` clone of
`e52-clean-075`, source `authored-g6_fractions-d1-1615231`). Edits: `Maya → Otto`, `marbles →
pebbles`, applied to every field. Numbers, options (`6/9, 2/3, 12/18, 3/4`), key and equation
`Eq(x, Rational(12, 18))` unchanged. The gate passes (it should - the clone is a valid item);
both solvers answer `b` with no objection (they should - it is a correct question);
`dedup_embedding` measures cosine distance **0.365255** to its own donor, seven times the 0.05
threshold, and does not flag it. `arithmetic_identity` does. This single record contains the
whole of §7.3.

**A clean true negative — `e52-clean-000`** (`authored-algebra_1-d1-69100`, unmutated). "A
magician asks you to think of a number, square it, and tell her the result. You say 64."
Options `8 or -8 / 4096 / 32 / 8`, key `a`. All seven detector columns false; both solvers
selected `a` and reasoned to ±8 explicitly, including why the bare `8` is not the complete
answer; nearest same-topic neighbour at distance 0.884. Cost 0.68¢.

## 10. Limitations

1. **The mutations are synthetic proxies for real defects.** Each class is defended above by
   the mechanism it exercises rather than by resemblance to a specific historical failure, and
   two of them (`wrong_numeric_answer`, `near_duplicate`) reproduce classes this project has
   actually recorded (D-229, D-273). The others are constructed. A shifted stem numeral is a
   *clean* instance of "the story and the model disagree"; a real generator failure of that kind
   is usually messier and may be easier or harder to see.
2. **Every mutation is single-fault.** Real rejected candidates often carry several defects at
   once, which raises catch rates. These recall figures are therefore conservative for
   multi-fault items and exact only for the single-fault case.
3. **n = 17 per class.** A 95% Wilson interval on 17/17 is roughly [0.82, 1.00] and on 13/15
   roughly [0.62, 0.96]. The pooled figures (n = 102 each side) are the tighter ones.
4. **The judge stage is not measured**, so `combined_pipeline` is a *lower* bound on what the
   full pipeline catches - the judge might see some `mismatched_hint_ladder` items (it is shown
   the hint ladder and scores hint quality), and this experiment does not say whether it does.
5. **The clean controls are approved items, not raw generator output.** They measure false
   positives against content that already passed this gate, which is the right control for
   "would this detector reject good content" and the wrong one for "how much raw generator
   output is clean" (that is E5.3).
6. **The dedup reference set is 102 items over 29 topics** - three or four per topic, far
   thinner than a real topic's bank. The 0/102 dedup false-positive rate is therefore weak
   evidence; the recall numbers, which only need the *donor* to be present, are not affected.
7. **The two name-based near-duplicate severities are word-problem-biased** (62 skipped
   candidates had no recognised first name), so their 2/6 and 0/5 describe named-protagonist
   word problems specifically.
8. **Solver results are one run of two models on one day.** No repeat trials; a re-run would
   move individual verdicts, most plausibly the two truncations and the two
   `contradictory_constraints` misses.

## 11. Reproducing this

```bash
# 1. the corpus - free, deterministic, no provider, no database
uv run python benchmarks/resume_evidence/05_content_generation/build_defect_corpus.py

# 2. the free detectors only - no provider, no spend
uv run python benchmarks/resume_evidence/05_content_generation/run_defect_detection.py --arm free

# 3. the paid arm - refuses to start without both env gates
eval "$(aws configure export-credentials --profile <profile> --format env)"
CURRICULUM_BENCH_REAL_BEDROCK=1 CURRICULUM_BEDROCK_PROVIDER=bedrock \
  CURRICULUM_BEDROCK_AWS_REGION=us-east-1 \
  uv run python benchmarks/resume_evidence/05_content_generation/run_defect_detection.py \
    --arm real --budget-cents 200

# 4. re-score an existing results file without calling anything
uv run python benchmarks/resume_evidence/05_content_generation/run_defect_detection.py --score-only
```

`--arm mock` exists for wiring smoke tests only; its solver answers `a` to everything and its
embeddings are hash-seeded noise, so it is labeled in the artifact header as **not a quality
result** (the AUD-C-05 lesson: what a mock eval measures is the mock).

## 12. Artifacts

| file | what it is |
|---|---|
| `defect_corpus.jsonl` | 204 labeled items + header: source bank id, class, seed, the exact mutation, the full item, the source-exclusion and mutation-skip ledgers |
| `detection_results.jsonl` | one row per item + header: every detector's verdict, the gate's failure strings, nearest-neighbour distance and id, both raw solver responses, objections, per-item cost, solver status |
| `detection_metrics.csv` | 70 rows - every detector × (6 classes + 3 near-duplicate severities + pooled), with TP/FN/FP/TN, unscored counts, n/N strings, precision, recall, F1, clean-set FP rate |
| `E5_2_REPORT.md` | this file |

Tests: `packages/curriculum/tests/test_e5_2_defect_corpus.py` (27) - one per mutation class
asserting the *defect* rather than the edit, the scoring quadrants, the D-230 unscored rule, the
combined-column rule, the budget/circuit/failure classification, cosine-distance semantics, the
interleaved run order, and the committed corpus's shape.
