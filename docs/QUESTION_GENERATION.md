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
| `requested` | the slot being generated for | an instruction — decides where the item is stored and what its template id says |
| `proposed` | the Generator | **anchored** — the Generator is told the target, so the number is weak evidence and the rationale beside it is the part worth reading |
| `reviewed` | the judge | the only independent reading. `QuestionJudgePayload` carries neither of the others |

Two gates, both rejecting at a gap of 2:

- `|proposed − reviewed| ≥ 2` — two readers of the same item disagree and nothing can say which is
  wrong.
- `|reviewed − requested| ≥ 2` — the item does not belong in the slot it would be stored at, which
  would offer it to students who have earned a different tier.

A gap of 1 on either keeps the item and sets `review_priority="high"`. Rejections land in their own
`rejected_at="difficulty"` bucket: a judge rejection says the question is bad, this one says the
question may be fine.

Both values, both rationales, both gaps and the decision are written to
`question_validation_runs.stage_results["difficulty"]`. The Generator's value is never silently
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
```

`--skill-id` and `--difficulty` repeat. `--candidates-per-difficulty` still works as the old name for
`--candidates-per-slot`.

**Seeds are deterministic**, so a second run at the same settings re-proposes the ids the first run's
survivors hold. `--seed-offset` claims a fresh range; the caller picks it deliberately rather than
from a timestamp, so runs stay reproducible. Narrowing a run does not move its seeds — a filtered run
proposes the same ids a full run would for the slots they share.

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
  fails into a bounded repair retry, then rejection.

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
| Cross-provider solvers | measured evidence that two Anthropic models are not independent enough |
| Auto-approval for a narrow slice | a near-zero human rejection rate over a real sample |
| Resume | an interrupted run that a fresh seed offset could not recover |

## 10. State

The bank holds 5 approved authored items (`curriculum/internal_math/authored/linear_equations.yaml`)
and 50 hand-authored shape templates. Twelve authored candidates sit at `pending` as the pilot's
human-review comparison set; eight equation-first candidates were retired in D-193.

**No paid pilot has been run.**
