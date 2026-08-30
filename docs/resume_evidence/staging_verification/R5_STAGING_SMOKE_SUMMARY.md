# R5 — post-deploy targeted smoke verification of D-467..D-470 on staging

**Build under test:** `523b9f0` / image tag `gha-523b9f036a53`
**Executed:** 2026-08-30, 06:37Z – 07:1xZ (all timestamps UTC)
**Scope:** targeted smoke only. No benchmark program was rerun, no bank was mutated, no product
code or Terraform was changed, no historical artifact was touched.
**Bedrock spend, whole task: 15.25 cents** of a ~120-cent ceiling (13.40 the consolidation probe,
1.85 the one chat smoke turn; sections B/C/D were $0).

Raw evidence for every line below is in this directory; the file is named in each row.

---

## 1. Check register

| # | Check | n/N | Verdict | Evidence |
|---|---|---|---|---|
| A1 | On-demand staging memory-consolidation run completed on the deployed image | 1/1 | **PASS** | `A_results.json`, `A_task_final.json` |
| A2 | **Silent truncations = 0**, proven by cross-check | 0 silent / 8 calls | **PASS** | `A_crosscheck.txt` |
| A3 | Truncation failures surfaced (fail-closed) | 8/8 | **PASS** | `A_job_log_raw.json` |
| A4 | Provenance: no fact written without re-verified evidence ids | 0 facts written (vacuous) + structural | **PASS** | `A_results.json` |
| A5 | Probe spend inside the guard | 13.40¢ / 60¢ guard | **PASS** | `A_results.json` |
| A6 | Ceiling still saturates on the real cohort | 8/8 truncated | **DEFECT REPORTED** | `A_results.json` |
| B1 | Safe trigger for a real unhandled 500 | 0 found / 16 probes | **NO SAFE TRIGGER — fallback taken** | `B1_probe_log.txt` |
| B1a | Fallback (a): deployed-image consistency | OK | **PASS** | `C_image_check.txt` |
| B1b | Fallback (b): permanent unhandled-exception tests | 5/5 | **PASS** | `B1_permanent_tests.txt` |
| B1c | Bonus: deployed filter correctly *excludes* the new JSON `unhandled_exception` line | 1 datapoint, not 2 | **PASS** | `B2_timeline.txt` |
| B2 | `Traceback` metric filter counts a synthetic traceback | 1.0 at 06:51Z | **PASS** | `B2_timeline.txt` |
| B3 | Alarm detects it **without paging** | OK→ALARM 06:52:07Z, actions disabled | **PASS** | `B2_timeline.txt` |
| B4 | Alarm self-resolved and actions fully restored | see §5 | **PASS** | `B4_cleanup.txt` |
| B5 | ADOT exporter sent/failed spans+metric-points fresh post-deploy | 19 datapoints × 8 series | **PASS** | `B3_adot_export_metrics.json` |
| B6 | ADOT export-failure alarms exist and are enabled; failures = 0 | 4/4 alarms, 0 failures | **PASS** | `B_alarms_before.json` |
| B7 | **No alarm in the account has actions disabled** (final read-back) | 0/40 | **PASS** | `B4_cleanup.txt` |
| B8 | Nothing left behind (synthetic stream, alarm state, test data) | see §5 | **PASS** | `B4_cleanup.txt` |
| C1 | Deployed image is 523b9f0's build | OK | **PASS** | `C_image_check.txt` |
| C2 | `test_hint_ladder_coherence.py` | 10/10 | **PASS** | `C_pytest_lane.txt` |
| C3 | `test_arithmetic_dedup.py` | 16/16 | **PASS** | `C_pytest_lane.txt` |
| C4 | E5.2-corpus lane (`test_e5_2_defect_corpus.py` + `test_authored_pipeline.py`) | 27/27 + 93/93 | **PASS** | `C_pytest_lane.txt` |
| C5 | Frozen D-469 numbers restated, not re-measured | — | **RESTATED** | `C_frozen_numbers.json` |
| D1 | Frozen 651-case + 46-span PII corpus re-run locally | recall 267/277, F1 96.7%, URL 74/74 | **PASS** | `D_pii_harness_stdout.txt` |
| D2 | Byte-identical to the frozen R4 post-fix metrics CSV | zero delta | **PASS** | `D_frozen_numbers.json` |
| D3 | New non-adversarial false positives | 0 | **PASS** | `D_frozen_numbers.json` |
| D4 | PII permanent pytest lane | 54/54 | **PASS** | `D_pytest_lane.txt` |
| E1 | Both services on the new revisions, at floor, rollout COMPLETED | learning :154→:155 (2/2), chat :152→:153 (1/1) | **PASS** | `E_results.json` |
| E2 | Guest chat session through CloudFront | 200, 14.6 s, 1 citation | **PASS** | `E_results.json` |
| E3 | Authenticated learning flow through CloudFront | 3 reads, all 200 | **PASS** | `E_results.json` |
| E4 | ALB 5xx post-deploy vs prior-day baseline | 0 vs 0 | **PASS** | `E_health.json` |
| E5 | 4xx post-deploy | 6, all this task's own probes | **EXPLAINED** | `E_health.json` |
| E6 | Alarms in ALARM state | 2, both autoscaling scale-in | **KNOWN/EXPECTED** | `E_results.json` |
| E7 | RDS `DatabaseConnections` in band | avg 16.3 / max 20 vs 24 h max 62 | **PASS** | `E_health.json` |
| E8 | Total Bedrock spend | 15.25¢ / ~120¢ | **PASS** | `E_results.json` |

---

## 2. Section A — the headline result

The probe ran the **same** ops task definition, command, subnets and security group the weekly
`intellichoice-staging-memory-consolidate` schedule uses, on `ops-task:147`
(`learning-api:gha-523b9f036a53`). One env override was added — `MEMORY_BEDROCK_RUN_BUDGET_CENTS=60`
— purely as a spend guard, because the job's own default is 3000 cents and that is not a bound
inside this task's ~120-cent ceiling. It was never reached (`students_skipped: 0`).

```
Consolidation run complete: 2 of 2 student(s), 0 added, 0 reconfirmed, 0 contested, 0 expired,
13.40 cents spent; 8 model call(s), 8 failed, 13872 event(s) dropped, 0 refused.
FAILED: all 8 model call(s) failed and no fact changed. Exiting non-zero so the ops-task failure
alarm fires (AUD-F-34).
```

**Silent truncations = 0, and here is the cross-check that establishes it.** The run's log stream
contains **zero** successful `bedrock_call` records. A silent truncation is by definition a call
that stopped on `max_tokens` and was nevertheless *counted successful* — with an empty success set
that shape cannot exist. Positively: all 8 attempted calls are matched one-for-one by a
`bedrock_call_failed` record **and** by a line naming the exact ceiling each one hit
(`max_output_tokens=2688` ×4, `max_output_tokens=4000` ×4). 8 attempted = 8 failed = 8 truncations
surfaced. The job report agrees independently: `model_calls: 8, failed: 8, added: 0`.

Under the pre-D-467 ordering this identical run would have reported `added=0, calls_failed=0,
exit 0` — indistinguishable from a quiet week. That is the whole claim D-467 makes, and it holds on
the deployed image. **It is not a claim that truncation has been eliminated** — see §3.

**Provenance** is satisfied structurally rather than by sampling, and vacuously in fact (0 facts
written). `consolidation.py` computes `verified_ids = _verify_evidence(...)` and then
`if not verified_ids: continue`, so a candidate fact whose model-cited event ids do not re-verify
against that exact `(student, window)` event set is never written; all three write sites pass
`evidence_event_ids=verified_ids`. No database read or write was performed by this verification.

**One SNS notification was sent, and it is a true positive.** Because every call failed, the CLI
exited 1 by design (AUD-F-34), so `intellichoice-staging-ops-task-failed` fired once
(`AWS/Events Invocations = 1`, `FailedInvocations = 0`). This is the alerting path working, not a
side effect to suppress.

---

## 3. Defect found — reported, not fixed

**`MEMORY-CEILING-STILL-SATURATED`.** On the real staging cohort at `523b9f0`, 8 of 8 consolidation
calls truncated and 0 facts were written. Two distinct shapes:

1. `student-ext-4`, 1 existing fact → derived ceiling **2688**, truncated on all 4 calls, 6,647
   events dropped over the per-student call cap, 5.39¢.
2. `student-ext-1`, ~26 existing facts → derived **5888**, which the gateway's
   `_HARD_MAX_OUTPUT_TOKENS` capped to **4000** (`bedrock_max_tokens_capped`,
   `memory_consolidation_payload_oversized`), truncated on all 4 calls, 7,225 events dropped, 8.01¢.
   Past `MAX_SAFE_EXISTING_FACTS = 11` no ceiling can rescue this — it is exactly the "finding under
   the finding" D-467's own docstring names as needing a bounded-payload decision of its own.

**Material caveat, stated because it changes the reading.** The rolling 7-day window includes this
week's resume-evidence load-test traffic, so 13,872 events dropped over the call cap is far above a
normal week. The 2026-08-23 scheduled run saw 8 students, 8 calls, **0 dropped**, 9 facts added. The
saturation is therefore partly a consequence of benchmark-generated event volume and not purely a
product regression; the next ordinary weekly run is what separates the two readings. Either way,
D-467 did its job: the failure is now loud instead of silent.

---

## 4. Section B1 — no safe 500 trigger exists, honestly

Sixteen probes across both apps' reachable surface (all read-only except one 202 `cancel`, see §5)
produced 200/401/403/404/422 and **not one unhandled 500**. That is a property of the code, not luck:

- `grep -rn "UUID|Uuid" packages/db/src/intellichoice_db/models/*.py` returns **nothing** — every
  column is `String`/`Text`, so the usual "non-UUID string into a `uuid` column → asyncpg
  `DataError` → 500" class is absent by construction.
- Malformed query values are rejected by Pydantic at the boundary (422), never inside a handler.
- Missing rows become explicit `HTTPException`s (404/409); authorisation refuses first (403).

Forcing a 500 would have required an unsafe trigger, which the Frozen Spec forbids, so the
spec-authorised fallback was taken: deployed-image consistency (`VERDICT: OK`, every image agrees on
`gha-523b9f036a53`, the commit that contains `_log_unhandled_exception`) plus the five permanent
tests (5 passed).

**One proof stronger than the fallback was obtained anyway.** The B2 synthetic pair wrote one
plain-text uvicorn traceback *and* one JSON `unhandled_exception` line (with `exc_info`) into the
live learning-api log group. `UnhandledTracebacks` recorded exactly **1.0, not 2.0** — so the
deployed filter's `-exc_info` exclusion behaves correctly against the exact line shape D-468 now
ships, on the running image, not in a test double.

---
## 5. Section B2–B4 — the alarm proved detection, and nothing was left altered

| UTC | event |
|---|---|
| 06:51:39 | `disable-alarm-actions intellichoice-staging-learning-api-unhandled-tracebacks` → `ActionsEnabled=false`, state `OK` |
| 06:51:51 | two synthetic events written to `r5-verification/synthetic-traceback` in the live learning-api log group: one plain-text uvicorn traceback, one JSON `unhandled_exception` line carrying `exc_info` |
| 06:51:00 (bucket) | `UnhandledTracebacks` = **1.0** — exactly one, not two. The filter `"Traceback (most recent call last):" -exc_info` counted the plain-text line and correctly excluded the JSON one |
| 06:52:07 | alarm `OK → ALARM` with actions disabled ⇒ **no SNS notification sent** |
| 07:07:30 | alarm `ALARM → OK` **on its own**, as the datapoint left the 900-second evaluation window — still with actions disabled, so no `OK` notification was sent either |
| 07:07:47 | `enable-alarm-actions` → `ActionsEnabled=true`, both `AlarmActions` and `OKActions` back to `intellichoice-staging-alerts` |
| 07:07:48 | `delete-log-stream r5-verification/synthetic-traceback` → the prefix now returns `[]`. The CloudWatch *metric* datapoint survives the deletion, so the evidence above is not destroyed |
| 07:11:11 | re-POST the same `(session, turn)` cancel pair to sweep the one row the B1 probe left (§6) |

**Final account-wide read-back at 07:11:26Z:** 40 alarms before, 40 after, identical set; **0 alarms
with actions disabled**; `ActionsEnabled` differs on none; `AlarmActions` differs on none. One state
change, `learning-api-p95-latency-scale-in` `ALARM → OK`, caused by this task's own request traffic
raising p95 above the scale-in threshold — an ordinary autoscaling signal that self-resolves.
`chat-api-p95-latency-scale-in` remains in `ALARM`, which is the normal resting state of an idle
staging environment.

**ADOT export metrics (B5/B6).** The exporter series carry a **required `exporter` dimension**; an
undimensioned query returns empty and would have read as a regression. Dimensioned, and proved
against a known-good pre-deploy control window:

| window | series | datapoints | latest |
|---|---|---|---|
| post-deploy 06:30Z → 06:49Z | 8/8 (both services × sent/failed × spans/metric-points) | **19 each** | 06:48Z |
| control 04:00Z → 05:00Z | 8/8 | 60 each | 04:59Z |

`otelcol_exporter_send_failed_spans` and `otelcol_exporter_send_failed_metric_points` are **0 across
both services in both windows**, and all four export-failure alarms exist with actions enabled.

---

## 6. State written to staging, and what happened to it

| what | disposition |
|---|---|
| `semantic_memory` rows from the Section A probe | **none written** — 0 added, 0 reconfirmed, because all 8 calls truncated. Had it written, that would be the weekly job's own normal behaviour over FIXTURE students, not pollution. |
| one guest chat session + turn from the Section E smoke | ordinary product traffic, the same shape the deploy workflow's own smoke produces; covered by the existing 90-day `chat-purge` and the checkpoint-retention posture. |
| `r5-verification/synthetic-traceback` log stream | **deleted** at 07:07:48Z. |
| alarm action state | **fully restored**; 0 alarms account-wide have actions disabled. |
| one `chat_turn_cancellations` row from a B1 probe (`POST /chat/sessions/not-a-uuid/turns/x/cancel` → 202) | **swept at 07:11:11Z.** This is the exact D-416 shape the code anticipates: `POST /chat/sessions` persists nothing, so the endpoint cannot tell a real session from an invented id and must not try. Re-posting the same pair after the 15-minute `STALE_AFTER` horizon is a no-op insert (`ON CONFLICT DO NOTHING`) followed by the **global** sweep of every row older than 15 minutes — which is that row. Table back to zero. |

No Terraform was applied, no product code was changed, no bank item was touched, and no file
outside `docs/resume_evidence/staging_verification/` was written.

---

## 7. Open items for the coordinator

1. **`MEMORY-CEILING-STILL-SATURATED` (§3)** — reported, not fixed, per the Decision Boundaries.
   Two sub-questions the executor may not answer: whether the derived ceiling needs raising again,
   and the bounded-payload decision D-467's docstring defers ("which facts get dropped?") for
   students past `MAX_SAFE_EXISTING_FACTS = 11`. The next ordinary weekly run (Sunday 18:30 UTC,
   i.e. later today) is the clean read that separates the load-test-inflated window from a real
   regression.
2. **The Section A probe legitimately paged once.** `intellichoice-staging-ops-task-failed` fired
   one SNS notification to `intellichoice-staging-alerts` because the CLI exited 1 by design
   (AUD-F-34, all calls failed). True positive, recorded so nobody reads it as an unexplained alert.
3. **Observability gap noticed in passing, not in scope.** In the ops task the gateway's structured
   `extra` fields are **not** rendered: `bedrock_call_failed` reaches CloudWatch as the bare string
   `bedrock_call_failed` with no `reason`, `max_output_tokens` or `task` field, because
   `configure_logging()` only runs inside `report_job_complete()` at the very end of the CLI. The
   cross-check in §2 still succeeds because the paired human-readable line names the ceiling, but
   the ops-task log group cannot be queried by `{ $.event = "bedrock_call_failed" }` the way the two
   API log groups can. Reported for the coordinator to decide on.
4. **One env override was used in Section A** — `MEMORY_BEDROCK_RUN_BUDGET_CENTS=60`, a spend guard
   only, never reached. Flagged because the spec said "same env the weekly job uses" and the job's
   own default (3000 cents) is not a bound inside a ~120-cent task ceiling.
