# USER_DECISION_QUEUE.md — the decisions only the user can make

**Date:** 2026-08-20. **Phase:** 4 (documentation-reconciliation audit), writer Q1.
**Companion:** `FINAL_OPEN_WORK_REGISTER.md` (same directory) carries every open item with its
disposition and evidence. This file carries **only** the subset whose disposition is
`USER_DECISION_REQUIRED`, and it decides nothing.

## Purpose

Twelve entries. Each is a question the audit could not answer by reading code, reading AWS, or
running a test — because the missing input is a judgement about money, privacy posture, child
safety, launch risk, or what the organization is told. Every entry states what is observed, what
the options cost, and what happens if the question is left alone.

## The inclusion filter, stated so it can be checked

An item is in this queue only if **all four** hold:

1. The question is not answerable from evidence. Where evidence *does* answer it, the answer is
   recorded in the register instead.
2. No existing decision already settles it. A decision that delegated the call *with a criterion*
   (D-417 §B6's "implement what has a favourable quality/latency trade-off, and measure rather
   than assume") counts as settled once the measurement meets the criterion.
3. What remains is a judgement, not an action. "Decided in principle, parked in practice" is
   scheduling, not deciding.
4. The user is the only possible owner — spend, privacy/legal posture, child safety, org
   communication, or student-facing product taste (SPEC §5.10.3's register).

Four classes are therefore **excluded** and listed in full at the end of this file, so nothing is
lost by omission:

- **Implementation questions the evidence answers.** Example: whether the gateway needs an input
  token bound. The user's own standing rule (paid APIs carry max-token limits) already decides it;
  it is engineering work, not a decision.
- **Stale opens.** Items whose premise was falsified or whose blocker was removed after the
  document that raised them was written.
- **Frozen-by-decision items.** D-152's integration freeze is a deliberate user sequencing choice.
  Frozen items are parked with a reopen condition; they are not awaiting an answer.
- **Recommendations dressed as decisions.** An option a document names and declines to take is a
  specified option, not an open question.

## Standing facts that bind every entry

- **Repository and deployed state are never flattened.** Staging runs image tag
  `gha-44a12dfc9549`; local HEAD is `344f016`; the gap is 10 commits (`LIVE_BEHAVIOR_FINDINGS.md:295-329`).
  A repo-side fix is not live until a deploy.
- **The D-310 rotation was executed 2026-08-20** (`REMEDIATION_D310_ROTATION.md`). Any wording
  elsewhere implying the staging token exposure is live is historical.
- **The SNS `PendingConfirmation` warning in D-419 is resolved** — both topics read
  `SubscriptionsConfirmed 1 / SubscriptionsPending 0` on 2026-08-20T00:05:15Z.
- **Production is frozen.** Findings about `go.intellichoice.org` route to UD-8, never to a fix here.

## How to read an entry

Each entry carries: the question · why evidence cannot decide it · relevant existing decisions
(with line references where the extractors supplied them) · current observed state (repo and
deployed stated separately where they differ) · options with their consequences · whether it blocks
current work · the default safe action if deferred · and the `FINAL_OPEN_WORK_REGISTER.md` entry key
where the full evidence lives. Nothing here blocks the canonical-document proposal, and exactly one
entry — UD-1 — blocks current work, partially.

---

# UD-1 — Deploy the 10 undeployed commits to staging

**Register entry:** `LB-05-DEPLOY-GAP` (sub-question: `C6-UNATTENDED`)

**Question requiring judgment.** Should the 10 commits between `44a12dfc9549` and `344f016` be
deployed to staging now, before the next feature session, or after it?

**Why technical evidence cannot decide it.** Every technical input is already measured: the diff is
known, CI is green on HEAD, `make image-check` reads OK, and the e2e instrument
(`journey-student.spec.ts`) was proven byte-identical between the two builds, which is what makes
any comparison across them legitimate. What is left is a timing and risk-appetite call on a deploy
that also runs an additive migration, re-seeds, and fires five one-off tasks. D-417 §C9 deliberately
left that trigger with a human — engineering evidence can say the deploy is safe, it cannot say now
is the moment to spend the migration and the re-seed.

**Relevant existing decisions.** D-417 §C9 (`DECISIONS.md:28379-28384` — deployment stays manual,
the `push` trigger stays commented out); OPEN_DECISIONS #10 (`OPEN_DECISIONS.md:345-346`, same
conclusion); D-416 (`DECISIONS.md:28189` — the previous deploy and the defect its probe found);
D-421 (`DECISIONS.md:28581` — the migration); LB-05 (`LIVE_BEHAVIOR_FINDINGS.md:295-329`).

**Current observed state.**
- *Implemented in repository (HEAD `344f016`)*: 10 commits — `f7c9d10`, `a6da941`, `f6f84a2`,
  `899547f`, `2e301d6`, `e583cb9`, `b41efc7`, `5b324a0`, `6f107c1`, `344f016`. Includes the whole
  **B4 escalation series** (D-420 visitor note on the escalation draft, D-421 no duplicate staff
  email, D-422 the approval-modal note field), **C8** (`f6f84a2`, ruff format), and D-423's docs.
- *Deployed in staging*: none of the above. Both ECS services run `gha-44a12dfc9549` — learning task
  definition `:150` (2/2 running), chat `:148` (1/1). **B4's behaviour has never been observed
  live.** `6f107c1` is docs-only, so D-423's latency numbers do describe the deployed build.

**Options.**
- **A. Deploy now, then re-walk B4 live.** The only route to live evidence for B4; costs one
  migration, one re-seed, one deploy window.
- **B. Deploy after the next session** (B6 part 2, the `scope_guard`/retrieval overlap) so one
  deploy carries both. Fewer deploy windows; the gap widens to 11+ commits, so any live regression
  afterwards has 11+ suspects instead of 10.
- **C. Leave it and stop describing staging as current.** Free; every live probe must state its
  build SHA (already LB-05's standing rule), and B4 stays verified only in CI.

**Consequences to carry regardless of the option chosen.**
- Migration `8509c0486d8d` (D-421) applies on deploy, which is what **closes `WORK-03`** — today
  nothing in the audit can rule out an unapplied migration, and an unapplied migration is an outage
  waiting for the first request that touches the new table.
- **B4 has zero live evidence until a deploy happens.** Three shipped features (D-420/421/422)
  currently rest on CI alone.
- **Deploying HEAD destroys the pre-D-423 latency baseline.** LB-08 measured a guest QA turn at
  **10.55 s** against D-423's recorded 10.62 s; because `6f107c1` is undeployed, that 10.55 s is a
  clean *before* number for the ~22% overlap optimisation. **Record LB-08's numbers as the baseline
  before deploying**, or the improvement can never be measured against an untouched control.
- **RD-01's Python-side fix is inert until a deploy.** If the nightly-heartbeat mismatch is fixed on
  the Python side (`scheduled_jobs.py:61`), nothing changes in staging until a new image ships; the
  terraform-side fix is `apply`-only. That asymmetry is part of this decision.

**Sub-question (gate integrity).** After the RD-01 fix ships, does §2.6 criterion 6's "≥1 week
unattended nightly firing" restart clean, or may it be satisfied by an instrument repaired
mid-window? The `session-consolidate` schedule was created 2026-08-16T04:10:34Z, so the week is
arithmetically impossible before 2026-08-23T18:00Z on the current clock — but the instrument meant
to measure it (`JobCompletions`) has never published a datapoint. If the fix lands 2026-08-21, the
earliest **defensible** satisfaction is ~2026-08-28, not 08-23. This is exactly the kind of gate
that gets quietly fudged, which is why it is asked rather than assumed.

**Blocks current work?** **Yes, partially** — no live verification of B4 is possible without it, and
every "the docs describe HEAD, staging runs older code" statement stays double-sided.

**Default safe action if deferred.** Option C, plus the discipline LB-05 already imposes: state the
build SHA beside every live number, and record LB-08's baseline now. Nothing degrades; the gap grows.

---

# UD-2 — Paid-measurement and spend authorization bundle

**Register entry:** `SPEND-AUTHORIZATION` (rider: `DB-CONTENT-VERIFY`; prerequisite:
`WORK-13-FIXTURES`)

**Question requiring judgment.** Which of the deferred paid measurements, if any, is worth real
Bedrock/AWS spend now rather than carrying its claim as-documented — and is a time-boxed read-only
staging database session authorized?

**Why technical evidence cannot decide it.** Each arm's technical value is already characterised,
and in two cases characterised as *low*: the access-hint recall re-run "re-derives nothing
statistically at n=8/n=6", and the whole-directory e2e re-run has a known test-side cause and a
known fix. What is unresolved is whether the user wants to pay for confirmation of numbers that are
already documented, on an account where the free tier is at its limit and the monthly budget is
itself an open call (UD-3). That is a money-priority judgement.

**Relevant existing decisions.** D-351 (`DECISIONS.md:25118` — the instrument and the recall 1/8 ·
precision 5/5 baseline); D-371 (`DECISIONS.md:25481` — "measured, deliberately not tuned", 15.61¢);
D-303 (`PROGRESS.md:1561` — tutor-path reading level needs paid generation); D-322 row 5
(`DECISIONS.md:22916` — "Depth generation deferred to the near future — the ~$13–16 stays parked");
OPEN_DECISIONS #5 (`:219-231`, "DECIDED — spend it, but later"); D-193 (per-candidate commit, so
stopping part-way is safe); `LIVE_BEHAVIOR_EVIDENCE.md:140-160` (the sub-arm residuals are rulings,
not blockages).

**Current observed state.** Five arms, one wallet, nothing blocking:

1. **Access-hint recall re-run.** `scripts/measure_access_hint_live.py` exists, 8 GATED + 5 PUBLIC,
   `CONFIRM_PAID_RUN=1` guard. The rule is frozen (`access_probe_policy.py`, last constant change
   `e1ab0ad`, 2026-08-04) and `git diff 44a12dfc9549..HEAD` on it is empty, so the deployed build
   carries the identical rule and D-351's baseline still applies.
2. **Whole-directory staging e2e re-run** (`E2E_ARGS="tests/learning"`, ~37 tests). **Do this only
   after the WORK-13 fixture-isolation fix** ("give each test its own fixture student, or clear
   sessions in `beforeEach`"); running it first just re-measures a known bug.
3. **Two real-Bedrock eval opt-ins** (`CHAT_EVAL_REAL_BEDROCK`, `EVAL_REAL_BEDROCK`) — the only two
   pytest skips in the suite, structurally silencing the free suite on real-model eval quality.
4. **Tutor-path reading level** (D-303) — `tutor_chat_messages` holds 0 rows, so measuring it means
   paying to generate a fresh sample.
5. **Depth generation, ~$13–16** — 84 of 153 occupied `(topic, tier)` cells at target, short 189
   items ≈ 315 candidates at the measured 60% acceptance, ~3.5 h wall clock at the account's
   measured ~1.5 candidates/min (account-capped: 3 parallel streams == 1 stream). Behind a green
   preflight and an explicit `--run-budget-cents`. Decided in principle ("spend it, but later"),
   so what is asked here is only *now or not now* — same wallet, same shape, hence the bundle.

*Free-tier context:* CloudWatch alarm+metric monitors **at limit** (10.0/10.0, forecast 16.32);
X-Ray traces **91,077 of 100,000 used, forecast 148,599**.

*Rider — read-only DB session.* Four claims about database *contents* are unanswerable through the
control plane because both staging databases are `PubliclyAccessible: false` in private subnets with
Secrets Manager credentials: `SEC-27` (do `cost_reservations` rows exist), `INT-29` applied-state
(is the enrollment FAQ still `status: draft` in the deployed store), `WORK-20` (is migration
`6538a95bc990` applied), and `WORK-03` (is `8509c0486d8d` applied — see UD-1). This is **one
structural limitation wearing four hats**, not four gaps. A time-boxed, read-only, user-approved
session (bastion or session-manager port-forward, `SELECT` only) closes them; without it, "is the
migration applied on staging?" stays permanently unanswerable, which is a poor place for a launch
gate to sit.

**Options.**
- **A. Authorize none.** Free; the free suite keeps saying nothing about real-Bedrock eval quality,
  and arm 3 stays a structural blind spot rather than a measured one.
- **B. Authorize arm 3 only.** The only arm whose absence is a *coverage* gap rather than a
  re-derivation; cheapest defensible subset.
- **C. Authorize arms 2 + 3.** Buys the staging-contention answer and eval coverage — valid only
  after the WORK-13 fixture fix lands.
- **D. Authorize all five.** Complete, and it pays for two measurements whose own records say they
  re-derive nothing.
- **E. Authorize the read-only DB session** (independent of A–D; near-zero cost, closes four
  otherwise-permanently-open verification questions).

**Blocks current work?** **No.** Explicitly ruled residual-not-blocking in Phase 3B. WORK-13's live
claim is already **closed** — do not re-run it as if it were open.

**Default safe action if deferred.** **A** — carry each claim as-documented with its `n` and its
date, which is what the records already do. Note that arm 5's cost of deferral is only the
"incomplete" clause on C1. **Two operational preconditions if any generation arm is authorized:**
export the real model ids (placeholder defaults fail into an opaque circuit breaker) and pass the
budget flag; and never run `make test` concurrently with Playwright — they share the dev Postgres.

---

# UD-3 — Budget and gross-spend posture

**Register entry:** `BUDGET-GROSS-SPEND`

**Question requiring judgment.** Is the $20 net monthly budget raised, accepted, or re-scoped — and
is a gross (credit-excluding) control wanted *before* the credits run out?

**Why technical evidence cannot decide it.** The numbers are fully measured and internally
consistent. What is undecided is how much this environment is allowed to cost and how early the
user wants to see the number that credits are currently hiding. That is the user's money call,
explicitly (`DEPLOYED_INFRA_DRIFT_REGISTER.md:186`, `:362`).

**Relevant existing decisions.** D-136 (the price table and the cost model built on it). No decision
records the budget limit as a deliberate posture.

**Current observed state.**
- `intellichoice-staging-monthly-budget` reads `ActualSpend $20.939` against a `$20.00` limit
  (**104.7%**), `ACTUAL > 80%` notification in ALARM. It sets `IncludeCredit: true`, so it measures
  **post-credit** spend.
- Cost Explorer by `RECORD_TYPE`, 2026-08-01…08-20: `Usage $249.9294`, `Tax $1.30`,
  `Credit $-230.2909`. True run rate ≈ **$250/mo gross** (Bedrock Haiku 4.5 dominant at 93.8% of
  net; NAT ~$32.9/mo gross, net $0 on credits; the rest infra).
- **The gross figure is invisible to every net-spend control until the credits are exhausted**, at
  which point the same workload registers as roughly **12×** the configured limit. Credit expiry is
  not exposed by any read-only API, so the date of that step change cannot be predicted.
- *Repository:* terraform declares exactly one budget (`modules/observability/main.tf:1-23`,
  `limit_amount = tostring(var.monthly_budget_usd)`, default 20). **No gross/credit-excluding budget
  is configured anywhere.**
- *Deployed:* a **second, console-created budget exists outside terraform** — `"My Monthly Cost
  Budget"`, $10.00 limit, `CostFilters: null`, `ActualSpend $251.229`, two notifications in ALARM.
  It is currently the only control that sees gross spend, it is firing, it is invisible to
  `terraform plan`, and anyone can delete it in the console without trace.
- Additional cost inputs: alarm billing 24 of 34 alarms billable ≈ **$2.40/mo** (no cost-model
  document mentions per-alarm charges); X-Ray trace storage forecast to exceed free tier.
- Internal oddity recorded, not judged: the `FORECASTED > 100%` notification still reads OK while
  ACTUAL has crossed 100%.

**Options.**
- **A. Keep the $20 net budget as an early-warning tripwire *and* add a terraform-managed gross
  budget at ~$300** (`IncludeCredit: false`), then delete the console budget. Makes the real number
  visible and reproducible; small terraform change.
- **B. Raise the single net limit** to something the current run rate does not breach. Stops the
  false-positive alarm; leaves the ~12× step change entirely unsignalled.
- **C. Accept the breach and the alarm as-is.** Free; the budget alarm stays permanently in ALARM,
  which is how a spend control gets ignored.
- **D. Delete the console budget without replacing it.** Removes the shadow config and the only
  gross-spend visibility in the same move — not recommended.

**Blocks current work?** No. But it is the input to UD-2's arms and to UD-4's Multi-AZ option, so
those two get cheaper to answer once this is settled.

**Default safe action if deferred.** Leave both budgets in place and treat the console budget as
load-bearing (i.e. do not delete it during any cleanup). The deferral cost is a latent step change
with an unknowable date and no control that will see it coming. Separately and independently of the
decision: `docs/ARCHITECTURE.md:254-283` quotes D-136's price table without the AUD-F-28 resize
caveat, and learning-api runs at 512/1024, so those per-task columns understate by 2× — that is a
documentation defect either way.

---

# UD-4 — RDS staging data-durability posture

**Register entry:** `RDS-POSTURE`

**Question requiring judgment.** Is 1-day backup retention, deletion protection off, and both
databases in one AZ the accepted posture for the environment the §2.6 gate criteria were measured
on — and what does production require instead?

**Why technical evidence cannot decide it.** The configuration is fully measured and internally
consistent; nothing is broken. The undecided part is how much irreversible loss is acceptable on a
synthetic environment whose measurements are load-bearing for a launch gate. That is a
cost-versus-consequence judgement — a few dollars a month against a one-command unrecoverable
delete — and no amount of reading answers it.

**Relevant existing decisions.** **None recorded.** RD-09
(`DEPLOYED_INFRA_DRIFT_REGISTER.md:262-291`) states "Related decisions: none recorded" and flags
`Genuine decision required?: YES` (`:290`, `:363`). Adjacent: `multi_az` defaults `false` in both
modules with no environment override, so single-AZ is intentional-by-default but never written
down. OPEN_DECISIONS #4 (`:171-216`) touches retention as a *privacy* control, not a durability one.

**Current observed state** (2026-08-20T00:04Z, both instances identical): `BackupRetentionPeriod`
**1**, `DeletionProtection` **false**, `MultiAZ` **false**, both in **`us-east-1a`**, `db.t4g.micro`,
`StorageEncrypted` true, `PubliclyAccessible` false, Performance Insights off. Consequences as
measured: **one AZ loss takes out both databases**, and point-in-time recovery reaches back **one
day**. Repository and deployed state agree exactly — these are defaults nobody wrote down, not drift.

**Options** (the fix-cost asymmetry is the point of splitting them).
- **A. Record the current posture as the deliberate staging answer**, with its consequence, in
  DECISIONS plus a terraform comment. Zero cost; makes the risk explicit instead of accidental.
- **B. Turn on deletion protection only.** Effectively free; removes the single worst failure mode
  (an accidental destroy of the environment the gate numbers came from); costs one extra step
  whenever the environment is intentionally rebuilt.
- **C. B plus raise retention to 7 days.** Small cost (backup storage past the DB size); buys a real
  recovery window; still single-AZ.
- **D. Full production posture now** (Multi-AZ, 7–14 days, deletion protection). Roughly **doubles**
  the RDS instance bill for a synthetic environment — **this option interacts directly with UD-3**
  and should not be chosen before the budget posture is settled.

**Blocks current work?** No.

**Default safe action if deferred.** **A.** The posture is defensible for staging; what is not
defensible is that it is nowhere stated, so the next reader cannot tell a choice from a default.

**Documentation obligation that stands regardless of the option chosen.** The honest statement is not
"staging is under-protected" but "**the §2.6 gate criteria were measured on a 1-day-RPO, unfenced,
single-AZ environment**". That sentence is owed even if the posture never changes.

**Separable observation, not part of this decision.** Both instances run AWS **default** parameter
groups (`default.postgres16`, `default.mysql8.4`), so any parameter-level tuning claim in the
documentation cannot be true today. Cheap follow-up: grep the docs for tuning claims (shared
buffers, max connections, work_mem, innodb settings). If none exists, close it outright.

---

# UD-5 — Product-KPI alarm floor

**Register entry:** `KPI-ALARM-FLOOR`

**Question requiring judgment.** Does a product-KPI alarm get created now — and on which metric, at
what floor — or is "no product-KPI alarm while traffic is synthetic" recorded as the settled answer
to P1-10?

**Why technical evidence cannot decide it.** The measurement is complete and points both ways. It
proves the metrics are live and would sustain a floor **and** that staging traffic is synthetic, so
any floor value would be a guess about a load script's cadence rather than about students. Choosing
between "an alarm on a number nobody generates" and "a documented blind spot" is a product-priority
plus spend call.

**Relevant existing decisions.** D-377 §P1-10 (recorded the blind spot as an open item); D-401 (the
alarm-severity split, with `sessions_completed_floor` routed to the quiet channel); D-419
(`DECISIONS.md:28463` — the split applied, and `sessions-completed-floor` is **absent** from the
deployed `alerts-info` set, exactly as configured); RD-07
(`DEPLOYED_INFRA_DRIFT_REGISTER.md:244-260`) and DRIFT-19
(`REPOSITORY_DRIFT_REGISTER.md:248-255`), both framing it as "raise the floor once real traffic
exists, or record the disabled state as the accepted answer".

**Current observed state.** **Product-KPI alarm count deployed = 0**, proven three independent ways:
the prefix query returns `{"MetricAlarms":0,"CompositeAlarms":0}`; a regex over the unfiltered
34-alarm dump hits only a *job* heartbeat matched on the word "session"; and all four
`describe-alarms-for-metric` calls across both namespaces return `{"MetricAlarms":0}`.

- *Repository:* a **double guard** makes the alarm impossible in staging —
  `count = var.daily_completed_sessions_floor > 0 ? 1 : 0` (`app_events.tf:130-131`) **and**
  `environments/staging/main.tf:787` sets the variable to `0` explicitly, with the reason written
  out: *"Staging traffic is synthetic … Left at 0 (disabled) rather than guessed at."*
  `qa_answers_total` has no alarm resource anywhere.
- *Deployed:* exactly what the config predicts. **Deployed agrees with repo** — the gap is
  intent-versus-both, not drift. The framing "configured but absent" is wrong and should not be
  repeated.
- Both KPI metrics carry live data: `learning_sessions_completed_total` 11 datapoints / **Sum 8**
  over 30 days; `qa_answers_total{result=grounded}` 9 datapoints / **Sum 409** over 30 days. So the
  previous defence ("no traffic yet, a floor would just flap") is **falsified** — a floor would be
  meaningful today.
- Umbrella context: 63 custom app metrics carry data, 12 have alarms, and all 12 are app *plumbing*.

**Options.**
- **A. Record the disabled state as the answer to P1-10**, citing the terraform comment as the
  reasoning, and close the open item. Free; the KPI blind spot becomes explicit and accepted.
- **B. Raise the floor to a synthetic-traffic-appropriate value now.** Exercises the whole path
  (metric → alarm → SNS → mailbox) before it matters; risks an alarm that fires on quiet days and
  trains its recipient to ignore the channel — the exact failure mode D-401's quiet channel exists
  to avoid, and the same lesson D-418 already paid for.
- **C. Defer to first real traffic**, with the trigger written into the variable. Correct in
  principle; ties an observability gap to an event D-152 has frozen.
- **D. Alarm `qa_answers_total` instead** (409 grounded answers / 30 d is the denser series). Needs
  a new resource; same guessed-threshold problem.

**Sub-question.** The §7-R9 checkpoint-repair tripwire (`learning_checkpoint_repairs_total`) is
instrumented, carries data, and is charted on the live `intellichoice-staging-overview` dashboard —
and alarmed nowhere (`checkpoint|repair` over the 34-alarm dump returns `[]`). §7-R9 treats a rising
repair count as a tripwire, which currently means a human must be looking at a dashboard for it to
trip. Does it get an alarm, or is the dashboard-review cadence accepted as the detector? The
threshold itself is an engineering judgement once the answer exists — but if no threshold can be
justified from observed data, say so rather than guessing a number.

**Blocks current work?** No.

**Default safe action if deferred.** **A.** It is the only option that leaves the record honest at
zero cost, and it is what the terraform comment already says in everything but name. Do **not** turn
63/12 into a target ratio — alarming everything is how a single mailbox becomes unreadable, which is
the failure mode UD-6 is already partway into.

---

# UD-6 — Alerting endpoint ownership

**Register entry:** `ALERT-ENDPOINT`

**Question requiring judgment.** Should the page channel reach an organization address (or a second
endpoint) rather than one personal mailbox, and is a separate informational endpoint wanted?

**Why technical evidence cannot decide it.** Who receives production pages, on what address, is an
operational-ownership call for a solo maintainer. Setting `informational_notification_email` is a
one-line change once the answer exists; the answer is not derivable from any measurement.

**Relevant existing decisions.** D-401 (the alarm-severity split into page and informational
topics). No decision records the endpoint choice.

**Current observed state.** Exactly two SNS topics exist account-wide, each
`SubscriptionsConfirmed: 1`, `SubscriptionsPending: 0`, and both `KmsMasterKeyId: NONE`.
**Both subscriptions are the same address** — a personal `gmail.com` address rather than an
`intellichoice.org` one. So D-401's split is real at the **topic** level while the **mailbox stays
one**: 26 of 34 alarms page that address, 4 go to `alerts-info`, 4 are Application-Auto-Scaling
actioned, and no alarm carries both topics. Separation is achievable only by topic ARN plus a mail
filter.

- *Repository:* the informational endpoint is `coalesce(var.informational_notification_email,
  var.notification_email)` with the informational variable defaulting to `null` and
  **no setter anywhere in the repo** (DRIFT-89). So the single-mailbox outcome is what the config
  predicts, not drift. No KMS key is configured for either topic.
- *Deployed:* as above, with both subscriptions genuinely confirmed.

**The interaction that makes this worth deciding now.** Since 2026-08-16 that single mailbox has
been receiving **RD-01's permanent false-ALARM traffic** — four nightly-job heartbeat alarms that
can never leave ALARM because the deployed metric-filter patterns search hyphenated event names
while the Python emitter produces underscored ones. Each has exactly one state transition in its
entire history, `INSUFFICIENT_DATA → ALARM`, and they are routed to the confirmed page mailbox with
`ActionsEnabled: true`. **A permanently-false alarm is actively training the recipient to ignore
the page channel.** Alert-channel hygiene matters much less in the abstract than it does here.

**Options.**
- **A. Set `informational_notification_email` to a second address** so the two channels land in
  different mailboxes. One-line terraform change; makes D-401's split real in practice.
- **B. Move the page channel to an `intellichoice.org` address**, keeping informational on the
  personal one. Ties paging to org identity; requires that address to exist and be monitored.
- **C. Accept one mailbox with a mail filter** and record it as the deliberate answer. Free; the
  filter becomes an undocumented single point of failure.
- **D. Add topic encryption** (`KmsMasterKeyId`). Small; **this is the weakest sub-point** — alarm
  names and states are not sensitive. Do not let it dominate the ask.

**Blocks current work?** No.

**Default safe action if deferred.** **C**, stated explicitly rather than left implicit — *and fix
RD-01 first regardless of this decision*. The endpoint question is genuinely open; the false-ALARM
noise is not a decision, it is a defect, and leaving it in place degrades whatever endpoint is
chosen.

---

# UD-7 — Retention enforcement and the privacy notice

**Register entry:** `RETENTION-CLUSTER` (separate entry: `SEC-13-PURGE`)

**Question requiring judgment.** One coherent cluster of seven linked calls about how long minors'
data is kept, what actually enforces that, and what the guardians are told.

**Why technical evidence cannot decide it.** Every window that exists is implemented and tested; the
dry-run default is *good engineering*, not a defect. What cannot be measured is which retention
window is right for a K-12 product, when a job that deletes a student's learning history is allowed
to delete for real, and what a privacy notice promises to guardians. All three are commitments the
user must own rather than have drafted unilaterally.

**Relevant existing decisions.** D-114 §4 (the privacy-notice obligation: state the 90-day chat
window, the 90-day derived-fact window, the 365-day report window); D-153 (365-day `learning_events`);
D-331 (the byte measurement); D-333 (three windows — completed 30 / abandoned 90 / chat 180 — shipped
**dry-run by default**); D-322 §4; U7 §9.1–§9.4 (`U7_CHECKPOINT_CONSOLIDATION.md:261-273`);
OPEN_DECISIONS #4 (`:171-216`, decided as option D). Map references:
`DECISION_SUPERSESSION_MAP.md:736-742`, `:762-765`, `:770-774`.

**Precondition to carry verbatim.** D-333 records the user's own instruction: *"Before deleting any
eligible checkpoint, run long-term memory consolidation first."* **That ordering must be verified
implemented before any dry-run flip is recommended.** It is the safety precondition, not a nicety.

**Current observed state.**
- **Dry-run.** `apply_enabled()` is true only for an explicit `CHECKPOINT_RETENTION_APPLY=true`, with
  the reason written in place — *"A job whose failure mode is silently deleting a K-12 student's
  learning history does not get to delete by default."* So the 30/90/180 windows delete nothing today.
- **Unscheduled.** The retention job is **absent from terraform entirely**
  (`checkpoint_retention_cli.py`; zero-hit terraform grep), which the scheduled-jobs module explains
  as deliberate ("scheduling it before this one would be actively unsafe"). The four *other* nightly
  jobs do have AWS schedules, which sharpens the contrast. A retention promise over minors' data has
  no scheduled keeper. Both halves are pinned by passing tests, including
  `test_apply_is_off_unless_explicitly_true` — **a closure recorded on code presence alone would be
  wrong.**
- **Chat checkpoints unbounded in practice.** `CHAT_RETENTION_DAYS = 180` exists, with
  `_chat_thread_ids` classifying "chat" by **two** positive conditions precisely so an unprojected
  learning thread cannot be deleted under the chat policy. Same dry-run default, same absent
  schedule → in practice unbounded. Measured 2,178 threads / 35.6 MB = **19.3%** of checkpoint bytes.
- **Age floor unchosen** (U7 §9.1). The dry-run reports zero eligible threads at 30, 90 and 180 days,
  so the choice costs nothing today and can be made on principle rather than on reclaim.
- **Abandoned sessions are the growth driver and were scoped out.** `pre_exam` 64.7% + `study` 12.4%
  = **77% of checkpoint bytes**. The user scoped them out (correctly per the document, on the
  reasoning that mixing windows is how the wrong policy gets applied), and the document then
  counter-recommends a 90-day floor as "a bigger, more honest win". A recommendation is not a
  decision. U7 as scoped addresses 1.7% of bytes and 0% today.
- **Five windows, no reconciled statement.** D-114's 90/90/365, D-153's 365-day `learning_events`,
  and D-333's 30/90/180 coexist with no document reconciling them. Choosing any single floor in
  isolation adds a fourth family.
- **Privacy notice undischarged.** D-114 §4's obligation is carried on PROGRESS and discharged
  nowhere, and it is now arguably stale because two later decisions added windows.
- **REQ-18 invalid-output capture.** The `rag_answer` structured-output path has a measured ~2–4%
  `schema_invalid` rate and the invalid text is **deliberately not captured pending a PII decision**,
  so the failures cannot be diagnosed. Confirmed absent from both sides: no schema-invalid metric
  filter exists on any of the five log groups, and no env-var name on either task definition matches
  `SCHEMA|INVALID|CAPTURE|REPAIR|SAMPLE`. Note the precision: what is proven is the absence of
  **CloudWatch-side capture**, not the absence of the underlying event.

**Options** (each sub-call is separable; they are bundled because answering one in isolation is what
created the sprawl).
- **(i) Lift D-333's dry-run** — after verifying the consolidation-first ordering. Turns a shipped
  policy into an enforcing one; the failure mode is deleting a student's history.
- **(ii) Keep dry-run and schedule the job in dry-run first.** Produces real eligibility numbers
  with zero deletion risk; costs one more window before anything is enforced.
- **(iii) Choose the §9.1 age floor now, on principle.** Free today (zero eligible threads); the
  choice then feeds the notice text.
- **(iv) Scope chat checkpoints** (accept 180 as the policy and schedule it) **or** record them as
  deliberately unbounded. The second is defensible only if written down.
- **(v) Revisit abandoned sessions as their own session** (77% of bytes) **or** accept the growth
  explicitly. Accepting silently is the current state and the worst of the three.
- **(vi) Reconcile the five windows into one statement** before writing the notice. Prerequisite for
  (vii), and the cheapest item in the cluster.
- **(vii) Discharge D-114 §4's privacy notice** — content and timing are user-owned. It must state
  five windows, **some of which do not currently enforce**; say so honestly rather than describing
  intent as practice.
- **(viii) REQ-18:** may schema-invalid LLM output — possibly containing student text — be stored for
  triage? Yes with redaction / yes in a bounded sample / no, and accept the undiagnosable failures.

**Blocks current work?** No — but it is the **first unblocked step** toward a launch-gating privacy
requirement, and it is not frozen by D-152. The causal chain: no reconciled retention policy → no
statable windows → the first-visit notice cannot be written → S45 cannot build it → and S45 is
frozen anyway. That makes the retention decision the one link in the chain that can move today.

**Default safe action if deferred.** Keep dry-run, keep the job unscheduled, and add a dated note to
D-114 §4 recording that the notice obligation now spans five windows across three decisions with no
reconciled statement. The deferral cost is that a privacy commitment about minors' data remains both
unenforced and unstated.

**Adjacent, deliberately kept separate.** `SEC-13-PURGE` (DRIFT-09) — the location purge is not in a
`finally` block and the cancelled-resume path is unguarded, with zero tests on a minors'
location-privacy boundary. That is engineering remediation, not a decision, and D-420 deliberately
added redacted visitor free text to exactly the `checkpoint_writes.__resume__` column no retention
job covers. Do not fold it into this cluster.

---

# UD-8 — Organization communications

**Register entry:** `ORG-COMMS`

**Question requiring judgment.** Is the production security report sent, and who signs off the §7-R1
accepted risk?

**Why technical evidence cannot decide it.** Sending a message to the organization is an external
action only the user can take (non-negotiable rule 4: every external action needs human approval).
Whether the report was *ever* sent is **unestablished** — the draft records no send date, no
recipient, and no confirmation, and its recipient placeholders are unfilled. Three separate claims
independently ask the same question, which is itself evidence the answer is "no".

**This is live user work, not frozen work.** INT-28 establishes that org notification is **permitted**
under the D-152 freeze — it is one of the only two live actions under it. Do not file this behind the
freeze.

**Relevant existing decisions.** D-153 §5/§7; S42_DISCOVERY §6 (`docs/S42_DISCOVERY.md:199-268`);
INT-02/INT-28 (reporting classed as permitted); §7-R1 (`docs/INTEGRATION_PLAN.md:502-517`);
D-152 §4; D-146 (the enrollment FAQ).

**Current observed state.**
- `docs/S42_SECURITY_REPORT.md` is a bilingual hand-off drafted 2026-08-02, intended to go as one
  message to the production operator. **Two High findings against a live production system sit in an
  unsent draft.** S42_DISCOVERY §6 catalogues six-plus findings (High → Informational) as the org's
  decisions.
- The client-supplied-role finding moved from *accepted* to *to be fixed by the org*, joining
  §6.1/§6.3/§6.4 on the list the user will send. The prescribed fix is inside the existing system
  (allowlist `Parent`/`Student`/`Tutor` at create with a 400 otherwise; accept no role in the
  duplicate-unverified branch; keep `Manager` a database/admin operation).
- **§7-R1's sign-off is orphaned.** The password-HMAC key and write-capable DB credentials live in
  the production repo's permanent history, so repo plus network access lets an attacker set a known
  password hash and log in as that user. Accepted as a permanent risk "to be signed off by the org at
  S42" — an occasion D-152 freezes, with no completion visible. Compounding: rung 1 (the confirmed
  viable data path) makes I14's password-hash-fingerprint revocation check **impossible by design**,
  so the mitigation named for R1 is unavailable rather than merely unbuilt.

**Options.**
- **A. Send the security report now** (fill the recipient, send, record the date in DECISIONS).
  Discharges the highest real-world-consequence item in the corpus; one answer closes SEC-32,
  INT-13 and INT-25 together.
- **B. Send a reduced version** covering only the two High findings. Faster; the Informational
  findings stay unreported and the draft stays half-live.
- **C. Do not send, and record that decision with its reasoning.** Free; two High findings against a
  system serving real users today remain unreported, which is a position that should be explicit
  rather than accidental.
- **For §7-R1 separately:** accept the risk into launch explicitly with a dated DECISIONS line, **or**
  make the org sign-off an explicit exception to D-152 and obtain it. An unmonitored acceptance is
  not an acceptance.

**Riders (same audience question, different recipients — do not bundle blindly).**
- **ORG_TIME hours ask** (`ARCH-35`). All three `ORG_TIME` env vars are present on both deployed task
  definitions with `ORG_TIMEZONE = America/Chicago`, `ORG_TIME_CONVENTION = local_dst_aware`, and
  **`ORG_TIME_CONFIRMED = false`**. Anything time-of-day dependent shown to students or parents is
  running on assumed hours. This is a one-message ask whose answer flips one variable; it stays
  BLOCKED-on-org. **Note:** D-153 §4's guard is buildable now, without integration.
- **Enrollment FAQ approval nudge** (`INT-29`). The Q&A app's canonical guest question "How do I
  enroll a student?" is gated on `public-enrollment-faq`, whose manifest is still `status: draft`
  (verified against `knowledge-content/manifests/public.yaml`). Four draft claims need org sign-off;
  on approval the work is editorial only (correct four facts, drop the DRAFT banner, flip
  `draft → approved`, re-run `make knowledge-load`) and `effective_from` is already past, so it goes
  live immediately. **Different audience — the org's content owner, not the system operator — so it
  must not be bundled with the security report or the timezone ask.** Blocked on the org's content
  owner. Cheap free check worth running first: which source the deployed guest answer actually cited,
  before accepting the "sole launch gate" claim.

**Blocks current work?** No, in the sense that no code waits on it. Yes, in the sense that the
enrollment FAQ gates the guest journey's most obvious question.

**Default safe action if deferred.** None is safe in the usual sense — deferring means findings about
a live third-party system stay unreported. The minimum honest action is to record, with a date, that
the report is deliberately unsent and why.

---

# UD-9 — Minors-safety policy set

**Register entry:** `REQ-32-SAFETY`

**Question requiring judgment.** Are Bedrock Guardrails adopted, is the "separately approved" safety
policy defined, or is SPEC amended to match what exists?

**Why technical evidence cannot decide it.** The engineering facts are settled and thin. What the
policy *says* — escalate to whom, tell whom, on what signal — is a safeguarding decision on a
platform whose primary users are minors. SPEC names the policy without defining it, so there is
nothing to implement against.

**Relevant existing decisions.** SPEC §5.11.4 and §5.12.2 (name the "separately approved safety
policy"); SPEC §5.25.1 (lists Guardrails as a gateway-provided feature); D-251
(`docs/HINT_SOLUTION_REVIEW.md` — the planned LLM hint/solution review instrument, planned and not
built; two prior hint-quality scorers already failed). No decision defines the routing policy.

**Current observed state.**
- **Guardrails are absent.** A repo-wide case-insensitive grep for "guardrail" across `packages`,
  `apps`, `scripts` including `.tf`/`.yaml`/`.json` returns **zero hits**. SPEC §5.25.1 nonetheless
  lists Guardrails as a gateway feature — the other eight listed features are present and quotable
  (`call_timeout_s=20.0`, retry loop, `_HARD_MAX_OUTPUT_TOKENS=4000`, `session_budget_cents=50.0`
  checked pre-call, circuit breaker, `worst_case_cost_cents`), so the gap is in the feature *list*,
  not in the gateway's implementation of what it does claim. Gateway-level PII redaction is also
  absent — redaction lives at callers.
- **The safety screen is a fixed ten-item substring match** on one of two surfaces. It
  short-circuits to a fixed response and persists `flagged_for_review=True`. It has **one caller**
  (`learning-api`); **no equivalent screen exists anywhere in `apps/chat-api`**. No approval
  artifact, policy document, or escalation destination beyond the boolean flag was found.
- **One test guards it repo-wide.** `test_self_harm_keyword_short_circuits_to_a_fixed_response_and_flags_for_review`
  executed and passed in a clean run; a grep for `safety_screen|crisis|self_harm|safety_flag` across
  `apps/` and `packages/` hits that one file and no other. The pass is necessary and nowhere near
  sufficient — a green test must not soften this entry.
- `HintResponse.answer_revealed = false` is present and correct.

**Options.**
- **A. Adopt Bedrock Guardrails** on both surfaces. Buys a maintained, model-side control instead of
  ten substrings; adds per-call cost and latency, and needs a configuration and an owner.
- **B. Define the approved routing policy** (what signal, what response, escalate to whom, notify
  whom) and implement it deterministically on both surfaces. Keeps the control in-repo and testable;
  the policy content is the user's to write and may want counsel input.
- **C. Amend SPEC** to describe the ten-keyword screen as the intended control and remove Guardrails
  from §5.25.1's feature list. Cheapest; leaves a K-12 product with a substring screen on one of two
  surfaces and no escalation destination.
- **D. A or B, plus extend coverage to `chat-api`** regardless of which control is chosen. The
  single-surface gap is the most concrete defect in this entry and is independent of the Guardrails
  question.

**Blocks current work?** No.

**Default safe action if deferred.** Nothing changes, which means a self-harm/abuse signal on the
chat surface is not screened at all and a flagged signal on the learning surface reaches no human by
any mechanism other than someone reading a boolean column. If deferring, at minimum record that
state as an accepted risk with a date — do not leave it implied. Keep the SPEC feature-list amendment
separable so the eight features that *are* present stop being under-credited.

---

# UD-10 — First-visit disclosures and the legal track

**Register entry:** `DISCLOSURES-LEGAL` (separate entry: `REQ-27`)

**Question requiring judgment.** Does the first-visit notice ship eight disclosures or eleven; is
counsel engaged; and who owns and schedules the §6.1 legal track?

**Why technical evidence cannot decide it.** The evidence establishes precisely which three
disclosures describe behaviour that does not exist. It cannot decide whether to build those
behaviours or drop the disclosures — and dropping one of them silently removes a right the SPEC
gestured at. Engaging counsel is an organizational act with cost and lead time. Both are product and
legal calls.

**These decisions are not frozen.** The S45 *build* stays behind D-152. The eight-versus-eleven
ruling, counsel engagement, and the §6.1 track's ownership are product and documentation work and can
proceed. Also: **the §6.1 enumeration shipped 2026-08-15** as `docs/FIRST_VISIT_NOTICE.md`
(`da2549f`, 237 lines) per DRIFT-99/DRIFT-101 — do **not** repeat "the track has not started". The
load-bearing prerequisite is discharged; the ruling and the build are not.

**Relevant existing decisions.** D-129 (T-02 — S45 transcribes the enumeration rather than drafting
it); SPEC §5.1.2 (the eleven disclosures, `docs/SPEC.md:96-110`); SPEC §5.1.1 (`:38-78` — counsel
review as a mandatory production release gate: COPPA as amended 2025-04-22, FERPA, PPRA, state laws,
breach notification, school contracts); SPEC §6.1 (the legal-and-policy track); D-114 §4; D-127 §3;
D-152 (S45 frozen). Register sources: DRIFT-08 (`REPOSITORY_DRIFT_REGISTER.md:112-121`), DRIFT-11
(`:147-156`), DRIFT-36.

**Current observed state.**
- **No DECISIONS ruling exists** on how many disclosures ship. The only two non-ledger hits are
  *recommendations* (`FIRST_VISIT_NOTICE.md:220`, `PROGRESS.md:982`), neither in DECISIONS.md.
- **Three of eleven describe behaviour that does not exist:** §2.11's "challenge learning results"
  (the phrase occurs once in the whole SPEC with no section, endpoint or UI — the *reporting* half is
  real, the *challenging* half is a right the product does not provide); §2.8's solution images (S29
  deferred, no upload path); §2.5's tutor/branch-manager sharing (roles gate the Q&A corpus, but
  learning-api has no tutor- or manager-facing view). A disclosure whose "True because" row reads NOT
  BUILT must not ship as written.
- **The notice itself is absent.** An exhaustive grep for `parental|consent|under 13|guardian` across
  `apps/learning-web/src` returns **zero** matches; 11 screens exist and none is a notice.
- **Counsel review has no consolidated launch-checklist home** (DRIFT-36) and, on the evidence, has
  not started. Its leading ledger status is a bare `CURRENT`, so a status-only sweep would miss it —
  yet it is arguably the hardest launch gate in the corpus.
- **The §6.1 track has no owner, no schedule and no status field** anywhere; it is tracked only by
  narrative mentions in two files. What remains missing after the enumeration shipped: the Privacy
  Notice and consent text, counsel review, an owner, and a schedule.

**Options.**
- **A. Ship eight**, and attach §2.5, §2.8 and §2.11 to the work that makes each true. The
  document's own recommendation; the notice states nothing untrue; dropping §2.11 silently removes
  the only place the right to challenge results is asserted.
- **B. Ship eleven and build the three behaviours** (a challenge route, an image upload path, a
  tutor/manager read view). Honours the SPEC as written; three unscoped features before a launch
  gate.
- **C. Ship eleven with the three reworded** to describe intent rather than capability. Fast; states
  three near-truths to minors and their guardians, which is the worst option for a document whose
  purpose is candour.
- **For counsel, separately:** engage now (unblocks the §6.1 text and the production gate) · engage
  at pilot (cheaper, and the gate then sits on the critical path) · record explicitly that launch
  proceeds without counsel review (not recommended — SPEC §5.1.1 makes it mandatory).
- **For the §6.1 track:** name an owner and a date now (cheap, and it is the unblocking act for a
  launch gate) · leave it narrative-tracked (the current state, in which nobody is accountable).

**Blocks current work?** No code waits on it. It gates a launch requirement whose owning session
(S45) must not start — a structural shape worth naming to the user directly, since SEC-09 has the
same one.

**Default safe action if deferred.** Record, with a date, that the eight-versus-eleven ruling is
outstanding and that counsel has not been engaged, and add an owner field to the §6.1 block even if
the owner is "user, unscheduled". The deferral cost is that a mandatory production gate stays
invisible to any status sweep.

**Separable and not a decision.** REQ-27's frozenset test (the token-claim contract) is owed
regardless of any answer here and is filed as implementation work.

---

# UD-11 — LangSmith account retention

**Register entry:** `LANGSMITH-RETENTION` (pair with: `LANGSMITH-INGEST`)

**Question requiring judgment.** What is the LangSmith account's run-retention setting, and is that
retention acceptable for a product whose primary users are minors?

**Why technical evidence cannot decide it.** Two reasons, both structural. The setting has **no
in-repo expression at all** — the repository is silent, so it cannot be right or wrong about it — and
it is reachable only through LangSmith's own console. `HIDE_INPUTS`/`HIDE_OUTPUTS` are *client-side*
flags: the repo can show what it intended to send, never what the SaaS stored or for how long. No AWS
API can report a third-party account setting. And even with the number in hand, whether it is
acceptable is a privacy judgement on minors' data.

**Relevant existing decisions.** D-242 (LangSmith tracing adopted); non-negotiable rule 1 (no PII in
LLM payloads, traces, or logs). Sources: `DEPLOYED_INFRA_STATE_EVIDENCE.md:592-596`,
`DEPLOYED_INFRA_DRIFT_REGISTER.md:388-390`.

**Current observed state.** *Repository:* client-side masking flags configured; zero expression of
the account retention setting. *Deployed:* `LANGSMITH_TRACING = "true"`,
`LANGSMITH_PROJECT = intellichoice-staging`, `LANGSMITH_WORKSPACE_ID` present as plain env on both
task definitions, one shared API-key secret ARN — and nothing more. Genuinely out of reach from this
AWS account. Routed out of Phase 3B-1 as external and out of 3B-2 as not-its-work; nothing has
verified it.

**Options.**
- **A. Read the setting and record it** (open LangSmith → workspace settings → retention; a
  two-minute action only the user can take), then judge. The only option that produces a fact.
- **B. Reduce retention to the shortest the plan allows**, unread. Safe direction; may break trace
  debugging windows and still leaves the current value unknown.
- **C. Disable tracing until the setting is known.** Maximally conservative; removes the main
  instrument for debugging a production LLM path, and NAT egress (~$32.9/mo gross) exists largely to
  serve it.
- **D. Record it as an accepted unknown** with a dated note. Free; a privacy-relevant unknown about
  minors' data stays open indefinitely, which is how it has stayed open so far.

**Pair with the ingest-failure investigation.** `LangSmithIngestFailed` 14-day Sums are learning-api
**2800**, chat-api **1441**, flapping rather than pinned (learning-api flipped OK→ALARM→OK five times
between 2026-08-17T03:02Z and 23:12Z), every flap landing in the quiet `alerts-info` topic by
deliberate D-401 design — so the tracing leg is substantially broken right now and nobody is paged
about it. The **cause** is undetermined (403 versus quota versus timeout needs log content). This
matters here in a specific, limited way: **less data reached the SaaS than the documents assume**,
which moves the privacy question in the *safe* direction — **but it is not a substitute for reading
the setting.** Two notes: if the cause turns out to be quota or plan limits, the remedy becomes a
paid-plan question, which is a separate user call; and if the failures are network-shaped, the NAT
and the ingest failures are the same investigation.

**Blocks current work?** No.

**Default safe action if deferred.** **D**, with the dated note — and take the two-minute read at the
next convenient moment, because the alternative is that this stays open forever. It is the one
privacy-relevant item in the infrastructure lane that no amount of AWS reading can close.

---

# UD-12 — One-line confirmations bundle

Six items that each need a single sentence from the user, not a discussion. They are bundled because
individually none justifies its own round-trip. **None blocks current work; each has a stated safe
default.**

### UD-12(a) — D-341 governs over D-322 §7

**Register entry:** `DIFFICULTY-TIERS-CONFLICT`

- **Question.** Confirm that D-341 governs and D-322 §7 gets a dated annotation.
- **Why evidence cannot decide it.** Both sides are **explicit user decisions**, so the corpus's own
  ranking rule (explicit user decisions outrank recommendations) is powerless — it cannot break a tie
  between two of them.
- **Existing decisions.** D-322 §7 (`DECISIONS.md:22918`, verified verbatim:
  `| 7 | **Edit difficulty_tiers to match the judge** | as recommended |`, 2026-08-14) versus D-341
  (`DECISIONS.md:24523-24528`, verified verbatim: keep the declarations unchanged, treat single-tier
  coverage as expected content gaps, do not modify the taxonomy because the bank is thin, 2026-08-15).
  D-342's supersession list names **D-322 §5, not §7**. D-417 §D10 fixed only OPEN_DECISIONS #7.
- **Observed state.** D-322 §7 stands unannotated and contradicts the later active decision. In
  practice **D-341 is being followed** — D-342 rests on it and D-417 §D10 rewrote OPEN_DECISIONS to
  defer to it. D-341's own reopen condition, verbatim: *"The current single-tier coverage is
  temporary because we plan to generate and approve more problems across the missing difficulty tiers
  later. Treat these as expected content gaps, not taxonomy/declaration errors."*
- **Options.** (i) Confirm D-341 governs; annotate D-322 §7 with a dated pointer. (ii) Reinstate
  D-322 §7 — which would be a fifth re-derivation of a question D-341 exists specifically to stop.
- **Default if deferred.** (i) is what the codebase already does; the only cost is that the decision
  log contradicts itself in one row. **Frame this as a confirmation, not an open architectural
  question.**

### UD-12(b) — D-141 §5's trim: which stands, the approval or the recommendation?

**Register entry:** `D141-TRIM`

- **Question.** D-141 §5 says *"Recommendation: do not trim, and this supersedes the approved
  action"* — a recommendation overriding a prior explicit **user** approval. Which stands?
- **Why evidence cannot decide it.** The ranking rule refuses to let a recommendation beat a user
  approval, and no later user decision in the chain restates the disposition
  (`DECISION_SUPERSESSION_MAP.md:596-598`, `:640-643`). So the action's true status is indeterminate
  by construction.
- **Existing decisions.** D-141, D-148. Domain: memory-consolidation trimming (scheduled jobs).
- **Observed state.** Indeterminate; no reopen condition stated. Low blast radius — a trim setting —
  but it is one of only **two** places in the whole supersession map where a recommendation is
  asserted to beat a user decision (the other is UD-12(a)'s neighbour, D-313 versus D-341).
- **Options.** (i) The approved trim stands; annotate D-141 §5 as a recommendation that did not
  supersede it. (ii) The recommendation stands; record it as a user decision with a date.
- **Default if deferred.** Neither is being acted on today, so nothing breaks — but the map will keep
  reporting this as unresolved on every future pass.

### UD-12(c) — Student-facing prose quality

**Register entry:** `PROSE-QUALITY`

- **Question.** Is the ~13% prose-defect class accepted as residual risk, parked like the quantity
  findings, given a one-off pass, or stopped by a gate rule — and the same for the repeated context
  sentence?
- **Why evidence cannot decide it.** Both facts are fully measured. What cannot be measured is
  whether they matter to a K-12 reader enough to spend a gate rule or an authoring pass. SPEC
  §5.10.3's register makes student-facing language the user's call.
- **Existing decisions.** D-289 (auto-approval with **no** sampling; a 20-item-per-wave spot check
  was recommended and declined, with the consequence stated in the entry: *"prose defects now reach
  students unless someone reads the bank for another reason"*); D-342 parks **quantity** findings
  only, and whether the prose class is parked under it is **not stated**
  (`DECISION_SUPERSESSION_MAP.md:1726-1728`). For the repeated sentence: **no decision exists** —
  OPEN_DECISIONS #10 is headed `✅ ALL DECIDED` while annotating this sub-item **`not raised`**
  (`:334`, `:347-349`), and it is absent from D-417's twelve answers. Carried unchanged at
  `PROGRESS.md:1567-1570` and `:12353-12354` ("cosmetic, no gate check").
- **Observed state.** `rendered_question` is `context_block + "\n\n" + stem`, and the model writes the
  setup into both: **15 of 92** items with a context block repeat the opening sentence, concentrated
  in new content — **6 of 8** in one recent batch against **9 of 84** pre-existing. No gate checks for
  it. The other four of OPEN_DECISIONS #10's five sub-items are genuinely closed.
- **Options.** (i) **Accept and delete the item** — free; 15 items keep reading twice and the 6-of-8
  rate means the share grows with the bank. (ii) **One-off content pass on the 15** — bounded
  authoring work; the generator keeps producing them. (iii) **Preflight gate rule** (reject a
  candidate whose stem opens with the context block's first sentence) — stops the source; one more
  rule that can be wrong, on a pipeline `docs/QUESTION_GENERATION.md` says to read before changing.
  (iv) **(ii) + (iii)** — fixes both the stock and the flow.
- **Default if deferred.** (i), **but say so explicitly** — the honest cost of silent deferral is
  that the ✅ on OPEN_DECISIONS #10 currently conceals a question that was never asked, which is the
  exact failure mode D-417 spent a section on. Lowest stakes in this queue; rank it last.

### UD-12(d) — SPEC §5.26.3's internal NL2SQL pipeline

**Register entry:** `DRIFT-66-NL2SQL`

- **Question.** Build it, scope it, or formally drop it — one DECISIONS line either way.
- **Why evidence cannot decide it.** It is an **unowned spec requirement**: a corpus-wide `NL2SQL`
  grep returns 10 non-ledger hits and every one addresses only the *runtime* prohibition or the
  untestability of the SQL-parser eval item. Nothing anywhere says the internal dev/eval/analytics
  variant is planned, dropped, or partially present — in **either** direction.
- **Existing decisions.** None. `SPEC.md:2641-2643` carries no amendment or deferral marker.
  Register: `REPOSITORY_DRIFT_REGISTER.md:759`.
- **Observed state.** The **runtime prohibition is separately confirmed intact**: no `QueryIntent`
  model, every RAG query a parameterized `select()`, and the only raw `text()` calls in runtime paths
  are advisory locks, `pg_notify`, and a parameterized purge. The internal variant remains unowned.
  Graded LOW because nothing user-facing depends on it; the *unowned* property is what makes it worth
  a sentence. Not blocked by D-152.
- **Options.** (i) One DECISIONS line formally dropping it — the cheapest possible resolution.
  (ii) Scope it to a future session. (iii) Build it — no current requirement asks for it.
- **Default if deferred.** It stays an unowned spec requirement that every future audit re-discovers.

### UD-12(e) — REQ-39's "Current estimated level" wording

**Register entry:** `REQ-39-ESTIMATED-LEVEL`

- **Question.** Ship the wording, or disposition the requirement?
- **Why evidence cannot decide it.** The absence is exhaustive, and there is a real argument that the
  intent is already met by a different route. Which of those is true is the user's read.
- **Existing decisions.** SPEC §5.10.2 (IRT deferred); D-409 (mastery bands in `ReportView`). No
  disposition exists for the wording.
- **Observed state.** `"Current estimated level"` hits only `docs/SPEC.md:1111`, `:1451` and the
  ledger — **zero hits in either web app** — and `grep -rniE "estimated"` over both frontends exits
  1, so the substring does not occur anywhere in either app's source in any case. What renders
  instead is `<h2>Mastery by skill</h2>` and a flat percentage with no estimate hedge. The only
  level-shaped labels shipped are per-question difficulty (`Level ${difficulty}`) and hint-ladder
  position, neither of which is the ability estimate SPEC wants hedged. The bootstrap weights are
  exact and no IRT/Bayesian implementation exists (only deferral docstrings).
- **Options.** (i) **Ship the wording** — cheap; satisfies §5.10.2 literally. (ii) **Disposition the
  requirement**, on the grounds that D-409's mastery bands meet the hedging *intent* without a
  numeric score — the strongest argument, and the reason this is a judgement rather than a string
  edit. (iii) Do neither and leave REQ-39's UI half unverifiable.
- **Default if deferred.** (iii), which is the current state. Non-negotiable rule 10 (growth-oriented,
  age-appropriate student-facing language) is what makes this more than a string; both (i) and (ii)
  are cheap, so it should not sit in a queue long. Note the user may already consider it satisfied.

### UD-12(f) — Committed org-draft policy

**Register entry:** `RISK-R7.2`

- **Question.** Are committed outbound drafts allowed, and which credential-mention policy governs a
  sent message?
- **Why evidence cannot decide it.** Both are about what leaves the project, which is the user's
  call. Neither is an editorial question.
- **Existing decisions.** `INTEGRATION_PLAN.md:619` states outbound communication drafts are kept
  "outside this repo (gitignored … not committed)"; D-153 §5/§7; CLAUDE.md's never-quote-the-secret
  rule.
- **Observed state.** **Three committed drafts exist** — `S42_ORG_ASKS.md`, `S42_SECURITY_REPORT.md`,
  `ENROLLMENT_FAQ_APPROVAL.md`. Either the rule was silently superseded or the files violate it, and
  **no document says which**. The two org-facing S42 drafts implement **opposite** policies on
  mentioning the committed-credentials issue: `S42_ORG_ASKS.md:366-371` excludes it from any sent
  message; `S42_SECURITY_REPORT.md:88-89` and `:151-153` include it as known context. **Neither draft
  quotes a secret value**, so this is a policy inconsistency, not an exposure.
- **Options.** (i) Allow committed drafts; amend `INTEGRATION_PLAN.md:619` and pick one
  credential-mention policy. (ii) Keep the rule; gitignore the three drafts and remove them from
  history-going-forward. (iii) Allow them as a documented exception, scoped to org hand-offs.
- **Default if deferred.** The inconsistency persists and a future reader cannot tell which policy
  governs the message they are about to send — which matters most at exactly the moment UD-8 is
  acted on. If the user rules quickly, the documentation half collapses to one sentence in
  `INTEGRATION_PLAN.md` and one in each draft.

---

# Excluded from this queue, with reasons

Sixteen rows. Everything considered and rejected is listed, so omission is never silent. Where a
reopen condition exists, it is stated.

## The seven NOT-GENUINE verdicts from the user-decision extraction (reasons verbatim)

| # | Considered | Excluded because (verbatim verdict) | Reopen condition |
|---|---|---|---|
| E-1 | **OPEN_DECISIONS #8 — the D-310 dev-token posture** | "NOT-GENUINE — the only live question in item 8 (rotate or not) was **resolved by action** on 2026-08-20 with user approval and full verification. What is left is one manual step and two engineering tasks." | Item 8's stated trigger ("staging stops being synthetic") is **not met** and is frozen behind D-152 regardless. Item 8 should be marked **superseded-operationally**, not left ⏸ UNCHANGED, because its current wording tells the next reader the exposure is live. |
| E-2 | **OPEN_DECISIONS #6 — video coverage and the YouTube API key** | "NOT-GENUINE — parked by an explicit user instruction eight lines into the file, with no reopen condition met and nothing after D-417 touching it." | The user schedules a further seeding run and provisions `YOUTUBE_API_KEY`. Catalog is healthy at 102 of 112 skills servable (497 videos, 363 active-and-approved); the 10 uncovered skills are a *content* question about the pinned channel (D-337: no further run changes them). |
| E-3 | **When to start S43/S44 integration** | "NOT-GENUINE — **PARKED_BY_DECISION**, reopen condition (an explicit user statement) not met, confirmed against every decision after D-417." D-417 §A1 states the freeze is "not 'nearly met'" — no accumulation of readiness reopens it. | An explicit user statement that integration is starting. Frozen by choice, not stuck. |
| E-4 | **An answer cache with citation-clamped TTL (substantive stage 1)** | "NOT-GENUINE — contingent on a requirement that does not exist. It is a *specified option*, not an open question; promoting it would be re-litigating rule 5." | Only if a substantive stage 1 ever becomes a requirement. |
| E-5 | **Proceeding with the `scope_guard`/retrieval overlap** | "NOT-GENUINE — covered by an accepted decision that delegated the call with a criterion the measurement meets." D-417 §B6's criterion is "implement what has a favourable quality/latency trade-off, and measure rather than assume"; the measured ~9.6 s → ~7.5 s (~22%) for a fraction of a cent per non-QA turn meets it. | None. Worth one user *acknowledgement* (not a decision): the user approved a different optimisation on a premise D-423 falsified — the embedding was pitched at ~2.5 s and measured at **124 ms**. |
| E-6 | **Depth-generation spend timing (~$13–16)** | "NOT-GENUINE — decided ('spend it'), parked in practice, and what remains is a scheduling action." | Folded into **UD-2 arm 5**: same wallet, same "is now the moment" shape, so it belongs in that one message rather than its own. |
| E-7 | **The U7 consolidation criteria** | "NOT-GENUINE — the *decision* is taken (option D); what remains is an engineering design review gated on an unread **free** measurement." | Becomes a user question only if the criteria turn out to trade privacy retention against learning value, which cannot be known before the staging measurement. Take the free measurement first. |

## Other items considered and excluded

| # | Considered | Excluded because | Reopen condition |
|---|---|---|---|
| E-8 | **§7-R8 read-scope acceptance** (REQ-09/SEC-09/ARCH-18/DRIFT-17) | **PARKED_BY_DECISION** under D-086/D-123's acceptance; the write half was closed by D-107. R8's own expiry trigger ("first real traffic") coincides with the only event that can unfreeze its closure path, so **no decision is owed now**. | **Integration reopen / first real traffic. This item MUST be re-presented to the user at integration start** — it is launch-blocking at that point, and parking it here is not the same as closing it. |
| E-9 | **`superseded` status-tag convention** | Not a standalone judgement: it is an **input to the canonical-document proposal**, and scope/appetite gets decided when the user reviews that proposal. The eight actively-misleading entries are the separable immediate fix. | Reviewed with the canonical-doc proposal; belongs on the migration backlog, not in PROJECT_STATE current work. |
| E-10 | **The six-schema split** (ARCH-21) | **DEFERRED** — a production-time schema question, not a staging one. | Reopens at production schema design. **Mandatory before archive:** extract it from FINAL_ARCHITECTURE so the question survives the document's retirement. |
| E-11 | **The 150-concurrent capacity ask to the org** | Withdrawn/parked per D-153 §3; it is an org ask inside the D-152 freeze. Separately, capacity today is honestly an *extrapolation* — 30-day peak ≈ 3.0 req/s, busiest minute 51 requests — and request rate is not concurrency. | Revisit at integration. Any launch-readiness claim resting on 100 concurrent must state that it is an extrapolation. |
| E-12 | **D-310 / OPEN_DECISIONS item 8** | **Resolved by action** on 2026-08-20 (targeted apply 03:20:57Z, both services drained by 03:24Z, probes 200 on the new value and 404 on a wrong literal and a missing header, `terraform plan -detailed-exitcode` exit 0, old versions destroyed rather than deprecated). *Same item as E-1; listed separately because the adjudication names both.* | None for the rotation. Three residuals, none a decision: the operator `localStorage` re-paste (an action, and the user is the person who must do it — **this needs telling, not deciding**); the `make load-staging-learning` docker env pass-through never re-measured for `ps` visibility (**unmeasured, not cleared** — same exposure class as D-310 on a different path); and `e2e/README.md:16-17`'s pre-D-310 export shape (a doc fix). No standing rotation mechanism exists — accepted; the S44 deletion plan stands and is frozen. |
| E-13 | **SNS `PendingConfirmation`** (D-419's ⚠️ block) | **Resolved live** — both topics read `SubscriptionsConfirmed 1 / SubscriptionsPending 0` with real subscription ARNs and exactly the four expected `alerts-info` members (2026-08-20T00:05:15Z). D-419's warning is stale and needs a dated annotation so nobody chases it. | None. Documentation-only. |
| E-14 | **WORK-04 — the answer cache** | **Settled by D-423**'s progress-line conclusion under D-417 §B6: with ~7.5 s remaining after the planned overlap and no ungrounded fast answer permitted, stage 1 is a progress line naming the stage. *Same item as E-4; listed separately because the adjudication names both.* | Reopens only if a substantive stage 1 becomes a requirement. |
| E-15 | **NAT gateway existence** | **Resolved** — exactly one NAT exists (`nat-07ab02d5cd28b6f72`, available, `us-east-1a`, created 2026-08-07T04:47:31Z, `ManagedBy=terraform`), the unfiltered call returns the same single element, and the private route table carries an active default route to it. It predates D-406 and D-419's apply by eleven days, which is why the plan showed no NAT diff. ~$32.9/mo gross, **net $0.00** on credits. | None. Residual is D-419's wording — documentation-only. |
| E-16 | **Editorial banner and wording choices** (freeze banners, DRIFT-40's citation numbering, DRIFT-98) | Editorial, not judgements. The qualified-citation rule is adopted **without** renumbering; DRIFT-98's substance was resolved by F-07. | None. Documentation-only, folded into the themed hygiene entries in the register. |

---

## Accounting

- **Queue entries:** 12 (UD-1 … UD-12).
- **Sub-questions inside UD-12:** 6 — (a) difficulty-tier conflict · (b) D-141 §5 trim ·
  (c) prose quality · (d) internal NL2SQL · (e) REQ-39 wording · (f) committed org drafts.
- **Named sub-questions attached to other entries:** 2 — UD-1's §2.6 criterion-6 gate-integrity
  question, and UD-5's R9 checkpoint-repair tripwire.
- **Excluded rows:** 16 (7 NOT-GENUINE verdicts + 9 others; E-12 restates E-1 and E-14 restates E-4,
  both listed because the adjudication names them separately).
- **Blocks current work:** UD-1 only, and only partially.
- **Blocks the canonical-document proposal:** nothing. UD-12(a) and the status-tag convention are
  *inputs* to it, and both have safe defaults.
</content>
</invoke>
