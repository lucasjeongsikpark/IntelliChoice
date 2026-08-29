# E4 — Long-term LLM memory: consolidation benchmark

> Theme 4 of `docs/resume_evidence/MEASUREMENT_PLAN.md`. Measured 2026-08-29 at repository
> `a6c80fa`. Nothing here changed product behaviour; no staging or production system was
> touched. Every student is synthetic (`bench-student-*`), every database is a dedicated
> benchmark database, and no real or fixture-derived PII exists anywhere in the corpus.
>
> **Environment labels, per arm — never blurred:**
>
> | arm | environment | what it may be quoted for |
> |---|---|---|
> | `mock` (E4.1) | **mock-model simulation, local** | pipeline mechanics only — tokens, batching, call counts, drops, compression, deterministic lifecycle and screens |
> | `scripted` | **deterministic code measurement, local (no provider)** | the transition protocol and the four candidate screens, as code |
> | `real / shipped` (E4.2-A) | **real-model evaluation (Haiku 4.5), local data** | what the shipped configuration actually does |
> | `real / headroom` (E4.2-B) | **real-model evaluation (Haiku 4.5), local data — ABLATION, not the shipped configuration** | model behaviour once the output budget is not the binding constraint |
>
> **No quality number is quoted from the mock arm.** Its facts derive from keywords in the
> code-rendered event summaries this benchmark itself generated, so they are correct by
> construction; what a mock eval measures is the mock (AUD-C-05). Quality numbers come
> only from the two real arms, and they are reported separately because they disagree.

---

## 1. Headline results

**The shipped output budget silently truncates real-model consolidation.** Against real
Bedrock with the shipped `MemoryUpdateResponse.max_output_tokens_for` budget, **29 of 30**
calls stopped on `max_tokens`, and every one of them was recorded as a successful call that
proposed nothing: **10 of 10 students** ended a three-week consolidation with **0 of 40**
planted facts recovered (the four scenarios that expect a fact to exist), not one fact on any
planted skill, **0 failed calls**, and a process exit code of 0. Raising the
output budget to the gateway's own 4,000-token ceiling on the same corpus produced
**367 facts across 20 students**. (§4)

**Consolidated memory is 15.8× smaller than the raw history it replaces**, median over
1,000 students (p10 12.77, p90 19.29) — 23,802 raw tokens against 1,537 tokens of live
memory at the median. Measured with the same serialisation the gateway sends, not
estimated. (§3, §6)

**40 of 1,000 students' raw three-week histories exceed the gateway's 32,000-token input
ceiling**, where a payload is *refused, never truncated* — for those students the
raw-context alternative is not expensive, it is impossible. (§6)

**Provenance is exact at every scale measured.** 17,429 of 17,429 mock-arm facts and 367 of
367 real-model facts carry only evidence event ids that re-resolve to a real event belonging
to that same student. Zero facts with unresolvable evidence in either arm. (§3, §4)

**The contradiction protocol works and is almost never reached.** Driven directly, it is
200/200 correct across create → contest → supersede (§5). Under a real model it fired
**twice in 20 students**, because the model leaves `polarity` at the schema default on
**98 of 120** `weak_skill` facts — and polarity is the field the whole protocol keys on. (§4.3)

**A regression does not reach the tutor.** In 985 of 985 mock-arm students the new,
correctly-evidenced, `active` negative fact was written — and in **0 of 985** was it the
fact `top_fact_for_skill` served. The read path ranks by confidence, which the older
positive fact accrues on every reconfirmation, and recency is not a term in the ordering. (§3.4)

---

## 2. Method

### 2.1 The corpus

`benchmarks/resume_evidence/04_memory/synthetic_histories.py` generates seeded, reproducible
student histories and a manifest of what each student's memory *should* end up containing.
Planning is pure (no database, no clock), so a re-run with the same seed reproduces the
corpus bit for bit and `plan_corpus(n=25)` is a strict prefix of `plan_corpus(n=1000)` —
which is what lets the real arms run the same students the mock arm ran.

Distribution anchors, all from the only real-data shapes this project has:

| parameter | value | anchor |
|---|---|---|
| events per session | 30–68, uniform | `U7_CHECKPOINT_CONSOLIDATION.md` §2.2, 9 completed staging threads |
| sessions per window | 1–2 | U7's growth model, 4 sessions/student/month over a 7-day window |
| windows | 3 weekly | the minimum that can express the two-stage contradiction protocol |
| heavy-tail events/window | 1,500 (10 students) | above the ~857-event point where the 4-call cap starts dropping |
| extreme-tail events/window | 4,600 (5 students) | ~13,800 over three windows, against AUD-F-34's real **13,865** (D-141 §5) |
| chat-turn share | 20% | D-141 §5: ~12,000 of those 13,865 events were `chat_turn` |

Realised corpus at N = 1,000: **362,025 events, 139,537 chat messages, 1,970 mastery rows**;
median 252 events per standard student over three weeks. Of those, **346,320 fall inside a
consolidation window and are what the measured totals below count** — see §8 for the 4.3%
that do not and exactly which students they belong to.

Each standard student carries one instance of six planted scenarios, each on its **own**
skill — a fact's natural key is `(student, fact_type, skill_id)`, so two scenarios sharing a
skill would interfere and neither would be attributable.

### 2.2 How a student is run

Each student is consolidated **window by window, in order**, through
`consolidate_student_window` — exactly what the deployed weekly job does. Running three
weeks as one call would be a different measurement: `existing_facts` is re-read per call, so
the window boundary is what lets a later week reconfirm (and therefore promote) or contradict
what an earlier week wrote.

### 2.3 Scoring

Two strict judgements per planted expectation, plus two deliberately laxer ones:

- **`status_correct`** — the lifecycle state of the fact for this `(skill, planted fact_type)`.
  `expected_status = None` means "nothing live for this skill at all", which is the correct
  outcome for both mastery-conflict scenarios.
- **`served_correct`** — what `top_fact_for_skill` would hand a tutor payload. This is the
  operational question, and the only sense in which this pipeline has memory *retrieval*:
  there is no candidate set and no ranking, so there is no recall@k to compute.
- **`any_live_fact_on_skill`** — coverage: did the pipeline learn *anything* about the
  planted skill?
- **`polarity_match_any`** — direction: does any live fact on that skill carry the planted
  polarity?

The last two exist because `status_correct` demands the exact planted `fact_type`, which is
right for a deterministic provider and too strict for a real model: a struggling student can
be described as `weak_skill`, `misconception` or `hint_dependence` and all three are
defensible. Scoring a vocabulary difference as a quality failure would be an error by fiat.

Facts on non-planted (filler) skills are counted as **unplanted extras**, not errors — a
fact supported by real events about a real skill is not wrong just because the generator did
not ask for it.

### 2.4 Isolation

Each arm runs against a dedicated Postgres **database** on the local docker-compose instance,
selected by `DATABASE_URL` (which `intellichoice_db.engine.create_engine` already reads, so
no product code and no second configuration path). A separate database rather than a schema,
because the migrations create extensions and assume the default `search_path`. The runner
**refuses to start unless the database name contains `bench`** — it TRUNCATEs six tables, and
a misplaced env var would otherwise be indistinguishable from a correct run until the dev
data was gone. All three benchmark databases were dropped after the run (§8).

### 2.5 Commands

```
export BENCH=postgresql+asyncpg://intellichoice:intellichoice@localhost:5432/intellichoice_e4_bench

# E4.1 - mock arm, N = 1,000 (Tier 1, $0)
DATABASE_URL=$BENCH uv run python \
  benchmarks/resume_evidence/04_memory/memory_benchmark.py --arm mock --students 1000

# the deterministic-transition lane (Tier 1, $0, no provider at all)
DATABASE_URL=$BENCH uv run python .../memory_benchmark.py --arm scripted

# E4.2-A - real Bedrock, SHIPPED output budget, N = 10
eval "$(aws configure export-credentials --profile <profile> --format env)"
MEMORY_BENCH_REAL_BEDROCK=1 AWS_REGION=us-east-1 \
  MEMORY_BENCH_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  MEMORY_BENCH_RUN_BUDGET_CENTS=80 DATABASE_URL=$BENCH_A \
  uv run python .../memory_benchmark.py --arm real --students 10 --run-label shipped

# E4.2-B - the ablation: same students, output budget raised to the gateway's 4,000 ceiling
MEMORY_BENCH_REAL_BEDROCK=1 ... MEMORY_BENCH_RUN_BUDGET_CENTS=170 DATABASE_URL=$BENCH_B \
  uv run python .../memory_benchmark.py --arm real --students 25 --run-label headroom \
  --output-token-floor 4000

# re-score an already-consolidated benchmark database, $0, no model calls
DATABASE_URL=$BENCH_B uv run python .../memory_benchmark.py \
  --arm score-only --students 20 --run-label headroom
```

`--arm real` refuses to start without `MEMORY_BENCH_REAL_BEDROCK=1`, so it can never run in
CI or under `pytest`.

---

## 3. E4.1 — mock arm, N = 1,000 students

**Environment: mock-model simulation, local.** `MockBedrockProvider`, local Postgres,
3,000 consolidation windows, 3,135 model calls, 0 failed. Artifacts: `mock_summary.json`,
`mock_results_n1000.jsonl`, `mock_metrics_summary.csv`,
`mock_ground_truth_manifest.jsonl`, `mock_raw_vs_consolidated.csv`.

### 3.1 Compression, tokens, and calls

| metric | value | n / N |
|---|---|---|
| compression ratio (raw history tokens ÷ live memory tokens) | **p10 12.77 · median 15.82 · p90 19.29** | 1,000 students |
| raw history tokens, all students | 31,379,901 | — |
| live memory tokens after consolidation | 1,496,978 | — |
| median raw tokens per window | 7,665 | 3,000 windows |
| median live memory tokens per student | 1,537 | 1,000 students |
| median live facts per student | 18 | 985 standard students |
| model calls | 3,135 | 0 failed |
| events dropped over the 4-call cap | **63,063 / 346,320 events** | 15 / 1,000 students |

The drops are concentrated exactly where the design says they should be: all 15 students with
dropped events are the heavy-tail and extreme-tail classes. A heavy-tail student (4,500 events)
dropped 2,229; an extreme-tail student (10,700 events, the AUD-F-34 shape) dropped 8,155. Every
one of them made exactly 12 calls — the `_MAX_CALLS_PER_STUDENT = 4` cap, three times. No
standard student dropped a single event, which is the coverage claim `consolidation.py`'s own
comment makes ("a real student's week is single-digit thousands of tokens, so one call still
holds all of it"), now with a number attached.

### 3.2 Lifecycle distribution

| status | facts | share of 17,429 |
|---|---|---|
| `active` | 11,043 | 63.4% |
| `provisional` | 6,386 | 36.6% |
| `contested` | **0** | 0% |
| `superseded` | **0** | 0% |

Zero `contested` and zero `superseded` is not a failure of the run; it is a structural
property of the mock, and finding it is what moved E4 to add the `scripted` arm.
`_memory_consolidation_json` always pairs `weak_skill` with `polarity="negative"` and
`strength` with `polarity="positive"`. The contradiction protocol triggers on an
opposite-polarity candidate **for an existing live fact with the same `(fact_type, skill_id)`**.
So under the mock those two states are unreachable by construction, and any report that
quoted "0 contested" as a quality result would be reporting the fixture. §5 measures the
protocol directly instead.

### 3.3 Deterministic correctness against planted truth

All six scenarios, 985 standard students each:

| scenario | status correct | served correct | any fact on skill | planted polarity |
|---|---|---|---|---|
| `repeated_weak` | 985/985 | 985/985 | 985/985 | 985/985 |
| `repeated_strength` | 985/985 | 985/985 | 985/985 | 985/985 |
| `under_evidenced` | 985/985 | 985/985 | 985/985 | 985/985 |
| `mastery_conflict_weak` | 985/985 | 985/985 | 0/985 (correct — nothing written) | 985/985 |
| `mastery_conflict_strength` | 985/985 | 985/985 | 0/985 (correct — nothing written) | 985/985 |
| `polarity_flip` | 985/985 | **0/985** | 985/985 | 985/985 |

**This measures `consolidation.py`, not model judgment.** The mock's proposals are a
deterministic function of the generator's own keywords, so what these rows establish is that
the promotion bar, the evidence verification, the mastery screen and the read path all behave
exactly as specified across 5,910 independent expectations — not that a model would propose
the right thing.

Two rows are worth reading closely:

- **`under_evidenced` 985/985 on both counts.** Two events in one session stayed
  `provisional`, and `top_fact_for_skill` returned `None` for all 985. The fail-closed
  promise ("`provisional` is never read") holds at n = 985.
- **The AUD-L-13 mastery screen fired 3,940 times** and refused every one. In 985/985
  students a `weak_skill` claim about a skill measured at 0.92 was refused, and in 985/985 a
  `strength` claim about a skill measured at 0.25 — the `aud-student-regressing` reproduction
  — was refused. The screen costs one dictionary lookup and is independent of model quality,
  which is exactly why it holds at this rate.

### 3.4 The finding: a regression is written but never served

`polarity_flip` plants two weeks of success on a skill followed by four failure events across
two sessions in week three. The result, in **985 of 985 students**:

```
strength    polarity=positive  status=active  confidence=0.70   <- served to the tutor
weak_skill  polarity=negative  status=active  confidence=0.60   <- the regression, ignored
```

`status_correct` is 985/985: the new negative fact *is* created, *is* correctly evidenced, and
*is* promoted to `active`. `served_correct` is 0/985: `top_fact_for_skill` orders by
`confidence DESC` and returns the stale positive fact every time.

Two mechanisms compound, and the scenario was designed to separate them from the
under-evidencing confound (the regression clears both evidence thresholds on purpose):

1. **The contradiction protocol is keyed on `(fact_type, skill_id)`.** A negative signal
   expressed as a *different* fact type (`weak_skill` against an existing `strength`) never
   reaches the demotion branch, so the two facts coexist instead of one demoting the other.
2. **`top_fact_for_skill` ranks by confidence, and confidence is monotone in reconfirmation.**
   `reconfirm_fact` raises confidence on every agreeing window, so an older fact outranks a
   newer contradicting one by construction. Recency is not a term in the ordering at all.

Reported, not fixed — this is measurement work and the fix is a product decision (which
signal should win, and on what evidence). See §7.

### 3.5 Provenance and payload bounds

| metric | value |
|---|---|
| facts whose every cited event id re-resolves to a real event of that student | **17,429 / 17,429** |
| facts with no resolving evidence | **0 / 17,429** |
| unplanted extra live facts (on filler skills) | 12,504 |
| windows whose existing-fact payload exceeded `MAX_SAFE_EXISTING_FACTS` (21) | **0 / 3,000** |
| highest existing-fact count seen at a window start | **19** |

Provenance is re-derived independently: every id is looked up again after the run and checked
to belong to that student, rather than trusting that `_verify_evidence` did its job at write
time. That is what turns "guaranteed by construction" into a number.

The payload-oversize row is a near miss worth stating plainly. U7 §2.2 records **20 facts** for
the one real student it measured; this corpus lands at a median of 18 and a maximum of 19 live
facts at a window start, against a threshold of 21 past which the derived output budget exceeds
the gateway's hard ceiling and the response can truncate. **The real-data anchor sits one to
three facts below the point where this saturates** — so the condition did not fire here, and
the headroom is roughly one more skill's worth of facts wide.

---

## 4. E4.2 — real-model arms (Haiku 4.5)

Model id `us.anthropic.claude-haiku-4-5-20251001-v1:0` in `us-east-1`, invocability
re-verified with a probe call before either run spent anything (D-273: AVAILABLE is not
invocable; the recorded 2026-08-11 stratum expired by its own rule). Both probes returned OK.

### 4.1 Arm A — the shipped output budget

**Environment: real-model evaluation (Haiku 4.5), local data.** N = 10 students × 3 windows =
30 calls. Artifacts: `real_shipped_summary.json`, `real_shipped_run.log`.

| metric | value |
|---|---|
| calls | 30, **0 failed** |
| calls that stopped on `max_tokens` | **29 / 30** |
| students with at least one truncated call | **10 / 10** |
| facts written, all 10 students, 3 weeks each | **6** |
| planted facts recovered (the 4 scenarios that expect a fact) | **0 / 40** |
| facts landing on any planted skill | **0 / 60 expectations** |
| AUD-L-13 mastery screen firings | **0** |
| cost, gateway-reported | 19.97¢ (2.00¢/student) |
| cost, conservative (cache-inclusive, §4.4) | 56.41¢ (5.64¢/student) |

**What happens, mechanically.** `max_output_tokens_for(0)` is 1,280. A window of ~100 events
spanning ~14 skills gives the model ~14 legitimate new-fact candidates, which needs about
1,600 output tokens. The call stops on `max_tokens`; Bedrock returns the partial `toolUse`
input as `{}`; `MemoryUpdateResponse` validates `{}` **cleanly**, because all three of its
fields default to `[]`. So `_validate_or_repair`'s `if truncated:` guard is never reached —
`_try_validate` succeeds first — and the caller sees `added=0, calls_failed=0`.

Reproduced outside the pipeline, same payload, same model, only `maxTokens` differing:

| `maxTokens` | `stopReason` | tool input | facts |
|---|---|---|---|
| 1,280 | `max_tokens` | `{}` | 0 |
| 4,000 | `tool_use` | `{"facts_to_add": [...]}` | 14 |

**A truncated consolidation is indistinguishable from a student with nothing to consolidate.**
`added=0`, zero failed calls, exit code 0 — which is AUD-F-34's exact failure *shape* (a
silent zero that exits successfully) one layer above where AUD-F-34 was fixed. It is invisible
under the mock, whose whole response is a handful of facts and never approaches the cap: the
mock arm's own `hit_output_ceiling` count is **0 / 3,135**.

The six facts that did survive were all on non-planted filler skills; **no planted skill
received any fact**, so the mastery screen never had a candidate to refuse and the two
mastery-conflict scenarios scoring 10/10 here are **vacuous passes** — an expectation of "no
fact" is trivially satisfied when the model produced no facts. They are excluded from any
quality claim.

### 4.2 Arm B — the output-budget ablation

**Environment: real-model evaluation (Haiku 4.5), local data — ABLATION, NOT the shipped
configuration.** The harness raises each call's `max_output_tokens` to at least 4,000 (the
gateway's own hard ceiling) and changes nothing else; product code is untouched. It exists
because "planted-fact recall = 0" in arm A is unattributable between the model and the budget,
and an unattributable number is not a measurement.

Requested N = 25. The run **aborted at student 21 of 25** when its conservative spend crossed
the 169.8¢ ceiling (172.42¢) — the abort-not-truncate guard doing its job, recorded in
`real_headroom_run.log`. The **20 students that completed before the abort** were re-scored
from the persisted database at **$0** (`--arm score-only`), which reproduces every quality
metric exactly; validated against arm A, where live and re-scored scenario scores, provenance,
lifecycle and extras all matched. Artifacts: `real_headroom_rescored_summary.json`,
`real_headroom_rescored_results_n20.jsonl`.

| scenario (n = 20 students each) | status correct | served correct | any fact on skill | planted polarity |
|---|---|---|---|---|
| `repeated_weak` (4 planted events) | 0/20 | 0/20 | **4/20** | 1/20 |
| `repeated_strength` (4 planted events) | 2/20 | 2/20 | **8/20** | 8/20 |
| `polarity_flip` (8 planted events) | 8/20 | 1/20 | **15/20** | 1/20 |
| `under_evidenced` (2 planted events) | 0/20 | 20/20 | 0/20 | 0/20 |
| `mastery_conflict_weak` | 20/20 | 20/20 | 0/20 | 20/20 |
| `mastery_conflict_strength` | 20/20 | 20/20 | 0/20 | 20/20 |

| metric | value |
|---|---|
| facts written | **367** across 20 students |
| facts whose evidence all re-resolves to that student | **367 / 367** |
| facts with no resolving evidence | **0 / 367** |
| unplanted extras (facts on filler skills) | 339 / 367 |
| lifecycle | 210 `active`, 155 `provisional`, **2 `contested`**, 0 `superseded` |
| AUD-L-13 mastery screen firings (from the run log) | **12** |
| compression ratio | p10 6.61 · median 9.84 · p90 13.23 (n = 20) |

**Planted-signal recall rises with signal density, and is low.** Coverage of a planted skill
is 4/20 and 8/20 for the two four-event scenarios and 15/20 for the eight-event one — against
~100 filler events per window spanning eight other skills. The model writes about the skills with the most
events; a four-event signal inside a ~250-event history is frequently not among them. This is
scenario-recall on a synthetic corpus with a deliberately noisy filler layer, **not** a claim
about real student data.

**The mastery screen is genuinely exercised here.** Unlike arm A, real candidates were
proposed and 12 of them were refused for contradicting a measured mastery score — the AUD-L-13
floor doing the job it was added for, against a real model rather than a fixture.

**Provenance survives contact with a real model.** 367/367 facts cite only event ids that
re-resolve to that student's own events in that window. The "model proposes, code verifies"
split (D-038's pattern, applied to memory) holds without a single exception at this n.

### 4.3 The polarity finding

The real model's fact types and polarities, over all 367 facts:

| fact type + polarity | active | provisional |
|---|---|---|
| `weak_skill`, **positive** | 64 | 34 |
| `weak_skill`, negative | 14 | 8 |
| `strength`, positive | 30 | 36 |
| `improvement`, positive | 36 | 22 |
| `effective_intervention`, positive | 17 | 28 |
| `hint_dependence`, positive | 15 | 14 |
| `misconception`, positive | 12 | — |

**98 of 120 `weak_skill` facts carry `polarity="positive"`.** `MemoryFactCandidate.polarity`
defaults to `"positive"`, and neither the system prompt nor the schema description tells the
model what the field means or that it must be set — so the model leaves it at the default
about 82% of the time even while writing a fact whose text describes a weakness.

That matters because **polarity is the single field the entire contradiction protocol keys
on**. A `weak_skill` fact stored with `polarity="positive"` can never be recognised as
contradicting anything, which is why `contested` appeared **twice in 20 students** under a
real model where the scripted lane reaches it 40/40 times. The mock cannot expose this,
because the mock sets polarity explicitly on every candidate.

Reported, not fixed (§7).

### 4.4 Cost, and an accounting gap

| | arm A (shipped) | arm B (ablation) |
|---|---|---|
| calls | 30 | 62 (to the abort) |
| gateway-reported cost | 19.97¢ | 86.23¢ |
| gateway-reported per call | 0.666¢ | 1.391¢ |
| **conservative cost** | **56.41¢** | **172.42¢** |
| conservative per call | 1.880¢ | 2.781¢ |
| conservative per student (3 windows) | 5.64¢ | 8.34¢ |
| cache-write tokens | 291,530 | — |

The gateway's own `_cost_cents` prices `input_tokens` only. With `cachePoint` blocks in play
(D-203), a cold call reports almost all of its input under `cacheWriteInputTokens` and only a
couple of dozen tokens under `inputTokens` — measured directly: `inputTokens=24`,
`cacheWriteInputTokens=6785` for one 12,113-character payload. `BedrockGenerationResult`
carries both fields and its own comment says they are "not yet billed off separately".

For a consolidation workload this is not a rounding error, and it points at a second finding:
**every consolidation payload is unique (one per student-window), so the prompt cache is
written on every call and read on none.** Bedrock bills a cache write at ~1.25× the base input
rate, so consolidation is paying a ~25% input surcharge for a cache that structurally cannot
hit. The `cachePoint` blocks are added for every `anthropic.` model regardless of whether the
caller's payloads repeat, which is the right default for the candidate-batch callers D-203 was
measured on and the wrong one here.

This benchmark therefore enforces its **run ceiling against whichever accounting is larger**,
using the published multipliers (write 1.25×, read 0.1×). Enforcing only the gateway's figure
would have let a run spend well past its ceiling while every printed number said it was inside
it — arm B would have reported 86¢ against a 170¢ ceiling while actually costing 172¢.

The gateway-reported 2.00¢/student in arm A is consistent with D-141 §8's recorded ~2–3¢ per
student; the conservative reading puts the same run at 5.64¢/student.

### 4.5 Total spend against the authorization

| | gateway-reported | conservative |
|---|---|---|
| arm A (exact) | 19.97¢ | 56.41¢ |
| arm B (exact, at abort) | 86.23¢ | 172.42¢ |
| pre-flight probes, smoke runs and diagnostics (estimated per-call) | ≈12.3¢ | ≈36.6¢ |
| **total** | **≈118.5¢** | **≈265.4¢** |

Against the **300-cent hard cap**, on the conservative accounting, with the cap enforced in
code (`RUN_BUDGET_CENTS_HARD = 300.0`; `MEMORY_BENCH_RUN_BUDGET_CENTS` can only *tighten* it —
a value above the default is ignored, because a run must never be able to raise its own spend
limit from the environment). The two arms' figures are exact and come from the runs' own
output; the diagnostics line is estimated from the measured per-call rates, since those calls
were made through ad-hoc probes rather than the metered runner.

---

## 5. The scripted lane — the transition protocol as code

**Environment: deterministic code measurement, local (no provider at all).** A fake gateway
returns pre-built `MemoryUpdateResponse` values, so the machinery can be driven into states no
provider reaches on its own and the screens can be given inputs a well-behaved model would
never produce. **This measures `consolidation.py`; it says nothing about any model.**
Artifact: `scripted_lane_results.json`.

| check | result |
|---|---|
| fact `active` after the first window (3 events, 2 sessions) | **40/40** |
| demoted to `contested` on the first opposite-polarity candidate | **40/40** |
| `superseded` on the second consecutive contradiction | **40/40** |
| replacement fact is live and carries the new polarity | **40/40** |
| `superseded_by_id` points at the replacement | **40/40** |
| out-of-enum `fact_type` dropped | **40/40** |
| PII-pattern `fact_text` dropped | **40/40** |
| citation that resolves to nothing dropped | **40/40** |
| citation that resolves to **another student's** real event dropped | **40/40** |
| well-formed control candidate accepted | **40/40** |

**400 / 400 checks, 0 failures.** The control row matters: without it, a lane whose screens
dropped everything indiscriminately would score identically to one whose screens work.

The PII probes are pattern-matching strings that are nobody's data — `.invalid` is reserved by
RFC 2606 and 555-000-0000 is not an assignable number. A test asserting that the screen fires
is only a test while the probe would actually trip it, which
`packages/memory/tests/test_synthetic_histories.py` asserts separately.

So plan §9's contradiction protocol is correct **when it is reached**. §3.2 and §4.3 are about
how rarely it is reached: never under the mock, twice in 20 students under a real model.

---

## 6. E4.3 — raw history vs consolidated memory

Arm B of this comparison is "send the student's raw event history as context instead of their
consolidated memory". It is **priced, never called** — the token counts are measured from the
same corpora with the same serialisation the gateway bills, so no model spend is needed to
evaluate it. Source: `mock_raw_vs_consolidated.csv` (per student), N = 1,000.

| | raw history | consolidated memory | one served fact |
|---|---|---|---|
| median tokens per student (3 weeks) | **23,802** | **1,537** | ~83 |
| median input cost per request, Haiku 4.5 rate | **2.380¢** | **0.154¢** | ~0.008¢ |
| compression vs raw | 1× | **15.8×** | **287×** |

Per-request input cost is what a tutor turn or a parent report pays *every time* it wants the
student's history in context. At the median that is 2.38¢ against 0.15¢ — a **2.23¢ saving per
request**, and consolidation costs a one-off ~5.6¢ per student per week (§4.4, conservative)
to produce. On these numbers the consolidation pays for itself at roughly **2–3 memory-bearing
requests per student per week**.

**The structural half is the more important one.** The gateway refuses any payload estimated
above `_HARD_MAX_INPUT_TOKENS = 32,000` — *refused, never truncated or chunked*, because
truncating asks the model a different question and gets a fluent answer to it. So:

| | count |
|---|---|
| students whose three-week raw history exceeds the 32,000-token ceiling | **40 / 1,000** |
| individual windows over the ceiling | **45 / 3,000** |
| heavy-tail student raw history (4,500 events) | 366,868 tokens — **11.5× the ceiling** |
| extreme-tail student raw history (10,700 events) | 870,003 tokens — **27× the ceiling** |

For those 40 students the raw-context alternative is not more expensive, it is **impossible**:
no cap can rescue it and the call cannot be made at all. This is the same wall AUD-F-34 hit
live at 215,355 tokens (D-141 §5), reproduced here at N = 1,000 with the distribution attached
— and it is the argument the architecture exists to make. The consolidated memory for those
same students is a few thousand tokens and always sendable.

Three weeks is also the shortest horizon that shows this. The ratio grows with history length
while consolidated memory stays roughly flat, so 40/1,000 at three weeks is a floor for what a
full term would produce.

---

## 7. Findings recorded, not fixed

This is measurement work; none of the below was changed. Each is reproducible from the
artifacts in this directory.

1. **`MEMORY-OUTPUT-TRUNCATION` (highest severity).** Under the shipped output budget the real
   model's consolidation response truncates on 29/30 calls and the truncated response
   validates as an empty update, so the run reports `added=0`, `0 failed calls`, exit 0.
   `max_output_tokens_for` derives the budget from the *existing* fact count on the stated
   reasoning that new facts do not scale with the input; a student with events across fourteen
   skills is a counter-example. Two independent gaps compound: the budget is too small, and
   `MemoryUpdateResponse`'s all-defaulted fields make a truncated response indistinguishable
   from a legitimate empty one, which is what keeps the gateway's existing `if truncated:`
   guard from ever running. Evidence: §4.1, `real_shipped_run.log`.
2. **`MEMORY-POLARITY-DEFAULT`.** The real model leaves `polarity` at its schema default on 98
   of 120 `weak_skill` facts, so the contradiction protocol — which keys on polarity — almost
   never fires. Neither the system prompt nor the schema tells the model what the field is for.
   Evidence: §4.3.
3. **`MEMORY-STALE-FACT-SERVED`.** After a sustained regression, the correctly-evidenced
   negative fact is written and promoted, and `top_fact_for_skill` still serves the older
   positive one in 985/985 students, because ranking is by confidence and confidence grows with
   each reconfirmation. Recency is not a term in the ordering. Evidence: §3.4.
4. **`MEMORY-CACHE-WRITE-UNBILLED`.** The gateway's `cost_cents` omits cache-write tokens,
   under-reporting real spend on this workload by ~2.8×; and because every consolidation
   payload is unique, the prompt cache is written on every call and read on none, so
   consolidation pays a ~25% input surcharge for a cache that structurally cannot hit.
   Evidence: §4.4.
5. **Payload-oversize headroom is one to three facts wide.** The real-data anchor is 20 live
   facts per student (U7 §2.2); this corpus peaks at 19; `MAX_SAFE_EXISTING_FACTS` is 21.
   Evidence: §3.5.

---

## 8. Limitations

- **The mock arm measures deterministic code, not model judgment.** Its lifecycle-correctness
  and screen numbers are properties of `consolidation.py`. No quality claim is made from it,
  and its `cost_cents` is priced off `MockBedrockProvider`'s invented token counts — the CSV
  labels every mock cost row "not a real cost".
- **Planted-truth recall is scenario recall on a synthetic corpus**, not a statement about
  real student data. The filler layer's density is a design choice that directly sets the
  difficulty, and §4.2's coverage numbers should be read as "recall of a k-event signal inside
  a ~250-event synthetic history", nothing wider.
- **Arm B is an ablation, not the shipped system.** Its recall and lifecycle numbers describe
  what the model does when the output budget is not binding. They must never be quoted as the
  shipped system's behaviour; §4.1 is that.
- **Arm B reached 20 of 25 students** before its spend ceiling stopped it, and is scored at
  n = 20. Its per-call cost and truncation counts come from the live run's log; its quality
  metrics were re-scored from the persisted database.
- **Arm A's per-student JSONL was lost** when its benchmark database was truncated during
  artifact regeneration (operator error, this session). `real_shipped_summary.json` is the
  run's own unedited stdout, preserved in full in `real_shipped_run.log`, and every arm-A
  number in this report comes from it.
- **Single run per arm; no repeat trials.** The mock and scripted arms are deterministic and
  reproduce bit for bit from their seed; the real arms are not, and no variance estimate
  exists for them.
- **Local Postgres, one process.** Wall-clock and throughput figures are not staging numbers
  and none are quoted here.
- **`n = 1` distributions are reported as `None`, never as a spread.** `percentiles()` returns
  a median and no deciles for a single sample, so a one-student arm cannot read like a
  measured distribution.
- **4.3% of generated events fall outside the window they were planned for, all of them in
  one student class.** Each event's timestamp is a cumulative random walk from its window's
  start, and for the five extreme-tail students (4,600 events per window) that walk overruns
  the 7-day window. Measured exactly: **38,766 of 362,025 planned offsets** exceed the window
  length, **every one of them belongs to an extreme-tail student**, the largest offset among
  all 985 standard students is 779 minutes against a 10,080-minute window, and **zero planted
  events are affected** — so no scored expectation and no standard student's numbers move.
  The consequence is that an overflowing window-0 event is consolidated in window 1 instead,
  and a window-2 overflow is never consolidated at all, which is the whole 362,025 → 346,320
  gap. The direction is safe for every claim made here: the extreme-tail students' raw
  histories and drop counts are **understated**, so §6's 40/1,000 over-ceiling count is a
  floor rather than an estimate. Left uncorrected deliberately — the two real arms were run
  against this exact generator, and changing it now would make the mock arm's corpus differ
  from theirs, which is a worse defect than a disclosed and bounded one.
- **Artifact size.** `mock_results_n1000.jsonl` is ~7.9 MB, an order of magnitude larger than
  the other themes' evidence. Redundant fields (per-fact evidence id lists, per-student
  scenario rationales) have already been removed. Every number in this report is reproducible
  from `mock_summary.json` and `mock_metrics_summary.csv` alone; the per-student JSONL is
  regenerable for $0 by re-running the mock arm, if its size is unwanted in git.

---

## 9. Artifacts in this directory

| file | what it holds |
|---|---|
| `mock_summary.json` | E4.1 aggregate — every headline mock number |
| `mock_results_n1000.jsonl` | per-student rows: windows, facts, scored expectations |
| `mock_metrics_summary.csv` | every metric as `(numerator, denominator, value, unit, note)` |
| `mock_ground_truth_manifest.jsonl` | the planted truth, with the corpus config in its header |
| `mock_raw_vs_consolidated.csv` / `.json` | E4.3 per student and in aggregate |
| `real_shipped_summary.json` | E4.2-A aggregate (recovered from the run's stdout — §8) |
| `real_shipped_run.log` | E4.2-A raw stdout: projection, probe, per-student spend, summary |
| `real_headroom_rescored_summary.json` | E4.2-B aggregate, n = 20 |
| `real_headroom_rescored_results_n20.jsonl` | E4.2-B per-student rows |
| `real_headroom_rescored_metrics_summary.csv` | E4.2-B metrics with numerators and denominators |
| `real_headroom_rescored_ground_truth_manifest.jsonl` | E4.2-B planted truth |
| `real_headroom_rescored_raw_vs_consolidated.json` | E4.3 over the real-model corpus |
| `real_headroom_run.log` | E4.2-B raw stdout, including the spend-ceiling abort |
| `scripted_lane_results.json` | the 400 deterministic transition and screen checks |

Harness: `benchmarks/resume_evidence/04_memory/synthetic_histories.py` (generator) and
`memory_benchmark.py` (arms, scoring, artifacts). Permanent tests:
`packages/memory/tests/test_synthetic_histories.py` (28 tests — generator determinism and
prefix stability, scenario/threshold invariants, scorer logic, the spend-ceiling clamp, and
the benchmark-database guard).
