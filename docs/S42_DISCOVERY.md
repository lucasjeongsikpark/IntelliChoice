# S42 Discovery — the production system, read from its own source

**Date:** 2026-08-01 · **Decision record:** D-151 · **Status:** source half complete; runtime half
still owed (§7)

The existing `go.intellichoice.org` system's source was made available locally at
`../IntelliChoice-web` (`icrest/` = Node/Express + Sequelize backend, `icweb/` = CRA React
frontend, `docs/codebase-analysis/` = a pre-existing 15-part analysis). The user designated it
**the source of truth for the existing system**. This document is what S42's discovery scope
(ROADMAP "Sessions 42–47", INTEGRATION_PLAN §5) asked for, answered from source instead of from
org recollection — which is strictly better evidence for every question source can reach.

## 0. Method, and what it is NOT

Eight parallel readers over the production source (auth/login, signups/attendance, schema, API
surface, time/timezone, the React consumer, the prior analysis docs, and the new stack's own
assumption baseline), synthesized into per-question answers, then **the ten most load-bearing
claims were re-read by independent adversarial verifiers instructed to refute them**. Result:
**8 CONFIRMED, 2 REFUTED-with-correction, 0 unclear.** Both corrections made the finding *more*
severe, not less — they are in §3 and §6.

The single most load-bearing claim (§2) was additionally verified by hand before being written
here, per this project's standing rule that a new measurement gets a control before its first
reading is quoted.

**Limits, stated plainly:**

- **Source ≠ deployment.** Everything below describes *this checkout*. Whether the deployed
  build matches it is unverified (§7). `sequelize.sync({alter: true})` (§4.5) means even the
  *schema* is not pinned by source.
- **Credentials were never read.** `icrest/app/config/db.config.js` and the committed Gmail
  service-account key were excluded by construction. Where a secret's *existence* matters, this
  document names its file and role and never its value.
- **Runtime facts remain org-only** (§7): network reachability from AWS, TLS/proxy topology,
  outage history, DNS, and the timezone *decision*.

## 1. Headline

**O1b is feasible.** `GET /api/accounts/signups` carries per-child, per-session `attended`,
scoped to the caller. That was the one fact O1b was contingent on (INTEGRATION_PLAN §3.1), and
it means **the attendance gate needs no direct-MySQL path at all** — the integration can sit on
I11 rung 1 (API-only), the lowest-coupling rung. Recommendation and its conditions: §8.

## 2. The signups contract — the O1/O1b decider

`icrest/app/routes/account.routes.js:13` mounts `GET /signups` under `app.use('/api/accounts',
router)`, so the path is `GET /api/accounts/signups`.

`account.controller.js: getSignups` builds its response from `Calendar.findAll({ include: [{
model: Signup, required: false, where: { accountId: account.id } }] })` and pushes the **full
Sequelize instances** into the response — there is no `attributes` restriction anywhere in the
handler, so every Signup column serializes. `app/models/signup.model.js` defines
`attended: BOOLEAN, allowNull: true`. Therefore each returned signup carries:

`id, hours, attendanceClaimed, attended, createdAt, updatedAt, calendarId, accountId, childId, chapterId`

**Response shape:** `{ account: {firstName, lastName, locationId, children[], profile}, locations[],
calendars[], pastCalendars[] }`

- `calendars` — non-deleted calendars whose signup window is currently open
  (`opensForSignups < now < closesForSignups`), across **all** locations, each with nested signups
  filtered to the caller. Ordered `startTime ASC`.
- `pastCalendars` — non-deleted calendars with `closesForSignups < now` where the caller has at
  least one signup (`required: true`). Also `startTime ASC`. **No pagination** — this grows
  without bound per account.
- Nested signups are filtered by **`accountId` only, never `childId`**, so a parent's array mixes
  their own signup (`childId` null) with one row per child (`childId` set). Per-child attendance
  is derived by matching `signup.childId` against `account.children[].id`.
- Session date **and** time live in the single `calendars.startTime` DATETIME. There is no
  separate date column and no session title.

**Guard:** `authBackgroundCheckNeeded` — `Student`/`Parent` pass unconditionally; other roles
additionally need `backgroundCheckStatus ∈ {passed, notNeeded}`, else 403 with code 4011.

**Three derivation hazards, all fail-closed-able:**

1. `attended = null` means *never marked*, not absent. It **must** be treated as not-present
   (CLAUDE.md rule 5), and it is the common case for any session a manager has not processed.
2. The `children` include has **no `deleted: false` filter**, so soft-deleted children are
   returned. The adapter must filter them; production's own read paths mostly do not.
3. "Attended this week" must be derived from `attended = true` on a calendar whose `startTime`
   falls in the current org-local week — which is exactly where the timezone question (§5) bites.

## 3. The login contract (O1's trust anchor)

`POST /api/accounts/login`. Reads exactly two body fields: `email` (lowercased server-side) and
`password` (plaintext, HMAC-SHA256-hashed before lookup).

**Success 200:** `{ token, profile: bool, name: string, permissions: string[] }` — and nothing
else. **No account id, no email, no role.** A caller needing identity must follow with
`GET /api/accounts`.

- `name` **falls back to the account email** when `firstName` is null.
- `profile` is true only when `firstName != null` **and** `lastProfileUpdateAt >= 2024-08-01`
  (a hard-coded staleness date).
- `permissions` is derived per request from role + `chapterRole` + the free-text
  `accounts.permissions` CSV (a `-` prefix removes).

**Error paths:**

| Condition | Status | Body | Note |
|---|---|---|---|
| Missing/empty email or password | 400 | `Content can not be empty!` | falsy check — empty-string password is 400, not 401 |
| Wrong password **or** unknown email | 401 | `Invalid email or password` | one combined `findOne(email + hash)` — **indistinguishable**, no user enumeration here |
| `verifiedAt === null` | 400 | `Verify your email` | **and re-sends the verification code email** |

⚠️ The unverified branch is reached **only after the password matches**, so a 400 there confirms
the credentials were correct — and it triggers an email send. The new stack must never surface
this path to end users.

**Side effects:** exactly one write — `lastLoggedinAt = now` plus Sequelize's automatic
`updatedAt`, on the fully successful path only. No login counter, no failed-attempt column, no
last-IP.

**Rate limiting: none.** Not on login, not anywhere. `package.json` declares only
`cors, express, jsonwebtoken, mysql2, nodemailer, sequelize, csv-stringify`; `server.js`
registers only `cors`, `json`, `urlencoded`. The new stack's own per-account + per-IP limiter is
therefore not a nicety — without it the new login endpoint would be a *better* brute-force oracle
than production's own.

**⚠️ REFUTED-and-corrected (KC2).** The first reading said a DB error becomes "a hung socket".
The verifier showed that is wrong in the direction that matters — see §6.1.

## 4. Schema — INTEGRATION_PLAN §1 verified

All four §1 schema claims **hold**:

| §1 claim | Verdict |
|---|---|
| `accounts` has 23 columns | ✅ for **model attributes**; the physical table is **28** once Sequelize adds `id/createdAt/updatedAt` + FKs `locationId`, `chapterId` (both nullable). Worth restating in §1 to avoid a reader mistaking it for table width. |
| `children.deleted` soft-flag | ✅ BOOLEAN NOT NULL. `children` and `calendars` are the only soft-delete tables; no `paranoid`/`deletedAt`. |
| `locations` has no address/coords/manager email | ✅ **only** `name` (unique), `online`, `active`. |
| `signups.attended` nullable | ✅ tri-state BOOLEAN. `hours` is DECIMAL(10,2), set to 2 (online) / 3 (in-person) only when attendance is marked. |

**4.1 Roles.** `accounts.role` is free-text `STRING NOT NULL` — **no enum, no validator, no
allowlist**. Exactly four Title-case values appear across both repos: `Parent`, `Student`,
`Tutor`, `Manager`. **There is no admin role** (a case-insensitive `admin` grep over `icrest`
returns zero); elevated access comes from the separate free-text `permissions` column.
`data.sql` contains no role strings at all. A second, unrelated free-text vocabulary exists in
`chapterRole`, hardcoded **only** in the frontend, with typos preserved:
`President`, `Vice President`, `Tresurer`, `Secretery`.

⚠️ **REFUTED-and-corrected (KC3):** the claim that `Manager` is server-assigned is **false**. The
register endpoint stores the client-supplied role string verbatim; the Parent/Student/Tutor limit
exists **only in the frontend form**. See §6.2. For the integration this means: **production role
strings are unvalidated user input**, so I7's mapping must fail closed on anything outside the
four known values, and a `SELECT DISTINCT role` against live data is the only way to learn what is
actually stored.

**4.2 Grades.** `gradeLevel` is **INTEGER** (0 = Kindergarten, 1–12), nullable on `accounts`,
NOT NULL on `children`. The new stack's `StudentProfile.grade` is typed `str`, so the adapter must
format (0 → `"K"`).

**4.3 Ids.** Integer auto-increment PKs; **no external ids anywhere**. The adapter mints
`acct-<id>` / `child-<id>` (two disjoint populations) per I3.

**4.4 Parent–child.** `children.accountId` FK NOT NULL — a direct ownership edge, **not** a join
table.

**4.5 Schema drift.** `db.sequelize.sync({ alter: true, force: false })` runs on **every boot**,
issuing `ALTER TABLE` against the live production database; there are no migrations. A sync
failure is only `console.log`ged and **the process keeps serving**. Collateral proof that this
does real damage: `scripts/drop-indexes.sh` exists solely to delete the duplicate unique indexes
(`email_1, email_2, …`) that `alter: true` recreates each boot — and it runs `sudo mariadb ic`,
confirming the engine is MariaDB and the database is named `ic`. **Consequence: I12's drift
defense (contract tests against a schema snapshot + a deploy-time read-only column probe +
degraded `/readyz`) is justified, not defensive over-engineering.**

**4.6 A latent association bug.** `models/index.js:84` wires `db.signups.belongsTo(db.children)` a
second time where `belongsTo(db.chapters)` was evidently intended; `signups` gets a `chapterId`
column (from `chapters.hasMany`) but no Sequelize chapter association. Harmless for our reads —
recorded so a future reader does not "fix" our adapter to match a broken association.

## 5. Time and timezone

**Storage is unambiguous.** All session datetimes are `Sequelize.DATE` (MySQL DATETIME), and the
connection is created with **no `timezone` option**, so Sequelize's default `+00:00` applies:
stored values are **UTC instants**, not server-locale-dependent.

**Display and reporting disagree with each other.** The report queries hard-code
`CONVERT_TZ(startTime, '+0:00', '-6:00')` at **three** sites — US Central *Standard* time,
year-round, **DST-unaware**. The frontend, meanwhile, renders with browser `Intl.DateTimeFormat`
and no explicit zone, i.e. **DST-aware local**. No timezone library exists in either repo
(`moment`, `dayjs`, `date-fns`, `luxon` all absent) and the string `America/Chicago` appears
nowhere.

**Verdict:** source **confirms** the org operates in US Central — all branches but Leupp AZ are
Central, and the seed data names sessions `Online 10 AM Central` / `Online 11 AM Central`. Source
**cannot** decide the convention: production itself implements the weaker fixed-offset in reports
(so in summer its reports show every session an hour early) while showing DST-aware times in the
UI. `ORG_TIMEZONE=America/Chicago` is confirmed; `ORG_TIME_CONFIRMED=false` should **stay false**
until the org answers Message A.

**Why it matters here and nowhere else:** the two conventions only disagree about a session's
*date* for sessions starting between 00:00 and 01:00 local — and about which *week* a session
belongs to for Sunday-evening sessions. Those are the only windows where a student who did attend
could be turned away by the weekly gate.

## 6. Findings in the production system (the org's decisions, not this roadmap's work)

These were found while answering integration questions. They are **not** in this project's scope
to fix — production is frozen by constraint — but leaving them unreported would be wrong.
Ordered by severity.

**6.1 (High) A single unauthenticated request can stop the API process.** The login handler is
`async` with no `try`/`catch`, and it calls string methods on `req.body.email` with no type
guard. A request whose `email` field is a non-string passes the falsy check and then throws, which
in an `async` handler becomes a **rejected promise Express 4 never sees** (its layer try/catch is
sync-throw only). No `unhandledRejection`/`uncaughtException` handler exists anywhere in the repo,
and the Node version is unpinned (no `engines`, no `.nvmrc`, no Dockerfile), so **on Node ≥ 15 the
default `--unhandled-rejections=throw` terminates the whole process**; only on Node ≤ 14 does it
hang a single socket. Same shape exists at `POST /api/accounts/resendCode`.
**Fix is small:** wrap the handlers in `try`/`catch` (or add a process-level handler and a typeof
guard). Worth telling whoever operates the box even though our integration will not trigger it.

**6.2 (High) Role is self-assignable at registration — and the org's own policy says it should not
be.** The register endpoint (`account.controller.js:26,33`) persists `req.body.role` verbatim —
no allowlist, enum, or validator. The Parent/Student/Tutor restriction lives **only** in
`icweb/src/components/register.component.js`'s three radio buttons, so a direct API call can set
any string, including `Manager`, which `auth.service.js` maps to branch-level permissions.

**Confirmed as a gap, not a design choice (D-153 §7):** the intended policy is that Student,
Parent and Tutor are self-selected while **`Manager` is granted by an administrator only** — which
is what the frontend implements and what the backend fails to enforce. There is no role-changing
endpoint anywhere, so `Manager` is in practice assigned by direct database edit; nothing in code
holds that up.

**A second path to the same escalation, targeting an account that already exists:**
`account.controller.js:56` — on `ER_DUP_ENTRY`, if the existing account has `verifiedAt === null`,
the handler **overwrites its `password`, `role` and `code`**. So an unverified account's role (and
password) can be rewritten by anyone who knows its email, with no proof of control over it.

**Fix (small, entirely inside the existing system):** allowlist `Parent`/`Student`/`Tutor` at
create and reject anything else with the 400 the handler already returns for missing fields; do
not accept a role at all in the duplicate-unverified branch. `Manager` stays a database/admin
operation, unchanged.

**Our side does not relax when that lands** — see D-153 §7: pre-fix rows may already carry a
self-assigned `Manager`, production is frozen and schema-drifting so we cannot assert the fix
persists, and authorization is not something this stack delegates to another system's input
validation (CLAUDE.md rule 3). `Tutor`/`Manager` stay behind an allowlist we control.

**6.3 (Medium) Credentials in logs.** The login handler `console.log`s the email and the stored
password hash on every attempt; the frontend `console.log`s the plaintext credentials object and
the token. Severity depends entirely on where stdout goes and who can read it — an org-only fact.

**6.4 (Medium) The 6-digit code is weak and over-shared.** One `accounts.code` INTEGER column
serves **both** email verification and password reset, generated with `Math.random` (not a CSPRNG),
with **no server-side expiry** (despite the email copy saying 20 minutes) and no rotation after
use — and no rate limiting in front of it.

**6.5 (Known, unchanged) Committed credentials.** Database credentials and a Google service-account
key remain committed to the production repo and in its history permanently. Already recorded in
INTEGRATION_PLAN §7; restated because it bounds everything above.

**6.6 (Informational) Token transport.** The token is read as
`req.body.token || req.query.token || x-access-token` — **no `Authorization: Bearer`** — and this
expression is duplicated verbatim in two files. Because GETs have no body, the frontend
authenticates with `?token=`, so JWTs land in access logs, proxy logs, browser history, and
`Referer` headers. Tokens are HS256 `{id, iat, exp}`, 12 h, signed with a source-visible literal,
with **no revocation and no logout endpoint**; expired/forged/malformed are all `403
Authentication failed`, so a client cannot drive refresh off status codes.
→ **Our integration must call with the `x-access-token` header, never the query param.**

**6.7 (Correction) A liveness endpoint does exist.** `GET /` returns 200 with a stock message —
so INTEGRATION_PLAN's "no health endpoint" is inaccurate for *liveness*. But it never touches the
database, and `sync` failures are non-fatal, so **200 on `/` does not imply the app can serve
data**. Availability measurement must exercise a DB-backed endpoint.

## 7. What still needs the org

Source access collapsed most of the original asks. What genuinely remains:

**Message A (timezone) — still needed, unchanged.** Source confirmed the facts; the *decision*
(true DST-aware Central vs. matching production's fixed UTC−6) is operational and not ours. Also
still needed: confirmation the org is in US Central, and whether any **Sunday-evening** or
**00:00–01:00** sessions exist — the only windows where the two conventions disagree about which
week a session belongs to.

**Message B (DNS) — unchanged.** Additive records for `learning.`, `chat.`, and a mail subdomain.

**Message C (topology/reliability) — unchanged and now sharper:**
- Where the `ic` MariaDB actually runs and whether it is reachable from AWS (only needed if we
  fall back to O2 — O1b removes this from the critical path).
- What terminates TLS and applies the production CORS origin. Source serves plain HTTP with CORS
  pinned to `http://localhost:3000` and an SPA API base hard-coded to `http://localhost:8080/api`,
  so **something upstream must be rewriting this** — and whether a proxy/WAF fronts the app
  materially changes §6.1 and §6.6.
- Observed outage history (no monitoring exists in code; S42 measurement can partly substitute).
- Where stdout goes (bounds §6.3).

**Message D (capacity) — unchanged.** Peak simultaneous users.

**New, and answerable only against the live system:**
- `SELECT DISTINCT role FROM accounts` — the real role vocabulary, since role is unvalidated input.
- `SHOW CREATE TABLE` for the five tables — how far `alter: true` has drifted the live schema from
  the models, and the `accounts.password` collation (which decides whether the SQL-side password
  compare is case-sensitive).
- Whether the deployed build matches this checkout.

## 8. Recommendation for the auth decision (yours to make)

**O1b**, on the evidence in §2: the signups listing carries per-child `attended` scoped to the
caller, so attendance needs no DB path, and the integration stays coupled to a *public HTTP
contract* rather than to production's internals. Concretely the new stack would: call
`POST /api/accounts/login` server-side, use the returned 12 h legacy token **transiently and
header-borne** for `GET /api/accounts` and `GET /api/accounts/signups`, discard it immediately,
and mint its own SPEC §5.1.2 token gated by consent (I9), fail-closed role mapping (I7), and
`verifiedAt` (I15) — plus the per-account + per-IP rate limiting production lacks.

**O2 (HMAC re-verification) stays the documented fallback**, to be chosen only if measurement
shows the login endpoint is unreachable or unreliable from AWS — it buys independence from icrest
uptime at the cost of the tightest possible coupling (an unsalted single-key scheme that would
break login *silently* if production ever fixed its hashing).

**Two things no auth option provides**, unchanged: branch **address/coordinates** have no
production source at all (they must come from the new stack's own `org_branches`, joined by branch
name), and **manager email** must be derived by joining `accounts` on `locationId` where
`role = 'Manager'` — which, per §6.2, is an unvalidated string.

**This is a recommendation, not a decision.** Per INTEGRATION_PLAN §3.1 it belongs in
DECISIONS.md with §7 residual-risk acceptance before S44 implements.

## 9. Consequences for the new stack (S43's real work list)

The MySQL dev fake models a system that **does not exist**. Every row below must be fixed before
`IcProfileAdapter` contract tests mean anything — a green test against the current fake is
evidence about a fiction.

| What | Production reality | Dev fake today | Severity |
|---|---|---|---|
| Branch metadata | `locations(name, online, active)` only | `branches(external_id, name, manager_email, address, latitude, longitude)` | must-fix |
| Roles | free-text, `Parent/Student/Tutor/Manager` | `ENUM('student','parent')` — wrong case, structurally cannot hold Tutor/Manager | must-fix |
| Attendance | per-session `signups.attended` tri-state + `calendars.startTime` | `attendance(student_external_id, week_key, status ENUM)` — pre-reduced to weeks | must-fix |
| Ids | integer PKs, no external ids | opaque `VARCHAR(64)` external ids | must-fix |
| Parent→child | `children.accountId` FK | `parent_child_links` join table | must-fix |
| Grade | INTEGER, 0 = K | `VARCHAR(16)`, and the Protocol types it `str` | must-fix |
| Unknown attendance | `attended = null` ⇒ not present | absent row ⇒ `UNKNOWN` | cosmetic — same intent |

The right shape for S43 is **production-shaped fixtures captured from this source** (and, once
available, from a live read), not an incrementally extended dev fake: the fake's job was to let
the app boot without the org, and it has been doing that faithfully against the wrong schema.
