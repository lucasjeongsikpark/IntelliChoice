# Audit registers — ID namespaces and how to cite them

Three audit registers live in this directory. **They collide on identifiers**, and none of them
states its relationship to the other two. This file is the namespace map. Created 2026-08-20.

## The rule: a bare audit ID never uniquely identifies a finding

Always cite **`<document>:<id>`** — `AUDIT_FINDINGS.md:AUD-L-19`, not `AUD-L-19`. A bare ID is
ambiguous, and the ambiguity is not theoretical: `AUD-L-01`…`AUD-L-19` exists in **two** registers
with **unrelated** meanings. `AUDIT_FINDINGS.md:AUD-L-19` is a P2 exam-membership scoring defect;
`AUDIT_LIVE_2026_08_17.md:AUD-L-19` is a P3 narrative replaying on resume. Nothing marks either as
the "real" one. The reconciliation corpus adopts the same qualified-citation rule.

**Cross-register references are unmarked too.** `AUDIT_LIVE_2026_08_17.md` cites `AUD-F-27` and
`AUD-F-02`, which are `AUDIT_FINDINGS.md` findings — so inside that file some bare IDs are local and
some point elsewhere, distinguishable only by prefix. Prefix is not a reliable guide either: see
`AUD-L`, below.

## Namespace map

| register | prefixes and ranges | notes |
|---|---|---|
| `AUDIT_FINDINGS.md` | `AUD-L-01…19` (S36, learning product correctness) · `AUD-C-01…27` (S37, chat product correctness) · `AUD-X-01…16` (S38, cross-cutting integrity) · `AUD-F-01…38` (S39, frontend contracts + operations) | Four namespaces, one per audit session. The letter encodes the **session/area**, not the app. |
| `AUDIT_2026_08_16.md` | `P1-1…P1-10` only | P2 (§3) and P3 (§4) findings are **unnumbered prose** — there is no ID to cite, so cite the section. Contains **no** `AUD-*` IDs of its own. |
| `AUDIT_LIVE_2026_08_17.md` | `AUD-L-01…19` · `AUD-CHAT-01…15` · `AEL-01…06` · `EDGE-CHAT-01…08` | `AUD-L-*` here is a **full reuse of `AUDIT_FINDINGS.md`'s `AUD-L` range with unrelated meanings** — including `AUD-L-19`, the very ID that had already been renumbered to resolve an earlier collision. |

## One sentence each, and how they relate

- **`AUDIT_FINDINGS.md`** (5,822 lines) — the Phase 0A register for audit sessions S36–S39, one row
  per finding with reproduction and evidence; **frozen 2026-08-05 by D-183**, so it is the historical
  baseline the other two were written against, not a live worklist.
- **`AUDIT_2026_08_16.md`** (300 lines) — four post-C1 sweeps (learning-web UI/UX, chat-web UI/UX,
  timing/races, observability), 46 findings, source-read rather than browser-driven; its ten P1s are
  closed (D-373 → D-380) and its P2/P3 remainder is the backlog `AUDIT_LIVE_2026_08_17.md` then
  walked live.
- **`AUDIT_LIVE_2026_08_17.md`** (142 lines) — four `agent-browser` walks over the **deployed** build,
  and the only register whose findings come from the running system; its value is the coverage
  critique (the Playwright suite was green on the same build that carried both P1s), and it partly
  re-finds and partly extends the 08-16 sweep.

## No mechanical re-map exists — do not renumber

The one renumber that happened — `AUD-L-17` → `AUD-L-19` in `AUDIT_FINDINGS.md`, applied 2026-08-04
by D-174 because D-159 minted an ID S36 already held — was applied **per reference**, and ranges were
**deliberately left ambiguous** rather than rewritten. There is therefore no table that maps old IDs
to new ones, and documents written before 2026-08-04 still say `AUD-L-17` for what is now
`AUD-L-19`. Consequences:

- **Renumbering is not attempted.** Any repo-wide `AUD-L-17` → `AUD-L-19` substitution would corrupt
  both the pre-2026-08-04 citations that are correct as written and the unrelated
  `AUDIT_LIVE_2026_08_17.md:AUD-L-17`.
- **Resolve IDs by reading the cited document**, and qualify every new citation with its document.

## Location note

The three registers land in this directory at the migration's move step; until then they are at
`docs/AUDIT_FINDINGS.md`, `docs/AUDIT_2026_08_16.md` and `docs/AUDIT_LIVE_2026_08_17.md`. This file
is created ahead of them on purpose — every cross-document finding lookup after 2026-08-16 is
ambiguous until the rule above exists somewhere.
