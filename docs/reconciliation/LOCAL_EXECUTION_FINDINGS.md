# LOCAL_EXECUTION_FINDINGS.md — Phase 3A.5 material findings

**Date:** 2026-08-19
**Companion document:** [LOCAL_EXECUTION_EVIDENCE.md](LOCAL_EXECUTION_EVIDENCE.md) — that file is the
per-claim execution record (every command, its verbatim output, and the claim it settles). This file
is the *material* residue: only what execution actually surfaced or sharpened.

**Scope.** This document records findings. It does not fix anything and it does not decide anything.
Every entry below traces to an executed command in the companion evidence file or to a direct
re-read of a repository file, quoted verbatim. Three categories are deliberately excluded:

- **Fixes.** Nothing found here was repaired. Where a finding names a defect, it is marked
  *not fixed — recorded*.
- **Decisions.** Where a finding implies a judgement (should chat-api carry a safety screen; should
  the `(Sn)` provenance convention be revived), the judgement is not made here.
- **Runtime / live / deployed halves.** Phase 3A.5 ran only local, free, non-credentialed,
  repository-defined commands. Every claim's live half keeps its 3B deferral. See §5.

Severities are quoted from the Phase 3A.5 adjudication and are not re-derived. Where the
adjudication assigned no severity, the entry says so rather than inventing one.

---

## 1. Headline: the suite is green

The primary result of Phase 3A.5 is a null result, and it is worth stating plainly before any
finding, because the findings below are all *sharpenings* rather than breakages.

Everything that was run, passed:

| Lane | Executed | Result |
|---|---|---|
| Targeted pytest (16 invocations) | 562 unique tests (566 executions) | all passed, **0 failed / 0 errors / 0 skipped** |
| learning-web unit tests | 26 tests, 4 files | 26 passed |
| chat-web unit tests | 49 tests, 5 files | 49 passed |
| `make lint` | `ruff check .` + `ruff format --check .` | `All checks passed!` / `440 files already formatted` |
| `make typecheck` | `uv run pyright` | `0 errors, 0 warnings, 0 informations` |
| `make e2e-typecheck` | `cd e2e && npx tsc --noEmit` | clean (only an unrelated node `ExperimentalWarning`) |
| learning-web `npm run build` | `tsc -b && vite build` | `built in 295ms` (one `>500 kB` chunk warning) |
| chat-web `npm run build` | `tsc -b && vite build` | `built in 185ms` |
| Alembic replay **from empty** | scratch DB, base to head | **37 migrations**, single head `8509c0486d8d` |
| AST field count | `LearningState` / `QAState` | 32 / 27 annotated fields |

Total: **562 unique tests (566 executions) + 75 frontend tests + lint + typecheck + two production builds + an e2e
typecheck + a 37-revision migration replay from an empty database — zero failures, zero errors, zero
skips.** (X1's reported 583 was an addition error, resolved during verification: its addend list sums
to 566, and one 4-test confirmation re-run was already counted inside the 83-test db-suite run.) Run
hygiene held throughout: `git status --porcelain` reported only the pre-existing
`?? docs/reconciliation/` after every step, `make fmt` and every git-mutating, terraform, aws, gh,
Playwright, and `npm install`/`npm ci` command was never invoked, and no `.env` or `*.tfvars`
content was read.

### What that does and does not mean

**It means** the largest single evidence conversion available in this audit landed. The Phase 3A
classification vocabulary distinguished "the cited artifact exists" from "the cited artifact
passes"; 3A.5 converted the second for every locally executable claim. All five
`TEST_EXISTS_NOT_EXECUTED` claims are now resolved at the pytest level (REQ-20, REQ-40, TEST-14
fully; TEST-22 and TEST-23 for their API halves). The repo's own declared gate,
`make lint typecheck test`, reproduces CI's `lint-typecheck-test` job exactly, and it is clean.

**It does not mean** the documentation is accurate, and it does not mean the deployed system behaves
this way. Three limits bound the whole result:

1. **Existence plus pass is still not deployed behaviour.** Every terraform-derived number in 3A and
   3A.5 is *file state*. See F-03: `terraform apply` is not part of `deploy-staging.yml`, and the
   repo has a written instance of a config change that was never applied.
2. **Several passes are weak by construction.** A green test is only as strong as what it iterates
   over and what it asserts. F-09 (REQ-44 sweeps 5 of 10 reason sets) and F-10 (exactly one test
   repo-wide guards the self-harm screen) are the two clearest cases. Passing them was necessary,
   not sufficient.
3. **Execution cannot confirm an absence, only relocate it.** Where a claim's substance is "X does
   not exist", running tests adds nothing; an exhaustive grep does. Several findings below are of
   that shape (F-05, F-06, F-11), and one absence was confirmed to have *no executable guard at
   all* (F-11).

---

## 2. Failing tests / broken builds / type-lint failures

**None.** Category by category, against what the phase brief asked for:

- **Failing tests:** none. 562 unique tests (566 executions) and 75 frontend tests, all passed.
- **Unexpected skips:** none. Every pytest invocation reported `0 skipped`. Notably TEST-12's cited
  test (`test_editing_an_item_already_in_the_database_propagates`), whose own 3A block warned it
  "needs a live DB and may be silently skipped", **ran** against the local Docker Postgres and
  passed — the skip worry is answered, not merely unobserved.
- **Broken builds:** none. Both Vite production builds and the e2e TypeScript compile exited 0. The
  only build-time warning is learning-web's `(!) Some chunks are larger than 500 kB after
  minification` on a 700.04 kB bundle, which is a bundle-size notice, not a failure.
- **Type failures:** none. `pyright` reported `0 errors, 0 warnings, 0 informations`.
- **Lint failures:** none. `ruff check .` reported `All checks passed!` and `ruff format --check .`
  reported `440 files already formatted` — read-only by design (D-417/C8), so no file was rewritten
  as a side effect of asking the question.

### Two zero-collection events — recorded as not-evidence, and recovered

The Makefile's own instrument-honesty rule (AUD-F-12: `scan-traces` "FAILS on zero traces scanned";
`scaling-evidence` "exits 2 on an empty window, because 'no refusals' from an instrument that saw
nothing is the AUD-F-12 false negative") applies to this phase too: **a pytest run that collects
zero tests is not a pass.** Two as-briefed commands collected zero. Both are recorded as
not-evidence and both were recovered:

1. **TEST-13.** `uv run pytest packages/knowledge/tests/ -k "quote_floor"` exited 5 with
   `40 deselected in 0.89s` — **collected 0**. The batch spec pointed at the wrong package. Recovered
   by grep: the quote-floor tests are in `apps/chat-api/tests/test_qa_service.py`, which ran
   `23 passed`. This mislocation is itself a finding — see F-04.
2. **REQ-32.** `uv run pytest apps/learning-api/tests/test_learning_chat.py -k "safety"` exited 5
   with `11 deselected in 0.78s` — **collected 0**. No test name in the file contains the substring
   "safety"; the test is named for the keyword class. Recovered by running the whole file:
   `11 passed`, including
   `test_self_harm_keyword_short_circuits_to_a_fixed_response_and_flags_for_review`. See F-10.

For completeness, two runs used `-k` deliberately and reported deselections that are *not* skips:
Batch 3a's `-k "solver"` (10 selected of 90) and Batch 7's `-k "token or staging"` (16 selected of
25). Those deselections were the point of the invocation, not a collection failure.

---

## 3. Material findings

### F-01 — COST-10 sharpened: the cost reserve hard-codes a 2000-token input assumption

**Related claims:** COST-10 (`PARTIALLY_IMPLEMENTED`), and by adjacency REQ-19 / COST-03 (the
gateway's six cost features, all of which passed).
**Severity: MEDIUM** (unchanged from 3A; the mechanism is now precise).

**What was found.** The 3A claim was that D-141's input-token bound is not in the gateway. Execution
plus a direct re-read confirms it and locates the consequence exactly. Two greps returned nothing:

```
$ grep -rniE "max_input|MAX_PROMPT|D-141" packages/adapters/src packages/shared/src --include="*.py"
exit 1 → no matches
```

So there is **no input-size ceiling anywhere in the gateway or the shared payload layer**. The only
ceiling is on output — `gateway.py:78`, `_HARD_MAX_OUTPUT_TOKENS = 4000`, commented "A spend guard:
no single call may bill for more output than this", applied at `gateway.py:236` and logged at `:239`.

The sharpening is what the *reserve* step does in the absence of an input bound. Verbatim,
`packages/adapters/src/intellichoice_adapters/bedrock/gateway.py:182-194`:

```python
    def worst_case_cost_cents(self, task: BedrockTask, max_output_tokens: int) -> float:
        """The most one `generate_structured` call for this task can cost.

        Public so a caller can *reserve* this amount against a per-day ceiling before
        making the call (AUD-X-08's reserve-then-settle). Deliberately the same number the
        session-budget check below uses, so the two ceilings cannot disagree about what a
        call is worth. The 2000-token input assumption is that check's, inherited here
        rather than re-guessed.
        """
        model_id = self._model_registry.get(task)
        if model_id is None:
            raise ValueError(f"no Bedrock model configured for task {task!r}")
        return self._cost_cents(model_id, 2000, min(max_output_tokens, _HARD_MAX_OUTPUT_TOKENS))
```

The docstring concedes the assumption in its own words: the 2000-token input figure is "inherited
here rather than re-guessed".

The one real input bound in the codebase lives a layer above the gateway and is local to a single
caller — `packages/memory/src/intellichoice_memory/consolidation.py:103-108`:

```python
_MAX_EVENT_TOKENS_PER_CALL = 20_000
_CHARS_PER_TOKEN = 3.0
_MAX_EVENT_CHARS_PER_CALL = int(_MAX_EVENT_TOKENS_PER_CALL * _CHARS_PER_TOKEN)
_MAX_CALLS_PER_STUDENT = 4
```

**Why it matters.** A large-input call is **neither refused nor correctly priced at the reserve
step**: a 50k-token prompt reserves against the 50-cent session budget as though it were 2000 input
tokens. Input bounding is therefore per-caller and voluntary rather than enforced at the gateway
seam — which is the shape non-negotiable rule 7 ("all paid calls go through the gateway with
timeouts, bounded retries, max-token limits, and cost accounting") exists to prevent. All 44
gateway/cost-reservation tests passed, including the concurrent failure-burst breaker test, so this
is not a broken mechanism; it is a mechanism whose input dimension was never built.

**Explicitly not traced in this phase:** whether **settlement** uses actual input tokens. If it
does, the exposure is bounded to the reserve-settle window rather than persisting. That question was
not investigated and no claim is made about it either way.

*Not fixed — recorded.*

---

### F-02 — WORK-40, new implementation finding: chat-web renders calendar times in the viewer's locale

**Related claims:** WORK-40 (`PARTIALLY_IMPLEMENTED`); defect class D-324.
**Severity: MEDIUM.** This is a **new** finding — it was not in the 3A ledger.

**What was found.** WORK-40's 3A block was about learning-web's date formatter. Executing the
cross-app grep surfaced the same defect class, unfixed, in the *other* app. Verbatim,
`apps/chat-web/src/screens/CalendarActionModal.tsx:11-15`:

```tsx
function formatDateTime(value: unknown): string {
  if (typeof value !== "string") return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
```

`date.toLocaleString()` is called with **no `timeZone` and no locale argument**, so it renders in
whatever zone and format the viewer's browser is set to.

This is precisely the defect D-324 fixed in learning-web. The fix there exists and works:

```
$ grep -rn "formatDateLabel\|buildDateLabelFormatter" apps/learning-web/src apps/chat-web/src
apps/learning-web/src/screens/StudentDashboardScreen.tsx:79:function buildDateLabelFormatter(timeZone: string): (value: unknown) => string {
apps/learning-web/src/screens/StudentDashboardScreen.tsx:220:  const format = buildDateLabelFormatter(timeZone);
apps/learning-web/src/screens/StudentDashboardScreen.tsx:427:  const formatOrgDate = useMemo(() => buildDateLabelFormatter(orgTimeZone), [orgTimeZone]);
```

Note the zero hits in `apps/chat-web/src` — the fix never crossed the app boundary. And the fix
itself is not unit-testable as written:

```
$ grep -n "export function buildDateLabelFormatter" apps/learning-web/src/screens/StudentDashboardScreen.tsx
exit 1 → not exported (module-private)
```

Its only coverage is the Playwright spec `e2e/tests/learning/dashboard-chart-labels.spec.ts` — the
deferred browser lane (§5). The four executed learning-web test files cover `masteryBands`, stream
liveness, `attendanceLabels`, and `ConnectingPanel`; none touches it.

**Why it matters.** Calendar-approval times — the times a human reads before approving an external
action under non-negotiable rule 4 — render in the viewer's browser zone rather than org time. A
parent or manager in a different zone approves an event whose displayed time is not the event's
time. The org timezone is available and plumbed: ARCH-35's execution confirmed `ORG_TIMEZONE` /
`ORG_TIME_CONVENTION` / `ORG_TIME_CONFIRMED` are set identically into **both** task definitions
(`staging/main.tf:497-499` and `:582-584`) and read by one shared module,
`packages/shared/src/intellichoice_shared/org_time.py`. chat-web simply does not use it here.

*Not fixed — recorded. This is an audit; the fix is out of scope.*

---

### F-03 — Systemic note for 3B framing: `terraform apply` is not part of `deploy-staging.yml`

**Related claims:** every terraform-derived claim in 3A and 3A.5 — COST-19, COST-23, COST-24,
COST-28, COST-29, SEC-10, ARCH-02, ARCH-10, ARCH-12, ARCH-29, ARCH-35, WORK-08, WORK-21, REQ-49.
**Severity:** not assigned in the adjudication; recorded as a framing constraint on Phase 3B.

**What was found.** The repository documents, in its own words, an instance of a terraform config
change that was written and never reached AWS. Verbatim,
`terraform/environments/staging/main.tf:547-552`:

```
  # D-344 authored `autoscaling_max_capacity = 1` here as a stopgap while D-349's relay was
  # built, and **it was never applied** - `terraform apply` is not part of `deploy-staging.yml`
  # and nobody ran it, so live stayed at the module default of 3 the whole time. Reverted
  # rather than left in place: a file claiming a capacity AWS does not have is worse than the
  # default it was trying to override, and the relay it was waiting for landed in the same
  # session anyway. The honest account is in D-344 itself.
```

**Why it matters.** This is the strongest available evidence that config and live can diverge in
this project, and it is the project's own testimony rather than an auditor's inference. Every
terraform-derived number in 3A and 3A.5 is therefore **file state only**. Phase 3B must not treat
config as live: the numbers to re-verify against AWS include learning-api's 512/1024/desired-2
sizing versus chat-api's inherited 256/512/desired-1 defaults (COST-29), the eight alarms in
`alarms.tf` (SEC-10, COST-24), the `anytrue`-driven NAT gateway (COST-28/ARCH-29), and the
single-worker task definitions (ARCH-12).

A second-order point of the same shape: the terraform-*parsing* pytest tests
(`packages/observability/tests/test_alarm_severity_routing.py`, 3 tests) passed, which upgrades
these config claims from "file read by an auditor" to "file asserted by an executed test". That is a
real strengthening and still not a statement about AWS.

---

### F-04 — Correction: TEST-13's quote-floor tests are not where the 3A block implies

**Related claims:** TEST-13 (`CONFIRMED`), and by suite adjacency TEST-14.
**Severity: LOW** (wording correction; substance unchanged).

**What was found.** The 3A block and the phase-target table both located the citation quote-floor
tests in `packages/knowledge/tests/`. They are not there:

```
$ uv run pytest packages/knowledge/tests/ -k "quote_floor" -q -rA
exit 5 — collected 0 (40 deselected in 0.89s)
```

The tests exist and pass, in `apps/chat-api/tests/test_qa_service.py` (`23 passed`):

- `test_the_quote_floor_is_measured_at_its_own_boundary`
- `test_the_floor_is_applied_to_the_normalized_quote`
- `test_a_quote_dropped_for_being_too_short_says_so_in_the_log`
- `test_the_quote_floor_excludes_only_heading_chunks`
- `test_a_one_character_quote_no_longer_verifies`
- `test_the_model_is_told_what_a_quote_has_to_be`

Implementation and measurement live at `apps/chat-api/src/chat_api/services/qa.py` and
`scripts/measure_citation_quote_floor.py`. The separate `packages/knowledge/tests/test_retrieval.py`
suite (TEST-14) ran independently: `22 passed`, including the no-floor-when-degraded test, with
three tests emitting expected `retrieval_rerank_degraded` / `access_probe_rerank_degraded` warnings
by design.

**Why it matters.** A ledger row pointing at the wrong package is a row that cannot be re-verified
by the next reader running the cited command — they get zero collected and no error, which is the
AUD-F-12 false-negative shape. The claim's substance ("traced does not equal enforced"; the floors
are measured constants with band-asserting tests) is confirmed by the tests that do exist.

---

### F-05 — Correction: `TOPIC_MAPPING` is declared and never used, not absent

**Related claims:** REQ-17 (`PARTIALLY_IMPLEMENTED`), REQ-51 (which explains *why*).
**Severity: LOW** (wording correction; substance unchanged).

**What was found.** The 3A claim rested on a repo-wide negative grep for `TOPIC_MAPPING`. The grep
returns one hit, not zero:

```
$ grep -rn "TOPIC_MAPPING" packages apps --include="*.py"
packages/shared/src/intellichoice_shared/bedrock.py:37:    TOPIC_MAPPING = "topic_mapping"
```

It is a `BedrockTask` enum member, and the class docstring concedes the reservation in advance
(`bedrock.py:30-34`):

```python
class BedrockTask(StrEnum):
    """SPEC §5.25.2 task table. Only `TUTOR` has a configured model this session - the
    others are named now so the model registry's keys are stable as later sessions add
    callers, not because logic exists for them yet.
    """
```

What is absent is everything downstream: no payload model, no response model, and **no caller in
any of the 18 non-test `generate_structured` files** or anywhere else in `apps`/`packages`. The only
other `topic_mapping`-shaped string in the tree is an unrelated filename,
`content.py:270: grade_mapping_doc = _read_yaml(content_root / "grade_topic_mapping.yaml")`.

REQ-51's execution explains the vacancy rather than contradicting it: `topic_resolver.py` makes zero
LLM calls (`grep -rn "generate_structured" .../topic_resolver.py` → exit 1), every import is a DB
repository/model or a deterministic policy constant, and its only `intellichoice_shared.bedrock`
import is the `TutorContext` dataclass it fills in for a later caller. Topic resolution is
deterministic by construction, consistent with D-024 and non-negotiable rule 2 — so the enum slot
has no caller *because* the deterministic-core rule won.

**Why it matters.** "`TOPIC_MAPPING` does not exist" is falsifiable by one grep and would discredit
the surrounding row. "`TOPIC_MAPPING` is declared and never used" is correct, and it is a materially
different finding: a reserved-but-unbuilt task slot with a documented reason, not a missing
implementation.

---

### F-06 — Correction: four `checkpoint_repair` lines in terraform, not three

**Related claims:** SEC-10 (`PARTIALLY_IMPLEMENTED`).
**Severity: LOW** (count correction; substance unchanged).

**What was found.** The 3A block cited "only 3 lines". There are four:

```
$ grep -rn "checkpoint_repair" terraform/
terraform/modules/ecs-service/main.tf:209:              "learning_checkpoint_repairs_total",
terraform/modules/ecs-service/main.tf:255:              "learning_checkpoint_repairs_total",
terraform/modules/observability/dashboard.tf:425:            # Should sit at zero. `checkpoint_repairs` is AUD-X-07's canary - a session
terraform/modules/observability/dashboard.tf:436:              [".", "learning_checkpoint_repairs_total", { label = "checkpoint repairs (AUD-X-07)" }],
```

Two of the four are metric-pipeline plumbing (`:209` the otel `filter/kpis` strict include list;
`:255` the `awsemf` exporter's `metric_declarations`, which promotes it to a real CloudWatch
metric), one is a comment, one is the dashboard widget.

**The substance is unchanged: no alarm references it.** `terraform/modules/observability/alarms.tf`
is the only alarms file, it defines eight `aws_cloudwatch_metric_alarm` resources, and their metrics
are `BedrockCircuitOpen`, `LangSmithIngestFailed`, `BedrockCallFailed`, `CPUUtilization`,
`FreeStorageSpace`, `DatabaseConnections`, `MemoryUtilized`, `BedrockCostCents`. None is
`learning_checkpoint_repairs_total`.

**Why it matters.** A metric whose own dashboard comment calls it "AUD-X-07's canary" that "should
sit at zero" is scraped, EMF-promoted, and charted — and silent. A checkpoint-repair burst is
invisible until a human opens the dashboard. The 3A note that
`packages/observability/tests/test_alarm_severity_routing.py` would not catch this is confirmed by
execution: those three tests passed, and they route alarms that exist rather than requiring an alarm
per tripwire metric.

---

### F-07 — Correction: ARCH-01 splits — decisions are current, session provenance is not

**Related claims:** ARCH-01 (`PARTIALLY_IMPLEMENTED`).
**Severity: LOW** (split verdict; one half of the 3A wording is refuted).

**What was found.** The 3A framing implied `ARCHITECTURE.md` is stale in the "up to" direction.
Execution splits it in two.

**Decision currency is fine.** `ARCHITECTURE.md` cites D-423 (`grep -noE "D-4[0-9][0-9]"` → ten
lines, eleven occurrences, `1177:D-423`), and D-423 is the newest entry in `DECISIONS.md`
(`28714:## D-423 — B6 part 1: the RAG latency split, measured, and the optimisation it cancelled
(accepted, 2026-08-18)`), the same decision as HEAD~1. It is not behind on decisions.

**Session provenance is genuinely incomplete.** The header (lines 3-13) promises "Session provenance
is tagged in each node (e.g. `(S6)`)" and claims coverage "through **S0–S34 plus the S36–S43 audit
and stabilization work and the §2.6 launch gate**". Tags exist for 32 of 48 sessions. The 16
untagged: **S23, S30, S31, S32, S33, S35, S36, S38, S40, S41, S42, S43, S44, S45, S46, S47** — i.e.
every session from S40 onward except the aspirational `(S48)`, which tags the *unbuilt* production
environment (consistent with ARCH-02's finding of exactly one environment directory and zero AWS
Organizations resources).

**Why it matters.** The accurate finding is "the `(Sn)` provenance convention was abandoned around
S39 while the header still advertises it", not "ARCHITECTURE.md is behind on decisions". The two
have different remedies and only the first is real. Whether to revive the convention or retract the
header promise is a judgement, not made here.

---

### F-08 — TEST-04: the executed `extra="forbid"` count is 41, against a documented 31

**Related claims:** TEST-04 (`PARTIALLY_IMPLEMENTED`), and SEC-06 (the payload PII floor, which
passed).
**Severity:** not assigned in the adjudication; the 3A block classified the drift LOW.

**What was found.** The declared mechanism was executed and is clean:

```
$ make typecheck
uv run pyright
0 errors, 0 warnings, 0 informations
```

So clause (b) of the §5.27 structural citation — "pyright in CI" — holds. The count does not:

```
$ grep -r 'model_config = ConfigDict(extra="forbid")' apps packages --include="*.py" | wc -l
41
$ grep -r ... | grep -vE '(^|/)tests?/|/test_[^/]*\.py:' | wc -l
41   (zero of the 41 are in test files; all 41 are source)
```

Concentrated in four files, 35 of them in one:

```
packages/curriculum/src/intellichoice_curriculum/adjudications.py:2
packages/curriculum/src/intellichoice_curriculum/authored_bank.py:2
packages/shared/src/intellichoice_shared/bedrock.py:35
packages/adapters/src/intellichoice_adapters/bedrock/smoke_cli.py:2
```

The documented figure, verbatim, `docs/TRACEABILITY.md:623`:

```
| **§5.27** Pydantic | **31** `extra="forbid"` models across `apps/` and `packages/` | `make typecheck` (pyright, 0 errors) in CI's `lint-typecheck-test`; ...
```

and `docs/DECISIONS.md:6870` repeats the 31.

**Why it matters.** Two facts the row should carry beyond the count. First, the strictness covers
**41 of 184** non-test `BaseModel`/`BaseSettings` classes repo-wide (22%) — `grep -rnE 'class
[A-Za-z0-9_]+\((BaseModel|BaseSettings)'` over the same non-test scope returns 184. Second, only 35
of the 64 `BaseModel` classes inside `bedrock.py` itself carry it. So "types every payload as an
`extra="forbid"` model" is true for the Bedrock payload surface and is **not** a repo-wide
invariant. No other `ConfigDict` variant exists anywhere (`uniq -c` over all `ConfigDict(...)` forms
returns the single line `41 model_config = ConfigDict(extra="forbid")`); the remaining 11 of 52
`model_config` lines are `SettingsConfigDict` in the 11 settings modules.

---

### F-09 — REQ-44 passed, and the pass is weak by construction

**Related claims:** REQ-44 (`PARTIALLY_IMPLEMENTED`).
**Severity:** not assigned in the adjudication; the vacuity caveat is adjudicated to stand.

**What was found.** `apps/chat-api/tests/test_turn_reasons.py` ran inside a 43-test batch,
`43 passed`. The no-reason-code-restated sweep works.

But the sweep **iterates only `REASON_MESSAGES`** — 5 entries. The copy that is *not* swept:
`UNAVAILABLE_INTENT_MESSAGES`, the `LOCATION_*` strings, `RATE_LIMITED_MESSAGE`, and the calendar
copy. The assertion is a plain substring check, so it **passes vacuously for any copy defined
outside the dict**.

**Why it matters.** This is the clearest case in the phase of a green test that must not be read as
coverage. The pass is necessary and not sufficient: adding a new user-facing message outside
`REASON_MESSAGES` that restates a reason code would leave this test green. Recording the pass
without the caveat would overstate the evidence in exactly the direction Phase 3A.5 exists to
correct.

---

### F-10 — REQ-32: exactly one test repo-wide guards the self-harm screen

**Related claims:** REQ-32 (`PARTIALLY_IMPLEMENTED`).
**Severity:** not assigned in the adjudication; recorded as a thinness observation.

**What was found.** After the zero-collection recovery (§2), the whole file ran: `11 passed`. The
test that matters is
`apps/learning-api/tests/test_learning_chat.py:474` —
`test_self_harm_keyword_short_circuits_to_a_fixed_response_and_flags_for_review`. It executed and
passed.

It is the only one. A grep over `apps/` and `packages/` for
`safety_screen|crisis|self_harm|safety_flag` hits that one file and no other.

**Why it matters.** The primary users of this platform are K-12 minors. The self-harm short-circuit
is a child-safety path, and its entire executable guard is a single test function against a fixed
10-keyword screen on learning-api only, with Bedrock Guardrails absent repo-wide and no escalation
destination beyond a boolean flag. The test passing is good; the coverage depth is a fact worth
recording. Whether chat-api should also carry a safety screen is a product judgement and is not
made here.

---

### F-11 — SEC-13 confirmed: `purge_resume_writes` has zero tests

**Related claims:** SEC-13 (`PARTIALLY_IMPLEMENTED`, flagged in 3A as new material drift —
privacy/minors), coupled to SEC-12.
**Severity:** not assigned in the adjudication; the 3A block classified it as new material drift.

**What was found.** The grep is exhaustive and every hit is under `src/`:

```
$ grep -rn "purge_resume_writes" apps packages --include="*.py"
apps/chat-api/src/chat_api/routers/sessions.py:66:from chat_api.services.checkpoint_privacy import purge_resume_writes
apps/chat-api/src/chat_api/routers/sessions.py:914:        await purge_resume_writes(db, chat_session_id)
apps/chat-api/src/chat_api/graph/nodes.py:801:    # payload, which `purge_resume_writes` removes. That asymmetry is deliberate rather than an
apps/chat-api/src/chat_api/services/checkpoint_privacy.py:24:async def purge_resume_writes(db: AsyncSession, thread_id: str) -> None:
```

Three files: the definition, its single call site, one explanatory comment. **No `tests/` path
appears in the result set at all.**

**Why it matters.** The function that scrubs resume-write payloads out of the checkpointer is the
enforcement point for the §5.30 / no-PII boundary on the branch-locator path — the place a visitor's
ZIP, city, address, latitude, and longitude stop existing. The 3A code-path finding was that it has
exactly one trigger, the successful-resume path: a cancelled resume returns before it
(`sessions.py:897-905` precedes `:907-914`), and any exception in `_run_turn` skips it. Execution
now adds that **the cancel path has no executable guard whatsoever** — and that its single call site
is one `await` inside a router, so a refactor deleting that line would break no test and fail no
CI job.

New-test authoring was deliberately out of audit scope, so this stays a code-path claim. It is named
in §5 as the highest-value post-audit test addition.

*Not fixed, and no test written — recorded.*

---

### F-12 — COST-06 residual: the flush-time `IntegrityError` branch remains untested

**Related claims:** COST-06.
**Classification after execution: still `CONFLICT`** (adjudicated unchanged).

**What was found.** Half (a) strengthened from existence to executed evidence: the cited test ran
and passed —
`packages/curriculum/tests/test_authored_pipeline.py::test_per_candidate_settlement_survives_a_duplicate_id`
(with `test_a_slots_rows_account_for_every_cent_the_slot_reports`), `2 passed`. The `_settle`
commit-time branch is covered.

Half (b) is unchanged. The `run_plan` flush-time `IntegrityError` branch — the `continue` at
`pipeline_cli.py:618` preceding `spend += outcome.cost_cents` at `:619`, which skips both the
increment and the `_settle` — has **no test in the repository**. Its money loss is demonstrated by
code path only. Writing the test would need no paid run (the fake gateway suffices), but authoring
new test code exceeds "repository-defined validation commands" in an audit.

**Why it matters.** Per the user's own standing rule, cost bugs are real production bugs. This one
is a spend that is incurred and then not attributed to the run total, on an error branch — the class
of path least likely to be exercised by hand. Execution narrowed the conflict by half and could not
close it, which is why the classification stays `CONFLICT` rather than resolving.

---

### F-13 — ARCH-33 strengthened by the workflow's own admission

**Related claims:** ARCH-33 (`PARTIALLY_IMPLEMENTED`).
**Severity:** not assigned in the adjudication; confirmed as claimed and strengthened.

**What was found.** The negative grep over the 711-line workflow returns no artifact-freshness
mechanism — no `sha256`, no `md5`, no `ETag`, no `content-hash`; the only `dist/` hits are the two
`aws s3 sync` lines (`:669`, `:674`). The pipeline is: `npm ci` → `npm run build` →
`s3 sync --delete` → blanket `create-invalidation --paths "/*"` → two `curl -sf` liveness checks.
There is no step comparing the built artifact to the served artifact.

The strengthening is that `deploy-staging.yml` says so itself, verbatim at lines 690-691:

```
      # The first two curls only prove the S3 origin serves the SPA - they would pass
      # against a completely stale deployment, and they never touch the API.
```

**Why it matters.** The Vite content-hash comparison that `ARCHITECTURE.md` presents as the frontend
half of the deploy gate is not in the pipeline, and the pipeline's own author documented that its
substitute has no teeth for asset freshness. The `/me` 401 probe that follows *does* have teeth —
for edge routing (D-158/AUD-F-37) — and says nothing about whether the bundle being served is the
bundle just built. A silently-failed sync or a cached edge object is undetectable by CI. A
documented concession is stronger evidence than an auditor's negative grep, because it cannot be
answered with "you grepped for the wrong string".

---

### F-14 — WORK-12 residual: the absence is confirmed, the status conflict is documentary

**Related claims:** WORK-12.
**Classification after execution: still `CONFLICT`** (adjudicated unchanged).

**What was found.** Execution confirmed the negative inventory precisely. learning-web:
`Test Files 4 passed (4) / Tests 26 passed (26)`, enumerated by name — `masteryBands` (7),
`stream.test.ts` liveness (6), `attendanceLabels` (8), `ConnectingPanel` (5). None asserts on a
rendered banner or a `streamState` value. The only grep hit is prose inside a test *name*:

```
$ grep -rnE "banner|streamState" apps/learning-web/src --include="*.test.*"
apps/learning-web/src/api/stream.test.ts:148:        "that has unmounted gets a state update and a banner for a stream nobody is watching",
```

And no Playwright spec either: `ls e2e/tests/learning/ | grep -i disconnect` → exit 1, while
`ls e2e/tests/chat/` → `stream-disconnect-visible.spec.ts`.

The asymmetry is now quantified from the other side. chat-web: `Test Files 5 passed (5) / Tests 49
passed (49)`, including six dedicated assertions in **both** directions:

```
 ✓ src/screens/ChatScreen.test.tsx > the disconnect banner > appears on error, says what is degraded, and its Reconnect control is wired
 ✓ src/screens/ChatScreen.test.tsx > the disconnect banner > does not appear while the stream is connecting
 ✓ src/screens/ChatScreen.test.tsx > the disconnect banner > does not appear while the stream is open
 ✓ src/screens/ChatScreen.test.tsx > the disconnect banner > does not steal the alert role from a turn that really failed
 ✓ src/screens/ChatScreen.test.tsx > the connection dot > reads idle before any turn exists, not connecting
 ✓ src/screens/ChatScreen.test.tsx > the connection dot > follows the real stream state once a turn exists
```

**Why it matters.** The in-code note at `apps/learning-web/src/App.tsx:958-960` calling the render
condition "deliberately untested (D-417/C7)" is **accurate as to state** — execution proves the
absence it describes. What no command can resolve is the conflict: `docs/PROGRESS.md:107-117` still
carries the item as open after W21, so two live statuses exist and neither has been retracted. That
is a documentary conflict requiring a scope judgement (chat versus learning), not a test. The gap is
one-directional and real: chat-web is the tested app, learning-web is not, for the same
user-visible failure.

---

### F-15 — REQ-39: the absence is now exhaustive, and the MEDIUM drift stands

**Related claims:** REQ-39 (`PARTIALLY_IMPLEMENTED`).
**Severity: MEDIUM** — adjudicated to stand.

**What was found.** SPEC prescribes a literal UI label twice —
`docs/SPEC.md:1111: Do not treat ten questions as an absolute measure of ability. The UI should say
'Current estimated level'.` as an instruction, and `docs/SPEC.md:1451: - Current estimated level` in
a screen's field list. The grep is now exhaustive in the strongest available form:

```
$ grep -rniE "current estimated level" apps/learning-web/src apps/chat-web/src   → exit 1
$ grep -rniE "estimated" apps/learning-web/src apps/chat-web/src                 → exit 1
```

The substring "estimated" does not occur anywhere in either frontend's source, in any case. The only
level-shaped labels shipped are per-question difficulty (`ExamScreen.tsx:71`, `Level ${difficulty}`)
and hint-ladder position (`InterventionScreen.tsx:262`), neither of which is the ability estimate
the SPEC wants hedged. The weights half passed (`test_mastery_bootstrap.py`, inside Batch 1's
`183 passed`), and the hedging *intent* is partly met elsewhere by D-409's mastery bands in
`ReportView` rather than a numeric score.

**Why it matters.** Non-negotiable rule 10 requires growth-oriented, age-appropriate
student-facing language, and the SPEC's chosen hedge for an ability estimate derived from ten
questions is this exact phrase. The prescribed label is not implemented and the deviation has no
disposition. Recorded, not decided.

---

### F-16 — REQ-27: the backend gate is executed-verified; the fail-closed frozenset is not

**Related claims:** REQ-27 (`PARTIALLY_IMPLEMENTED`).
**Severity:** not assigned in the adjudication.

**What was found.** The backend half exists and is tested. `packages/shared/.../auth.py:106` refuses
a non-exempt student without `parental_consent_verified`, and the tests covering it ran inside Batch
1's `183 passed` (`apps/learning-api/tests/test_auth_and_attendance.py:178,182`).

The student-facing half is absent, exhaustively:

```
$ grep -rniE "parental|consent|under 13|guardian" apps/learning-web/src apps/chat-web/src
23 matches — ALL in chat-web, ALL location-consent. Zero matches in apps/learning-web/src.
```

All 23 hits are the `location_consent` interrupt (the modal, its type, its router wiring) — a
different consent under SPEC §5.1.4, which does not discharge the COPPA notice. `SPEC.md:96`
sentence 3 requires learning-web — the app it names — to "present an age-appropriate notice to the
student"; learning-web has zero matches for all four patterns.

Separately, the **fail-closed empty-frozenset code half remains unexecuted**: no test pins
`AGE_BANDS_NOT_REQUIRING_PARENTAL_CONSENT` being empty, so nothing fails if a band is added to it.
Named in §5 as a new-test candidate.

---

### F-17 — Positive strengthenings worth recording

None of these is a defect. They are the conversions that make the rest of the ledger trustworthy,
and each was adjudicated as a strengthening.

- **TEST-02 — the largest single evidence conversion in the audit.** All 13 cited pytest files ran
  in one invocation: `183 passed in 18.90s`, 0 failed / 0 skipped / 0 errors. The five sampled
  TRACEABILITY criterion-1 rows move from "the cited artifact exists" to "the cited artifact
  passes". TRACEABILITY's rule is that "would fail if the requirement broke" is the substance and is
  unverifiable without execution; this is that execution. (The 14th cite,
  `scripts/scan_logs_pii.py`, needs staging CloudWatch → 3B.)
- **WORK-15 — D-342's parking premise is now executed-verified.** The load-bearing property (every
  declared tier of every spanning skill is servable, driven from the real taxonomy rather than a
  fixture, with its own vacuity guard) passed. A fail would have invalidated the parking decision;
  it passed.
- **WORK-37 — the 182-row deactivation incident guard holds.** The guard at
  `packages/youtube/tests/test_sync_preflight.py:157` (docstring citing "182 videos") and its three
  tests — `test_a_resumable_run_that_skipped_covered_skills_must_not_deactivate`,
  `test_a_quota_capped_run_must_not_deactivate`,
  `test_only_a_run_that_searched_every_skill_may_deactivate` — all executed and passed, pinning the
  computation that marked 182 videos inactive on staging 2026-08-15. The test targets the
  computation rather than the flag's effect, because the old tests passed the flag in.
- **WORK-03 + ARCH-08 — replay from empty, verified.** A scratch database was created, migrated
  base-to-head, inspected, and dropped: **37 migrations in one run**, `9e6877432c14` (initial domain
  schema) through `8509c0486d8d` (d421 chat escalation sends), with `alembic current` and
  `alembic heads` both reporting `8509c0486d8d (head)` — a single head, no branch divergence. That
  head *is* the D-421 `chat_escalation_sends` migration WORK-03 is about. `packages/db/tests/` then
  ran `83 passed`, including all four
  `test_autogenerate_never_drops_the_checkpoint_tables.py` tests. This directly satisfies the
  project convention "migrations must replay from empty". No repository file was touched and the
  scratch DB was confirmed absent afterwards. Staging schema state remains 3B.
- **WORK-11 — format enforcement is executed-verified.** `make lint` produced `All checks passed!`
  and `440 files already formatted`, using `ruff format --check` per D-417/C8 so the verification
  pass cannot rewrite files as a side effect of asking a question.
- **WORK-21 — both halves of the retention finding confirmed by test.** `test_checkpoint_retention.py`
  ran inside a 55-test batch, all passed, including
  `test_apply_is_off_unless_explicitly_true` (dry-run default) and
  `test_the_chat_classifier_requires_the_absence_of_phase_not_just_a_missing_summary` (the
  two-condition classifier, which is what stops an unprojected learning thread being deleted under
  the chat policy). The three decided windows are covered too. **The unscheduled-in-terraform drift
  stands unchanged** — the policy is implemented, tested, and not scheduled.
- **Also confirmed as claimed by executed greps or terraform-parsing tests**, with no new finding:
  REQ-51, ARCH-02, ARCH-12, ARCH-35, COST-16, COST-29 (config half), TEST-09 (absent *by decision*,
  D-125, tracked to S50 A7 — dispositioned, not an oversight), REQ-49 (both absences: zero
  dead-letter/DLQ hits anywhere, zero `fallback_model`/"smaller model" hits, so degradation is
  binary), REQ-52 (32 `LearningState` fields by AST parse; no `ephemeral_location` in `QAState`),
  SEC-23/COST-27/ARCH-30 (masking is assignment, not `setdefault`), SEC-25/ARCH-03 (16 gate tests
  passed; zero external identity providers by exhaustive grep), REQ-28/SEC-12 (branch-locator suite
  passed), COST-17 (client-error reporting), TEST-12 (ran against the local DB, was **not** skipped,
  and passed), WORK-27 (the fail-closed solver-distinctness preflight), WORK-35 (consolidation,
  scheduler, and memory tests), TEST-22 and TEST-23 (API halves), REQ-20, REQ-40, TEST-14.

---

## 4. Test-vs-document contradictions

Executed evidence against the document statement it contradicts. Every row is a documentation
correction; none requires a code change.

| # | Document statement | Executed evidence | Verdict |
|---|---|---|---|
| 1 | 3A ledger / target block locate the quote-floor tests in `packages/knowledge/tests/` (TEST-13) | `pytest packages/knowledge/tests/ -k quote_floor` → exit 5, **collected 0**; the six tests are in `apps/chat-api/tests/test_qa_service.py`, `23 passed` | **Contradiction.** Location wrong; tests exist and pass. See F-04 |
| 2 | `TRACEABILITY.md:623` and `DECISIONS.md:6870` cite **31** `extra="forbid"` models | `grep -r ... \| wc -l` → **41**, all in source, none in tests, in 4 files; 41 of 184 non-test `BaseModel`/`BaseSettings` classes | **Contradiction.** Documented number stale and low by 10. See F-08 |
| 3 | 3A wording: `TOPIC_MAPPING` **absent** (REQ-17) | `grep -rn "TOPIC_MAPPING"` → **1 hit**, `bedrock.py:37`, zero callers | **Contradiction of wording, not of substance.** "Declared, never used" is correct. See F-05 |
| 4 | 3A block: "only **3** lines" of `checkpoint_repair` in terraform (SEC-10) | `grep -rn "checkpoint_repair" terraform/` → **4 lines** | **Contradiction of count only.** No alarm references it either way. See F-06 |
| 5 | 3A framing: `ARCHITECTURE.md` is stale on decisions (ARCH-01) | It cites D-423, the newest entry in `DECISIONS.md` | **Contradiction.** Decisions current; the stale thing is session provenance (16 of 48 untagged). See F-07 |
| 6 | Prior evidence recorded **437** files for `ruff format --check` (WORK-11) | `make lint` → `440 files already formatted` | **Not a contradiction.** Consistent growth: three files added after C8, and the enforcement mechanism is unchanged and green |

Row 6 is included deliberately. A moved denominator on a growing codebase is expected; calling it
drift would dilute the five real corrections above it.

---

## 5. What execution did NOT reach

Phase 3A.5 ran only local, free, non-credentialed, repository-defined validation commands. Two
whole categories were therefore untouched, and neither absence is a gap in the phase — both are
deliberate. The **browser lane** was deferred by phase design: the Playwright suite shares the dev
Postgres with pytest (running both concurrently manufactures network-level failures that look like
regressions), and it needs both APIs plus both Vite dev servers up. The **live lane** is Phase 3B's
subject by definition. Beyond those, the whole-suite `make test` was not run because the targeted
batches answered every claim at claim level and a blanket run adds no claim-level evidence, and no
new test code was written because authoring tests exceeds "repository-defined validation commands"
in an audit.

Specifically not reached:

- **The Playwright set.** TEST-22's 5 specs; TEST-27's behavioural half (the `assertClean()` /
  `expectNotBlank` / `expectNotStuck` claims — only `make e2e-typecheck` ran, which proves the
  fixture compiles); WORK-40's three breadcrumb specs and
  `e2e/tests/learning/dashboard-chart-labels.spec.ts`, the *only* coverage of the module-private
  `buildDateLabelFormatter` (F-02); WORK-12's absent learning-web banner spec (F-14);
  `e2e/tests/chat/stream-disconnect-visible.spec.ts`.
- **Every live / deployed half — Phase 3B.** All AWS-credentialed make targets (`scan-traces`,
  `scan-logs`, `scheduler-evidence`, `scaling-evidence`, `image-check`, `profile-span`,
  `e2e-staging`, `load-staging-chat`, `load-staging-learning`, `security-scan-staging`);
  `scripts/scan_logs_pii.py` (reads staging CloudWatch, and is TEST-02's one non-pytest cite);
  `terraform plan`/`apply`/`init` (forbidden — live state); live ALB reachability (SEC-25/ARCH-03),
  live task size and count (COST-29, ARCH-10), staging schema state (WORK-03), applied-versus-
  unapplied terraform (WORK-08), and every LangSmith-side fact (SEC-23's retention, span
  attributes). **F-03 is the governing constraint on all of these: config is not live.**
- **Paid runs.** `question-gen-run` / `question-gen-authored` and `scripts/measure_*` spend real
  money and were not invoked.
- **The three new-test candidates.** Named only. Each would close a finding entirely, locally,
  against the dev fakes and dev Postgres, with no live or paid dependency — which is exactly why
  they are the highest-value post-audit test additions rather than 3B items:
  1. **SEC-13's cancel path** (F-11) — a test in `apps/chat-api/tests/` that cancels a resume and
     asserts the `__resume__` row survives, proving the coordinate/address leak the code path
     implies. This is the highest value of the three: it is a privacy boundary for minors, it
     currently has *zero* tests, and its single call site is one deletable `await`.
  2. **COST-06's flush-time branch** (F-12) — a test forcing an `IntegrityError` inside `run_plan`'s
     flush, proving the spend is incurred and not attributed. The fake gateway suffices; no paid run
     needed. Would resolve a standing `CONFLICT`.
  3. **REQ-27's fail-closed frozenset** (F-16) — a test pinning
     `AGE_BANDS_NOT_REQUIRING_PARENTAL_CONSENT` empty and `account_refusal_reason`'s behaviour, so a
     later addition to that set cannot silently open the COPPA gate.

  None was written. Recording them here is the deliverable; implementing them is not.
