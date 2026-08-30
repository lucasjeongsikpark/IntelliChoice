# R3 — post-remediation re-measurement: hint/stem coherence and the wired arithmetic fingerprint

> Remediation task **R3**, 2026-08-29/30 (artifacts stamped `2026-08-30T04:52Z`). Code SHA at
> measurement time `7d0fe03` (working tree,
> uncommitted). Corpus `defect_corpus.jsonl`, `corpus_git_sha 469bb56`, `corpus_seed 520000` —
> **frozen and unmodified**: 102 labeled defects over six classes against 102 clean controls
> drawn from the same approved bank.
> **Spend: $0.00.** No model was called. The four free detector columns were recomputed against
> the fixed code; the two paid columns (`dedup_embedding`, `solver_panel`) were carried verbatim
> from E5.2's committed `detection_results.jsonl` (arm `real`, SHA `469bb56`) and are **not**
> re-measured — the fixes do not touch them, and re-buying them would spend money to restate them.
> Historical E5.2 and E5.3 artifacts are untouched; everything R3 produced is in this directory.

Reproduce (free, deterministic, ~10 s):

```bash
uv run python benchmarks/resume_evidence/05_content_generation/run_postfix_detection.py
```

## 1. What was broken, and what changed

Two holes E5.2 and E5.3 measured, both of them free to close and neither of them closed:

- **R3a — nothing in the pipeline compared a hint with its stem.** `mismatched_hint_ladder`
  (three rungs lifted wholesale from a different item, chosen to share no numeral with the
  question they are grafted onto) scored **0/17 on every detector** — 17 of the pipeline's 28
  total misses, and the only defect class with no detector at all.
  `hint_ladder_monotonicity_violations` is verbatim containment between rungs and says so in its
  own docstring, `check_no_answer_leakage` asks whether a rung states *this* item's answer, and
  `SolverPayload` never carries a hint. The gap was structural, not a threshold.
- **R3b — `arithmetic_identity` existed, was tested both ways, and was never wired.**
  `ai_pipeline` §2b recorded the reason honestly (the cause had been fixed upstream by
  `avoid_equations`; wiring the backstop failed four test fixtures). E5.2 supplied the number
  that argument was missing: **17/17** on near-duplicate mutants at every cosmetic severity,
  against the paid embedding check's 8/17 — and **0/5** for the embedding check once the
  protagonist and the story object are both renamed, which is the shape D-273 actually measured
  in production output.

The changes:

| | change | where |
|---|---|---|
| R3a | `check_hint_ladder_is_about_this_question` — new deterministic gate check | `authored_validation.py`, called from `validate_authored_item` (so **both** the generation path and `loader.py`'s re-gate, per D-276's one-gate rule) |
| R3b | `arithmetic_identity` wired as a fourth dedup predicate, same-topic scoped, placed **before** the paid embedding call | `ai_pipeline.run_authored_candidate` §2b, with `QuestionRepository.authored_equations_in_topic` supplying the topic's equations |

## 2. R3a — the coherence rule, and why this shape

**The rule.** An item fails when its hint ladder names one or more numerals and **none** of them
occurs in the question, its equation, its options or its figure. The item side of that comparison
is expanded before the lookup — never the hint side — with the four decompositions the approved
bank actually needs, each one traced to the item that required it:

| expansion | why | bank item |
|---|---|---|
| the digits of each numeral | place-value coaching: "the ten-thousands digits are 4, 6, and 5" against `45,832 / 67,419 / 52,106` | the ten `number_sense` compare/round items |
| place-value components (`32` → `30`, `2`) | column arithmetic: "add the ones place first: 2 + 4, then the tens place: 30 + 20" | `authored-g2_addition-d2-7201` |
| the two parts of a decimal | money: "regroup when subtracting cents: 50 cents minus 35 cents" against `$21.50 − $9.35` | `authored-measurement-d2-959202` |
| the canonical numeric spelling (`7.00` → `7`) | an item writing a trailing zero must ground a hint that does not | — |

plus two normalisations before any numeral is read at all: thousands separators are stripped
(`38,472` is one number, D-274's rule) and superscripts are expanded (`2³` carries a 3 no ASCII
scan would find, `authored-pre_algebra-d3-1166300`), and a figure's own numbers join the grounded
set (`"What time does this clock show?"` states its numbers in the picture — without this the ten
`telling_time` items are all disjoint from their own questions).

**Why knobless.** The obvious stronger rule — fail when *most* hint numerals are foreign — is
better on recall and worse as a gate. Measured over the 17 grafted ladders, the 102 clean controls
and all 958 approved bank items:

| rule | recall | clean-control FP | approved-bank FP | headroom to live content |
|---|---:|---:|---:|---|
| foreign ratio ≥ 0.50 | 15/17 | 1/90 | 10/831 | — (already firing) |
| foreign ratio ≥ 0.75 | 13/17 | 0/90 | 0/831 | **0.036** (the highest ratio any approved item reaches is 0.714) |
| **disjointness (ratio = 1.0)** | **12/17** | **0/90** | **0/831** | **0.286** |

One extra catch for a knob sitting 0.036 above shipped content is not a trade worth making. D-249
records what a fuzzy novelty rule does one layer down — it punishes legitimate restatement and
rewards synonym-swapping — and `HINT_SOLUTION_REVIEW.md` §1 records two hint scorers that failed
because they graded quality. This grades nothing: it asks one closed question with a yes/no answer.
(Denominators of 90 and 831 rather than 102 and 958 because a ratio is undefined for an item whose
ladder names no numeral; those items are counted as "not judged" below, not as passes.)

**What it does not cover, stated rather than averaged away.** Five of the 17 grafted ladders pass,
each because its donor's arithmetic happened to reuse one of the host question's numerals
(`e52-mismatched_hint_ladder-003/-011/-013/-015/-016`, named as fixtures in
`test_hint_ladder_coherence.py`). And **127 of 958** approved items have no numeral in their hint
ladder at all, so the check is silent on them by construction. This is a floor on hint/stem
coherence, not a measure of it; semantic hint quality remains `HINT_SOLUTION_REVIEW.md` §3's LLM
instrument and is deliberately still not in this gate.

## 3. Before → after, on the frozen 102 + 102

### 3.1 The class R3a targets

| detector | scope | before | after |
|---|---|---:|---:|
| `deterministic_gate` | `mismatched_hint_ladder` | **0/17** | **12/17** (P 1.000, F1 0.828) |
| `deterministic_gate` | clean-control FP for that block | 0/17 | **0/17** |
| `deterministic_gate` | ALL | 51/102, F1 0.667 | **63/102, F1 0.764** |
| `deterministic_gate` | clean FP, pooled | 0/102 | **0/102** |

Acceptance criterion 1's first half: recall on `mismatched_hint_ladder` moved off zero, with
**zero** new false positives on the clean controls, pooled or blocked.

### 3.2 The class R3b targets

`arithmetic_identity`'s own numbers are unchanged — R3b wired an existing predicate, it did not
alter it — so the movement is in the **dedup stage**, which is what the pipeline actually runs:

| severity of the cosmetic edit | `dedup_embedding` (0.05, paid) | `arithmetic_identity` (free) | dedup stage before | dedup stage after |
|---|---:|---:|---:|---:|
| `typography_only` | 6/6 | 6/6 | 6/6 | **6/6** |
| `name_swap` | 2/6 | 6/6 | 2/6 | **6/6** |
| `name_and_noun_swap` | 0/5 | 5/5 | 0/5 | **5/5** |
| **all near-duplicates** | 8/17 | **17/17** | 8/17 | **17/17** |

### 3.3 The pipeline, unioned the way it actually unions

`combined_pipeline` is fail-closed: any stage rejects. E5.2's union was
`gate OR dedup_embedding OR solver_panel`. After R3b the dedup stage is
`dedup_embedding OR arithmetic_identity`, so the post-fix union has four parts. Both are reported,
and a control row recomputes E5.2's three-part union over the same post-fix rows so the two halves
of the improvement are attributable rather than definitional:

| union | recall | precision | F1 | clean-set FP |
|---|---:|---:|---:|---:|
| before (E5.2, 3 parts) | 72/100 | 1.000 | 0.837 | 0/102 |
| **control: post-fix rows, E5.2's 3-part union** — isolates R3a | **84/100** | 1.000 | **0.913** | 0/102 |
| **after (4 parts, the pipeline as it now stands)** | **94/100** | 0.959 | **0.949** | 4/102 |

So **R3a is +12** catches and **R3b is +10** on the same 204 items, and the pipeline's F1 over the
frozen corpus moves **0.837 → 0.949**. Per class, after: `wrong_numeric_answer` 17/17,
`no_correct_option` 17/17, `mismatched_solution` 17/17, `mismatched_hint_ladder` 13/17
(12 from the gate, 1 an off-class `arithmetic_identity` flag), `contradictory_constraints` 13/15
(2 unscored — E5.2's solver truncations, D-230), `near_duplicate` 17/17. The full 70-row
quadrant table is `detection_metrics_postfix.csv`; the re-derived before-table is
`detection_metrics_prefix.csv`.

**The four clean-set flags are `arithmetic_identity`'s and none of them is a false positive.**
E5.2 §7.4 read all four by hand: they are genuine same-topic duplicate pairs already in the
approved bank (`Eq(x, 9 + 9)` in `g1_addition`, `Eq(x, 30 + 40)` in `g2_addition`, and four more
defect-block items whose *unmutated sources* already collide). Against the check's actual claim —
"this arithmetic already exists in this topic" — it made **0 false positives in 102**. The 0.959
precision above is therefore a **lower bound** on the post-fix pipeline, carried at face value
because the scorer must not be allowed to argue with its own labels.

## 4. The approved-bank scan (`bank_scan.json`)

The landing gate, run before either check was allowed to ship:

| | result |
|---|---|
| items scanned | **958** |
| **hint-coherence failures** | **0** |
| — ladders naming no numeral (not judged) | 127 |
| same-topic arithmetic-identity groups | **58** |
| — approved items sitting in one | **133** |
| — items with no parseable equation (skipped) | 18 |

**Zero hint-check failures is the fact that decided where R3a lives.** `loader.py` re-gates every
bank item on load, in every environment including production, and aborts the run on failure — so a
check that failed even one approved item would have broken `make curriculum-load` and CI and would
have had to be scoped to the generation path only. It fails none, so it is in the shared gate,
called from both places (D-276's one-gate rule). `make curriculum-load` was run directly against the
dev database after the change and reports `templates_unchanged: 958, templates_retired: 0` — all 958
items re-gated through the new check and none rejected.

**58 groups / 133 items is a *finding*, not a regression, and no bank content was touched.** Three
things about it:

1. **It cannot break anything.** The dedup stage is in `ai_pipeline`, not in the loader's re-gate
   (verified in code: `loader._gate` calls `validate_authored_item` and nothing else), so the
   fingerprint has no effect on serving or loading. It changes only what a *future* candidate is
   compared against.
2. **The R3 task spec expected 6 pairs; the real number is 58 groups.** The 6 is E5.2 §7.4's count
   on its **102-item sample**, not on the bank. Every one of those six is present here and each is
   larger than it looked at n=102 — `9 + 9` in `g1_addition` is five items, not two; `30 + 40` in
   `g2_addition` is three; `7 − 9` in `g1_subtraction` is three.
3. **Nothing was deduplicated, deactivated or edited.** Whether the bank should be deduplicated is
   a content decision the user has not made; every group is listed in `bank_scan.json` with its
   topic, its number set, its operators and its template ids, and that is the whole of the action
   taken here.

## 5. Finding: the arithmetic fingerprint cannot close E5.3's residual

**R3's task spec states that E5.3's whole validated-arm residual — 8 of 174 machine-accepted items,
7 collision groups — is the arithmetic-identity class, and requires those groups to be caught. That
is not what E5.3 measured, and the fingerprint provably cannot catch them.**

Every one of the 8 survivors carries `defect_families == ["duplicate scenario (skeleton
collision)"]`, and `E5_3_REPORT.md` §5.1 defines that as *"the same sentence with different
numbers"*. Different numbers means a different fingerprint by construction. The eight form four
same-topic groups, and each group's two members have two distinct identities:

| topic | member A | member B | collide? |
|---|---|---|---|
| `g5_word_problems` | `Eq(x, 63*5/9)` | `Eq(x, 32*5/8)` | no |
| `g6_word_problems` | `Eq(x, 120/6)` | `Eq(x, 216/6)` | no |
| `g6_word_problems` | `Eq(x, 56/8)` | `Eq(x, 84/7)` | no |
| `g6_word_problems` | `Eq(x, 135/9)` | `Eq(x, 180/4)` | no |

**0 of 4.** The fingerprint is the right instrument for E5.2's class (same numbers, different
story — 17/17) and structurally the wrong one for E5.3's (same story, different numbers).

What *would* catch E5.3's class is a stem-skeleton check scoped **within** a topic — D-286's
`stem_skeleton_exists_in_another_topic` with its cross-topic scoping dropped. Its cost, measured on
the approved bank rather than assumed: **8 same-topic skeleton groups covering 35 of 958 items**, of
which at least 22 are legitimate by design — `place_value_compare`'s "Which of these numbers is the
largest?" twelve times and `time_read_clock`'s "What time does this clock show?" ten times, both
questions whose content lives in the options or the figure rather than the sentence. That is
precisely the case D-286's docstring gives as its reason for scoping the check across topics only.
Closing E5.3's residual therefore needs a narrower instrument (skeleton **and** same skill, with a
figure/options exemption) and re-opens a recorded decision, so it was left out of R3's scope and
raised to the coordinator instead.

**E5.3's 4.60% residual is unchanged by R3 and remains open.**
`test_the_e5_3_residual_is_a_class_this_check_provably_cannot_catch` pins this so the conclusion
cannot silently go stale: if the fingerprint ever starts catching E5.3's groups, that test fails
and this section must be re-measured rather than re-worded.

## 6. Regression tests

Permanent, all free, all deterministic:

| test | what it pins |
|---|---|
| `test_hint_ladder_coherence.py::test_the_grafted_ladders_are_caught_at_the_measured_rate` | 12/17 on the frozen corpus, as an equality, with the 5 misses named |
| `…::test_no_clean_control_and_no_other_defect_class_is_flagged` | 0/102 clean and 0/85 other-class (D-221's direction) |
| `…::test_the_whole_approved_bank_passes_the_check` | 0/958 — the condition that lets the check live in the shared gate |
| `…::test_a_legitimate_ladder_that_names_derived_numbers_passes` ×4 | the four measured false-positive families, as fixtures |
| `…::test_a_figure_item_is_grounded_by_its_figure`, `…::test_a_ladder_that_names_no_number_is_not_judged` | the two structural exemptions |
| `…::test_a_ladder_from_another_item_is_rejected_by_the_whole_gate` | the check is *wired*, not merely written |
| `test_arithmetic_dedup.py::test_every_e5_2_near_duplicate_mutant_collides_with_its_source` | 17/17 on the frozen corpus, topic-scoped |
| `test_arithmetic_dedup.py::test_the_e5_3_residual_is_a_class_this_check_provably_cannot_catch` | §5's negative result |
| `test_authored_pipeline.py::test_same_arithmetic_different_story_is_rejected_at_dedup` | the dedup stage rejects, names the existing template, persists the reading, and does it **before** the embedding call (`embedding_calls == 0`) |
| `test_e5_2_defect_corpus.py::test_mismatched_hint_ladder_is_now_a_defect_the_gate_can_see` | the E5.2 guard test, inverted — it previously asserted the gate could *not* see this class, and its own docstring said to re-measure rather than re-word when it failed |

Five existing pipeline tests needed their fixtures varied rather than their assertions relaxed:
they persist two candidates in one topic and `_good_item` gave every one of them `Eq(x, 2 + 2)`, so
the newly-wired backstop correctly called them duplicates. `_good_item_summing(first, second)` now
varies equation, options and worked solution together. One of the five —
`test_the_pipeline_accepts_a_lowest_terms_item_for_the_skill_that_declares_the_form` — was a
**genuine catch**: its fixture's `Eq(x, Rational(12, 18))` is the arithmetic of a shipped bank item
(`authored-g6_fractions-d1-1615231`), so the fixture was a real duplicate of approved content. It
now reduces `20/45`, which `g6_fractions` does not use.

## 7. Limitations

- **12/17, not 17/17.** A disjointness rule cannot see a grafted ladder that reuses one numeral by
  coincidence, and 5 of the 17 do. The alternative that catches 13 is a knob 0.036 above live
  content; the trade is argued in §2 and the choice is reversible with one constant.
- **The check is silent on 127 of 958 bank items** whose ladders name no numeral at all — a common
  case, not an edge one.
- **The paid columns are carried, not re-measured.** `dedup_embedding` and `solver_panel` are
  E5.2's numbers at SHA `469bb56`; neither fix touches those stages, but the combined rows inherit
  whatever those columns already were, including E5.2's two solver truncations.
- **Precision 0.959 is a floor**, for the reason in §3.3.
- **The corpus is 102 + 102 from one bank.** Everything here is measured against that denominator
  and the 958-item bank, and neither is a sample of some larger population of generated content.
- **E5.3's residual is untouched** (§5).

## Artifacts

| file | what |
|---|---|
| `R3_POSTFIX_REPORT.md` | this document |
| `detection_metrics_postfix.csv` | the 70-row post-fix quadrant table (detector × scope) |
| `detection_metrics_prefix.csv` | the same table re-derived from E5.2's committed results, i.e. the before-numbers re-confirmed rather than transcribed |
| `detection_results_postfix.jsonl` | per-item verdicts; header records which columns were recomputed and which were carried |
| `bank_scan.json` | the 958-item scan: hint failures (none) and every same-topic identity group |
| `benchmarks/…/run_postfix_detection.py` | the driver, a thin layer over E5.2's own instrument |
