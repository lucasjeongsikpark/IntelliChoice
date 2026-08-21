> ## ⛔ These sessions are **frozen by D-152** (not blocked — deferred)
>
> The user's decision: **finish and test this codebase against the dev fakes first, then
> integrate.** So **S43–S47 are closed until the user says integration is starting.** No
> measurement, benchmark, reachability check, or org answer can meet the reopen condition — the
> only thing that reopens this work is the user reopening it. **Do not start this work, do not
> scope it, do not "unblock" it.** Measuring now produces values that are stale by the time they
> are used, and the auth decision is only meaningful on top of a fresh measurement.

# Frozen and downstream integration sessions (S42–S51)

Extracted from `ROADMAP.md` so that archiving the roadmap does not archive live scope. This is a
**reference record of scope**, not a work queue.

## What this file is not

**There are no acceptance criteria here, because none exist.** `ROADMAP.md` holds **no "Done when"
criteria for S43–S51** — verified as zero occurrences across the whole intervening range of the
source file. Nothing in this file may be read as an acceptance test, and nothing may be added as
one: if and when the user reopens integration, the acceptance criteria get **written then**, with
the measurements that are deliberately not being taken now. Fabricated criteria for frozen work
would be worse than no criteria at all.

Also not carried: the roadmap's gate-standings prose and per-session status history. For full
original context see `docs/archive/ROADMAP.md`.

Decision reasoning stays in `DECISIONS.md`: **D-152** (why S43–S47 are frozen) and **D-049** (the
session renumbering that makes pre-2026-07-18 session labels ambiguous — entries written before
that date use the old numbers).

## Where the five embedded constraints live

These five are the load-bearing constraints inside the scope bullets below. They are recorded
verbatim in place; this index exists only so they can be found.

| # | Constraint | Lives in |
|---|---|---|
| 1 | Production `role` must never by itself grant an elevated role (D-153 §5) | S43 |
| 2 | The six structural dev-fake mismatches (D-151) | S43 |
| 3 | `IcProfileAdapter` merges TWO sources for `BranchInfo` (D-152 §3) | S43 |
| 4 | Assert no session starts 00:00–01:00 local or on a Sunday evening (D-153 §4) | S43 |
| 5 | The `/dev/token` deletion cascade, including the `sub` assertion (D-167) | S44 |

## Section mapping, as the roadmap holds it

`ROADMAP.md` carries **no SPEC-section-to-session mapping table** for this range. What it maps
instead — carried here as-is:

- **Sessions 42–47** → `INTEGRATION_PLAN` §3, §5; work items **I1–I15**.
- **Sessions 48–51** → `INTEGRATION_PLAN` §5, §6.
- SPEC sections appear only **inline** in the bullets below (§5.1.2's first-visit notice and
  §5.1.3's `LocationConsentModal` pattern at S45; the §6.1 legal-and-policy track gating it;
  SPEC claim set at S44), plus `INTEGRATION_PLAN` §1's four schema claims, §3.1's auth selection
  and §7's residual-risk acceptance at S42.

---

## Sessions 42–47 — Integration readiness and implementation *(INTEGRATION_PLAN §3, §5)*

### S42 — discovery, Tier 1 org asks, and the auth decision gate

**Status: complete on its source half (2026-08-01, D-151).** Its remaining items are org- or
runtime-only and are deferred with the integration (D-152).

The user made the production system's source available at `../IntelliChoice-web`, so discovery was
answered from source rather than org recollection: **[S42_DISCOVERY.md](S42_DISCOVERY.md)**
(8 readers → synthesis → adversarial verify; 8/10 claims confirmed, 2 refuted-with-correction).
**`GET /api/accounts/signups` carries per-child `attended`, so O1b is feasible and the DB path
leaves the critical path** (I11 rung 1). Login and profile contracts, the full schema, the role
vocabulary, and the timezone facts are all captured; INTEGRATION_PLAN §1's four schema claims
verified.

**Answered 2026-08-02 by the user (D-153), so the outstanding list shrank:** DNS is available
(added at integration); the **timezone question is closed by evidence** — the published schedule
is Mon–Fri 10:00–12:00 / 18:00–20:00, and the two conventions diverge only for Sunday evenings
and 00:00–01:00 starts, so they produce identical dates and weeks; peak concurrency is
unmeasured but the planning assumption is **~1,000 students across a week**.

**Still genuinely org- or runtime-only, and all deferred with the integration (D-152):**
TLS/proxy topology + outage history + where stdout goes (Message C), the from-AWS reachability
measurement, and three live-DB reads (`SELECT DISTINCT role`, `SHOW CREATE TABLE` for drift and
password collation, deployed-build confirmation). **The §3.1 auth selection and I11 rung are
recommended (O1b, O2 as fallback) but NOT decided** — they need §7 residual-risk acceptance in
DECISIONS.md before S44 implements, and that decision waits for the reachability measurement.

### S43 — `IcProfileAdapter`

**Status: frozen by D-152.** Do not start it, do not rewrite the dev fake, do not build against it.

(I3–I7, I15) behind the existing `ProfileAdapter` Protocol: id namespacing
(`acct-<id>`/`child-<id>`), attendance derivation from `signups.attended`, fail-closed role
mapping, branch enrichment; contract tests against captured fixtures + a deploy-time schema smoke
probe (I12).

**⚠️ Scope known from D-151, to be handled *when S43 runs* (not before — D-152):** the MySQL dev
fake models a system that does not exist — six structural mismatches (branch metadata columns
production lacks; a role ENUM that cannot hold Tutor/Manager and is the wrong case; week-keyed
attendance vs per-session tri-state; opaque external ids vs integer PKs; a parent-child join
table vs an FK; grade `VARCHAR`/`str` vs INTEGER 0=K). Build `IcProfileAdapter` against
production-shaped fixtures rather than extending the fake — S42_DISCOVERY.md §9. **Do not
rewrite the fake in the meantime:** the mismatches stay behind the Protocol seam, and the live
schema can still move under `sync({alter:true})`.

**Design fact to plan for (D-152 §3): `IcProfileAdapter` merges TWO sources.** `BranchInfo`
requires non-nullable `manager_email`/`address`/`latitude`/`longitude`; production `locations`
has none of them — address and coordinates come from the new stack's own `org_branches`, and
manager email from an `accounts` join on `locationId` where `role = 'Manager'`.

**⛔ Security constraint (D-153 §5, rationale updated in §7): production `role` must never by
itself grant an elevated role here.** The org's policy is that Student/Parent/Tutor are
self-selected and `Manager` is admin-only — the frontend implements that, the API does not
(`req.body.role` is persisted verbatim), and a fix has been requested. **The constraint stands
regardless of that fix**: pre-fix rows may already carry a self-assigned `Manager`, production
is frozen and schema-drifting, and authorization is not delegated to another system's input
validation (CLAUDE.md rule 3). Map Student/Parent from production; gate `Tutor`/`Manager`
behind an allowlist the new stack controls.

**Also at S43 (D-153 §4): assert no ingested session starts 00:00–01:00 local or on a Sunday
evening**, and log loudly if one ever does — that is the only window where the timezone
convention could change which week a session belongs to.

### S44 — independent auth

**Status: frozen by D-152.** Its prerequisite decision (§3.1 auth selection) is itself deferred.

(I1, I14): the selected option, token issuer with SPEC claims + per-app secrets, login UI
replacing `DevLoginScreen`, per-account+per-IP login rate limiting, refresh/revocation, logout
semantics.

**Added by D-167:** deleting `/dev/token` also deletes the `staging_token_shared_secret` setting,
both `DevLoginScreen`s and their stored-secret keys, and the deploy probe's wrong-credential arm —
so that probe needs re-pointing at the real login path rather than dropping. And confirm the new
issuer **asserts** `sub` from verified credentials rather than accepting it from the request body:
every per-student cost ceiling partitions on `sub`, so a caller-chosen `sub` makes those ceilings
non-binding. That is safe today only because the endpoint is closed (D-167's measurement).

### S45 — consent

**Status: frozen by D-152.** See the recorded asymmetry below — this block contains a
launch-blocking privacy item and is nonetheless inside the freeze.

(I9, I10): ledger (external ids + enums only, no PII), parent-grants-for-child capture UI,
age-band derivation, no-consent→no-token; legal text from the §6.1 track.

**Plus, assigned here by D-129 as T-02's disposition: §5.1.2's first-visit Adaptive Learning
notice** in `apps/learning-web` — the eleven required disclosures, gated on the §6.1 track having
enumerated them, following `LocationConsentModal.tsx`'s pattern for §5.1.3. It was owned only by
implication until [TRACEABILITY.md](../../TRACEABILITY.md) went looking for it.

### S46 — role scoping + frontend completion

**Status: frozen by D-152.**

(I2, I8): student/parent-only issuance, the formal D-086 disposition, entry/login/session UX
end-to-end in both apps.

### S47 — integration-specific test pass

**Status: frozen by D-152.**

E2E against a production-schema replica seeded with realistic edge data (soft-deleted children,
NULL attendance, unknown roles, unverified accounts, duplicate signups), auth abuse tests,
staleness drill, PII re-audit of the new login path.

---

## Sessions 48–51 — Rollout *(INTEGRATION_PLAN §5, §6)*

**Status: unstarted — downstream of frozen sessions, not itself frozen.** D-152 does not freeze
these; they simply cannot run before S43–S47, which are frozen. That distinction matters because
this block contains launch-blocking security work (see the asymmetry below), so treating it as
"frozen too" would hide a launch dependency behind someone else's freeze.

S48 production environment (`terraform/environments/production`: multi-AZ, ≥2 tasks, deletion
protection, dev-token gates off, domains + ACM + additive DNS, alarms to a monitored inbox);
S49 real credentials + feature-flag audit (SES or email flag-off; Maps/Calendar/YouTube
real-or-off) and the live connectivity path; S50 A7 close-out (WAF, backup-restore drill, ZAP
on prod config, runbook updated for the integrated topology); S51 pilot start + graduated
rollout (allowlist → single-branch pilot → all branches → public chat).

---

## The recorded asymmetry

Three launch-blocking items sit on the wrong sides of the freeze line, and this is recorded rather
than resolved:

- **S45 is inside the freeze** and carries a launch-blocking **privacy** item — the consent ledger
  and §5.1.2's first-visit notice.
- **S50 A7 is in the unfrozen-but-unstarted block** and carries two launch-blocking **security**
  items — **GuardDuty** and **WAF**.

So one launch-blocking privacy item is frozen while two launch-blocking security items are merely
unstarted. Neither placement is being changed here; the point is that "frozen" and "unstarted" are
not the same status and neither implies "not launch-blocking".

## Dependency spine

S35 → the four audits → stabilization → **gate** → discovery (S42) → adapter → auth →
consent/scoping → integration testing. Parallel: A6 real content — the *knowledge* half (3 of 23
docs real) gates the *pilot*, but the **curriculum half now gates launch (D-185, 2026-08-05)**, so
it has its own track in the roadmap and this parenthetical no longer states its own scope; A7 gates
*public* chat promotion, not the pilot; §6.1 legal docs gate the pilot.

---

*Provenance: extracted 2026-08-20 from `ROADMAP.md` (now `docs/archive/ROADMAP.md` after this
migration) lines 1436–1530. The sequencing rationale and dependency spine are carried; nothing
else was altered. No acceptance criteria were authored, because the source holds none for
S43–S51.*
