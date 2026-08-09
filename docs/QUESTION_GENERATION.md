# AI question generation — the as-built design

Status: **implemented** as described. Decisions: D-026, D-186, D-188 … D-194.
This is the narrowed design of record. A broader system was drafted; what is deferred from it, and
why, is at the end.

Scope right now: **one topic** (`linear_equations`), **multiple-choice only**, solo-maintained.
Everything below is sized for that and is expected to grow when there is evidence it should.

---

## 1. What this is

An **offline** pipeline that adds validated questions to the bank. It is never called from a student
request path (CLAUDE.md rule 2). Students are served from the bank by deterministic, low-latency
selection, which is what keeps latency, cost, reproducibility and pre/post comparability intact.

**Authored-first is the only AI-authored mode.** The Generator writes the complete student-facing
item; independent reviewers then check it. An equation-first mode (generate the equation in code,
have the model dress it in a story) was built and retired in D-193: it guarantees the *equation's*
answer, not that the story encodes that equation, and no downstream stage can see the difference
because they all inherit the pre-chosen answer. A wrong item reached `pending` that way.

## 2. The pipeline

```
build_plan()  ── slots: (topic, skill, tier, index) → seed → template id
     │
     ▼
Generator ─ writes the whole MCQ, and proposes its own difficulty + rationale + prerequisites
     │
     ▼
shuffle_options() ─ seeded, in code. Never left to the prompt (D-191: six items in a row were "b")
     │
     ▼
Deterministic §5.8.5 gate ─ SymPy solve, exactly-one-correct, leakage, hint monotonicity,
     │                       wording, readability, HTML
     ▼
Dedup ─ stem embedding, cosine distance
     │
     ▼
Solver A ─┐  both see only the stem and options; neither sees the answer
Solver B ─┴─→ solver_objections(): no_option_matches / is_unambiguous checked BEFORE agreement
     │
     ▼
Judge ─ ambiguity, alignment, age-appropriateness, internal consistency, hint quality,
     │   and an independent difficulty rating. Blind to the requested and proposed tiers.
     ▼
judge_difficulty() ─ deterministic comparison of the two ratings
     │
     ▼
pending  ──→  review_cli (human)  ──→  export_cli  ──→  versioned YAML  ──→  CI → staging → prod
```

Nothing is auto-approved, auto-exported or auto-deployed. `pending` → `approved` is a human action
through `review_cli` (D-026), and approved content only reaches an environment by being committed as
a file (D-190).

## 3. Difficulty

The Generator proposes; the judge reviews independently; a deterministic rule decides.

Three values, answering different questions:

| value | source | what it is |
|---|---|---|
| `requested` | the slot being generated for | an instruction — it fixes the template id permanently, and it is where the item is stored *unless* the judge moves it (D-239). The `d{n}` in a template id is always the tier the item was **authored** at; read `difficulty_label` for its current one (D-235) |
| `proposed` | the Generator | **anchored** — the Generator is told the target, so the number is weak evidence and the rationale beside it is the part worth reading |
| `reviewed` | the judge | the only independent reading. `QuestionJudgePayload` carries neither of the others |

**One gate decides, and since D-239 it moves the item rather than discarding it.**

`|reviewed − requested| ≥ 2` — the item does not belong in the slot it would be stored at, which
would offer it to students who have earned a different tier. The item is **kept and stored at
`reviewed`**, `validation_status="pending"`, `review_priority="high"`, and the move is recorded in
`stage_results["difficulty"]` as `stored_at_difficulty` / `retiered_from`. The run counts it as
`retiered` — a filled slot, reported separately from a clean pass and from a rejection.

Rejecting it destroyed a question that had already passed the generator, both solvers and every
judge flag, because one number was two away from the slot it happened to be generated for. D-238
measured what that number is worth: `place_value` items sat two tiers from where the judge read them
because the *rubric* conflated two skills, and the repair was to move tiers without touching a single
item's content. The tier is the cheap thing to change; the item is the expensive one.

**The move is gated on the judge discriminating.** A judge answering the same tier for everything
produces small gaps on any bank centred near that tier and reads as excellent calibration, so
re-tiering on it would quietly restack a run onto one tier and report a high yield for doing it.
`JudgeDispersion` accumulates the run's own `reviewed` values; a move needs ≥ 5 observations with the
dominant tier holding < 80% of them (D-231 — dispersion, not distinctness: its first version passed
`{2: 20, 5: 1}`). Below that the item is **rejected exactly as before**, and the reason says so.
Consequence worth knowing: the first few candidates of any run can never be re-tiered, and a short
run moves nothing.

**`|proposed − reviewed|` no longer rejects (D-239).** Over all 41 pipeline candidates carrying a
difficulty stage it rejected independently of the slot gap **zero** times, and `requested == proposed`
in **30** of them — the Generator is anchored, so its number was never independent evidence. Kept as
a rejection it would have fired on the same items the re-tier exists to save. It still contributes to
`review_priority="high"`, and `proposed` plus its rationale stay in the evidence as provenance.

A gap of 1 on either keeps the item and sets `review_priority="high"`. Rejections still land in their
own `rejected_at="difficulty"` bucket: a judge rejection says the question is bad, this one says the
question may be fine.

Both values, both rationales, both gaps, the decision, and the tier the item was actually stored at
are written to `question_validation_runs.stage_results["difficulty"]`. The Generator's value is never silently
overwritten.

**Acceptability is computed, not asked of the model.** A judge blind to the proposal cannot say
whether it is acceptable, and a judge shown the proposal is not independent. Arithmetic on two
numbers is the only coherent answer, and the one that cannot be argued out of.

**This is provisional.** Model-estimated difficulty is a placeholder for empirical calibration from
real student responses — proportion correct, median response time, hint usage, discrimination between
higher- and lower-mastery students. When that data exists it supersedes these estimates;
`difficulty_confidence` is the field it lands in. The Generator's proposal stays useful as
provenance.

## 4. Running it

```bash
# Free. Calls nothing, writes nothing. Run before every paid batch.
make question-gen-preflight

# A narrower batch, with room to spend.
make question-gen-authored QUESTION_GEN_ARGS="\
  --topic-id linear_equations \
  --skill-id linear_both_sides \
  --difficulty 3 --difficulty 4 \
  --candidates-per-slot 3 \
  --seed-offset 40000 \
  --run-budget-cents 100"

# Same plan, listed slot by slot, still calling nothing.
uv run python -m intellichoice_curriculum.pipeline_cli --mode authored --dry-run

make question-review     # human approval, item by item
make question-export     # approved rows → curriculum/internal_math/authored/<topic>.yaml

# Free and read-only: what a rejected candidate actually said, and which gate stopped it.
# Builds no gateway, so it cannot spend; has no approve path, so it cannot promote.
make question-review-rejected
make question-review-rejected QUESTION_REVIEW_ARGS="--planned-id authored-linear_equations-d4-400400"
```

`--skill-id` and `--difficulty` repeat. `--candidates-per-difficulty` still works as the old name for
`--candidates-per-slot`.

**Seeds are deterministic**, so a second run at the same settings re-proposes the ids the first run's
survivors hold. `--seed-offset` claims a fresh range; the caller picks it deliberately rather than
from a timestamp, so runs stay reproducible. Narrowing a run does not move its seeds — a filtered run
proposes the same ids a full run would for the slots they share.

## 4a. Repair loop (D-198)

Off by default. When on, a candidate rejected for something a rewrite could fix is sent back to the
Generator with a description of what was wrong, and re-gated from scratch.

```bash
make question-gen-authored QUESTION_GEN_ARGS="... --max-repair-attempts 1"
```

**The slot keeps one template id across every attempt**, which is why the loop lives inside
`generate_authored_candidate` rather than in `run_plan`: the seed *is* the id, so retrying at the
plan level would need a fresh seed and would claim a slot promised to another candidate.

**What may be fed back is filtered, not forwarded** — `ai_pipeline.repair_feedback` is the only
place that decides:

| stage | repairable | what crosses |
|---|---|---|
| `validation` | ✅ | the deterministic failures verbatim — objective, no verdict |
| `solver` | ✅ | *that* a solver could not find the answer, or found it ambiguous — **never which option any solver chose** |
| `judge` | ✅ | the qualitative flags — **never `reviewed_difficulty`** |
| `difficulty` | ❌ terminal | the only useful feedback is the judge's tier, and returning it is relabeling, not repair |
| `dedup`, `generator` | ❌ terminal | nothing to repair from |

The reason is not squeamishness. The raw rejection reasons read
`independent solver disagreement: solver_a='b' solver_b='a' declared='c'` — and the cheapest way to
resolve that is to declare `b`. The gate passes, the item is unchanged, and the independent solve
has become a lookup. Same for the judge's tier: returning it makes D-194's blind review a target.

`difficulty` is terminal for a second, measured reason: D-197 found `linear_both_sides`
proposed-4/judged-2 four times across three sessions. That slot's authoring plan is miscalibrated,
not its items, so repairing them buys nothing.

**Every attempt is fully re-gated and fully recorded.** A failed repair writes its own
`question_validation_runs` row with its own snapshot and `attempt` number, so
`make question-review-rejected` shows the whole history. Only an attempt that clears every gate
persists a template, and it persists as `pending` — repair never approves anything.

**Cost is bounded twice:** `--max-repair-attempts` caps attempts per slot, and the run budget is
enforced *inside* the loop as well as between slots, so a slot cannot overshoot it. Preflight prints
the worst case in Generator calls before anything is paid for. `RunSummary` reports
`generator_calls`, `fixed` and `still_rejected` separately, because "repair helps" and "repair is
affordable" are different claims.

## 5. Preflight

Zero model calls, zero embedding calls, zero writes — asserted by test, not assumed. It reports
provider, all five resolved model ids, selected topic/skills/difficulties, candidates per slot,
scheduled count, planned and already-used template ids, seed offset, budget ceiling and estimated
maximum calls.

It **fails** on: Solver A and B resolving to the same *underlying model*; planned ids that already
exist; a requested budget above the configured hard cap. Bedrock's `us.` / `global.` / `eu.` /
`apac.` inference-profile prefixes are stripped before that comparison — they are routing aliases
for the same weights, and comparing raw strings let two spellings of one model report PASS.

Planning failures — unknown topic, a skill outside it, a difficulty off the 1–5 scale, a filter
matching no slots — raise before the engine is created.

**A paid run refuses to start when preflight fails.** A mock run continues and says so.
`--allow-preflight-failure` is the documented override, because a single-model solver pair is the
right configuration for a mock smoke test.

Maximum *spend* is deliberately not estimated: per-call cost depends on the model ids and output
length, and the one measurement this project has (Haiku, ~0.29¢/call) says nothing about a premium
generator. The enforced budget ceiling is a real bound; an invented average would read like one.

## 6. Models

Intended paid configuration:

| role | tier | why |
|---|---|---|
| Generator | premium Anthropic | writing a good item is the hard part and the one worth paying for |
| Solver A | lower-cost Anthropic | independence matters more than capability here |
| Solver B | **a different** lower-cost Anthropic model | two solvers that are one model agree by construction |
| Judge | lower-cost or mid-tier Anthropic | reads a finished item against a rubric |

### Measured availability (account 320503430250, us-east-1, 2026-08-05)

Read from `bedrock get-foundation-model-availability` and `cloudwatch list-metrics` — no invocation.
Only **two** Anthropic models have an available agreement:

| model | agreement | ever invoked | usable |
|---|---|---|---|
| `us.anthropic.claude-haiku-4-5-20251001-v1:0` | AVAILABLE | yes (S32 onward) | **verified** |
| `us.anthropic.claude-sonnet-5` | AVAILABLE | no | indicated, unproven |
| Opus 4.1 / 4.5 / 5, Sonnet 4 / 4.5, Claude 3 Haiku | NOT_AVAILABLE | no | no |

Two consequences worth knowing before configuring a run:

1. **The shipped code default `anthropic.claude-sonnet-5` is not invocable as written.** Every ACTIVE
   Anthropic model in this region is `INFERENCE_PROFILE` only, so the bare id has no on-demand
   throughput and the call fails. Use the `us.`-prefixed inference profile id, as `.env.example`
   already does.
2. **There is no second low-cost model to give Solver B.** With two accessible models, a
   premium-generator configuration forces Solver B onto the generator's own model. That passes the
   diversity gate but weakens it: the same weights re-reading their own question fail in correlated
   ways. Solver A stays genuinely independent, so a generator error it catches still rejects — the
   weakness is asymmetric, not fatal. Enabling model access for one more low-cost Anthropic model
   is what makes a clean three-model setup possible.

Solver A and B **must** be different model ids. They currently are not: both slots default to the
same value, so every "independent solver agreement" recorded before D-194 was one opinion counted
twice. Preflight now says so before the money is spent.

Anthropic only. A non-Anthropic provider is a real integration, not a config change — the gateway
assumes Anthropic's tool-use contract (`model_json_schema()` as the tool input schema).

## 7. Safety properties worth keeping

- **Per-candidate commit.** One candidate's failure or duplicate id costs that candidate, not the
  batch. An interrupted run keeps everything committed up to the interruption. There is no resume
  framework — a fresh `--seed-offset` is the supported way to continue.
- **Reasoning first.** `reasoning` is the first field of both `SolverResponse` and
  `QuestionJudgeResponse`, because a model emits JSON in schema order and a verdict declared before
  the reasoning cannot be revised by it. D-193 has the measured failure this prevents.
- **Solvers can decline.** `no_option_matches` and `is_unambiguous`, checked before agreement. Either
  solver objecting is enough.
- **Bounded scales.** Every 1–5 field carries `ge`/`le`, so the bound reaches the model in the tool
  schema. An unbounded one was invented into a 1–10 scale and silently disabled the gate reading it.
- **Strict schemas.** `extra="forbid"` on payloads and on the authored response; a drifted model
  fails into a bounded repair retry, then rejection. `hint_ladder` is bounded to exactly three
  entries in the schema itself (D-195 §5), so the rule reaches the model rather than only the gate.
- **A rejected candidate keeps its content.** Every rejection after the Generator returned an item
  persists a complete `candidate_snapshot` — stem, context, options, declared answer, hints,
  solution, equation, proposed difficulty and its rationale, prerequisites, misconception tags,
  estimated time, plus the slot, seed and generator model id. Taken *after* `shuffle_options`, so it
  is the item the gates actually judged. Read it with `make question-review-rejected`.
- **Nothing is invented where no item existed.** A Generator-stage failure records
  `generator_request` and the provider's exact error instead of a snapshot.

## 8. Run metrics

`scheduled`, `processed`, `pending`, per-stage rejections (`generator`, `validation`, `dedup`,
`solver`, `judge`, `difficulty`), `skipped_budget`, `skipped_duplicate_id`, `total_cost_cents`.

`processed` is the honest denominator for quality; `scheduled` is the one for coverage. Budget skips
never reached a model and are not rejections. Only counters with a real producer exist — a counter
nothing increments reads as "measured zero" rather than "not measured".

## 9. Deferred, and what would justify each

Not built. Each waits on evidence from a real pilot rather than on a schedule.

| deferred | would be justified by |
|---|---|
| YAML presets | more than one routinely-repeated argument set. Attaches to `build_plan`; no generation logic changes |
| Verifier router beyond the SymPy check | a second topic whose mathematics SymPy does not model |
| Separate engagement judge | evidence that the current judge misses dull-but-correct items |
| Non-MCQ types (proof, open response) | a serving path. Grading is deterministic option matching today, so generating them would create content the app cannot show |
| Auto-approval for a narrow slice | a near-zero human rejection rate over a real sample |
| Resume | an interrupted run that a fresh seed offset could not recover |

## 9a. Hand-authoring, when the pipeline is not available (D-222, extended in D-223)

`fraction_operations`' 30 items and `place_value`'s 25 were written by hand, not generated.
**A topic's content has to be authored-mode YAML** under `curriculum/internal_math/authored/`.
D-222 tried a shape bank for `fraction_operations` first and had to revert it — `_servable()`
filters on `authoring_mode == "authored"` (D-210), so those templates loaded and were then filtered
out of every serving read. D-226 deleted that route entirely, so this is now the only route rather
than the correct one of two.

What a hand-authored item gets, and what it does not:

| | authored by the pipeline | authored by hand |
|---|---|---|
| deterministic §5.8.5 gate | ✅ at generation *and* every load | ✅ every load |
| two independent solvers | ✅ | ❌ |
| blind judge + difficulty gate | ✅ | ❌ |
| human approval before export | ✅ | ✅ (the author is the reviewer) |
| provenance | model ids in `review_model_versions` | `generator_model: hand-authored-v1`, empty `review_model_versions` |

The two missing gates are the ones that cost money, and they are the ones that catch what
determinism cannot: an under-specified stem (the solver panel) and an implausible scale or a
mis-tiered item (the judge). Hand-authoring therefore carries an obligation the pipeline does not
put on the author — state every quantity the question asks the student to use, in the stem — and it
leaves the difficulty tiers as one person's judgement, which is what `difficulty_confidence` and
SPEC §5.8.4's empirical calibration exist to supersede.

The file is still the artifact: write it, load it, then `make question-export` so it matches what
the database would produce, byte for byte. `test_the_repo_bank_file_matches_what_the_database_would_export`
compares the whole list, order included, and the export orders by `(skill_id, difficulty_label, id)`.

### How many items a topic needs (D-223)

The availability floor is 2 per difficulty (`QUESTIONS_PER_DIFFICULTY`), and it is a floor, not a
target: a pre-exam draws 2 per tier, so a topic sitting on the floor serves a student *its whole
bank* and repeats it in full on the next session. Measured on `fraction_operations` at 3 per tier,
two independently-built exams had to share at least 5 of 10 items; at 5–7 per tier, three exams
covered **19 of 30** distinct questions with **3/10 and 6/10** overlap.

Two things do *not* have to be filled in, and treating them as targets would cost content quality:

- **Every `(skill, difficulty)` cell.** Adding like-denominator fractions is not a difficulty-5
  skill. Nothing requires the cell to be non-empty — the pre-exam reads per difficulty across the
  topic, and the study selector reads the skill's whole pool and takes `_closest_to_recommended`,
  so an absent tier degrades to the nearest present one.
- **An equal count per skill.** The bank should follow where the skill actually spans.

## 10. State

The bank holds **127 approved authored items** — 47 `linear_equations`, 30 `fraction_operations`
(15 in D-222, 15 more in D-223), 25 `place_value` (D-225) and 25 `multiplication_division`
(D-228) — so every topic in the taxonomy is stocked and grades 1-7 all resolve to one. **That is now the whole bank**: D-226 deleted the 50 hand-authored
shape templates and the machinery behind them, which `_servable()` had filtered out of every serving
read since D-210. Fifty inert `authoring_mode='shape'` rows remain in databases that already loaded
them; nothing reads them. Twelve authored
candidates sit at `pending` as the pilot's human-review comparison set; eight equation-first
candidates were retired in D-193.

### The first paid pilot (D-195, 2026-08-06)

Four candidates, seed offset `400000`, 13.21¢. **0 accepted, and that was the correct outcome** —
all four were defective and each was caught by a different gate.

| # | stage | defect |
|---|---|---|
| 1 | validation | four hints where the contract says three |
| 2 | validation | equation with no unknown *and false* (8.5 ≠ 9); a hint leaking the answer; `"The question is adjusted to ask for..."` in the student-facing stem |
| 3 | difficulty | mathematically correct; generator proposed 4, blind judge reviewed 2, requested 4 |
| 4 | solver | stem gave no starting amounts or rates; both solvers objected, one set `no_option_matches` |

What the pilot established, beyond the four rejections:

- **The gates work, including the ones that cost money.** The deterministic gate cannot see an
  under-specified stem (#4) — only the solver panel caught it. The solver panel cannot see an
  implausible scale (#3's 8 cm × 18 cm "garden") — nothing caught it.
- **Candidate 3 is the case to understand before touching the difficulty policy.** It was correct,
  well-built, and lost to a genuine two-tier disagreement between two independent readings. Its true
  tier is ~3; the generator and judge were each off by one in opposite directions. At a requested
  tier of 3 it would have passed. The gate is doing its job, not misfiring.
- **No planned template id was created**, so seed offset `400000` remains reusable.

**Next:** one identical four-candidate repeat — same models, same seed offset, with D-195 §5's
snapshot in place so the content can actually be read this time. If it again yields 0 of 4, stop
using Mistral Large 3 as Generator and obtain additional model access: it is the only accessible
model that passes the generator contract, so there is no better one to switch to.
