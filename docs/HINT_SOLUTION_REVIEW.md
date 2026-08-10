# Hint & solution quality review — design (D-251)

**Status: planned, not built.** Steps 1 and 2 of §8 are implemented; the instrument itself is
not. Read this before adding any hint- or solution-quality scoring anywhere.

The goal is to **replace routine human review** of generated hint ladders and canonical
solutions with LLM review that emits automatable decisions — while keeping content diverse
rather than converging on one house style.

---

## 1. The problem

The gap is **not a missing judge**. Two already exist and neither works as intended.

| | where | state |
|---|---|---|
| `hint_quality_score` (1–5) | inside the §5.8.5 judge (`ai_pipeline.py`) | D-249: the `<= 3` rule fired on **46% of hand-authored, human-approved bank items** against 45% of generated candidates, so it measured the judge rather than the item. Removed from review-priority. The `< 2` **rejection** (`_HINT_QUALITY_REJECT_BELOW`) is still live and **has never been measured** |
| `run_llm_judge` + `LEARNING_JUDGE_DIMENSIONS` | `packages/evals` | Already names `hints_avoid_revealing_the_answer` and `solution_accuracy_and_clarity`. **No production caller** — reserved and unused since S8 (D-022) |

Building a third scorer without a way to tell whether it works would repeat D-249 at a larger
scale. **The missing thing is not a judge. It is a way to falsify one.**

### The five root causes the design fixes

1. **Absolute 1–5 scalar.** Difficulty got per-topic `difficulty_anchors` (D-232); hint quality
   got "3 is usable but shallow" and nothing else.
2. **Seven jobs in one call.** D-200/D-205 established "five calls with different jobs, not one".
   The judge is the standing counterexample.
3. **One reading.** D-193's solver panel requires two independent readings; the quality score
   has one.
4. **No ground truth, ever.** D-246 built a negative control for `hint_reveals_answer` and it
   scored 32/32 immediately. Nothing equivalent exists for quality.
5. **Never falsified before use.** Which is how it shipped and sat for months looking reasonable.

---

## 2. The instrument

One new `BedrockTask`, **separate from the §5.8.5 judge** — not another field on it (cause 2).
Per-item, no reference item, no arbitrary scalar (cause 1).

**Output:**

- `verdict`: `PASS | REPAIR | REJECT`
- `defects`: location + what is wrong + what would fix it
- `uncertainty`: the model's own signal that this was a close call

`PASS / REPAIR / REJECT` is enough to automate decisions on its own. Repair is a mechanism for
**recovering good candidates**, not a precondition for removing humans.

Reuses `packages/evals`' existing `run_llm_judge` harness rather than a new one.

### Why not pairwise

Pairwise comparison is not inherently harmful. It is skipped here because we need **per-item
decisions, not rankings** — a ranking cannot produce `PASS`/`REPAIR`/`REJECT` for a single item.
The thing to avoid is a *better-than-a-reference objective*, which would drive every ladder
toward one canonical style. That risk lives in the objective, not in the comparison format.

---

## 3. Deterministic vs LLM

**Deterministic — exact invariants only:**

- `check_no_answer_leakage` — verbatim answer text in stem/context/hints
- `check_hint_solution_answer_agreement` — `canonical_solution.final_answer` vs declared option
- SymPy arithmetic (`derive_answer`)

**LLM — every semantic judgment:** hint usefulness, rung-to-rung progression, clarity,
pedagogical fit, solution followability.

### One check is already mislabelled

`hint_ladder_monotonicity_violations` is verbatim substring containment
(`later.strip() in earlier`). It cannot see a paraphrase and would not fire on a reordered
ladder. It **stays** — it is exact and free — but it is *not* monotonicity coverage, and real
progression belongs to the LLM. Its docstring now says so.

---

## 4. Decision flow

```
item → deterministic invariants → [fail: REJECT, no LLM call]
     → instrument (1 reading)
         PASS (confident)          → accept
         PASS (sampled/uncertain)  → 2nd reading
         REPAIR                    → one bounded repair attempt → re-read → PASS or REJECT
         REJECT                    → 2nd reading
     → two readings disagree       → LLM adjudicator (both readings + the item)
     → adjudicator unresolved      → human
```

**Second readings are risk-triggered in both directions**, never blocking-only. Triggering on
blocking verdicts alone protects against false *rejection* while leaving false *acceptance*
entirely unseen. Triggers: `REJECT`, self-reported uncertainty, domain-matched cross-component
disagreement, and the `PASS` audit sample.

**Disagreement routes to an LLM adjudicator or targeted repair before a human.** Escalation is
the exception — minimizing routine human review is the whole point.

---

## 5. Reliability and falsification — *not* a correctness proof

None of these checks establish that a verdict is right. Each is an attempt to **disqualify** the
instrument. An instrument that survives all five is *not validated*; it is *not yet falsified*.
Check 3 keeps running permanently for exactly that reason.

### Check 1 — Reproducibility: small sample × repeated readings

~8 items × 4 readings. This is a **per-item claim** ("does *this* item's verdict flip"), so
repetition is the design and D-237 applies: never n=2 for a per-item claim. Reuses D-245's M1
metric, which already worked.

*Falsifies:* verdicts that flip on identical input. *Says nothing about* correctness — a stable
instrument can be stably wrong.

### Check 2 — Approved-bank sanity: broader sample × single reading

~50 bank items × 1 reading. This is an **aggregate rate claim** ("how often does it reject
human-approved content"), so breadth is the design and n=1 per item is correct — the sample size
lives across items, not within them.

Splitting checks 1 and 2 matters: repetition and coverage are different jobs, and one shared
sample buys neither well.

*Falsifies:* an instrument that rejects content a human individually approved. **Not a complete
benchmark** — one topic, one authoring style, and approval ≠ excellence. It sees false rejection
only.

### Check 3 — Both-direction production monitoring

Randomly sample `PASS` alongside `REJECT`/`REPAIR` for independent review; **prefer LLM
cross-review/adjudication**, since removing routine human review is the objective. This is *the
explicit sampling mechanism for detecting false acceptance among otherwise-passing items* —
other pipeline disagreements may also surface failures. Ongoing cost, not a one-time gate.

### Check 4 — Cross-component disagreement: domain-specific routing

**Already computed — build no detector.** Two things to get right, both verified in code:

- **Fatal conflicts never reach this instrument.** `solver_objections()` is a reject gate
  (`ai_pipeline.py:1709-1711`). The usable residue is the *survivable* disagreement:
  `_DIFFICULTY_FLAG_AT`'s 1-off `flagged`, where the item is kept (`:301-302`, `:1884`).
- **Do not wire any trigger to `retiered`.** It requires `slot_gap >= _DIFFICULTY_RETIER_AT`
  **and** `may_retier`; without the second it becomes `rejected` (`:289-292`). A double
  condition — a trigger on it would look correct in review and fire near-zero times.

**`flagged` must not become a generic quality trigger.** A difficulty disagreement means *the
tier may be filed wrong*, not *the hints may be bad*. D-238 settled this: **"the tier is a
label; the item is the work."** Routing it to a hint/solution reviewer would repeat the
conflation that put 26 of 29 candidates at `high` priority and told the reviewer nothing.

| signal | routes to |
|---|---|
| `flagged` / `retiered` | difficulty re-review |
| `solver_objections()` | already a reject gate upstream — never arrives |
| hint/solution-domain judge outputs | this instrument |

**Honest consequence:** once routing is domain-matched, the set feeding this instrument from
check 4 may be small or empty. **Do not manufacture a trigger to fill it.** Check 4 is a routing
discipline, not a guaranteed source of second readings.

### Check 5 — Population distributions

Drift and anomaly monitoring only. **Never a pass/fail criterion.** Similar distributions
between the approved bank and a generated batch do not imply a useless judge — the batch may
genuinely be as good as the bank. (Correcting an over-generalisation of D-249: its force was
per-item disagreement with real human approvals, not distributional similarity.)

### Stopping rule — pre-registered

The instrument ships only if it **survives** checks 1 and 2. Flipping verdicts, or a meaningful
rejection rate on human-approved content, disqualifies it. Surviving is not evidence that it is
right; check 3 exists because that question stays open permanently.

This is the rule D-245 followed when its own rubric clause failed measurement and was not
shipped.

---

## 6. `hint_quality_score` disposition

**Do not delete the field.** It is not unused — it has two independent thresholds and only one
is measured:

| | where | nature | measured? |
|---|---|---|---|
| `_HINT_QUALITY_FLOOR = 3` | `scripts/audit_authored_bank.py` | flag only, no dependents | **yes — D-249** |
| `_HINT_QUALITY_REJECT_BELOW = 2` | `ai_pipeline.py:1769` | **live rejection** | **no** |

It is also read from stored evidence dicts by `review_cli.py:111`, and appears in the judge
prompt, `QuestionJudgeResponse`, the mock provider, and the smoke CLI.

**Decided:**

- Remove `_HINT_QUALITY_FLOOR` from the audit script's decision surface. Keep reporting the raw
  value — observation is not decision-making.
- **Do not add a paid LLM call to the audit script** in its place. If it wants a quality signal
  later, it consumes a verdict the pipeline already produced and stored.
- `_HINT_QUALITY_REJECT_BELOW` **stays until measured.** D-249 measured `<= 3`; it never
  measured `< 2`.
- Deleting the field is a later question that only arises if both thresholds go.

### ⚠️ Caution for any re-analysis of stored scores

8 rows carry `hint_quality_score` of 8 or 9, all from 2026-08-05, written before
`Field(ge=1, le=5)` bounded the field (D-243 area). **Pre-bound and post-bound rows are on
different scales and must not be pooled.**

---

## 7. Cost

| | |
|---|---|
| check 1 | ~8 items × 4 readings = 32 calls |
| check 2 | ~50 items × 1 reading = 50 calls |
| **checks 1 + 2 together** | ~82 calls, order of **~55¢**, hard-capped |
| check 3 | ongoing, proportional to batch size — the standing price of the instrument |
| checks 4 and 5 | free; the signals are already produced |
| repair | one bounded attempt, only on `REPAIR` |

**No new labeled corpus, no new human labeling effort, no dedicated evaluation corpus to
maintain.**

---

## 8. Sequencing

1. ✅ Remove `_HINT_QUALITY_FLOOR` from the audit script's decision-making.
2. ✅ Correct `hint_ladder_monotonicity_violations`' docstring to state actual coverage.
3. Build the instrument as a separate `BedrockTask` on `run_llm_judge`.
4. Validation run: checks 1 and 2, hard-capped.
5. If it survives → wire the decision flow, with check 3 sampling on from day one.
6. Wire check 4's routing; add check 5's monitoring line.
7. Measure `_HINT_QUALITY_REJECT_BELOW` (`< 2`) — the unmeasured live rejection.

---

## 9. Explicitly out of scope

- **Mutation corpus / golden human-labeled test set.** Rejected: an artifact that rots as the
  generator and prompts move, and D-249 showed a judge can be falsified without one.
- **Growing `GOLDEN_DATASET_BAD_ITEMS`.** It stays a coverage tracker pointing at test files,
  not a corpus.
- **Deleting `hint_quality_score`.** See §6.
- **Pairwise comparison.** See §2 — a fit argument, not a safety one.
