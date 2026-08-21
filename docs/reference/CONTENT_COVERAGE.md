# Content coverage — every row of the source taxonomy, and what it would take to serve it

> ## 📌 AS-OF BANNER — read before acting on any status column
>
> **Measured 2026-08-11. Annotated 2026-08-20. Not re-measured since.**
> *(W-37 `DOC-SNAPSHOT-BANNERS`, W-06 `DOC-CONTENT-PIPELINE`, W-43 `BATCH-LOW-UNMARKED-SPEC`,
> W-35 `RISK-R6.4-SESSION-LABELS`.)*
>
> **The taxonomy facts in this file are durable. The status columns are not.** Several of them
> describe needs that were built **the same day this file was written** or in the two days after, so
> a reader following them would **rebuild an existing router or re-author items that are already
> fixed**. Every such column now carries a dated annotation. Nothing was deleted: the original
> reading is the record of what was known on 2026-08-11.
>
> What changed after this snapshot, in one place:
>
> | this file says | actually, since |
> |---|---|
> | family B "needs the Phase R answer-model router" | the router **landed 2026-08-11** (D-273 Phase R), fail-closed, both-directions tests |
> | `selection` is its own answer-model family needing a predicate verifier | **`selection` is not a distinct answer model** — no such model exists in `packages/curriculum` (verified 2026-08-20: the only two hits are comments explaining why it was never built); comparison rides `value` (W-43) |
> | family C "⛔ needs figure support (Phase 5 decision gate)" | **built** (D-279); two figure checks are wired into `validate_authored_item` (verified read-only 2026-08-20) and 40 items carry a non-null `figure_spec` (register measurement, DRIFT-52 — not re-derived in this pass) |
> | `place_value_compare` is **15 of 15** wrong-shape | **re-authored to 0 of 15** on 2026-08-11 (D-273 Phase R; 15 updated, 115 unchanged) |
> | `grade_topic_mapping.yaml` populates **4** of 12 bands | **7** bands are populated (`1-2`, `2-3`, `4-5`, `6-7`, `8-9`, `10-11`, `11-12`) — verified read-only 2026-08-20 |
> | the bank is **47/30/28/25** | **958 items, 99 of 99 authorable skills stocked** as of 2026-08-13 (D-312) |
>
> **All coverage-driven generation is parked (D-342, 2026-08-15).** Nothing in this file is a work
> list today; gaps here are a tracked backlog, not defects.
>
> ### ⚙️ Process note — nothing regenerates this file (W-06 engineering split)
>
> This document is **generated**, but no pipeline step regenerates it: it is produced by
> `scripts/build_content_coverage.py` over a live database, and every drift above exists because the
> script was never re-run after the pipeline changed. **Regenerate rather than hand-edit.** Verified
> 2026-08-20: `scripts/build_content_coverage.py` **exists** in the repository, so the fix is a
> process step (run it as part of any pipeline change), not new tooling. Its census figures have
> never been re-derived in any reconciliation phase, so "stale in the places listed above" is a
> **floor, not a ceiling**.

**Session label.** "C1" in this file always means the **full-taxonomy content-seeding session C1 of
2026-08-11 (D-273)**. It is *not* the earlier chat-content session also labelled "C1" (= S17). Bare
session labels are ambiguous project-wide and are qualified at first use — see the session-label
convention in `docs/PROJECT_STATE.md` (W-35, 2026-08-20).

Status: **Phase 0 of ROADMAP Session C1 — the 2026-08-11 content-seeding session (D-273)**, built
2026-08-11. Free to reproduce, and the **supported** way to update this file:

```bash
.venv/bin/python scripts/build_content_coverage.py
```

Source: `knowledge-content/intellichoice_math_topics.csv`.
Machine-readable output: `curriculum/coverage/csv_row_dispositions.csv` (one row per source
row, with its topic id, skill id, answer model and family).

This file is the **disposition record**: every source row is either covered, or explicitly
deferred with a reason. A row that is silently absent is the failure mode this exists to
prevent — the same posture TRACEABILITY.md takes for SPEC requirements.

---

## 1. What the source actually is

| | |
|---|---|
| source rows | **246** |
| unique `(grade, book, topic)` triples | **245** ← the honest denominator |
| internal topics (one per book) | **34** |
| distinct skills (one per unique row) | **245** |

Two properties of the CSV that decide how it must be read, both measured rather than assumed:

- **One exact duplicate.** `('6', 'Grade 6 Fractions', 'Three Fractions')` appears twice. Coverage
  is therefore counted against **245**, not 246.
- **A row is meaningful only as a triple.** There are just **194 distinct topic strings** across
  the 246 rows — `Fractions` appears in **seven** different books, `Mixed Calculations` in five,
  `Area` and `Length` in four each. A bare topic slug would collide across books and silently
  merge two unrelated skills, so **skill ids are book-qualified**
  (`grade_3_geometry_measurement__fractions`) and coverage is tracked by triple, never by name.

**Mapping decision (D-273):** CSV **books → internal topics**, CSV **rows → skills**. The serving
model is built on that shape — exams are drawn per topic, `difficulty_anchors` are written per
topic, and a study session runs five skill-lines — so 245 one-skill topics would mean 245 rubrics
and 245 topic cards. "Every row covered" therefore means **every row is a stocked skill**.

---

## 2. The axis that decides pipeline fit: the answer model

What determines whether the existing §5.8.5 gate can verify an item is **the shape of its
answer**, and that cuts across subject matter. `derive_answer` requires the item to be modelled as
**one equation, one unknown, exactly one solution**. Measured against the real function on
2026-08-11:

| written as | result |
|---|---|
| `Eq(3*x + 2, 11)` | `3` ✅ |
| `Eq(x, round(3847, -2))` | `3800` ✅ |
| `Eq(x, 2**5)` | `32` ✅ |
| `Eq(x, 43)` | `43` ✅ — **passes, and verifies nothing** |
| `Eq(4, 4)` | rejected: *"restates the answer instead of deriving it"* |
| `x**2 = 9` | rejected: *"has 2 solutions, expected exactly one"* |
| `3*x + 2 > 11` | rejected: *"is not a single equation"* |
| `Eq(x + y, 10)` | rejected: *"has 2 unknowns, expected exactly one"* |

The gate is **strictly fail-closed** — there is no silent skip on any path. But two consequences
follow, and the second is why C1 builds the router before it seeds:

1. **`Eq(x, <expression>)` is fully supported**, so "compute this" questions of every kind —
   rounding, GCF, exponents, order of operations, averages, percents, formula-driven area and
   volume — are servable today. Family A is large.
2. **`Eq(x, <bare constant>)` also passes, while verifying nothing.** It is D-191's defect wearing
   a relation costume: D-191 closed the bare-string form (`answer_expression: '7'`) and left the
   relation-shaped form open, because the check it added tests the *shape* of the model, not
   whether the model does any work. **Measured: 0 of 130 shipped items use it, and 0 are
   unsolvable** — the hole is latent, not live.

### The live consequence

> **Corrected 2026-08-20 (W-06 / W-37).** Two things below were true on 2026-08-11 and are not now.
> **(a)** `place_value_compare` was **re-authored the same day** (D-273 Phase R): **15 of 15 → 0 of
> 15**, four numbers whose rubric discriminator decides the answer plus three BUILD items modelled as
> `Eq(x, Max(<every permutation>))`, re-gated through the real loader (15 updated, 115 unchanged).
> **Do not re-author these items.** **(b)** The premise that a *selected* answer forces the choice
> below was **measured false**: `Eq(x, Max(34, 43))` derives 43 and passes the unchanged gate, as do
> `Eq(x, gcd(12, 18))`, `Eq(x, floor(3847/100)*100)` and `Eq(x, Mod(7, 2))`. Comparison questions
> were always expressible — the 15-item defect was an **authoring failure, not a gate limitation**.
> The diagnosis of the *pattern* below still stands and is why the section is kept.

For a skill whose answer is *selected* rather than *derived* — compare, identify, classify, name
— an author has exactly two moves: write the vacuous form above, or reshape the question until
something is derivable. **The bank shows which one happened.** `place_value_compare` is **15 of
15** *"how many more"* subtraction word problems, filed under *"Compare and order multi-digit
numbers by place value"*. Not one item asks a student to compare. Every other skill in the bank
measures **0/N** on that pattern, because for those the natural question already *is* an equation.

This is the third instance of a pattern D-238 recorded twice as a symptom (`div_remainder` items
that all stated the remainder in the stem). It is the first time the cause is named: **the gate
does not forbid non-equation skills — it makes the honest version unverifiable and the verifiable
version a different question.**

---

## 3. The 245 rows by family

| family | rows | share | answer models | status **as measured 2026-08-11** | status annotation, 2026-08-20 |
|---|---|---|---|---|---|
| **A** | **173** | 70.6% | `value` | ✅ servable by the pipeline as it stands | unchanged |
| **B** | **37** | 15.1% | `symbolic` 19, ~~`selection` 11~~, `interval` 3, `tuple` 2, `multi_root` 2 | ⚠️ needs the Phase R answer-model router | ✅ **router built 2026-08-11** (D-273 Phase R): `route_answer` / `_option_matches` cover `value`, `multi_root`, `interval`, `tuple`, `symbolic`, fail-closed. **Family B is no longer routed to Phase R.** And `selection` is **not a distinct answer model** — see the note below (W-43) |
| **C** | **34** | 13.9% | `figure` | ⛔ needs figure support (Phase 5 decision gate) | ✅ **figure support built** (D-279) — **family C is not gated.** `check_figure_agrees_with_the_question` / `check_reading_matches_the_figure` are wired into `validate_authored_item` (verified read-only 2026-08-20), and 40 items carry a non-null `figure_spec` (register measurement, DRIFT-52 — not re-derived here) |
| **D** | **1** | 0.4% | `reshape` | ↻ *Writing Numbers* (g1) — reshape to "which shows twenty-three?" (`selection`) or drop | still open; the reshape target is expressed as `value`, not `selection` |

> **`selection` is not a distinct answer model — annotated 2026-08-20 (W-43
> `BATCH-LOW-UNMARKED-SPEC`, DRIFT-96).** The 11 rows are real skills; the *family label* is not.
> Verified read-only 2026-08-20: **no `selection` answer model exists in `packages/curriculum`** — the
> only two occurrences of the word are source comments recording that it was deliberately never built
> (`content.py`: *"the same rule that kept `selection` out of the Phase-R router until something used
> it"*; `authored_validation.py`: *"what did NOT need building, and the measurement that saved the
> work"*).
> The capability landed under a different design: comparison questions are expressed through the
> **`value`** model, as the router's own tests state — *"it is `value` because the answer* is *a
> value — the point is that `Max` does the selecting"*. Worth naming so a future reader does not go
> looking for a missing predicate verifier. Recorded in the register's wording: the family was
> **declared and never used**, not absent.

### Family B, and why its ordering is not the obvious one

> **Superseded 2026-08-11, annotated 2026-08-20 (W-06).** The ordering argument below was acted on
> and then **falsified by its own first measurement**: `selection` needed no verifier at all, because
> the existing gate already derived `Eq(x, Max(34, 43))`. The reordering still earned its place —
> it found that out *before* 34 topics of rubrics were written against a false constraint — but the
> third bullet ("the cheapest verifier to write") describes a verifier that was never needed and
> **does not exist**. Kept as the reasoning of record, not as a build order.

`symbolic` is the largest sub-family (19 rows) but **`selection` is the one to build first**, for
three reasons that have nothing to do with count:

- It is where the **live defect** is. Nothing else in family B has shipped wrong content.
- **10 of its 11 rows are grades 1–5**, which is where a K-12 product's students actually
  concentrate. `symbolic` is 16 of 19 in grades 9–12.
- It is the cheapest verifier to write: evaluate a predicate over the stated objects
  (`max`, `is_odd`, `is_prime`, place-value read) and confirm the declared option is the one that
  satisfies it — no equivalence algebra required.

### The finding that most changes the roadmap's shape

**Algebra I is 0 family A out of 6 rows.** Square Roots, Quadratic Equations, Inequalities,
Functions and Graphs, Systems of Equations, Factorization — *every* row in that book needs the
router. The current pipeline cannot author a single Algebra I item, and no amount of prompt or
rubric work changes that, because the rejections are structural (`2 solutions`, `not a single
equation`, `2 unknowns`).

Grades 10, 11 and 12 are similar in kind if not degree: 3 of 6, 3 of 7, and 3 of 4 rows blocked.
**High school is router-gated; elementary is not.**

> **Annotated 2026-08-20 (W-06/W-37).** "The current pipeline cannot author a single Algebra I item"
> was true on 2026-08-11 and is **no longer a blocker**: the router that unblocks `multi_root`,
> `interval`, `tuple` and `symbolic` landed the same day (D-273 Phase R), which is exactly what
> "high school is router-gated" was pointing at. Whether Algebra I is *stocked* is a separate,
> authoring question — and all coverage-driven authoring is **parked (D-342)**. The structural
> analysis of *why* those rows were blocked is why this section is kept.

### Per-grade distribution

| grade | A | B | C | D | topics |
|---|---|---|---|---|---|
| 1 | 25 | 4 | 3 | 1 | 4 |
| 2 | 23 | 2 | 3 | – | 4 |
| 3 | 30 | 1 | 4 | – | 5 |
| 4 | 30 | 1 | 3 | – | 5 |
| 5 | 14 | 2 | 6 | – | 3 |
| 6 | 22 | – | 2 | – | 3 |
| 6–8 | 19 | 9 | 13 | – | 5 |
| 9 | **0** | **6** | – | – | 1 |
| 10 | 3 | 3 | – | – | 1 |
| 11 | 4 | 3 | – | – | 1 |
| 12 | 1 | 3 | – | – | 1 |
| 9–12 | 2 | 3 | – | – | 1 |

Family C concentrates in grades 5 and 6–8 (19 of 34 rows) — coordinate geometry, congruence,
transformations, angle relationships, solids. ~~That is the block Phase 5's decision gate is about.~~
**Annotated 2026-08-20 (W-06): the Phase 5 figure decision gate is closed — figure support was built
(D-279) and two figure checks run inside `validate_authored_item`. Family C is an authoring backlog
now, and it is parked (D-342), not a gated capability.**

---

## 4. Grade bands

SPEC §5.7.3 defines **12 bands**. **As of 2026-08-20, `grade_topic_mapping.yaml` populates 7** —
`1-2`, `2-3`, `4-5`, `6-7`, `8-9`, `10-11`, `11-12` (verified read-only by reading the file; W-06
`DOC-CONTENT-PIPELINE`, DRIFT-52). ~~currently populates **4** (`1-2`, `2-3`, `4-5`, `6-7`)~~ — that
was the 2026-08-11 reading, before the C1 waves for grades 8–12 were listed. Filling the rest is
Phase 1 work (**parked, D-342**), done wave by wave as each band's topics are actually stocked — a band pointing at an unstocked topic is safe (`recommended_for_grade` is
conjunctive with `available`, D-187) but pointless.

**The trap, pinned by `test_adding_a_band_never_steals_a_grade_from_an_existing_one`:** bands
overlap by design, `topics_for_grade` returns the **first** match, and a band matches on its
*endpoints* rather than as a range. So band order in the file is load-bearing, and a new band
inserted above an existing one can take a grade away from it. Add the §5.7.3 band that contains
the grade; never widen an existing band by renaming it.

---

## 5. What each family needs, and where it is handled

*Status column added 2026-08-20 (W-06/W-37). The "needed" column is the 2026-08-11 plan; four of the
six rows were satisfied within two days of it, so read the status before scheduling any of it.*

| family | needed (as planned 2026-08-11) | phase | status, 2026-08-20 |
|---|---|---|---|
| A (173) | nothing new — rubrics and generation only | Phase 1 waves | authoring only; **parked (D-342)** |
| B `selection` (11) | ~~predicate verifier over stated objects~~; re-author `place_value_compare` as the proof case | **Phase R** | ✅ **done, and the verifier was never needed** — `selection` is not a distinct answer model (W-43); `place_value_compare` re-authored 15/15 → 0/15 |
| B `multi_root`/`interval`/`tuple` (7) | solution-set verifiers; unblocks Algebra I entirely | **Phase R** | ✅ **built 2026-08-11** (D-273 Phase R), fail-closed, both-directions tests (D-246) |
| B `symbolic` (19) | expression-equivalence verifier (`simplify(a - b) == 0`) | **Phase R** | ✅ **built 2026-08-11** (D-273 Phase R) |
| C (34) | a figure feature: data model, renderers, frontend, generation contract | ~~**Phase 5** decision gate~~ | ✅ **built (D-279) — no longer gated.** Two figure checks run inside `validate_authored_item`; 40 items carry a non-null `figure_spec` (register measurement, DRIFT-52) |
| D (1) | reshape *Writing Numbers* into ~~`selection`~~ `value`, or disposition out | Phase 1, grade-1 wave | still open; authoring, parked (D-342) |

**Volume target: 5–7 items per occupied tier (~25–35 per topic, ~1,000 items across 34 topics)** —
D-223's measured figure, chosen by the user over SPEC §5.8.1's 100-per-topic (~3,400 items, 3× the
spend and review burden). §5.8.1's number has never been met by any topic — the bank was
**47/30/28/25 when this was written on 2026-08-11**; it was **958 items across 99 of 99 authorable
skills on 2026-08-13** (D-312), which is still short of §5.8.1 for every topic, so the argument
holds and only the figure moved (annotated 2026-08-20, W-37). Nothing has measured §5.8.1's number
as necessary, whereas D-223 measured 5–7/tier as the depth at which independently-built exams stop
repeating themselves.

> **Provenance caveat on "5–7", added 2026-08-20 (W-06 member E2-33).** D-223 does not *state* 5–7
> as a target: it records the per-tier distribution **5 / 6 / 7 / 6 / 6** it achieved on
> `fraction_operations`. D-273 turned that into the target quoted above; **D-313** (2026-08-13) sizes
> the remaining backlog using **5 per occupied `(topic, tier)` cell** (84 of 153 cells at 5; 189
> items to close). Full reconciliation in
> [QUESTION_GENERATION.md](QUESTION_GENERATION.md) §9a. The exact per-cell number is confirmed **when
> D-342 is lifted**, not before.

Not every `(skill, tier)` cell needs filling, and treating it as a target costs content quality
(D-223): the pre-exam reads per difficulty across the topic and the study selector takes
`_closest_to_recommended`, so an absent tier degrades to the nearest present one. The bank should
follow where a skill actually spans.
