# R1 — MEMORY-OUTPUT-TRUNCATION: fix and post-fix re-validation

**Remediation task R1** of the post-measurement program (user-commissioned 2026-08-29), against
the defect E4 found and D-460 accepted. Reproduce → smallest fail-closed fix → permanent
regression tests → minimum paid re-measurement.

**Nothing in this directory replaces an E4 artifact.** Every historical E4 file under
`docs/resume_evidence/04_memory/` is byte-for-byte unchanged; this run wrote only here, under the
`postfix` run label.

---

## 1. The defect, and why the existing guard never fired

E4 arm A measured the shipped consolidation path and found a **silent success**: 29 of 30 real
calls stopped on `max_tokens`, 10 of 10 students had at least one, and the run reported
`added=0, calls_failed=0, exit 0` — indistinguishable from ten students with nothing to
consolidate.

The gateway already had a truncation guard (`OutputTruncatedError`, D-115), and it was not
broken. It was **unreachable on this path**, for one reason:

```
_validate_or_repair:
    value = _try_validate(raw_text)      # ran FIRST
    if value is not None: return value   # ← returned here
    if truncated: raise OutputTruncatedError(...)   # ← never reached
```

The guard only ran when validation *failed*. That is correct for a fragment cut mid-string —
which is what the existing test `test_a_truncated_response_is_not_repaired_under_the_same_ceiling`
scripts. But Converse does not return a string fragment. On `max_tokens` it returns the **partial
`toolUse` input**, and a model cut off before emitting its first key returns `{}`. `{}` is valid
JSON, and it is valid against `MemoryUpdateResponse`, whose three list fields all default to `[]`.
So the partial validated cleanly and was returned as a legitimate empty update.

`MemoryUpdateResponse` is the **only** response model in the codebase whose `{}` validates
(verified by enumerating every `*Response` model in `intellichoice_shared.bedrock`), which is why
this defect surfaced on exactly one task and why the mock never saw it (0 / 3,135 mock calls).

Two compounding gaps, and both are fixed:

| gap | before | after |
|---|---|---|
| the gateway judged truncation by *validation outcome* | truncated `{}` returned as success | truncation judged by the **stop reason**, checked before validation |
| the output budget's premise was refuted | base 1,280 — held ~8 new facts; a real window offers ~14 | base **2,560**, priced from E4's own measurement |

---

## 2. The fix

**Gateway** (`packages/adapters/.../bedrock/gateway.py`) — the `if truncated:` check moves
**above** `_try_validate`. A response that stopped on the output ceiling is a failure of that
call, whatever shape the fragment happens to have. Deliberately preserved:

- **no repair retry** under the same ceiling (D-115 — same prompt, same ceiling, same truncation);
- **no `_record_failure()`** — the call reached Bedrock and came back, so truncation stays a
  schema-class failure and cannot open the circuit on every other task (D-115's blast-radius
  half). Asserted by a new regression test, not merely intended.
- `OutputTruncatedError` remains a `StructuredOutputError` ⊂ `BedrockGatewayError`, so it lands
  in the branch AUD-F-34 already built in `consolidation.py`, counts as `calls_failed`, and
  reaches `consolidate_cli.py`'s all-failed → exit 1 contract. **No runner change was needed** —
  the reporting was already correct and was being starved of failures to report.

**Output budget** (`packages/shared/.../bedrock.py`, `MemoryUpdateResponse.max_output_tokens_for`)
— base `1280 → 2560` (~17 new facts × ~149 tokens; clears E4's measured 14-candidate window at
~2,086 with ~23% headroom). The `128 × existing_facts` term is unchanged; it was never the
problem. Every fact count gets strictly more budget than before, so the D-115 §10 floor argument
still holds. Not raised to the gateway's flat 4,000 ceiling, because D-233 measured what happens
when an unbounded response component is given more room — it expands to fill it and buys nothing,
and here the unbounded component is the *candidate count*, where more room trades precision for
noise (D-221).

`MAX_SAFE_EXISTING_FACTS` drops `21 → 11`. The old 21 was arithmetic over the refuted base: it
promised safety at 21 live facts while E4 truncated at **zero**. 11 is honest, and
`consolidation.py`'s oversize warning now fires when truncation risk is real.

---

## 3. Reproduction, shown failing before the fix

Four new tests. On unfixed product code (fix stashed, tests present):

```
FAILED packages/memory/tests/test_consolidation.py::test_the_output_budget_admits_the_e4_worst_case_new_fact_slate
FAILED packages/memory/tests/test_consolidation.py::test_a_truncated_call_through_the_real_gateway_is_never_a_silent_zero
FAILED packages/adapters/tests/test_bedrock_gateway.py::test_a_truncation_that_happens_to_validate_still_fails_closed
FAILED packages/adapters/tests/test_bedrock_gateway.py::test_a_truncated_empty_response_does_not_trip_the_circuit_breaker
4 failed, 5 passed
```

The end-to-end one reproduces the defect through the **real** gateway (only the provider is
doubled), and its failure is the defect stated as an assertion:

```
>           assert result.calls_failed == 1  # was 0 - the whole defect
E           assert 0 == 1
```

Two further tests guard the edges: `{}` from a call that **finished** is still a valid empty
update (empty ≠ broken), and truncation still must not trip the circuit breaker.

---

## 4. Post-fix re-validation — the paid run

**Environment: real-model evaluation (Haiku 4.5), local data.** Shipped (post-fix) budget, no
ablation floor. Same harness, same corpus, same seed, **same ten students** as E4 arm A.

| | |
|---|---|
| model | `us.anthropic.claude-haiku-4-5-20251001-v1:0`, `us-east-1` |
| build | `783aa0a` + this change, as-of 2026-08-29 |
| invocability probe | **OK** before any spend (D-273), 0.1780¢ |
| N | 10 students × 3 windows = 30 calls, 2,264 events |
| run ceiling | **150¢ hard**, abort-not-truncate; **not** reached |
| spend | **36.30¢ gateway-reported** (3.63¢/student); 43.32¢ conservative, cache-inclusive |
| aborted | false |

Artifacts: `real_postfix_summary.json`, `real_results_n10_postfix.jsonl`,
`real_postfix_ground_truth_manifest.jsonl`, `real_postfix_metrics_summary.csv`,
`real_postfix_raw_vs_consolidated.{json,csv}`.

### Before → after

| metric | E4 arm A (before) | R1 post-fix (after) |
|---|---|---|
| calls | 30 | 30 |
| **calls reported failed** | **0** | **11** |
| calls that silently truncated | **29** | **0** |
| students with a silent truncation | **10 / 10** | **0 / 10** |
| **facts written** | **6** | **119** |
| facts with evidence ids | — | **119 / 119** |
| facts whose evidence all resolves to that student | — | **119 / 119** |
| facts with no resolving evidence | — | **0** |
| lifecycle | 6 active | 50 active, 68 provisional, 1 superseded |
| median compression ratio | 24.4 (n=1) | **11.5** (n=8, p10 7.1 / p90 16.7) |
| spend (gateway) | 19.97¢ | 36.30¢ |

**The headline is the pair, not either number alone.** Facts went 6 → 119 with **100% provenance**
on both measures, and every call that still could not finish is now a *counted, reported failure*
instead of a zero that exits 0. The primary acceptance criterion — "facts are actually produced
with verified provenance, and any truncation that still occurs is reported as a failed call,
never a silent zero" — is met on both halves.

### The distinction the fix creates, visible in the data

Exactly **one** window (`...nt-00007`, window 1) has `calls_failed=0, added=0`: a genuine empty
update. Before the fix, that window and the eleven truncated ones were the same observation. They
are now different rows.

### Reading `hit_output_ceiling: 0` correctly

The summary reports `calls.hit_output_ceiling = 0`, and that is **not** a claim that truncation
stopped. The harness derives that counter from `stop_reason` on a *returned result*; post-fix a
truncated call raises instead of returning, so the counter is structurally 0 and truncation lands
in `calls.failed`. Both fields are kept, and the harness comment now says so. **11 of 30 calls
still truncated** — they are simply no longer silent.

---

## 5. What this run does *not* claim

- **Planted-fact recall is still poor, and R1 did not target it.** 111 of 119 facts are on
  non-planted filler skills; `repeated_weak` recovers 0/10 and `polarity_flip` 0/10 on served
  polarity. This is E4 arm B's pre-existing quality finding (the model, not the budget), unchanged
  and out of R1's scope. The two `mastery_conflict_*` scenarios again score 10/10 by refusing to
  write, and are again **vacuous passes** for the same reason E4 gave.
- **11 of 30 calls still truncate at 2,560.** The base raise is necessary but not sufficient for
  this corpus's densest windows, and truncation does not track input size (failures at 4,737
  input tokens, successes at 11,741) — it tracks how many candidates the model chooses to emit.
  The remaining fix is bounding the *response*, which is a behaviour decision (which candidates
  get dropped?) and is deliberately not made here.
- **Synthetic corpus.** These are generated histories, not production students, and D-152 keeps
  production out of scope.
- 4 of 30 windows carried an oversized existing-fact payload (>11 live facts) and were capped at
  the gateway's 4,000 ceiling — logged, as designed.

## 6. Follow-on candidates (not started)

1. **Bound the consolidation response** so a dense window cannot truncate at all (needs a
   decision on which candidates to drop).
2. **Recovery rather than refusal** — retry a truncated consolidation once at a raised ceiling.
   `OutputTruncatedError` was split out (D-207) for exactly this caller, and nothing uses it yet.
3. The `provisional`-heavy lifecycle (68 of 119) is worth its own look now that there are enough
   facts to have a distribution at all.
