# 2026-08-23 — the D-324 date-zone pair resolved (seventh Orca coordinator/executor run)

Historical narration only — non-authoritative (DQ-1). Current state: `docs/PROJECT_STATE.md`;
durable evidence: `apps/learning-web/src/lib/orgDate.ts`, `apps/chat-web/src/lib/eventDateTime.ts`,
their tests, and git history. No new judgment was made, so no DECISIONS entry exists for this
session.

**Queue-gate note.** Queue row 1 (RD-01's Sunday confirmation) stays time-blocked until
2026-08-24 18:30 UTC, so the cursor took row 2: `DRIFT-59-DATE-SHIFT` + `WORK-40-TZ` (also
closing `WORK-40`'s residual third build item).

**What was done.** Seventh Orca run. Frozen Spec `tasks/date-zone-rendering-pair.md`
(run `run_462c3ce718a4`, task `task_18737238f34d`, dispatch `ctx_74e87fcb6c63`; agent `claude` /
model `opus` / effort `high`, receipt requested == effective). Zero correction rounds. The
coordinator's spec pre-identified that no shared frontend TS package exists (`ui-brand` is
CSS/assets only) and that `CalendarEvent.start_datetime`'s wire shape was unpinned.

**What the executor delivered (two commits, landed by PR #375 as `8e82ba9`/`805e986`).**

- **learning-web (`8e82ba9`):** `buildDateLabelFormatter` relocated to the exported
  `src/lib/orgDate.ts` (D-324's comment record travels verbatim) with the date-only back-a-day
  shift fixed — recorded failing first (`2026-08-22` → `8/21/2026` under `America/Chicago`);
  the six instant-path guards passing pre-fix proved the relocation behaviour-preserving.
- **chat-web (`805e986`):** `CalendarActionModal` renders through the new
  `src/lib/eventDateTime.ts`. The wire shape was pinned from primary evidence as **mixed by
  path**: `to_calendar_event` copies tz-aware `OrgEvent.starts_at` → offset-tagged instants,
  converted into `event.timezone`; `extract_calendar_event` builds naive wall-clock from
  model-drafted text, whose repo-settled meaning (`ics._to_utc`: `dt.replace(tzinfo=tz)`) is
  "in `event.timezone`" → rendered as its own components. Locale pinned `en-US`; every failure
  path returns the value as written. Pre-fix under `TZ=Asia/Seoul` a Chicago event rendered
  `11/2/2023, 2:00:00 AM` beside a `(America/Chicago)` suffix — wrong hour, wrong day,
  self-contradictory on a rule-4 approval surface. No schema/API change was needed.

**Evidence.** Test-first failing runs both apps; vacuity controls per fix plus in-test TZ-pin
controls (`Intl` resolvedOptions asserted `Asia/Seoul`, so an org-zone machine cannot make the
assertions vacuous); learning-web 34/34, chat-web 67/67, both `tsc -b`/lint clean (two
pre-existing lint warnings unchanged), `make lint typecheck test` exit 0 (1778 passed).
Coordinator independently re-ran both suites and a render-zone mutation kill (13 failed as
predicted, reverted). All 12 CI checks green on PR #375.

**Reconciliation applied.** PROJECT_STATE: three rows deleted (`WORK-40-TZ` §4.1,
`DRIFT-59-DATE-SHIFT` + `WORK-40` §4.2; counts 21→18, 12→11, 9→7), §4.3 paragraph deleted (now
"two items"), queue row deleted and renumbered (17 rows), the multi-section fan-out key list
updated, snapshot header to `805e986` — **the deploy gap reopened at 2 product commits** (both
SPA fixes are HEAD-only until the next deploy; §1/§3 restated). Register: dated resolution
annotations on both entries — including the armed-not-firing nuance on DRIFT-59 (the
learning-api side already serializes tz-aware deliberately) and the corrected "shared module"
premise on WORK-40-TZ (two genuinely different functions → two mirrored app-local modules;
`WORK-40`'s phantom-symbol residual closes with it). DECISIONS: untouched — the two-modules
shape was pre-authorized by the Frozen Spec's boundaries, not a new judgment.

**Unresolved handoff items.** (1) Both fixes are deploy-gated — staging renders the old
behaviour until the next deploy (the reopened 2-commit gap). (2) `OPEN_DECISIONS #10`'s
"ALL DECIDED" heading with the phantom `formatDateLabel` symbol lives in `docs/archive/` —
historical, not corrected (archives are never rewritten; the register annotation carries the
correction). (3) The register's severity question — whether chat-web's calendar approval is
reachable by parents/managers in other zones — needs the deployed build (a live-probe question).
(4) Queue row 1 remains RD-01's Sunday 2026-08-24 confirmation.

**Commits/SHA.** Worktree `d4dd112`/`4ab5cd1` on `lucasjeongsikpark/date-zone-rendering`; landed
as `8e82ba9`/`805e986` by PR #375.
