# Hint & solution quality review — design (D-251 → D-256)

**Status: the reviewer and the panel exist and are measured; the loop around them is not built.**
The instrument survived two falsification runs — single-reviewer (D-254) and the two-reviewer
union (D-256) — and D-257/D-258 measured its precision (6/6 blocks real) and its recall (~43% on
the one class checkable for free). `review_panel.py` implements §4's panel step: unanimity,
fail-closed on a missing verdict, hallucinated locations filtered.

`review_panel.py` implements the panel; `hint_solution_repair.py` and `review_loop.py` implement
the targeted repair and the bounded loop (D-259/D-260).

**Still not built: any pipeline caller.** Nothing in the generation pipeline runs §4, by choice.
Read this before adding any hint- or solution-quality scoring anywhere.

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

### Correction: `run_llm_judge` is not reused, and cannot be

An earlier version of this section said the instrument would reuse `packages/evals`'
`run_llm_judge` "rather than a new one". Reading it settled the question the other way, and
the reason matters more than the outcome.

`run_llm_judge` is 37 lines and its own docstring calls it *"a thin wrapper over
`BedrockGateway.generate_structured`"*. Its entire substance is its response contract —
`RubricDimensionScore.score: int`, **a 1–5 scalar per dimension**, plus `overall_pass: bool`.
Reusing it would have reintroduced root cause 1 on the first line of code. Its dimension
lists are SPEC §5.31.3 verbatim and are not ours to repurpose.

So `BedrockTask.HINT_SOLUTION_REVIEW` is its own task with its own response model, reusing
the *pattern* — a thin task-specific wrapper — which is this codebase's convention for every
task anyway. `run_llm_judge` keeps its SPEC role and remains without a production caller.

**Found while reading it:** `RubricDimensionScore.score` was unbounded while its own system
prompt said "1 (fails) to 5 (excellent)" — the same defect that made the question judge emit
8s and 9s against thresholds of 2 and 3. It has never bitten because nothing calls it. Now
bounded.

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

## 4. Decision flow — two reviewers on every item, unanimity to accept

**Revised after D-254.** The previous version read each item once and triggered a second reading
on risk (`REJECT`, self-reported uncertainty, the `PASS` audit sample), then sent disagreement to
an LLM adjudicator and finally to a human. That is replaced.

```
generate (Model A)
  ↓
deterministic invariants ───── fail ──→ back to repair (no LLM reviewer call spent)
  ↓
Reviewer B  ‖  Reviewer C      (always both, one reading each, in parallel)
  ↓
both PASS? ── yes ──→ ACCEPT (to the pending queue; §5.8.5 approval is unchanged)
  │
  no
  ↓
merge the two reviewers' defects  →  targeted repair (Model A)
  ↓
deterministic invariants  →  Reviewer B ‖ Reviewer C     ← every round, in full
  ↓
up to 5 repair rounds, or early stop
  ↓
still not unanimous PASS  →  DISCARD (snapshot retained, §4.4)
```

### 4.1 Why the risk trigger had to go anyway

**D-254 measured `uncertainty` at `low` on 48 of 50 items — 96% constant.** The old flow routed
second readings partly on that field. A trigger that fires on 4% of items is not a safety
mechanism; it is a branch that looks like one. Always-two removes the question. `uncertainty`
stays in the schema as an **observability signal only** (§5 check 5) — it costs nothing, it is
already validated, and deleting a field from a measured instrument to tidy a diagram is a change
with risk and no benefit.

### 4.2 `REPAIR` and `REJECT` now route identically, and that is deliberate

Both feed the same merged-defect repair path. The distinction survives in exactly one place: the
early-stop rule below treats a `REJECT` as evidence the item may be unrecoverable, where a
`REPAIR` is not. Nobody should read the two verdicts as different destinations — they are the
same destination with different weight.

### 4.3 Early stop, before the 5-round limit

Stop and discard early when either holds:

- **The same blocking defect recurs** across rounds — the repair is not landing, and rounds 3-5
  will spend the same money to learn the same thing.
- **The item is clearly unrecoverable** — e.g. both reviewers `REJECT` on the *stem's* premise
  rather than on the ladder or solution. A hint repair cannot fix a question that asks the wrong
  thing. D-254 found exactly this case in shipped content (`place_value-d4-200402`: the ladder
  teaches place-value comparison for a question that requires subtraction), and no amount of hint
  rewriting fixes it.

**Detecting the first condition requires storing every round's defects.** That is not optional
bookkeeping — see §4.4.

### 4.4 Discard must keep the evidence (D-195's lesson, restated because it now applies twice)

D-195: *rejected candidates kept no content, so a pilot that rejects everything leaves nothing to
review.* Under this flow a discarded item has consumed up to 17 model calls, so discarding
without a record is more expensive than it was then. Every discarded item retains its
`candidate_snapshot`, the merged defects **per round**, and the round count. Two consumers:
the recurring-defect early stop, and any question about whether a batch's discard rate is the
generator's fault or the reviewers'.

*(This lesson was re-learned the hard way during D-254 itself: the measurement script recorded
defect **counts** and not defect **content**, so the run's five blocked items could not be read
without re-buying them.)*

### 4.5 No adjudicator, no routine human escalation

Disagreement between B and C is not adjudicated — it simply is not unanimity, so the item goes to
repair. After the round limit the item is discarded. Nothing queues for a human on the failure
path.

**One consequence to state plainly:** this removes the only mechanism by which a *false rejection*
would ever be seen. An item the reviewers are jointly wrong about is now discarded silently. §5
check 2 is the only defence, and it is a pre-ship measurement rather than a live one — so it has
to be re-run whenever a reviewer model changes, not once.

**`ACCEPT` means "passed the automated bar", not "served".** Accepted items still land in the
pending queue and the §5.8.5 approval path is untouched; this document does not change who reads
an item before a student does.

### 4.5b A reviewer that returns nothing is not a `PASS` — fail closed

**Found by D-256, not designed in.** `openai.gpt-oss-120b-1:0` failed to produce a valid verdict
for `place_value-d4-200402`: it emitted `defects[0].index = 0` against `Field(ge=1)`, and the
gateway's single repair retry did not recover it. The schema was right to refuse — a 0-based
index would point at the wrong hint — but the architecture had no answer for what happens next,
because "unanimous `PASS`" is undefined when one reviewer returns no verdict at all.

**The rule: a missing verdict counts as blocking.** This is CLAUDE.md rule 5 (*fail closed*)
applied to a case the two-reviewer design created. The alternative — treating an unreachable
reviewer as consent — makes an outage look like approval, which is the failure mode that rule
exists to forbid.

Two things worth noticing about *which* item did this:

- It is **the single most defective item in the sample** — the one B rejected in D-254 for a hint
  ladder that teaches a method which cannot answer its own question. The item with the most to
  say is the one that pushed a reviewer past its schema. Errors are not uniformly distributed
  over content, so an error rate measured on easy items understates this.
- It is why the union's check-2 denominator is **49, not 50**. Stated rather than rounded away.

### 4.6 Repairs are targeted, not re-rolls

The repair prompt carries the item **plus** the merged defects, and changes only what the defects
name. Everything the reviewers did not object to is preserved verbatim.

Two reasons, one of them already paid for:

- **D-198 established the principle** — a rejection already says what is wrong, and re-rolling
  throws that away. The bounded repair loop exists precisely because the feedback is the asset.
- **A re-roll invalidates the round history.** The early-stop rule (§4.3) fires on *the same
  blocking defect recurring*. If each round produces a fresh item, "the same defect" is not
  defined, and the 5-round limit becomes 5 independent generations wearing a loop's clothing.

`out_of_range_defects()` is a **hard filter here, not a report line**: a defect pointing at a
hint index the item does not have must never reach a repair prompt, because repairing against a
location that does not exist is how a correct item gets damaged. D-254 measured M3 = 0 for
reviewer B, so this has never yet been needed — which is the argument for wiring it before it is.

---

## 5. Reliability and falsification — *not* a correctness proof

None of these checks establish that a verdict is right. Each is an attempt to **disqualify** the
instrument. An instrument that survives all five is *not validated*; it is *not yet falsified*.
Check 3 keeps running permanently for exactly that reason.

### Check 1 — Reproducibility: small sample × repeated readings

~8 items × 4 readings, **run per reviewer and again on the union verdict**. This is a **per-item
claim** ("does *this* item's verdict flip"), so repetition is the design and D-237 applies: never
n=2 for a per-item claim. Reuses D-245's M1 metric, which already worked.

**Both levels are required**, and the reason is not the one first written here.

> ~~Unanimity makes the union *less* stable than either reviewer alone — an item flips the union
> if **either** reviewer flips.~~ **Measured false (D-256.)** B split on 1 of 8, C on 2 of 8, and
> the **union on 1** — more stable than one of its own members.

The mechanism, visible in the per-item data: unanimity-to-accept means a reviewer that blocks an
item *consistently* **masks** the other's instability, because the union is already blocked on
every reading. On `fraction_operations-d2-100205` both reviewers individually split and the union
did not. On `fraction_operations-d3-100307` only C split, B passed consistently, and the union
inherited C's flip.

So union stability depends on **whether the blocking is correlated**, and cannot be derived from
the per-reviewer numbers in either direction. That is exactly why both levels get measured
instead of one being inferred from the other.

*Falsifies:* verdicts that flip on identical input. *Says nothing about* correctness — a stable
instrument can be stably wrong.

**Result, single reviewer (D-254, Haiku 4.5):** M1 = **1 of 8**, against a pre-registered
disqualifier of 3. Not falsified. The union number is unmeasured.

### Check 2 — Approved-bank sanity: broader sample × single reading

~50 bank items × 1 reading **per reviewer**, scored on the union. This is an **aggregate rate
claim** ("how often does it block human-approved content"), so breadth is the design and n=1 per
item is correct — the sample size lives across items, not within them.

Splitting checks 1 and 2 matters: repetition and coverage are different jobs, and one shared
sample buys neither well.

*Falsifies:* an instrument that blocks content a human individually approved. **Not a complete
benchmark** — one topic, one authoring style, and approval ≠ excellence. It sees false rejection
only.

**Result, single reviewer (D-254):** M2 = **10%** blocking, M2r = **2%** reject, against
disqualifiers of 30% and 10%. Not falsified — and **the blocks were not noise**: two of the five
were read by hand and both are real defects in live content, one of them serious (a ladder
teaching a method that does not solve its own question).

**Result, union (D-256, B = Haiku 4.5, C = gpt-oss-120b):** M1 **1 of 8**, M2 **22.4%**,
M2r **2%**, M3 **0**, over 49 items (§4.5b explains the missing one). All four disqualifiers
survived. The pre-registration predicted 15-25% for M2 and it landed at 22.4% — about 2.2x
reviewer B alone, close to the ~19% an independence assumption gives.

**22.4% turned out to be the wrong thing to worry about (D-257/D-258).** The disqualifier is 30%
and the pair blocks a little over one in five human-approved items — but **6 of 6 blocks read by
hand were real defects**, and a free deterministic audit finds the same defect class in **8 of the
38 items the pair passed**. Measured recall on that class is **~43%**.

So the union **understates** the defect rate rather than inflating it. Perfect recall on that one
class would put it near 28.6%, approaching the disqualifier from the *correct* direction. The
worry inherited from D-249 — a signal that fires on everything — is not this instrument's problem;
being conservative is.

### Check 3 — Both-direction production monitoring, now needing a *third* opinion

Randomly sample `ACCEPT` alongside discarded items for independent review. **The change forced by
§4:** an accepted item has already been passed by both B and C, so re-reading it with B or C is
not independent — it is asking the same two models the same question. Check 3's sampler must be
**a third model or a periodic human audit**, or it measures nothing.

This is *the* mechanism for detecting false acceptance, and §4.5 removed the other one: with no
adjudicator and no human escalation on the failure path, a jointly-wrong pair discards silently.
Ongoing cost, not a one-time gate.

**A deterministic audit is a third option, and it is already earning its place (D-258).** Running
`scripts/audit_solution_step_completeness.py` against the items the union *passed* found **8 of
38** carrying the exact defect class the pair blocked others for — the first false-acceptance
evidence this project has, at zero cost. It needs no opinion, has perfect recall on its own narrow
class, and **cannot be jointly wrong with the reviewers because it is not a reviewer.**

It does not replace the model or human sampler: `linear_equations-d3-2609301`'s "two operations
described as one" is invisible to any regex, and 5 of 11 blocks were for things no audit could see.
**Both belong in check 3** — the audit for exhaustive coverage of a narrow class, the sampler for
everything else.

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

Three signals the two-reviewer architecture produces for free, all monitored and none a gate:

- **B-vs-C disagreement rate.** The single best early warning that one reviewer has drifted or
  that the two have collapsed onto the same opinion. **Near-zero is as suspicious as high**: two
  reviewers that never disagree are one reviewer being billed twice, and the model-diversity
  requirement (§5.6) exists to prevent exactly that.
- **Round-count distribution.** How many repair rounds items actually take. If almost everything
  resolves in round 1 or dies at round 5, the middle rounds are being bought for nothing and the
  limit should move.
- **`uncertainty` distribution.** It routes nothing now (§4.1). D-254 measured it at 48/50 `low`,
  so its baseline is known: a shift away from ~96% `low` is the signal, not the level.

### 5.6 Model roles and diversity

| role | model | why |
|---|---|---|
| A — generator *and* repairer | `mistral.mistral-large-3-675b-instruct` | already the pipeline's generator (D-205); a repair is authoring with a constraint, so one model does both. |
| B — reviewer 1 | `us.anthropic.claude-haiku-4-5` | the only reviewer configuration with a falsification result (D-254). |
| C — reviewer 2 | `openai.gpt-oss-120b-1:0` | **measured** — see below. |

**Three providers: Mistral, Anthropic, OpenAI.** That is genuine cross-family diversity, not the
partial version.

**Two corrections to the first draft of this section, both found by checking rather than
assuming.**

- *"C = Mistral"* is wrong on **independence**, before any capability question: Mistral Large 3
  is Model A. A generator reviewing its own output is not an independent reviewer, and no amount
  of family diversity fixes that.
- *"D-204 measured Mistral as unable to use tools at all"* is wrong on **fact**. D-204 measured
  `mistral.magistral-small-2509` returning no `toolUse` block; `mistral.mistral-large-3-675b-instruct`
  passed both smoke and the generator contract. Two different models, one family name.

**C was chosen on a measurement, not a preference.** `smoke_cli --contract hint_solution_review`
(added for this) probed the candidates for one call each:

| model | invocation | stop reason | repaired |
|---|---|---|---|
| `openai.gpt-oss-120b-1:0` | SUCCESS | `tool_use` | no |
| `qwen.qwen3-32b-v1:0` | SUCCESS | `tool_use` | no |

Both emit the contract. **C = gpt-oss-120b** because D-204 measured it as the judge that *solved
the question rather than asserting about it* — the one property a reviewer's job depends on —
while Nova 2 Lite failed exactly that test in the same run. Qwen3-32b is the fallback and needs
no new probe.

Sonnet 4.5 is no longer proposed. It is configured and frictionless, but it is B's family and
this roster no longer needs the compromise.

### Stopping rule — pre-registered

The instrument ships only if it **survives** checks 1 and 2. Flipping verdicts, or a meaningful
rejection rate on human-approved content, disqualifies it. Surviving is not evidence that it is
right; check 3 exists because that question stays open permanently.

This is the rule D-245 followed when its own rubric clause failed measurement and was not
shipped.

**Status after D-254, and what it does *not* cover.** Reviewer B (Haiku 4.5) survived all four
pre-registered thresholds as a **single** reviewer: M1 1/8, M2 10%, M2r 2%, M3 0. That result
does not transfer to the architecture in §4. **The two-reviewer union is a different instrument
and is unmeasured** — its blocking rate is higher by construction, its stability is lower by
construction, and reviewer C does not yet exist. Nothing is wired until the union has its own
run, with its predictions registered before it, exactly as D-254's were.

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

## 7. Cost — recomputed for two reviewers and 5 repair rounds

D-254's measured unit price: **29.1¢ for 82 review calls = ~0.36¢ per review call** (Haiku 4.5,
`max_output_tokens=1500`, real bank items).

### Falsification runs (one-time, per reviewer model)

| | |
|---|---|
| check 1 | 8 items × 4 readings × **2 reviewers** = 64 calls |
| check 2 | 50 items × 1 reading × **2 reviewers** = 100 calls |
| **together** | ~164 calls, order of **~60¢**, hard-capped |

Double the single-reviewer run because **each reviewer must be falsified on its own** before the
union is trusted. A union metric alone cannot tell a good reviewer paired with a broken one from
two mediocre ones.

### Per item, in production

| | review calls | repair calls |
|---|---|---|
| best case (unanimous first pass) | 2 | 0 |
| worst case (5 rounds, then discard) | 12 | 5 |

Best case ≈ **0.7¢** per item. Worst case ≈ 4.3¢ of review **plus 5 full authoring calls**, which
are the expensive ones — a 15-field forced schema, not a 4-field verdict.

**The round limit is not a spend limit, and this needs both.** Five rounds bounds *iterations*;
it does not bound cents, because a repair call's cost is set by the authoring schema and not by
this document. A **per-item cent cap** is required alongside the round cap, enforced the way
`--run-budget-cents` already is — otherwise a pathological item can spend a batch's budget inside
its own round limit while looking compliant.

### Standing costs

| | |
|---|---|
| check 3 | ongoing, and now needs a **third** opinion — see §5 check 3 |
| checks 4 and 5 | free; the signals are already produced |

**No new labeled corpus, no new human labeling effort, no dedicated evaluation corpus to
maintain.**

---

## 8. Sequencing

1. ✅ Remove `_HINT_QUALITY_FLOOR` from the audit script's decision-making.
2. ✅ Correct `hint_ladder_monotonicity_violations`' docstring to state actual coverage.
3. ✅ Build the instrument as its own `BedrockTask` — `HINT_SOLUTION_REVIEW`,
   `curriculum/hint_solution_review.py`, with a mock-provider branch and contract tests.
   **Wired to nothing**: no pipeline caller exists until step 4 passes.
4. Validation run: checks 1 and 2, hard-capped. **First paid step.**
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
