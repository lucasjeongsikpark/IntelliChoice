# Integration Plan — Chat & Learning apps with the existing production system

Rewritten 2026-07-24 under a hardened scope constraint (user-set, supersedes the two
earlier drafts of this document):

> **The production system powering intellichoice.org and go.intellichoice.org
> (`icrest`/`icweb` + the `ic` MySQL database) is immutable.** No changes to its
> frontend, backend, schema, auth logic, credentials, deployment, security posture, or
> operational processes may be planned — even to fix known weaknesses. All
> compatibility problems are resolved inside the new Chat/Learning stack via adapters,
> translation layers, read-only access, independent authentication/session handling,
> and configuration. Pre-existing production risks may be recorded as assumptions or
> accepted residual risks only.

**Boundary tiers** (clarified 2026-07-24):

- **Tier 0 — prohibited**: any change to production application code, schema, auth
  implementation, or existing behavior. Nothing in this plan touches Tier 0.
- **Tier 1 — additive integration support (org asks, clearly separated from
  application changes)**: a read-only database account, network connectivity
  (VPN/tunnel access), schema snapshots, scheduled data exports, new DNS records.
  These add access alongside production without altering anything it runs. Every
  Tier 1 ask is labeled as such and has a fallback if refused.
- **Tier 2 — the new stack**: absorbs *all* compatibility logic — adapters,
  translation, independent session handling, configuration. Calling production's
  existing public endpoints as-is (e.g., its login API) is Tier 2 usage of existing
  behavior, not a production change.

Analysis-only; no code changed. Sources: this repo, and the production codebases at
`IntelliChoice-web/` (reviewed **only** to understand interfaces, auth behavior,
schema, data formats, roles, and operational constraints — its own
`docs/codebase-analysis/` holds the full review).

---

## 1. Facts about the production system that shape the design

These are observations, not work items. Where a fact is also a weakness, it appears
again in §7 as an accepted residual risk.

- **Auth**: HS256 JWTs, payload `{id: <accountId>}`, 12 h expiry, signed with a
  source-visible literal secret. Frontend keeps the token in per-origin
  `sessionStorage` and sends it as a `?token=` query param. No SSO/handoff mechanism
  of any kind exists, and none can be added.
- **Passwords**: `accounts.password` = HMAC-SHA256 of the plaintext with a fixed,
  source-visible key; the algorithm is fully reimplementable from the icrest source.
- **Schema** (`ic` database, integer PKs, no external ids): `accounts` (23 columns:
  identity + profile + compliance; `role` is free text — Parent/Student/Tutor/Manager
  by convention; `verifiedAt`, `dob`, `gradeLevel`, `locationId`), `children` (name,
  gradeLevel, `deleted` soft-flag, belongs to a parent account), `locations`
  (= branches: name/online/active only — **no** address, coordinates, or manager
  email), `calendars` (dated sessions per location, `deleted` soft-flag), `signups`
  (account + optional child + calendar, `attended` nullable boolean), `chapters`,
  `alerts`.
- **Attendance** is per-session (`signups.attended` against a `calendars.startTime`),
  recorded by branch managers, sometimes for "non-registered" ad-hoc children who have
  no account linkage.
- **Schema management**: `sequelize.sync({alter:true})` on every icrest boot — the
  live schema can drift without any migration artifact.
- **No consent, age-band, or tutor→student-assignment data exists anywhere.**
- **Hosting/topology is undocumented** — where the MySQL server runs, and whether it
  is network-reachable from AWS, is unknown from the repos.
- **DB credentials (write-capable) and the Gmail service-account key are committed to
  the production repo** and will remain so.

---

## 2. Phase 0 — audit first, then stabilize (before any integration discovery)

### 2.1 Why a full audit rather than a known-issues fix list

Earlier drafts treated the apps as "functionally complete through S34" because 497
tests pass and every roadmap criterion was met. That inference is not safe, and this
project's own history is the evidence: almost every session that performed **live**
verification found a previously unknown, real defect the unit tests had missed —
S23's checkpoint erasure (`last_items: None` silently wiping the exam batch on the
first answer), S26's EventSource race (a new session could *permanently* receive no
SSE), S28's parent auto-select gap, S31's two instrumentation-ordering bugs, S33's
proxy-header bug (the rate limiter broken in the live deployment the whole time),
S34's middleware-ordering bug (429s invisible to logging and metrics) and the
`/healthz` ALB-health-check gap. Each surfaced only when someone exercised the
running system from the outside. Flows that have never been driven end-to-end under
adversarial conditions must be presumed to hide more of the same — and integration
would otherwise be built on top of them.

Phase 0 therefore runs **audit sessions first** (hunt unknown defects; compare SPEC
against implementation), then **stabilization sessions sized by the findings**, with
a measurable gate (§2.6) before integration discovery. The discovery session
formerly numbered S38 moves to **S42**.

### 2.2 Structure

S35 (deploy restoration) → S36–S39 (four audit sessions) → S40+ (stabilization,
elastic count) → §2.6 gate → Phase 1 discovery (S42). S35 stays first because half
the audit surface (deployment behavior, live performance, alarms, scheduled jobs)
needs a working deployed environment to be auditable at all.

**S35 — restore the deploy pipeline (known-blocker work):** diagnose the failing
Alembic step (real traceback never seen), verify both service deploy steps, apply
the withheld Terraform (canary bake + CloudWatch alarms + autoscaling + deployment
circuit breaker + per-app JWT signing secrets), confirm a real image healthy under
`/readyz`.

### 2.3 Audit sessions — scope and method

Common method for all four: (1) **requirements traceability** — walk the launch-scope
SPEC sections against code and tests, recording every discrepancy, risk-ordered
(money, minors, authorization, data integrity first); (2) **defect-pattern sweeps** —
every bug class this project has already produced once gets hunted everywhere it
could recur (checkpoint channel overwrites, resumed-node replay side effects,
interrupt discards, silent `except Exception` swallows, middleware/instrumentation
ordering, unseeded RNGs, fail-open defaults, frontend renders gated on absent
fields); (3) **adversarial end-to-end runs against live staging**, not happy paths —
refresh mid-exam, double-submit, concurrent tabs, expired timers, dropped SSE
mid-stream, malformed/boundary inputs, role-confusion attempts; (4) findings are
logged with severity (§2.4), reproduction, and evidence — fixes land in Phase 0B,
not mid-audit, except P0s, which stop the line.

**AUD-L (S36) — Learning product correctness.** Assessment creation and policy
snapshots; question generation/validation pipelines (shape + authored) including
what actually sits `approved` and deliverable in the bank today; attempt/answer
flows incl. skip/flag/time and finalize idempotency; deterministic scoring and
re-grade consistency; mastery bootstrap + retry-ladder transitions vs SPEC
§5.10–5.11; the full hint ladder (canonical + personalized + leak checks); learning-
gain math; **dashboard and report numbers recomputed independently from raw rows**
and compared against what the API and UI actually show; stage-narrative grounding;
memory-consolidation effects on tutoring payloads.

**AUD-C (S37) — Chat product correctness.** Retrieval quality measured with the
existing eval harness *extended* (paraphrase, adversarial, and negative/no-answer
sets; grounded-citation rate and correct-refusal rate as tracked metrics);
role/branch/date filtering verified pre-retrieval for every audience including
anonymous; conversation state across turns, interrupts (email/calendar/locator),
and reconnects; tool-call validation + audit-trail completeness; citation verbatim
verification; **every degraded/refusal/empty response shape rendered visibly in the
frontend** — the S22.5 blank-turn bug is the known exemplar of a class, so every
response-shape × render combination is enumerated; error handling under gateway
failure, timeout, and rate limiting.

**AUD-X (S38) — Cross-cutting integrity.** New-stack authn/authz boundaries:
audience separation, cross-student/cross-parent access attempts on every route,
SSE `?token=` handling, dev-token gates, checkpoint-thread hijack attempts; data
consistency between LangGraph checkpoints and domain tables after crashes (kill
mid-node, mid-interrupt, mid-finalize; resume and verify invariants); idempotency of
every retryable write; interrupted-workflow recovery and retry behavior; Bedrock
cost-ceiling enforcement under concurrency; PII floor re-verified against **live
staging** logs/traces/metrics/payloads, not only unit tests.

**AUD-F (S39) — Frontend contracts + operations.** Scripted walk of **every launch
user journey** (student pre→study→post→results; parent child-select→dashboard→
report; chat ask/escalate/calendar/locate per role; every consent/interrupt modal)
against the real APIs with console and network capture — every contract mismatch
recorded; CI-coverage inventory (chat-web has none — known); deployment drills (a
deliberate bad-image deploy must demonstrably auto-roll-back via the circuit
breaker/canary); scheduled-job dry runs; verification that each CloudWatch alarm can
actually fire and reach a human; live-staging load/perf re-run.

### 2.4 Severity and disposition

- **P0** — authorization bypass, PII leak, data corruption, child-safety failure,
  uncontrolled spend: stop the line, fix immediately, regression-test.
- **P1** — a launch journey broken, fail-open behavior, cost/latency out of bounds:
  fixed and re-verified before the §2.6 gate.
- **P2** — degraded UX/quality with a workaround: fixed in Phase 0B if cheap,
  otherwise documented with owner and target phase.
- **P3** — polish: backlog.

Every finding gets a disposition recorded in DECISIONS.md; "won't fix" requires a
written reason.

### 2.5 Stabilization sessions (S40+, count set by the audit backlog)

Seeded today with the already-known items — S22.5 `access_hint` blank turn, S11
parent auto-select, chat-web CI, the unseeded-RNG flake, `question_variants`
accumulation (610 rows on one template, worsening), the 249k-row `checkpoints`
sweep, EventBridge schedules for the four manual jobs (the 90-day `chat-purge`
retention promise must not depend on a human running make) + small retention jobs
for `stage_transitions`/`student_reports`, and the ≥2-task/autoscaling P95 fix with
a live load re-baseline — plus every P1 (mandatory) and cheap-P2 audit finding.

Parallel tracks, unchanged: **A6** real content (3 of 23 knowledge docs are real;
curriculum breadth is `linear_equations`-only authored, D-060) gates the *pilot*;
**A7** (WAF, backup-restore drill, ZAP, pen-test scheduling) gates *public*
promotion.

### 2.6 Measurable exit criteria — the gate before integration discovery (S42)

All of the following, with evidence recorded in PROGRESS.md:

1. **Traceability**: 100% of launch-scope SPEC requirements mapped to implementation
   + test; every discrepancy dispositioned in DECISIONS.md.
2. **Defects**: zero open P0/P1 from any audit; each fix carries a regression test
   and a live re-verification.
3. **Journeys**: every launch user journey passes a scripted E2E run against live
   staging **twice consecutively** — zero console errors, zero 5xx, zero
   blank/stuck states.
4. **Test signal**: 3 consecutive full `make lint typecheck test` runs green (flake
   eliminated); CI builds and tests every deployable including chat-web.
5. **Deploy**: 2 consecutive clean `deploy-staging.yml` runs including migrations +
   canary bake; one deliberate bad-image deploy demonstrably auto-rolled-back.
6. **Jobs**: all scheduled jobs ran on schedule in staging for ≥ 1 week with zero
   manual intervention.
7. **Performance**: live load test meets the S34-calibrated thresholds (P95 ≤ 3 s at
   150 concurrent, error rate < 1%) with ≥ 2 tasks and autoscaling active.
8. **Observability**: every CloudWatch alarm fired at least once (induced) and the
   notification reached a monitored inbox.
9. **PII**: zero PII found in live staging logs/traces/metrics/LLM payloads across
   the audit window (purity tests + manual sampling).

---

## 3. Integration layers, the authentication decision, and the incompatibility catalog

### 3.0 Three distinct integration layers — what the constraint allows

| Layer | Achievable without production application changes? | Resulting UX |
|---|---|---|
| **Backend/data integration** (profiles, parent-child links, attendance, branches) | **Yes, fully** — via production's existing API and/or Tier 1 read-only DB access, absorbed by adapters (I3–I7, I11) | Invisible to users |
| **Shared-account authentication** (existing IntelliChoice credentials work in the new apps) | **Yes** — the new stack verifies credentials using production as-is and mints its own tokens (§3.1) | One familiar account everywhere; users log in on the new domains |
| **Seamless frontend/SSO** (no re-login; nav links inside go.intellichoice.org) | **No** — requires icweb changes (frozen); `sessionStorage` is origin-locked and no handoff mechanism exists | **Reduced scope accepted**: separate explicit login per new domain; discovery via out-of-band links (org email, branch announcements, QR) |

The plan delivers the first two in full and explicitly accepts the reduced-scope third.

### 3.1 Shared-account authentication — options compared (decision open until S42 discovery)

The prior draft pre-selected hash re-verification; that selection is **withdrawn**.
All feasible Tier 2 approaches, none requiring production application changes:

**O1 — Server-to-server delegation to the existing login API (provisional
recommendation).** The new app's login form posts to the new backend, which calls
production's public `POST /api/accounts/login` with the user's credentials; a success
response *is* the verification, and the new stack mints its own SPEC-claim token. The
legacy JWT in the response can be used once, server-side, for `GET /api/accounts`
(own profile + children) and then discarded — it is never a trust anchor beyond that
single already-authenticated exchange.

**O1b — API-only variant of O1.** Additionally source attendance from
`GET /api/accounts/signups` *if* discovery confirms the response carries per-session
`attended` for the caller's children — which would eliminate the DB network path for
the core flows entirely (see I11's revised ladder).

**O2 — Read-only verification against the stored password hash (fallback).**
Reimplement production's HMAC-SHA256 scheme (algorithm and key are source-visible)
and compare against `accounts.password` via read-only DB access.

**O3 — Email magic link.** Prove control of the account email (lookup read-only,
send via the new stack's own SES sender) — no password handled at all; trust level
equivalent to production's own email-based reset flow.

**O4 — Standalone accounts in the new stack.** Own registration/passwords; abandons
the shared-account goal — last resort only (§7-A1), if no read path and no reachable
login API exist.

| Criterion | O1 login-API delegation | O2 hash re-verification | O3 magic link |
|---|---|---|---|
| Trust anchor | Password knowledge, verified by **production's own logic** (verified-account checks included, enforced by production itself) | Password knowledge, verified by a **reimplementation** the new stack must keep faithful | Email control only (≈ production's own reset-flow trust level) |
| Credential exposure | Plaintext transits new backend → HTTPS to icrest (same wire as a normal login); transient handling, never stored/logged | Plaintext handled **and** hash values read into the new stack; the weak HMAC key must be held in Secrets Manager | None — no credentials handled |
| Coupling surface | Production's **public API contract** (endpoint + response shape) — the loosest available; survives any internal production change, including a future hashing fix | Production's **internal implementation** (column semantics + algorithm + key) — the tightest; any future hashing change breaks login silently | Email→account lookup (DB read) + sender infrastructure |
| Operational reliability | New *logins* depend on icrest uptime (unmonitored, no health endpoint — real risk); active sessions/refresh unaffected; **no DB network path needed for auth** (public HTTPS reaches it today) | Independent of icrest uptime, but requires the DB network path — potentially the hardest Tier 1 ask (topology unknown) | Depends on SES deliverability + DB read; inbox latency per login |
| Side effects on production | Uses existing behavior as designed; login updates `lastLoggedinAt` (org's "last login" data now includes new-app logins — documented, not a change) | None (pure reads) | None (pure reads) |
| UX | Familiar email+password on the new domain | Identical | Slower (inbox round-trip); awkward for shared/parent-managed email |
| Implementation complexity | Low: HTTP client + timeout/retry + error mapping + own rate limiting in front | Low for the HMAC itself; high if the DB path is hard to obtain | Moderate: one-time links, sender setup (I13) |

**Provisional recommendation: O1, upgraded to O1b if discovery confirms the signups
response carries attendance; O2 held as the documented fallback** (if the login API
proves unusable server-to-server, or its availability is unacceptable); O3 optionally
later as a convenience/recovery path; O4 only as the §7-A1 last resort. Rationale:
O1 is the only option whose coupling is to a *stable public interface* rather than to
internal implementation details, it needs no special network path for auth, it never
teaches the new stack production's hashing internals, and production's own login
semantics stay enforced by production. Its one real weakness — new logins depend on
icrest being up — is bounded (existing sessions keep working) and honest: if icrest
is down, the org's *primary* system is down too.

**Decision gate:** finalized at S42 (discovery) from evidence (login-API response
shape/latency/reachability from AWS, signups-response contents, icrest availability
history), recorded in DECISIONS.md before S44 implements. Common to every option:
the new stack's own issuer signs SPEC §5.1.2 claims with its per-app secrets (S33
Terraform); consent (I9) and role mapping (I7) gate minting; dedicated per-account +
per-IP login rate limiting with backoff (the new endpoint must not become a better
brute-force oracle than production's own unprotected login); credentials handled
transiently only — never stored, logged, or traced.

### 3.2 Incompatibility catalog and new-stack-side solutions

Every known mismatch between what the new apps assume and what production actually
provides, each resolved without touching production.

**I1 — Token contract.** New apps require SPEC §5.1.2 claims (role, consent, age band,
audience); production tokens carry `{id}` only, signed with a secret that must be
treated as public (source-visible, unrotatable under the constraint) — so legacy
tokens can never be a trust anchor on their own.
→ Independent session handling: the new stack authenticates per §3.1 (option finalized
at the S42 gate) and mints its own audience-scoped tokens. The dev
`FakeTokenIssuer`/`/dev/token` remain dev-only; the real issuer replaces the
never-going-to-exist "go-issued SPEC token".

**I2 — No SSO / no in-product entry point.** `sessionStorage` is origin-locked, icweb
cannot gain nav links or a handoff flow.
→ Accept one explicit login per device on the new domains (session persistence
new-stack-side; refresh tokens ≤ 24 h). Discovery is out-of-band: org emails, branch
announcements, printed/QR links — a rollout-communications task, not code. (See §5
impossible-items list.)

**I3 — Profile schema mismatch.** `MySQLProfileAdapter` queries an invented dev schema
(`users`/`parent_child_links`/`attendance(week_key)`/`branches`); production has
`accounts`/`children`/`locations`/`calendars`/`signups`.
→ **`IcProfileAdapter`**: a second implementation of the existing `ProfileAdapter`
Protocol (the exact seam D-002 built), env-selected, querying the real tables
read-only. The dev-fake adapter remains the dev/test default.

**I4 — No external ids.** Production uses integer PKs; Postgres must reference
external ids only.
→ Prefix-namespaced ids minted by the adapter: `acct-<id>` (account-holding students,
parents, adults) and `child-<id>` (parent-registered children — a disjoint population
that must not collide). "Non-registered" ad-hoc students have no account linkage and
are out of integration scope.

**I5 — Attendance semantics.** New apps expect week-keyed status; production records
per-session `signups.attended`.
→ Derive in the adapter: *present this week* ⇔ a `signups` row with `attended = true`
joined to a non-deleted `calendars` row whose `startTime` falls in the current week
(timezone convention read from icrest's own report queries — confirm in-session).
NULL/false/no row → absent/unknown → the existing fail-closed gate and
`resolve_attendance` interrupt (branch-manager email) handle it, unchanged.

**I6 — Branch metadata gaps.** `locations` has no manager email, address, or
coordinates; `BranchInfo` wants all three.
→ Manager email: under I11 rung ≥ 2, resolved read-only (`accounts` where
role=Manager and matching `locationId`; multiple managers → deterministic pick, none
→ None and the escalation path degrades gracefully as already built); under API-only
(rung 1), that query has no API equivalent — use a small new-stack-owned
branch→manager-email config table administered by the org (or the public
`org_team_members` roster where it lists branch contacts). Address/coordinates keep
coming from the already-built `org_branches` table (webcontent sync of the public
site), joined by branch name — production needs nothing.

**I7 — Role mapping.** Free-text `role` column; `Manager` vs `branch_manager` naming.
→ Adapter-level mapping table; **any unrecognized role string fails closed** (no
token). Emit a metric on unknown roles so surprises are visible, not silent.

**I8 — No tutor→student assignment model** (the data D-086 needs does not and will not
exist in production).
→ Launch scope = **student + parent (+ anonymous public chat) only** — the unscoped
roles are simply never issued tokens. branch_manager can follow later using
`accounts.locationId` (branch-level scope, data exists); tutor role stays off until
the org has an assignment source *outside* the immutable system (e.g., a
new-stack-owned assignment table administered by the org). Record as the formal D-086
disposition.

**I9 — No consent/COPPA data.** Token claims require consent fields; production stores
none and its registration flow can't be extended.
→ Consent ledger in the new Postgres — `account_external_id`, version, timestamp,
granting parent — external ids and enums only, **no PII**, so it belongs there
legitimately. First-entry consent UI in the new frontends (parent grants for each
child/student account; adults self-consent). No consent row → no token (fail closed).
Consent *text* comes from the §6.1 legal parallel track — a true pilot blocker.

**I10 — Age bands.** `student_age_band` claim has no direct source.
→ Derive: `accounts.dob` for account-holding students; `children.gradeLevel` →
band via the existing curriculum banding for children. Documented approximation.

**I11 — Data-access path (the biggest unknown, now with a cheaper first rung).**
Production hosting is undocumented; moving/replicating the DB from the production
side is prohibited. A ladder, descended only as far as discovery forces (each rung is
a Tier 1 ask *only* from rung 2 down; rung 1 needs no ask at all):
  1. **API-only (O1b)** — auth via the login API; own profile + children via
     `GET /api/accounts` (using the response's legacy JWT once, server-side);
     attendance via `GET /api/accounts/signups` if it exposes `attended`. No DB
     path, no new credentials, nothing to ask for. Coupling is to undocumented,
     unversioned response shapes — mitigated the same way as I12 (contract tests
     against captured fixtures + a deploy-time probe against the live endpoint).
  2. **Hybrid** — API for auth/profile; **direct read-only DB connection** for what
     the API can't serve (attendance detail, manager lookups, I14's revocation
     check), over a private path the new stack owns (site-to-site VPN or an
     SSH-tunnel sidecar in the new VPC using org-*provided* access). Ask for a
     read-only DB account; if even an additive grant is refused, enforce read-only
     discipline in adapter code using existing credentials from Secrets Manager —
     weaker, documented in §7.
  3. **DB-only** — the full `IcProfileAdapter` reads everything from MySQL (pairs
     with auth option O2 if the login API is also unusable).
  4. **Snapshot-sync replica** — org-operated scheduled exports of the five needed
     tables imported into the existing RDS MySQL; staleness becomes a first-class
     state (older than threshold → attendance unknown → the existing fail-closed
     interrupt flow), acknowledged as adding real branch-manager email workload.
  The `ProfileAdapter` Protocol is the seam in every case; rungs differ only in what
  sits behind it.

**I12 — Silent schema drift.** `sync({alter:true})` can change the live schema on any
icrest restart, breaking the adapter without warning.
→ Contract tests against a schema snapshot (refreshed at each discovery checkpoint), a
deploy-time read-only smoke probe (SELECT the exact columns the adapter uses), and a
runtime degraded mode: adapter query errors → 503 via `/readyz`, never a
half-answered authorization decision.

**I13 — Email identity.** Attendance/admin escalation emails need a sender; the
production Gmail service account may not be touched or reused (its committed key must
be treated as compromised, and rotating it is prohibited).
→ The new stack gets its **own** sender: AWS SES on a new subdomain (e.g.
`no-reply@mail.intellichoice.org`) with its own additive DNS records — or, if any DNS
addition is off-limits, email features stay flag-off at launch (the graceful-
degradation paths already exist and are tested).

**I14 — No revocation propagation.** A production password change/compromise response
can't invalidate new-stack sessions (and vice versa).
→ Short access-token TTL (≤ 1 h) in every case. The stronger check — refresh
compares a stored **fingerprint of the password hash** (never the hash itself)
against `accounts.password`, so a changed password kills the session at next
refresh — requires the DB read path (I11 rung ≥ 2). Under pure API-only (rung 1)
that check is impossible; compensate by capping total session length (re-login
within ~24 h, in the spirit of production's own 12 h tokens). Logout clears
new-stack state only (matches production's own client-side-only logout semantics).

**I15 — `verifiedAt` / account-status semantics.** New claims carry `account_status`.
→ Map from `verifiedAt` (unverified → no token). Background-check fields gate only
tutor/manager flows, which are out of launch scope (I8).

---

## 4. Genuinely impossible without production changes — with alternatives instead

Per the constraint, none of these become planned work; each gets a new-stack
alternative or a reduced-scope rollout answer.

| Requirement | Why impossible | Alternative adopted |
|---|---|---|
| Seamless SSO from go.intellichoice.org | No handoff mechanism exists; icweb/icrest frozen; `sessionStorage` origin-locked | Independent login with existing credentials (I1); one extra login per device |
| In-product discovery (nav links on go/marketing site) | Both frontends frozen | Out-of-band links: org email, branch announcements, QR handouts (§6 rollout comms) |
| Trust anchor immune to production-repo compromise | Legacy JWT secret, HMAC key, and write-capable DB creds stay in the prod repo forever | Credential verification per §3.1's selected option (either anchors on password knowledge, not the forgeable token) + accepted residual risks §7-R1/R2 |
| Server-side revocation across systems | No production session store; logout is client-side only | Short TTLs + hash-fingerprint refresh check (I14) |
| Consent captured in the org's official registration flow | Registration flow frozen | New-stack consent ledger + first-entry capture (I9) |
| Tutor role with real per-student scope | No assignment data exists in production | Role not issued at launch; later via a new-stack-owned assignment table (I8) |
| Guaranteed-fresh attendance if the DB isn't reachable from AWS | Can't move/replicate the DB from the production side | Snapshot-sync + staleness→fail-closed→existing interrupt flow (I11 fallback) |
| Reusing `office@intellichoice.org` as sender | Gmail key untouchable | Own SES identity on additive DNS, or email flag-off (I13) |

**Additive shared-infrastructure asks (flagged, minimal, not production *changes*):**
DNS records for `learning.`/`chat.intellichoice.org` (+ SES sender domain) — new
records only, no existing record modified; a read-only MySQL account or scheduled
dumps; a network path (VPN/SSH access). If DNS additions are also off-limits, the apps
ship on their CloudFront default domains (reduced scope, ugly but functional).

---

## 5. Session plan (S35+, continuing ROADMAP numbering)

Numbering beyond S41 is indicative — it shifts if the audit backlog needs more than
two stabilization sessions.

| Phase | Session | Content | Depends on |
|---|---|---|---|
| **0A — Audit** (§2.3) | S35 | Restore the deploy pipeline: Alembic fix, verified deploys, withheld Terraform applied | — |
| | S36 | **AUD-L** — Learning product correctness (assessments, generation/validation, scoring, mastery, hints, reports, dashboards) | S35 |
| | S37 | **AUD-C** — Chat product correctness (retrieval quality, role filtering, conversation state, tools, citations, degraded renders) | S35 |
| | S38 | **AUD-X** — cross-cutting integrity (new-stack authn/authz boundaries, consistency/idempotency/crash recovery, cost ceilings, live PII floor) | S35 |
| | S39 | **AUD-F** — frontend contracts for every launch journey + CI/deploy/jobs/observability/perf operations audit | S35 |
| **0B — Stabilization** (§2.5) | S40–S41 (elastic) | All P1s + cheap P2s from the audits, merged with the seeded known-issues backlog (fixes, EventBridge jobs, retention, autoscaling/P95, test-signal debt) | S36–S39 |
| — | **Gate** | §2.6 exit criteria all green, evidenced in PROGRESS.md | S40–S41 |
| **1 — Integration readiness** | S42 | **Discovery, org asks (Tier 1 only), and the auth decision gate**: exercise `POST /api/accounts/login` + `GET /api/accounts` + `GET /api/accounts/signups` server-side from AWS (reachability, response shapes incl. whether signups carries `attended`, latency, captured fixtures); icrest availability history; DB topology, network path or dump cadence, read-only account, DNS additions; live role-string survey, timezone convention, schema snapshot; **select the §3.1 auth option and I11 rung**, record with §7 residual-risk acceptance in DECISIONS.md | Gate |
| | S43 | **`IcProfileAdapter`** (I3–I7, I15) backed by the selected I11 rung (API client, read-only SQL, or hybrid): id namespacing, attendance derivation, role mapping fail-closed, branch enrichment; contract tests against captured fixtures/schema snapshot + deploy smoke probe (I12); staging runs against a prod-shaped replica | S42 |
| **2 — Integration implementation** | S44 | **Independent auth** (I1, I14): implement the selected §3.1 option (O1 delegation client with timeout/retry/error mapping, or O2 verifier), token issuer with SPEC claims + per-app secrets, login UI replacing `DevLoginScreen`, dedicated per-account+per-IP rate limiting, refresh/revocation per I14, logout semantics | S43 |
| | S45 | **Consent** (I9, I10): ledger, capture UI (parent-grants-for-child), age-band derivation, no-consent→no-token; legal text integrated from the §6.1 parallel track | S44 |
| | S46 | **Role scoping + frontend completion** (I2, I8): student/parent-only issuance, D-086 disposition recorded, entry/login/session UX end-to-end in both apps | S44 |
| **3 — Integration testing** | S47 | **Integration-specific test pass** (not the first comprehensive E2E — Phase 0A owns that): E2E against a production-schema replica seeded with realistic edge data (soft-deleted children, NULL attendance, unknown roles, unverified accounts, duplicate signups); auth abuse tests (brute-force limits, forged/expired tokens, cross-audience); staleness drill for the I11 fallback; PII-boundary re-audit covering the new login path | S43–S46 |
| **4 — Rollout** | S48 | Production environment: `terraform/environments/production` (multi-AZ, ≥2 tasks, deletion protection, dev-token gates off), domains + ACM + additive DNS, prod alarms to a monitored inbox | S35 |
| | S49 | Real credentials + feature-flag audit (I13 SES or flag-off; Maps/Calendar/YouTube real-or-off); connectivity path live (I11) | S42, S48 |
| | S50 | A7 close-out: WAF, backup-restore drill, ZAP on prod config; incident-response runbook updated for the integrated topology | S48 |
| | S51 | Pilot start + graduated rollout (§6) | S45–S50, A6, legal docs |

**Dependency spine:** S35 → the four audits → stabilization → **§2.6 gate** →
discovery (S42) → adapter → auth → consent/scoping → integration testing · A6 real
content + §6.1 legal docs → pilot (S51), never the build · A7 → *public* chat
promotion, not the pilot.

---

## 6. Incremental rollout

1. **Stage 0 — synthetic**: staging green end-to-end (exit of Phase 0).
2. **Stage 1 — prod-shadow**: production environment live against real (or
   snapshot-synced) data; the new stack's own token issuer mints **only for an
   allowlist** (org staff + own families). The allowlist is the throttle *and* the
   kill switch — entirely new-stack-owned.
3. **Stage 2 — single-branch pilot (2–4 weeks)**: one branch's students/parents;
   consent flow exercised for real; discovery via org email/branch announcement (I2);
   cost/latency/alarm dashboards reviewed weekly; chat link-only.
4. **Stage 3 — all branches, then public chat** after A7 completes and pilot metrics
   hold.
5. **Rollback at any stage**: the new stack never writes MySQL → production data is
   structurally untouched; disable = stop issuing tokens (+ optional maintenance
   page). Per-deploy rollback = the S34 canary bake + circuit breaker.

---

## 7. Accepted residual risks and standing assumptions (documented, never planned work)

- **R1 — Production-repo compromise ⇒ new-stack impersonation.** The HMAC key and
  write-capable DB credentials live in the production repo. An attacker with repo +
  network access could set a known password hash on any account and then log into the
  new apps as that user. No new-stack mitigation exists beyond I14's refresh check;
  accepted, to be signed off by the org at S42 (discovery).
- **R2 — Weak password hashing persists in production** regardless of the §3.1
  option; a DB leak is crackable at SHA-256 speed. Under the O2 fallback the new
  stack additionally reimplements and depends on that scheme. New-stack login rate
  limiting prevents *online* abuse only.
- **R3 — Brute-forceable production reset codes.** An icrest account takeover via its
  unlimited, never-expiring 6-digit codes becomes a new-stack login as that user.
  Out of scope by constraint; recorded.
- **R4 — Schema drift without notice** (`sync({alter:true})`): mitigated to
  detection-and-fail-closed (I12), never prevention.
- **R5 — Attendance freshness** bounded by the sync cadence if I11's fallback is used;
  fail-closed behavior converts staleness into branch-manager interrupts, which adds
  real workload for managers — monitor during pilot.
- **R6 — Discoverability ceiling** (I2): adoption depends on out-of-band
  communication; expect slower ramp than an in-product link would give.
- **R7 — New-login availability coupled to icrest (under O1).** icrest has no health
  endpoint, monitoring, or documented process supervision; when it is down, new
  logins fail (active sessions and refresh keep working). Accepted — when icrest is
  down, the org's primary system is down too. Tier 2 mitigation: the new stack's own
  alarms probe the login endpoint externally, so the org hears about outages faster
  than it does today. Side note, accepted: new-app logins update `lastLoggedinAt`
  (production behaving as designed), so the org's "last login" data includes them.
- **A1 (assumption)** — the org can provide *some* lawful read path to the `ic`
  database (network, account, or dumps). If literally none exists, integration with
  real accounts is impossible and the apps can only launch standalone (own
  registration), which contradicts the shared-auth goal — surface immediately at S42
  if discovery fails.
- **A2 (assumption)** — role strings in live data match the four known values;
  unknowns fail closed and are surfaced by metric (I7).
- **A3 (assumption)** — additive DNS records are permitted; otherwise CloudFront
  default domains (reduced scope).
