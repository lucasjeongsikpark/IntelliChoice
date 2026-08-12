# Content coverage — every row of the source taxonomy, and what it would take to serve it

Status: **Phase 0 of ROADMAP Session C1 (D-273)**, built 2026-08-11. Free to reproduce:

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

| family | rows | share | answer models | status |
|---|---|---|---|---|
| **A** | **173** | 70.6% | `value` | ✅ servable by the pipeline as it stands |
| **B** | **37** | 15.1% | `symbolic` 19, `selection` 11, `interval` 3, `tuple` 2, `multi_root` 2 | ⚠️ needs the Phase R answer-model router |
| **C** | **34** | 13.9% | `figure` | ⛔ needs figure support (Phase 5 decision gate) |
| **D** | **1** | 0.4% | `reshape` | ↻ *Writing Numbers* (g1) — reshape to "which shows twenty-three?" (`selection`) or drop |

### Family B, and why its ordering is not the obvious one

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
transformations, angle relationships, solids. That is the block Phase 5's decision gate is about.

---

## 4. Grade bands

SPEC §5.7.3 defines **12 bands**; `grade_topic_mapping.yaml` currently populates **4** (`1-2`,
`2-3`, `4-5`, `6-7`). Filling the rest is Phase 1 work, done wave by wave as each band's topics
are actually stocked — a band pointing at an unstocked topic is safe (`recommended_for_grade` is
conjunctive with `available`, D-187) but pointless.

**The trap, pinned by `test_adding_a_band_never_steals_a_grade_from_an_existing_one`:** bands
overlap by design, `topics_for_grade` returns the **first** match, and a band matches on its
*endpoints* rather than as a range. So band order in the file is load-bearing, and a new band
inserted above an existing one can take a grade away from it. Add the §5.7.3 band that contains
the grade; never widen an existing band by renaming it.

---

## 5. What each family needs, and where it is handled

| family | needed | phase |
|---|---|---|
| A (173) | nothing new — rubrics and generation only | Phase 1 waves |
| B `selection` (11) | predicate verifier over stated objects; re-author `place_value_compare` as the proof case | **Phase R** |
| B `multi_root`/`interval`/`tuple` (7) | solution-set verifiers; unblocks Algebra I entirely | **Phase R** |
| B `symbolic` (19) | expression-equivalence verifier (`simplify(a - b) == 0`) | **Phase R** |
| C (34) | a figure feature: data model, renderers, frontend, generation contract | **Phase 5** decision gate |
| D (1) | reshape *Writing Numbers* into `selection`, or disposition out | Phase 1, grade-1 wave |

**Volume target: 5–7 items per occupied tier (~25–35 per topic, ~1,000 items across 34 topics)** —
D-223's measured figure, chosen by the user over SPEC §5.8.1's 100-per-topic (~3,400 items, 3× the
spend and review burden). §5.8.1's number has never been met by any topic — the bank is
47/30/28/25 — and nothing has measured it as necessary, whereas D-223 measured 5–7/tier as the
depth at which independently-built exams stop repeating themselves.

Not every `(skill, tier)` cell needs filling, and treating it as a target costs content quality
(D-223): the pre-exam reads per difficulty across the topic and the study selector takes
`_closest_to_recommended`, so an absent tier degrades to the nearest present one. The bank should
follow where a skill actually spans.
