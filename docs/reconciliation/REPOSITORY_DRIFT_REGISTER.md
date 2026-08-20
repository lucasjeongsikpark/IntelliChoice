# REPOSITORY_DRIFT_REGISTER.md — Phase 3A drift register

**Date:** 2026-08-19. Companion to `REPOSITORY_STATE_EVIDENCE.md`.

This file **records divergence between documented intent and repository-observed state. It fixes
nothing and decides nothing.** Every entry traces to evidence a Phase 3A inspector captured or to a
ruling in the Phase 3A adjudication. Where an inspector's self-chosen severity differed from the
adjudication, the adjudication's ruling is used verbatim.

## 1. How to read this register

**HIGH** means a reader or operator acting on the current documents would do something wrong (send an
already-answered question to the org, trust a stale deployment description, work a frozen plan as
live), or a real-world obligation against a live system is invisible in the documents that are
supposed to carry it. **MEDIUM** means materially misleading, or a requirement/expiry condition with
no owner — unlikely to cause an immediate wrong action but wrong to rely on; entries marked
"high-adjacent" were adjudicated MEDIUM–HIGH and are recorded at MEDIUM per the register's
convention, likewise "medium-adjacent" for LOW–MEDIUM. **LOW** is precision and staleness noise:
counts, line citations, wording that reads wider than the code. Two booleans accompany each entry.
*Resolvable by Phase 3B?* asks whether live observation of the deployed system could settle the
divergence — most documentation drift is "no" because the defect is an unmade edit, not an unknown
fact. *Genuine decision required?* asks whether closing the entry needs a judgement (product, legal,
or operational) rather than an edit or a mechanical fix; where it is "yes" the entry names the
question and does not answer it.

Entries are grouped HIGH → MEDIUM → LOW and numbered in insertion order within those bands.
**DRIFT-98 onwards are late additions** from inspector W10's coverage-gap closure (ARCH-01, SEC-20,
TEST-04, TEST-10, WORK-35), appended at the end of the entry list rather than renumbered into their
bands — so the **Severity** field, not the id, is authoritative for a given entry's severity.

## 2. Drift entries

### HIGH

- **Drift ID**: DRIFT-01
- **Title**: FINAL_ARCHITECTURE.md presents three superseded status claims as current
- **Related claims**: ARCH-26, ARCH-27 (staleness carried here), ARCH-21 (question 5 still unowned) / **Related decisions**: D-004, D-085–D-094 (S33), D-095 (S34), D-334/D-335/D-349
- **Intended state**: The document's own L183-185 instructs that it be regenerated; its status claims were 2026-07-21 projections.
- **Observed state**: All three claims are stale. `PROGRESS.md:10456` records "S33 (Security hardening) shipped, 2026-07-23"; `:10364` records S34 shipped 2026-07-24; `DECISIONS.md:29` records D-004 as "accepted, decided at S32 2026-07-22" while FINAL_ARCHITECTURE still calls it "proposed". Its "known gap" single-instance SSE bus is closed by `SessionEventBus`/`SessionEventRelay` over Postgres `LISTEN`/`NOTIFY` (`ARCHITECTURE.md:610-631`, chat-api since D-349). The file was never regenerated. Its open question 5 (six-logical-DB / schema split) also remains unowned: terraform creates a single `db_name` per engine and `alembic/env.py:36` is `target_metadata = Base.metadata` with no `include_schemas` or `schema_translate_map`.
- **Evidence**: `docs/FINAL_ARCHITECTURE.md:112-120`, `:146-152`, `:175-176`, L183-185; `docs/PROGRESS.md:10364`, `:10456`; `docs/DECISIONS.md:29`; `docs/ARCHITECTURE.md:610-631`; `packages/db/alembic/env.py:36,59,72`.
- **Severity**: HIGH
- **Likely explanation**: Written as a forward projection at S32 and never regenerated as its own closing instruction requires; three sessions and one accepted decision landed in the following three days.
- **Resolvable by Phase 3B?**: no — the divergence is between the document and already-recorded session history, both in-repo.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-02
- **Title**: GuardDuty is "tracked to S50 A7" in TRACEABILITY but absent from every S50 A7 scope
- **Related claims**: SEC-17, TEST-06 (same attribution defect class), TEST-09 / **Related decisions**: D-125, D-087
- **Intended state**: D-125 deferred GuardDuty with a written reason and tracked it to S50 A7; SPEC §5.30.3 still requires it.
- **Observed state**: ROADMAP's S50 line reads "S50 A7 close-out (**WAF, backup-restore drill, ZAP on prod config, runbook** updated for the integrated topology)" — no GuardDuty. `INTEGRATION_PLAN.md:475`'s S50 row is identical and equally GuardDuty-free. The only GuardDuty mention in all of ROADMAP.md is `:1429`, inside tranche-1 narrative describing T-01 as a gap, not a scheduling entry. Terraform contains no `aws_guardduty_*` resource; the absence is annotated at the CloudTrail wiring site (`terraform/environments/staging/main.tf:740-742`). So a required control is deferred to a destination that does not list it.
- **Evidence**: `docs/TRACEABILITY.md:737-744`; `docs/ROADMAP.md:1516-1519`, `:1429`; `docs/INTEGRATION_PLAN.md:475`; `docs/SPEC.md:2868`; `terraform/environments/staging/main.tf:740-748`; `terraform/modules/cloudtrail/main.tf:10`.
- **Severity**: HIGH
- **Likely explanation**: The deferral was recorded in TRACEABILITY and in D-125's prose, but the corresponding edit to ROADMAP's and INTEGRATION_PLAN's S50 A7 scope lists was never made.
- **Resolvable by Phase 3B?**: no — an in-repo scope list is missing an item; no live observation bears on it.
- **Genuine decision required?**: no — the recorded intent is A7; only the edit is missing.

- **Drift ID**: DRIFT-03
- **Title**: Two High findings against a live production system sit in an unsent draft with no send-status field
- **Related claims**: SEC-32, INT-13, INT-25 / **Related decisions**: D-151, D-152
- **Intended state**: The S42 security report is sent as one message to the production operator; §6.1/§6.2/§6.3/§6.4 all go on that message, and the E-group findings are notified to the org.
- **Observed state**: No send record exists anywhere. `S42_SECURITY_REPORT.md:1-13` carries only `**Drafted:** 2026-08-02 (S43)` with no send, recipient, or confirmation field, and `:12` still reads "**Send:** §6.1 …, §6.2 …, §6.3 …, §6.4". A corpus grep across PROGRESS/DECISIONS/ROADMAP for send/notification language in English and Korean (`통지`, `발송`, `notified`, `sent to the org`, `전달`) returns **zero** confirmations. PROGRESS's live pointer still lists it as the user's outstanding step: "**Send the two drafted messages** (written and send-ready; the remaining step is you sending them to the right people)" (`:13703`, also `:7726`). `S42_OPEN_QUESTIONS.md:39-40` still lists the E-group notification under "아직 유효한 예외:" and `:110` as one of only two currently-valid actions.
- **Evidence**: `docs/S42_SECURITY_REPORT.md:1-13`; `docs/PROGRESS.md:7726`, `:13689`, `:13703`; `docs/S42_OPEN_QUESTIONS.md:39-40`, `:94-104`, `:110`; `docs/DECISIONS.md:8928-8931`, `:9000-9005` (zero send records).
- **Severity**: HIGH — real-world, not documentation. The documents represent the action as open correctly; what is missing is the action and any field that would make its absence visible on the report itself.
- **Likely explanation**: The report was drafted at S42/S43 and the freeze (D-152) removed the org interaction that would have carried it; nothing re-owned the send.
- **Resolvable by Phase 3B?**: no — a send is an out-of-band real-world act; negative evidence in-repo cannot be improved by live inspection.
- **Genuine decision required?**: no — already decided; execution is owed. See DRIFT-04 for the sign-off obligation frozen the same way.

- **Drift ID**: DRIFT-04
- **Title**: R1's org sign-off has no occasion left, and R8/R9's expiry conditions have no monitor and lose their expiry text in one of two homes
- **Related claims**: SEC-33, INT-22, INT-33 / **Related decisions**: D-148 (gate closure), D-152 (freeze), D-086, D-097, D-107
- **Intended state**: §7-R1 is accepted as permanent "to be signed off by the org at S42 (discovery)"; criterion 2's closure is honest only because R8/R9 carry expiry conditions that are tracked.
- **Observed state**: (a) The R1 obligation occurs exactly once, at `INTEGRATION_PLAN.md:513`; a `sign.off|signed off` grep across DECISIONS/PROGRESS/INTEGRATION_PLAN/S42_SECURITY_REPORT returns nine hits, none about R1 or any org sign-off, and its only occasion (S42 org interaction) is frozen by D-152. I14's refresh check is prospective and scoped to S44, inside the frozen S43–S47 block. (b) The expiry conditions live only in `INTEGRATION_PLAN.md:503-507`, `:535`, `:551-565`; the copies at `ARCHITECTURE.md:605-609` reproduce the risks **without** the expiry text. Nothing tracks either trigger: R8's named closures (S43/S46) are frozen, and R9's commit-ordering fix is recorded untouched at `AUDIT_FINDINGS.md:71`. R9's own tripwire has no alarm (DRIFT-10).
- **Evidence**: `docs/INTEGRATION_PLAN.md:500-517`, `:535`, `:551-565`; `docs/ARCHITECTURE.md:605-609`; `docs/AUDIT_FINDINGS.md:71`; `docs/ROADMAP.md:1438-1445` (freeze banner), `:1492`; `docs/DECISIONS.md:8635-8660` (D-148 §1); `docs/reconciliation/DOCUMENTATION_RISK_REGISTER.md:108`.
- **Severity**: HIGH
- **Likely explanation**: The risks were accepted with closure sessions named; D-152 froze those sessions and no re-owning edit followed. The ARCHITECTURE copy was made for readability and dropped the qualifier that made the acceptance conditional.
- **Resolvable by Phase 3B?**: no for the ownership question; a live check of R9's counter would show today's value but not create a monitor.
- **Genuine decision required?**: yes — who owns the R1 sign-off now that its occasion is frozen, and who owns R8/R9 expiry monitoring. Cross-reference DRIFT-17 (the same expiry-vs-frozen-closure shape in code) and DRIFT-10.

- **Drift ID**: DRIFT-05
- **Title**: INTEGRATION_PLAN.md carries no trace of the freeze, and its §5 session table reads as live
- **Related claims**: INT-06, INT-07 / **Related decisions**: D-151, D-152, D-153, D-148
- **Intended state**: The plan is superseded as to timing and urgency by D-152/D-153; §5's table should be reconcilable against actual session history.
- **Observed state**: `grep -c "D-152\|D-153" docs/INTEGRATION_PLAN.md` = **0** — zero mentions of either decision anywhere in the file. The front matter (`:1-15`) is a 2026-07-24 "Rewritten … under a hardened scope constraint" block about production immutability, with **no freeze banner and no pre-freeze-artifact disclaimer**; the §3.1 auth gate at `:281-288` still reads as live. §5's 17-row table (`:455-476`) is accurate for S35–S41 and the Gate, wrong-as-current for S42 (source half done 2026-08-01/D-151, measurement half frozen, §3.1 option recommended not decided), and silently wrong for the frozen S43–S47; the dependency spine at `:479-482` still reads as a live sequence. It has no representation of the 27 W-sessions (W1–W27, D-393→D-423) that actually ran after the gate. A reader arriving from `ROADMAP.md:1438` gets the ⛔ banner; a reader opening this file directly does not.
- **Evidence**: `docs/INTEGRATION_PLAN.md:1-15`, `:281-288`, `:448-482`; zero-hit `D-15[23]` grep; `docs/ROADMAP.md:1438-1521`, `:2806-3304` (W1–W27); `docs/DECISIONS.md:8635`; `docs/PROGRESS.md:1238`.
- **Severity**: HIGH
- **Likely explanation**: The freeze was recorded where it was decided (ROADMAP, DECISIONS) and never propagated to the primary integration reference or its sibling S42 files.
- **Resolvable by Phase 3B?**: no — purely a documentation-state divergence.
- **Genuine decision required?**: yes — whether the file is deliberately preserved as a pre-freeze artifact or should carry a freeze banner / be marked historical. Its sibling files carry the same question separately: DRIFT-06 (`S42_ORG_ASKS.md`) and DRIFT-07 (`S42_OPEN_QUESTIONS.md`).

- **Drift ID**: DRIFT-06
- **Title**: ORG_ASKS' status table says "Send now" for a downgraded message and an already-answered one
- **Related claims**: INT-26 / **Related decisions**: D-152, D-153 §4
- **Intended state**: The status table is superseded post-D-152/D-153; Message A was downgraded to a courtesy question and Message B's subject was answered.
- **Observed state**: `S42_ORG_ASKS.md:7-14` still reads **A** Timezone convention → "**Send now**" ("The only item that changes what gets built"); **B** DNS additions → "**Send now**"; **C** DB hosting + API reliability → "Hold until S42". Its internal notes at `:386-389` still read "Message A is due **before S43 opens** … and Message B before **S48**" — S43 is frozen by D-152. The file's only dates are 2026-07-24/07-25 and it contains no D-152 or D-153 reference. `S42_OPEN_QUESTIONS.md:15-22` meanwhile records C3/DNS as answered ("조직이 통합 시점에 추가해줌"), C1·C2/timezone as closed by evidence, and Message A as downgraded to a courtesy question per D-153 §4. Anyone acting on this table sends the org a question it already answered.
- **Evidence**: `docs/S42_ORG_ASKS.md:1-5`, `:7-14`, `:386-389`; `docs/S42_OPEN_QUESTIONS.md:15-22`, `:108-113`; `docs/DECISIONS.md:9084-9097`, `:9122-9127`.
- **Severity**: HIGH
- **Likely explanation**: The dispositions moved into the OPEN_QUESTIONS ledger and D-153; ORG_ASKS was left as the pre-decision artifact without a marker.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: yes — whether ORG_ASKS gets a freeze banner or is marked historical. Same question as DRIFT-05 and DRIFT-07.

- **Drift ID**: DRIFT-07
- **Title**: S42_OPEN_QUESTIONS records C3 as answered-and-closed and as an urgent undeferrable action, in one file
- **Related claims**: INT-28 / **Related decisions**: D-152, D-153
- **Intended state**: The C3 half is superseded; only the E-group notification half remains current.
- **Observed state**: All three statements are live in a 121-line file. `:110` (under "## 지금 순서 (D-152 이후)") reads "**C3(DNS) 발송**, **E그룹을 조직에 통지** — 이 둘만 지금 유효"; `:76` marks C3 **🔴** "**미룰 수 없음** — 순수 리드타임"; `:17` reads "**C3(DNS)** — **가능하다고 확인됨. 조직이 통합 시점에 추가해줌** → 더 이상 미결 아님". The D-153 ledger at `:15-19` is dated 2026-08-02 while `:110`'s action list is dated to D-152 (2026-08-01) and was never updated. `:110` is the file's own "what to do now" list, and this file is the designated re-entry document for integration.
- **Evidence**: `docs/S42_OPEN_QUESTIONS.md:17`, `:39-40`, `:74-78` (C3 row at `:76`), `:106-113`.
- **Severity**: HIGH
- **Likely explanation**: The next-day ledger block was prepended without rewriting the action list beneath it.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: yes — which statement wins, and whether the action list is rewritten or dated in place. Same family as DRIFT-05/DRIFT-06.

- **Drift ID**: DRIFT-08
- **Title**: The eight-vs-eleven first-visit disclosure decision is unmade, owned by a frozen session, and exists only as a recommendation
- **Related claims**: WORK-33, REQ-25, REQ-26, WORK-32, INT-19 / **Related decisions**: D-129 (T-02), D-152 (S45 frozen), D-114 §4
- **Intended state**: A product decision on how many of SPEC §5.1.2's eleven disclosures a minors-facing first-visit notice ships with, owned by S45.
- **Observed state**: No DECISIONS ruling exists. A corpus grep for the decision language (`ship eight`, `eight, not eleven`, `eight of the eleven`, `eight disclosures`) returns exactly two non-ledger hits and **both are recommendations, neither in DECISIONS.md**: `FIRST_VISIT_NOTICE.md:220` ("**The recommendation is to ship eight, not eleven**…") and `PROGRESS.md:982`. The blocking statement is intact at `FIRST_VISIT_NOTICE.md:236` ("Counsel review of the resulting text remains a §6.1 launch gate"), the document disclaims being the Privacy Notice (`:3-13`), and its owner S45 sits inside the D-152-frozen S43–S47 block. The three disclosures in question describe behaviour that does not exist: no challenge route, no image upload path, no tutor/manager read view (grep over `apps/learning-api/src`, `apps/learning-web/src`, `apps/chat-api/src` returns only difficulty labels `ExamScreen.tsx:65-66`).
- **Evidence**: `docs/FIRST_VISIT_NOTICE.md:214-218`, `:220`, `:231-237`, `:3-13`; `docs/PROGRESS.md:978-982`; `docs/ROADMAP.md:1500-1507`, `:1438-1445`; zero-hit DECISIONS grep; `apps/learning-web/src/screens/` (11 screens, none a notice); `apps/learning-web/src/components/QuestionFigure.tsx:5-7`.
- **Severity**: HIGH — launch-gate-adjacent for a minors-facing notice.
- **Likely explanation**: The analysis was done and the recommendation written; the ruling was deferred to the session that would transcribe it, and that session was frozen.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: yes — eight versus eleven disclosures is a product and legal call. Related to DRIFT-11 (the §6.1 track that would enumerate them).

### MEDIUM

- **Drift ID**: DRIFT-09
- **Title**: `purge_resume_writes` is unreachable on the cancelled-resume and error paths, so coordinates and typed addresses can persist
- **Related claims**: SEC-13, SEC-12, REQ-28 / **Related decisions**: D-045, D-333 (retention windows), AUD-C-03
- **Intended state**: SPEC §5.1.3 forbids storing precise coordinates in PostgreSQL; TRACEABILITY frames AUD-C-03's `__resume__` purge as having closed the last coordinate leak.
- **Observed state**: The purge is exactly as documented — a parameterized `DELETE FROM checkpoint_writes WHERE thread_id = :thread_id AND channel = '__resume__'` (`services/checkpoint_privacy.py:24-30`) — but it has **exactly one trigger**, the successful/declined resume return path at `routers/sessions.py:907-914`. Ordering inside `respond_to_interrupt` is `_run_turn(...)` → `if cancelled: … return cancelled_response` (`:897-905`) → the purge. So (a) a cancelled location-consent resume returns before the purge and (b) any exception inside `_run_turn` (Bedrock/Maps/deadline) skips it, leaving precise coordinates or a manually typed address in `checkpoint_writes.__resume__`. No retention job covers that table's rows for live threads: `checkpoint_retention_cli` is unscheduled and dry-run by default (DRIFT-45/DRIFT-46). An abandoned consent is safe by construction — no `__resume__` row is ever written.
- **Evidence**: `apps/chat-api/src/chat_api/services/checkpoint_privacy.py:24-30`; `apps/chat-api/src/chat_api/routers/sessions.py:863-869`, `:897-914`; `apps/chat-api/src/chat_api/graph/nodes.py:801`; `docs/SPEC.md` §5.1.3.
- **Severity**: MEDIUM — flagged prominently: this is a SPEC §5.1.3 exposure class over minors' location data, not a wording defect.
- **Likely explanation**: The purge was added at the one path the finding was measured on; the cancel path (D-402/`CANCELLED`) and the exception path were not enumerated when it landed.
- **Resolvable by Phase 3B?**: no — the gap is repository-evident from the call ordering.
- **Genuine decision required?**: no — a code fix, out of audit scope; recorded only.

- **Drift ID**: DRIFT-10
- **Title**: The §7-R9 acceptance's expiry condition has a metric, a dashboard widget, and no alarm
- **Related claims**: SEC-10, ARCH-17, INT-22 / **Related decisions**: §7-R9, D-148 (criterion 2 qualified), AUD-X-07
- **Intended state**: The seam is accepted for the pilot on the evidence of a flat `learning_checkpoint_repairs_total`, and "acceptance is void the moment the counter moves."
- **Observed state**: The metric exists (`packages/observability/src/intellichoice_observability/metrics.py:46-54`, "Should be flat at zero; any movement means requests are dying between the checkpoint commit and the domain commit"), is incremented at exactly one site (`apps/learning-api/src/learning_api/routers/sessions.py:756` `CHECKPOINT_REPAIRS.inc()`), is bridged to CloudWatch (`terraform/modules/ecs-service/main.tf:209`, `:255`) and rendered on a dashboard widget (`terraform/modules/observability/dashboard.tf:436`, rationale `:425-427`). But `grep -rn "checkpoint_repair" terraform/` returns **only those three lines** — `alarms.tf` contains no reference. The tripwire's only reader is a human opening a "Content health" widget; nothing can page on the event that voids the acceptance.
- **Evidence**: as cited above; `apps/learning-api/src/learning_api/services/checkpoint_reconcile.py:4-9`, `:22-25`, `:88-99` (seam (b) still open).
- **Severity**: MEDIUM, high-adjacent (adjudicated MEDIUM–HIGH).
- **Likely explanation**: The metric was built to make the seam observable and the alarm step was never taken; the expiry condition was written in INTEGRATION_PLAN, which no infra artifact reads.
- **Resolvable by Phase 3B?**: no — live verification cannot close a gap that is in the configuration. A 3B read of the counter would give today's value only.
- **Genuine decision required?**: yes — add an alarm, or accept a human-review cadence as the detector. See DRIFT-04.

- **Drift ID**: DRIFT-11
- **Title**: The §6.1 legal track gates the pilot, a frozen session and a coding deliverable, with no owner, schedule or status
- **Related claims**: INT-19, REQ-30, WORK-33 / **Related decisions**: D-114 §4, D-129 (T-02), D-152
- **Intended state**: Consent text comes from the §6.1 "Parallel track (any time, non-coding) — Phase 0 legal & policy docs", described as a true pilot blocker.
- **Observed state**: The track has not started and now gates more than the pilot. `ROADMAP.md:2148-2160` defines it with **no start or progress marker**; `PROGRESS.md:8447` states plainly that "the §6.1 track gates the pilot, **has not started**, and already carries D-114 §4's obligation." D-129 additionally made it gate a coding session: "**Now also gating a coding session (D-129, T-02): enumerate §5.1.2's eleven first-visit disclosures** … as a written deliverable **S45 transcribes rather than drafts**" — and S45 is frozen. The dependency spine confirms "§6.1 legal docs gate the pilot" (`ROADMAP.md:1526`). There is no owner field, no schedule, and no status anywhere; the track is tracked only by narrative mentions in two files. `FIRST_VISIT_NOTICE.md` is partial coverage of the disclosure sub-deliverable and explicitly "not the Privacy Notice, and not a substitute for counsel review". W10's later coverage adds one correction: the track is **no longer wholly unstarted** — its T-02 disclosure-enumeration deliverable shipped 2026-08-15 as `docs/FIRST_VISIT_NOTICE.md` (`da2549f`, 237 lines), writing out all eleven disclosures as copy in two registers with a "True because"/"Goes false if" row each, and `ROADMAP.md:2148-2157` now carries the enumeration inside the §6.1 block; what remains missing is the Privacy Notice and consent text, counsel review, an owner, and a schedule.
- **Evidence**: `docs/ROADMAP.md:2148-2160`, `:1502`, `:1504`, `:1526`; `docs/PROGRESS.md:8447`; `docs/INTEGRATION_PLAN.md:357-363`, `:437`, `:467`; `docs/FIRST_VISIT_NOTICE.md:10`, `:236`.
- **Severity**: MEDIUM, high-adjacent (adjudicated MEDIUM–HIGH).
- **Likely explanation**: A non-coding track has no session number, so the session-numbered planning documents have nowhere to carry its status.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: yes — scheduling and owning the legal track. Cross-reference DRIFT-08 and DRIFT-36.

- **Drift ID**: DRIFT-12
- **Title**: SPEC §5.30.2's six-role matrix names an admin row with no role, no route and no enforcement point
- **Related claims**: SEC-04, SEC-09, REQ-07 / **Related decisions**: D-086, D-153 §5 (allowlist constraint)
- **Intended state**: All six rows of the authorization matrix are enforced in the backend/query layer, never in prompts.
- **Observed state**: Four rows are enforced in the query layer, two partially, one is absent. `packages/shared/src/intellichoice_shared/auth.py:13-17` declares `Role` with exactly STUDENT/PARENT/TUTOR/BRANCH_MANAGER — **no admin member** — and no admin route or admin role check exists in either API's routers; the only "admin" strings are the admin-escalation email recipient (`chat-api/config.py:102`). So the admin row is unenforceable as specified rather than unenforced. Tutor and branch_manager have the audience predicate enforced in SQL (`role_access.py:124`) but no per-student scope (the known R8, DRIFT-17), and their `branch_external_id` resolves to `None`, giving org-wide chunks only.
- **Evidence**: `packages/shared/src/intellichoice_shared/auth.py:13-17`; `apps/chat-api/src/chat_api/services/role_access.py:119-145`; `apps/learning-api/src/learning_api/authorization.py:30-45`, `:47-71`; `apps/learning-api/src/learning_api/routers/parents.py:44-48`; `packages/db/src/intellichoice_db/repositories/rag.py:47-84`; `docs/TRACEABILITY.md:185`.
- **Severity**: MEDIUM
- **Likely explanation**: SPEC's matrix was written against the org's role vocabulary; the built system only ever needed four roles, and the matrix was never amended.
- **Resolvable by Phase 3B?**: no — the role enum is repository-evident.
- **Genuine decision required?**: yes — define admin's fate (build it, scope it to the S43/S44 allowlist, or amend the matrix).

- **Drift ID**: DRIFT-13
- **Title**: Bedrock Guardrails are named as a control for a minors platform; the safety screen is ten keywords on one of two surfaces
- **Related claims**: REQ-32, REQ-19 / **Related decisions**: SPEC §5.11.4, §5.12.2
- **Intended state**: `HintResponse` carries `answer_revealed=false`; Guardrails are configured; self-harm and abuse route through a separately approved safety policy.
- **Observed state**: The schema field is present (`bedrock.py:111-120`; the deterministic fallback sets `answer_revealed=False` at `tutor.py:104`). **Guardrails are absent**: a repo-wide case-insensitive grep for "guardrail" across `packages`, `apps`, `scripts` including `.tf`/`.yaml`/`.json` returns **zero hits** — no Guardrail id, configuration or invocation. Safety routing exists but is a fixed 10-item substring screen: `screen_for_safety_concern` (`apps/learning-api/src/learning_api/services/tutor_chat.py:161`) matches `_SAFETY_KEYWORDS` and short-circuits to a fixed `SAFETY_RESPONSE`, called at `graph/nodes.py:1457` before intent classification, persisting `flagged_for_review=True`. It has **one caller** — no equivalent screen exists anywhere in `apps/chat-api`. No approval artifact, policy document, or escalation destination beyond the boolean flag was found.
- **Evidence**: `packages/shared/src/intellichoice_shared/bedrock.py:111-120`; `apps/learning-api/src/learning_api/services/tutor.py:96-107`; `apps/learning-api/src/learning_api/services/tutor_chat.py:66-84`, `:161`; `apps/learning-api/src/learning_api/graph/nodes.py:1457`; `packages/db/src/intellichoice_db/models/tutor_chat.py:33-36`; zero-hit "guardrail" grep.
- **Severity**: MEDIUM
- **Likely explanation**: The keyword screen was built as the shippable floor for the learning surface; Guardrails and a reviewed policy were left as SPEC text.
- **Resolvable by Phase 3B?**: no — a Guardrail attached out-of-band in the AWS console is conceivable, so 3B could narrow the absence, but the missing policy artifact and the chat-api gap are repo-evident.
- **Genuine decision required?**: yes — this is a minors platform and SPEC §5.12.2 names the control; adopt Guardrails/an approved policy or amend the requirement. Shares the Guardrails half with DRIFT-14.

- **Drift ID**: DRIFT-14
- **Title**: "Guardrails" is listed as a gateway-provided feature and no guardrail configuration exists
- **Related claims**: REQ-19, COST-02, REQ-32 / **Related decisions**: D-022, D-233, SPEC §5.25.1
- **Intended state**: Every paid call routes through `BedrockGateway` providing timeouts, bounded retry, max-token ceiling, per-session budget, circuit breaker, PII redaction, guardrails, model versioning and a pre-flight `worst_case_cost_cents`.
- **Observed state**: Eight of the ten listed features are present and quotable — `call_timeout_s=20.0` (`gateway.py:88`, per-call override per D-233 at `:215`), `_max_retries` loop (`:285`), `_HARD_MAX_OUTPUT_TOKENS = 4000` (`:78`) applied at `:236`, `session_budget_cents=50.0` (`:93`) checked pre-call at `:244-263`, circuit breaker (`:110-134`), `worst_case_cost_cents` (`:182-194`). **Guardrails: zero hits repo-wide.** Gateway-level PII redaction is also absent — redaction lives at callers. The gap is in SPEC/ledger's feature list, not in the gateway's implementation of what it does claim.
- **Evidence**: `packages/adapters/src/intellichoice_adapters/bedrock/gateway.py:78-194`, `:215-263`, `:285-310`; `packages/shared/src/intellichoice_shared/bedrock.py:1579-1602`; zero-hit "guardrail" grep across `packages`, `apps`, `scripts`.
- **Severity**: MEDIUM
- **Likely explanation**: SPEC §5.25.1 enumerated an aspirational feature set; the gateway shipped the cost- and reliability-bearing half and the list was never trimmed.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: yes — adopt Bedrock Guardrails or amend SPEC §5.25.1's feature list.

- **Drift ID**: DRIFT-15
- **Title**: Two of §5.29's named common failure mechanisms do not exist — no dead-letter queue, no smaller-model fallback
- **Related claims**: REQ-49, REQ-16 / **Related decisions**: D-115 (truncation not repaired), SPEC §5.29
- **Intended state**: Nineteen named failure rows each with an implementation and a test; common mechanisms include a dead-letter queue and a smaller-model fallback on Bedrock timeout.
- **Observed state**: Of four rows sampled, two mechanisms are present and two are absent. Present: the static concept-hint fallback (`tutor.py:96` `_fallback_hint`, invoked on `except BedrockGatewayError` at `:150-153`) and non-blocking telemetry (`request_logging.py:105-120` `except Exception` with the D-393 comment, mirrored at `metrics.py:157-164`, `scheduled_jobs.py:64`). **Absent: dead-letter queue** — zero hits for `dead.letter`, `dead_letter`, `DLQ` across `packages`, `apps`, `scripts` (`.py`/`.tf`/`.yaml`), and zero `sqs` resources in terraform. **Absent: smaller-model fallback** — zero hits for `fallback_model`, `smaller_model`, "smaller model", "fallback model"; the timeout path is bounded retry against the *same* `model_id` (`gateway.py:285-310`) then `_record_failure()` → circuit open. No model downgrade exists.
- **Evidence**: `apps/learning-api/src/learning_api/services/tutor.py:96-153`; `packages/adapters/src/intellichoice_adapters/bedrock/gateway.py:285-320`; `packages/observability/src/intellichoice_observability/request_logging.py:105-120`; `metrics.py:157-164`; `scheduled_jobs.py:64`; negative greps as listed.
- **Severity**: MEDIUM
- **Likely explanation**: The matrix was written as a design catalogue; the mechanisms that mattered for the shipped surfaces were built and the two infrastructure-shaped ones were not.
- **Resolvable by Phase 3B?**: no — absence is grep-provable in-repo; only fifteen unsampled rows remain unmeasured (a coverage limitation, not a 3B item).
- **Genuine decision required?**: yes — build them or amend SPEC §5.29's common-mechanism list.

- **Drift ID**: DRIFT-16
- **Title**: SPEC §5.1.4 enumerates six interrupt-gated actions; two of the six have nothing to gate
- **Related claims**: REQ-10, REQ-11 / **Related decisions**: D-078 (S29 deferred), CLAUDE.md rule 4
- **Intended state**: Explicit `interrupt()` approval before six enumerated external actions, including analysis of an uploaded solution image and inclusion of potentially sensitive information in an email.
- **Observed state**: Five interrupt classes exist: learning `child_selection` (`learning-api/graph/nodes.py:331`) and `email_approval` (`:460`); chat `email_approval` (`chat-api/graph/nodes.py:793`), `calendar_action` (`:1019`), `location_consent` (`:1134`). **No image-analysis interrupt** — `analyze_image` exists only as an unimplemented gateway method named in a docstring (`bedrock.py:5`), so there is no feature to gate (expected under D-078). **No gate distinct from `email_approval` for "sensitive information in an email"** — the nearest mechanisms are the email-preview payload inside the existing interrupt and unconditional redaction of free text before the node; neither is keyed on sensitivity. CLAUDE.md's four-action list is closer to the code than SPEC's six. The mechanism itself is sound: `sessions.py:770-776` refuses any non-`/respond` invoke while an interrupt is pending.
- **Evidence**: as cited; `apps/learning-api/src/learning_api/routers/sessions.py:756`, `:770-776`, `:1819`; `apps/learning-api/tests/test_learning_graph_routes.py`, `apps/chat-api/tests/test_calendar_action.py`, `test_admin_escalation.py` (all exist, unexecuted).
- **Severity**: MEDIUM — a requirement that lists two ungateable actions reads as satisfied while two-sixths of it has no code.
- **Likely explanation**: SPEC's list predates D-078's deferral; the "sensitive information" item may never have been intended as a separate interrupt class, which is a SPEC-reading question rather than a code gap.
- **Resolvable by Phase 3B?**: no — this is a SPEC-interpretation item.
- **Genuine decision required?**: yes, doc-side only — whether "sensitive information in an email" was ever meant as a gate distinct from `email_approval`. The image half needs no decision (dispositioned by D-078).

- **Drift ID**: DRIFT-17
- **Title**: The tutor/branch_manager read-scope acceptance expires "at first real traffic" and its closure sessions are frozen
- **Related claims**: REQ-09, SEC-09, ARCH-18 / **Related decisions**: D-086, D-107 (write half closed), D-097, D-152, §7-R8
- **Intended state**: The unscoped read is an accepted risk expiring at first real traffic, with S43's `IcProfileAdapter` unblocking it and formal disposition scheduled for S46.
- **Observed state**: The gap is present and unchanged. `apps/learning-api/src/learning_api/authorization.py:66-71` reads `if access == "write": raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This role may not modify a student's records")` then `return requested_student_id` — writes fail closed, reads fall through returning the client-supplied id. The in-code disposition at `:47-65` states "These two roles have no per-student scope check … That is D-086's recorded, accepted risk since S33, and S43's `IcProfileAdapter` is what unblocks it; the formal disposition is scheduled for S46." Both named sessions are inside the D-152-frozen block, and the expiry condition is unreconciled in code or comment. Reach is confirmed: dashboard, history and report routes all call with `access="read"` (`students.py:160,315,366,429`).
- **Evidence**: `apps/learning-api/src/learning_api/authorization.py:7-14`, `:22`, `:47-71`; 15 call sites in `students.py`, `sessions.py`, `stream.py:173,220`, `main.py:464`; `docs/ROADMAP.md:1438-1445`; `docs/INTEGRATION_PLAN.md:503-507`.
- **Severity**: MEDIUM
- **Likely explanation**: The acceptance named future sessions as its closure; the freeze removed them and the expiry condition was never re-expressed as something a running system could trip.
- **Resolvable by Phase 3B?**: no — whether "first real traffic" has begun is not determinable from the repository, and a live check would not re-own the acceptance.
- **Genuine decision required?**: no as adjudicated for the code half; the ownership question is carried by DRIFT-04.

- **Drift ID**: DRIFT-18
- **Title**: A duplicate-id branch loses paid spend from the row, the run total and the budget-gating running total
- **Related claims**: COST-06, COST-08, REQ-20, COST-05 / **Related decisions**: D-294, D-342 (pipeline parked)
- **Intended state**: The `skipped_duplicate_id` path is not covered by a test; the row is rolled back and the money stays attributable to the run total.
- **Observed state**: **CONFLICT — the claim is wrong in both directions.** A test does exercise the path: `test_per_candidate_settlement_survives_a_duplicate_id` (`packages/curriculum/tests/test_authored_pipeline.py:1673-1716`) forces a collision and asserts `summary.skipped_duplicate_id == 1`. And the accounting gap is worse than described in one branch: the `_settle` commit-time branch (`pipeline_cli.py:303-312`) does `summary.total_cost_cents += outcome.cost_cents` before incrementing, so money does stay in the run total — but the `run_plan` flush-time branch (`pipeline_cli.py:602-618`) catches `IntegrityError`, rolls back and `continue`s **before** `spend += outcome.cost_cents` at L619 and never reaches `_settle`. Paid calls precede the row flush (`generate_structured` at `ai_pipeline.py:981`, `:1328`; `create_template` at `:2046`), so real spend on that branch reaches neither the row, nor `summary.total_cost_cents`, nor the `spend` total the run-budget check at L577 reads.
- **Evidence**: `packages/curriculum/src/intellichoice_curriculum/pipeline_cli.py:295-312`, `:560-635` (the `continue` at L618 preceding L619), `:577`, `:590-592`; `packages/curriculum/src/intellichoice_curriculum/ai_pipeline.py:981`, `:1328`, `:1600-1615`, `:2046`; `packages/curriculum/tests/test_authored_pipeline.py:1673-1716`; `docs/TRACEABILITY.md:246-248`.
- **Severity**: MEDIUM (adjudicated down from the inspector's HIGH: per-event loss is bounded to one slot's spend, `budget_ceiling_cents` still bounds during the call, duplicate-id collisions are rare, and the pipeline is parked by D-342).
- **Likely explanation**: The ledger note was written from the `_settle` branch's behaviour; the flush-time branch was added for crash-safety and its interaction with the running total was not traced.
- **Resolvable by Phase 3B?**: no — repository-evident from call ordering.
- **Genuine decision required?**: no — a code fix, out of audit scope; recorded only.

- **Drift ID**: DRIFT-19
- **Title**: D-141's input bound lives in the memory package, and the gateway still has no input bound at all
- **Related claims**: COST-10, REQ-19 / **Related decisions**: D-141, AUD-F-34
- **Intended state**: The AREAS note locates D-141's fix as "an input-token bound in gateway code."
- **Observed state**: The bound exists and is sized against the timeout exactly as claimed, but it is at the caller. Grep for `max_input|MAX_INPUT|MAX_PROMPT|max_prompt|D-141` across the bedrock adapter and `packages/shared/.../bedrock.py` returns **zero hits**; the gateway bounds output only (`_HARD_MAX_OUTPUT_TOKENS = 4000`, `gateway.py:78`) and uses a hardcoded 2000-token input *assumption* for pricing (`:194`, `:244`) — an estimate, not a bound. The real fix is `packages/memory/src/intellichoice_memory/consolidation.py:81-114`: `_MAX_EVENT_TOKENS_PER_CALL = 20_000` with the incident written in place ("one week of a load-tested student's tutor chat built a 215,355-token prompt against Haiku 4.5's 200,000-token context and every call failed - while the process exited 0"). Any *new* paid caller therefore inherits the AUD-F-34 shape.
- **Evidence**: `packages/memory/src/intellichoice_memory/consolidation.py:81-114`; `packages/memory/src/intellichoice_memory/settings.py:17`, `:36`; `packages/adapters/src/intellichoice_adapters/bedrock/gateway.py:78`, `:194`, `:244`; zero-hit grep as described.
- **Severity**: MEDIUM
- **Likely explanation**: The bound was sized against one job's measured failure and placed where that job could reason about batch size; generalising it to the gateway was never scoped.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: yes — a gateway-level input bound, or a per-caller convention recorded as the answer.

- **Drift ID**: DRIFT-20
- **Title**: "All 10 P1s closed / four new application alarms reading OK" is not reconcilable with P1-10 at config level
- **Related claims**: COST-21, COST-25, COST-24, COST-19, COST-17 / **Related decisions**: D-377, D-401, D-419
- **Intended state**: The 2026-08-16 audit's status block records all ten P1s closed, four new application alarms reading OK.
- **Observed state**: Zero product-KPI alarms are instantiated by the configuration, and that is provable from config alone. The only alarm on a product KPI metric is `sessions_completed_floor` (`metric_name = "learning_sessions_completed_total"`), guarded by `count = var.daily_completed_sessions_floor > 0 ? 1 : 0` (`app_events.tf:131`); the variable's default is `0` (`variables.tf:185-193`) **and** the staging module call also explicitly sets `daily_completed_sessions_floor = 0` (`environments/staging/main.tf:783-787`) with the reason written out ("Staging traffic is synthetic … Left at 0 (disabled) rather than guessed at"). No other setter exists anywhere in `terraform/**.tf`. `qa_answers_total` has no alarm at all. The repo's own test comment corroborates it: "**Configured, not deployed** (found by a `terraform plan` for D-406) … the deployed alarm count and the configured one are not the same number" (`test_alarm_severity_routing.py:34-41`). So the one alarm answering P1-10's own suggested fix is guarded to zero instances by two independent settings and no document records raising it.
- **Evidence**: `terraform/modules/observability/app_events.tf:130-157`; `terraform/modules/observability/variables.tf:185-193`; `terraform/environments/staging/main.tf:783-787`; `packages/observability/tests/test_alarm_severity_routing.py:34-41`; `docs/AUDIT_2026_08_16.md` status block.
- **Severity**: MEDIUM — weakens the Phase-2 "P1s all closed" claim family; COST-25 is the load-bearing evidence against COST-21 and the two must be read together.
- **Likely explanation**: The closure was counted at the level of "an alarm resource now exists in configuration", which is true, and the count guard was not re-read.
- **Resolvable by Phase 3B?**: no — the count guard makes the config-level answer determinate; a live alarm enumeration would only confirm it.
- **Genuine decision required?**: yes — raise the floor once real traffic exists, or record the disabled state as the accepted answer to P1-10.

- **Drift ID**: DRIFT-21
- **Title**: No labelled counter pre-initialises its label sets, so every low-frequency labelled KPI is unalarmable until first occurrence
- **Related claims**: COST-22, COST-20 / **Related decisions**: the recorded fix for `qa_service_degraded_total`
- **Intended state**: Pre-initialise labels at import so the series exists before the first outage.
- **Observed state**: **Not fixed, and the gap is module-wide.** There is exactly one metrics module in the repo (`find -name metrics.py` excluding `node_modules`/`.venv` returns one file) and it contains no import-time `.labels()` call for any labelled counter. `QA_SERVICE_DEGRADED` is declared with three documented `stage` values (`metrics.py:85-89`, `labelnames=("stage",)`) and touched at one runtime site inside the degradation handler (`chat-api/graph/nodes.py:271`), so no series exists until a provider actually fails. A grep of every `.labels(` call site across `apps/chat-api/src`, `apps/learning-api/src`, `packages/observability/src` returns 21 hits, all inside functions or handlers, none at module scope; no `preinit`/warm-up loop exists. `grep -rn "qa_service_degraded" infra/` returns nothing. The same shape applies to `ATTENDANCE_CHECKS`, `QA_ANSWERS`, `SSE_RELAY_FAILURES` and every other labelled counter.
- **Evidence**: `packages/observability/src/intellichoice_observability/metrics.py:85-89`; `apps/chat-api/src/chat_api/graph/nodes.py:271`; exhaustive `.labels(` and metrics-module greps as described.
- **Severity**: MEDIUM
- **Likely explanation**: The finding was recorded as one metric's oversight; nothing generalised it, and Prometheus/EMF's lazy label creation makes the gap invisible until the first event.
- **Resolvable by Phase 3B?**: no — a live check would show which series exist today but not create them.
- **Genuine decision required?**: no — a mechanical fix; recorded.

- **Drift ID**: DRIFT-22
- **Title**: The D-136 price table's per-task columns were measured at 256 CPU units and learning-api now runs 512
- **Related claims**: COST-29, ARCH-12, ARCH-13 / **Related decisions**: D-122 (AUD-F-28), D-134, D-136
- **Intended state**: Before reusing the D-136 capacity/price table as current, confirm task size and count are unchanged.
- **Observed state**: Task count unchanged; **task size changed.** learning-api is still pinned at two tasks (`desired_count = 2`, `autoscaling_min_capacity = 2`, `capacity_floors.learning-api.min_capacity = 2`), but the task is now `cpu = 512 / memory = 1024` (`environments/staging/main.tf:432-433`), and the terraform comment identifies the measurement's provenance: "AUD-F-28 (D-122): this service is CPU-bound - a measured sweep on the old **256/512 task** showed throughput pinned at ~5.8 req/s from 10 concurrent sessions upward … at 256 CPU units the p95 <= 3s promise held only to ~8 concurrent sessions. 512 units x 2 tasks is 4x that." `ARCHITECTURE.md:254-283` quotes the table's per-task columns as current and carries **no** AUD-F-28 resize caveat. chat-api meanwhile runs on module defaults (256/512, min 1), so the two services are not the same size at all. Reusing the table today under-states capacity per task.
- **Evidence**: `terraform/environments/staging/main.tf:423-447`, `:517-556`, `:819-835`; `terraform/modules/ecs-service/variables.tf:53-69`, `:187-191`; `docs/ARCHITECTURE.md:254-283`.
- **Severity**: MEDIUM
- **Likely explanation**: The resize was made for a measured latency reason and annotated in terraform; the architecture document's price table was not revisited.
- **Resolvable by Phase 3B?**: no for the doc caveat; a live task-size read would confirm 512 but the arithmetic defect is in-repo.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-23
- **Title**: The spend-attribution finding is unmarked-open two days after D-400 closed it, in a file that marks its neighbour resolved
- **Related claims**: COST-11, COST-13, COST-14 / **Related decisions**: D-394, D-400
- **Intended state**: D-400 (2026-08-17) closed per-student/per-session Bedrock spend attribution.
- **Observed state**: Two documents still carry it as open. `AUDIT_2026_08_16.md:239-241` still states "Bedrock spend is attributable per day and per app but **never per student or per session**" with **no resolution marker**, while an adjacent paragraph in the same block does carry one (`✅ resolved 2026-08-17, D-394`) — so the file marks resolutions selectively and left this one unmarked. `PROGRESS.md:11664` still reads "**Carry-over:** per-student spend attribution and the single-inbox alarm target are the last two observability items from the 08-16 audit." Both are contradicted by `ROADMAP.md:2909-2914` (W8 ✅ done 2026-08-17, D-400) and `PROGRESS.md:250-258`.
- **Evidence**: `docs/AUDIT_2026_08_16.md:239-241` vs `:247-248`; `docs/PROGRESS.md:11664`, `:250-258`; `docs/ROADMAP.md:2909-2914`; `docs/INCIDENT_RESPONSE.md:222-268`.
- **Severity**: MEDIUM
- **Likely explanation**: The resolution was recorded in ROADMAP/PROGRESS's current section; the audit file's finding text is not dated in place and reads as current, so it was missed in the same-file sweep that marked its neighbour.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-24
- **Title**: The Vite content-hash comparison presented as a standing deploy control is a manual technique nothing implements
- **Related claims**: ARCH-33, ARCH-34 / **Related decisions**: D-418
- **Intended state**: ARCHITECTURE.md:455-458 presents a deterministic Vite content-hash comparison as the "second, independent answer" covering the S3/CloudFront half of every deploy, alongside the ECS control-plane gate.
- **Observed state**: The ECS half is confirmed exactly — the gate step asserts `len(d) != 1 → FATAL`, `status != 'PRIMARY' → FATAL`, `rolloutState == 'FAILED' → FATAL`, `desiredCount < 1 → FATAL`, `runningCount < 1 → FATAL`, then compares `TAG != EXPECTED → exit 1` outside the retry, bounded by `WAIT_SECONDS=300`/`sleep 15`. But grepping the whole 711-line workflow for `sha256|md5|ETag|content-hash|dist/|vite` yields **no hash-comparison step**, and no `make` target or script implements one either; the frontend leg is `aws s3 sync … --delete` + a CloudFront invalidation + three curls (`/`, `/`, `/me` must be 401). ARCHITECTURE.md itself phrases the check as "building the commit locally and comparing" — i.e. a procedure, not a control. `make image-check` is likewise operator-invoked only (DRIFT-80).
- **Evidence**: `.github/workflows/deploy-staging.yml:409-501`, `:667-711`; `docs/ARCHITECTURE.md:455-458`; negative grep over the workflow and over `Makefile`/`scripts/`.
- **Severity**: MEDIUM — refutes the Phase-2 reading of ARCH-33 as a standing control.
- **Likely explanation**: The technique was used once by hand to answer a real question and written up in the architecture document in the present tense.
- **Resolvable by Phase 3B?**: no — the absence of a workflow step is repository-evident.
- **Genuine decision required?**: no — either implement it or reword the document; editorial/engineering, not product.

- **Drift ID**: DRIFT-25
- **Title**: Two ARCHITECTURE.md pipeline sections still assert manual triggers that the terraform falsifies
- **Related claims**: ARCH-06, ARCH-04, ARCH-05 / **Related decisions**: AUD-F-06, D-114, D-333
- **Intended state**: Per the losing text, `memory-consolidate` is "manual trigger only" and `chat-purge` has "no scheduler yet".
- **Observed state**: **Falsified by configuration.** Both jobs have enabled `aws_scheduler_schedule` resources: `chat-purge` `cron(10 18 * * ? *)` enabled (`terraform/modules/scheduled-jobs/main.tf:65`, `:72`) and `memory-consolidate` `cron(30 18 ? * SUN *)` enabled (`:91`, `:105`), with `schedule_expression_timezone = "UTC"` (`:196`) and `state = var.enabled && each.value.enabled ? "ENABLED" : "DISABLED"` (`:198`). The module's own opening comment records exactly the prior state those doc sections describe: "Before this existed, `aws events list-rules` and `aws scheduler list-schedules` were both empty and all four jobs were `make` targets a human ran (AUD-F-06)" (`:3-6`). This settles the Phase-1/2 scheduler contradiction at the configuration level in favour of `ARCHITECTURE.md:28-30`.
- **Evidence**: `terraform/modules/scheduled-jobs/main.tf:3-6`, `:52-125`, `:196-198`; `terraform/environments/staging/main.tf:842-866`; `docs/ARCHITECTURE.md:1850-1851`, `:2068`, `:28-30`.
- **Severity**: MEDIUM — an operator reading those sections would believe a 90-day retention promise depends on a human.
- **Likely explanation**: The scheduler module closed AUD-F-06 and the summary at L28-30 was updated; the two per-pipeline sections deeper in the same file were not.
- **Resolvable by Phase 3B?**: no at configuration level; whether the schedules have actually fired unattended is a separate 3B question and does not bear on the doc defect.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-26
- **Title**: SPEC §5.33 prescribes AWS Organizations, EKS and Aurora; the repository implements none of it and carries no marker
- **Related claims**: ARCH-23, ARCH-25 (SPEC §5.36's sibling defect), TEST-06 / **Related decisions**: D-004, D-082, D-083, D-084
- **Intended state**: SPEC §5.33 prescribes an AWS Organization with three accounts, production EKS across three AZs with Karpenter/HPA/PDB/NetworkPolicy/IRSA, and Aurora PostgreSQL Multi-AZ writer plus reader.
- **Observed state**: Zero of it exists. A grep across terraform `*.tf`/`*.sql` for `eks|kubernetes|aurora|karpenter|aws_organizations` returns **zero resource hits**; the only matches are two comments that explicitly reject the model (`modules/ecs-service/variables.tf:109-110` "this deploys to Fargate, not EKS, per D-004/D-082-084"; `modules/ecs-service/main.tf:384-386` "SPEC §5.33.4 'HPA signals' … Fargate has no HPA"). Instead: one VPC with `az_count` default 2, one ECS Fargate cluster, `aws_db_instance` (not `aws_rds_cluster`) with `engine = "postgres"` and `multi_az = false`, one account, one environment prefix. `SPEC.md:3116-3187` carries no superseded marker.
- **Evidence**: negative grep as described; `terraform/modules/vpc/variables.tf:12-16`; `terraform/modules/rds-postgres/main.tf:37-38`; `terraform/environments/staging/main.tf:217`, `:248-264`, `:358`; `docs/SPEC.md:3116-3187`.
- **Severity**: MEDIUM
- **Likely explanation**: D-004 deferred the enterprise footprint 27 days before this audit and the decision was recorded in DECISIONS and in terraform comments; SPEC was never annotated. Same pattern as DRIFT-35.
- **Resolvable by Phase 3B?**: no — account-structure verification would confirm the absence, not the missing marker.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-27
- **Title**: SPEC §5.33.4's five HPA signals plus SQS worker scaling versus exactly one configured signal per service
- **Related claims**: ARCH-24, ARCH-11, ARCH-13 / **Related decisions**: D-004, D-344 (stopgap never applied)
- **Intended state**: HPA on CPU, memory, active requests, SSE connections and P95, with worker scaling on SQS queue depth.
- **Observed state**: Exactly **one** signal is live per service and it is ALB p95. Both services set `enable_latency_step_scaling = true` (`environments/staging/main.tf:457`, `:544`), and `aws_appautoscaling_policy.cpu`'s count is `var.enable_autoscaling && !var.enable_latency_step_scaling` (`modules/ecs-service/main.tf:408`), so the CPU target-tracking policy is instantiated for **neither** service. Configured: `AWS/ApplicationELB TargetResponseTime` p95 step-scaling out (threshold 3s, 2×60s) and in (threshold 1s, 15×60s with `FILL(m1,0)`). Not configured anywhere: memory-based scaling, `ALBRequestCountPerTarget`, SSE-connection scaling, and **any SQS resource at all** (grep `sqs` → zero hits in terraform). Memory is watched as an alarm only (`ecs_memory_alarm_mib = 716`). Secondary, config-internal and LOW (medium-adjacent): `modules/observability/main.tf:156` still describes "one ECS task, one uvicorn worker process, no autoscaling", stale against `desired_count = 2` and two active step-scaling policies.
- **Evidence**: `terraform/modules/ecs-service/main.tf:384-397`, `:408-422`, `:435-565`; `terraform/environments/staging/main.tf:457`, `:544`, `:798`; `terraform/modules/observability/main.tf:156`; zero-hit `sqs` grep.
- **Severity**: MEDIUM (the in-config stale comment noted above is LOW, medium-adjacent).
- **Likely explanation**: SPEC's signal list is Kubernetes-shaped; the ECS translation is documented in terraform comments and the SPEC section was never amended. The observability comment predates the desired_count change.
- **Resolvable by Phase 3B?**: no — live policy inventory would confirm the config reading, not the SPEC divergence.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-28
- **Title**: Documentation says NAT and tracing are gated on a single `langsmith_tracing_enabled` flag; config has been consumer-keyed since D-406
- **Related claims**: ARCH-29, COST-28, ARCH-28 / **Related decisions**: D-406, D-419
- **Intended state**: ARCHITECTURE.md:2161-2174 (and the COST prose) describe both NAT and tracing as gated on one flag.
- **Observed state**: The gate is a two-consumer map, verbatim in config: `private_egress_consumers = { langsmith_tracing = var.langsmith_tracing_enabled, youtube_sync = var.youtube_sync_enabled }` with `needs_private_egress = anytrue(values(local.private_egress_consumers))` (`environments/staging/main.tf:115-119`), consumed at `:136` as `nat_gateway_enabled = local.needs_private_egress`. The reason is recorded in place: the previous wiring "was one consumer hardcoded as the condition … `youtube-sync` also runs in a private subnet with `assign_public_ip = false`, and the YouTube Data API has no VPC endpoint - so switching tracing off would have silently stripped that job's egress" (`:101-114`), cross-referenced at `modules/scheduled-jobs/main.tf:120-124`. The documented condition is therefore narrower than the implemented one. LangSmith is still the only *active* consumer today because `youtube_sync_enabled` defaults false.
- **Evidence**: `terraform/environments/staging/main.tf:100-138`; `terraform/environments/staging/variables.tf:163-189`; `terraform/modules/scheduled-jobs/main.tf:120-124`; `docs/ARCHITECTURE.md:2161-2174`.
- **Severity**: MEDIUM for the ARCHITECTURE.md instance; the equivalent COST-prose instance was adjudicated LOW. Both are the same doc-vs-config divergence and are recorded here together.
- **Likely explanation**: D-406 generalised the gate for a measured trap; the prose describing the old single-flag design was not updated.
- **Resolvable by Phase 3B?**: no for the doc wording; NAT existence itself is DRIFT-29 and DRIFT-57.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-29
- **Title**: D-419's "NAT absent from the plan entirely" is not reproducible from the checked-in defaults
- **Related claims**: ARCH-29, ARCH-28, COST-28 / **Related decisions**: D-406, D-419
- **Intended state**: D-419 records the NAT gateway as absent from the plan entirely.
- **Observed state**: Under the checked-in variable defaults the NAT resources are **present** with count 1: `aws_eip.nat` and `aws_nat_gateway.this` are both `count = var.nat_gateway_enabled ? 1 : 0` (`modules/vpc/main.tf:78-94`), `nat_gateway_enabled = local.needs_private_egress`, and `langsmith_tracing_enabled` defaults **true** (`environments/staging/variables.tf:183-189`, "Turned on 2026-08-06 at the user's explicit request"). A plan showing no NAT would require `langsmith_tracing_enabled = false`, which only `terraform.tfvars` could supply — that file exists, is gitignored, and was deliberately not read in Phase 3A; no terraform command was run. Recorded hypothesis, not fact: D-419's sentence may describe the plan *diff* (no NAT changes) rather than NAT absence.
- **Evidence**: `terraform/modules/vpc/main.tf:73-110`; `terraform/environments/staging/main.tf:115-119`, `:136`; `terraform/environments/staging/variables.tf:183-189`; `.gitignore:55` (`*.tfvars`).
- **Severity**: MEDIUM (severity from the inspector; the adjudication deferred the resolution rather than the grading).
- **Likely explanation**: Either tfvars overrides tracing off, or the decision note describes a plan diff; both readings are consistent with the recorded text.
- **Resolvable by Phase 3B?**: **yes** — 3B should read the live NAT gateway count first, then the tfvars question if the count disagrees with the defaults.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-30
- **Title**: SPEC requires the UI to say "Current estimated level"; the phrase appears nowhere in either frontend
- **Related claims**: REQ-39, REQ-40 / **Related decisions**: SPEC §5.10.2 (IRT deferred)
- **Intended state**: Ten questions are not an absolute ability measure, so the UI must render "Current estimated level"; bootstrap weights 1.0/1.4/1.9/2.5/3.2 and no IRT path.
- **Observed state**: The weights are exact (`mastery_bootstrap.py:29`) and no IRT/Bayesian implementation exists anywhere (only deferral docstrings). **The UI wording is absent.** A grep for `"Current estimated level"` across the repo excluding `node_modules`/`.git`/`.venv` hits only `docs/SPEC.md:1111`, `docs/SPEC.md:1451` and the ledger — **zero hits in `apps/learning-web/src` or `apps/chat-web/src`** — and a grep for `estimated` in `apps/learning-web/src` returns nothing. What renders instead: `StudentDashboardScreen.tsx:532` `<h2>Mastery by skill</h2>`, `:544` `aria-label="Mastery by skill chart"`, `:571` `name="Mastery"` — a flat percentage with no estimate hedge. No disposition exists.
- **Evidence**: `apps/learning-api/src/learning_api/services/mastery_bootstrap.py:3-4`, `:29`, `:105-109`; `apps/learning-web/src/screens/StudentDashboardScreen.tsx:532`, `:544`, `:571`; `docs/SPEC.md:1111`, `:1451`; exhaustive negative grep across both web apps.
- **Severity**: MEDIUM — weakens the Phase-2 CURRENT status of REQ-39's UI half.
- **Likely explanation**: The requirement's measurable half (weights, no IRT) was implemented and traced; the wording half had no test and no owner.
- **Resolvable by Phase 3B?**: no — a live walk would show the same strings the source contains.
- **Genuine decision required?**: yes — ship the wording or disposition the requirement.

- **Drift ID**: DRIFT-31
- **Title**: Four of SPEC §5.8.5's eleven validation bullets have no deterministic implementing check inside the gate
- **Related claims**: REQ-41, REQ-42, TEST-11 / **Related decisions**: D-226, D-249, D-286
- **Intended state**: Every multiple-choice item passes the §5.8.5 check list before use, implemented with Python/SymPy/custom evaluators; the ledger says twelve checks.
- **Observed state**: `validate_authored_item` (`authored_validation.py:1862-1901`) runs eleven named checks and six of them are not in SPEC at all. Four SPEC bullets have **no implementing deterministic check inside the gate**: (1) *no division by zero* — grep for `zoo`/`ZeroDivision`/`division by zero` across `packages/curriculum/src` returns nothing; (2) *numeric values within allowed range* — the only range check is on metadata (`check_difficulty_rubric_compliance:1684-1690` asserts `MIN_DIFFICULTY <= difficulty_label <= MAX_DIFFICULTY` and `estimated_time_seconds > 0`); (3) *semantic topic/skill alignment* — deterministic coverage is structural only (`pipeline_cli.py:443`, `ai_pipeline.py:1581-1588`), the semantic half is the LLM reviewer; (4) *no duplicate question* — absent from the gate, implemented one layer up (`ai_pipeline.py:1821`, `:1834`, and a cosine threshold at `:816` whose own comment calls it "a placeholder pending real-embedding calibration"). Two further named checks are materially narrower than their bullets, with substance delegated to the LLM judge (`difficulty-rubric compliance`; `check_age_appropriate_wording:1705`, whose comment calls itself "a rough proxy only; real nuance is the LLM judge's job"). Secondary LOW: the ledger says "twelve" checks where SPEC lists eleven bullets and states no count.
- **Evidence**: `packages/curriculum/src/intellichoice_curriculum/authored_validation.py:129-131`, `:199-219`, `:1684-1901`; `ai_pipeline.py:811-816`, `:1581-1588`, `:1810-1840`, `:1948-1988`; `pipeline_cli.py:414-449`; `docs/SPEC.md:926-944`.
- **Severity**: MEDIUM (the count defect is LOW, recorded in-entry). Weakens Phase-2 REQ-41 as written.
- **Likely explanation**: The gate grew from the checks that had a deterministic instrument; the rest were absorbed by the LLM judge without the bullet list being reconciled.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-32
- **Title**: SPEC §5.5.2's component table declares two node types the implementation does not match
- **Related claims**: REQ-51, REQ-17 / **Related decisions**: D-024 (topic_resolver deterministic), D-022 (don't stub ahead of time)
- **Intended state**: Each of the sixteen §5.5.2 components is implemented at its declared type.
- **Observed state**: The four deterministic components and the LLM-agent component match, and the closing rule holds ("Grading, attendance, authorization, and score calculation remain deterministic", `SPEC.md:531`). Two declared types do not match. (a) **Topic Resolver — declared "Structured LLM", implemented deterministic**, self-dispositioned in code: `services/topic_resolver.py:3-9` "This is a deterministic (non-LLM) resolver … SPEC §5.25.2's 'Topic mapping | Reliable structured output' row implies an eventual LLM-based resolver … but that has no caller until a free-text endpoint exists"; no `generate_structured` call in the module. Dispositioned by D-024 (`DECISIONS.md:415`), unmarked in SPEC. (b) **Tutor Summary Generator — declared "Structured service"**, but the tutor summary is produced by the same LLM report path as the parent report, differing only by audience field allowlist (`report.py:487-496` reached for every audience, `:202-211` gating fields, `:515` logging the audience), with grounding check and deterministic fallback at `:497-517`. Read as descriptive labels, "Assessment Manager | Subgraph" and "Attendance Escalation Agent | Tool agent" are also unmatched structurally (no `add_subgraph`; `attendance.py:130-187` is a deterministic template plus an MCP `gmail.send_email` call) but are not falsifiable type claims.
- **Evidence**: `docs/SPEC.md:493-531`; `apps/learning-api/src/learning_api/services/topic_resolver.py:3-9`; `apps/learning-api/src/learning_api/services/report.py:202-211`, `:487-517`; `apps/learning-api/src/learning_api/graph/build.py:100-117`; `apps/learning-api/src/learning_api/services/attendance.py:130-187`; `docs/DECISIONS.md:415`.
- **Severity**: MEDIUM — documentation drift in the §5.5.2 table's stale rows; the deterministic-core closing rule itself holds.
- **Likely explanation**: The table was written as a design allocation; two allocations were later decided differently (D-024, and the report path's reuse for tutor summaries) without amending the table.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-33
- **Title**: `LearningState`'s field count is stated three different ways, and SPEC's `QAState.ephemeral_location` does not exist in code
- **Related claims**: REQ-52, REQ-28, SEC-05 / **Related decisions**: D-045 (location travels only in the interrupt resume value)
- **Intended state**: SPEC says `LearningState` enumerates ~40 fields; U7's correction says 31; SPEC §5.19.3 says `QAState` carries `ephemeral_location` rather than persisted coordinates.
- **Observed state**: `LearningState` is a single `BaseModel` with **32** top-level fields (`learning-api/graph/state.py:13-125`) — not ~40 and not 31. Identity fields are `user_external_id`, `student_external_id`, `parent_external_id`, `candidate_children: list[str]`; no name-, email- or coordinate-shaped field exists. `QAState` **does not carry `ephemeral_location`** at all, and grep finds the identifier only inside a stale in-code comment (`chat-api/graph/state.py:4-7`: `location_consent`/`ephemeral_location` "are still not present - S15 adds them" — S15 shipped and D-045 chose differently). Adjudication: the **code is right** — location travels only in the interrupt resume value, never through `QAState` — so both SPEC §5.19.3 and the in-code comment are the drift. Carried as a limitation rather than a drift: the checkpoint tables (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, `checkpoint_migrations`) are outside `Base.metadata` and therefore outside `test_schema_purity.py` entirely, and untyped `dict` fields (`last_items`, `last_intervention`, `pending_*`) are outside any name-based check.
- **Evidence**: `apps/learning-api/src/learning_api/graph/state.py:13-125`; `apps/chat-api/src/chat_api/graph/state.py:4-7`, `:23-29`; `packages/db/tests/test_schema_purity.py:56-66`; `packages/db/src/intellichoice_db/migration_filters.py:21-24`; `docs/SPEC.md` §5.19.3.
- **Severity**: MEDIUM — three-way documentation drift.
- **Likely explanation**: The counts were written at three different moments and never re-derived; the S15 comment was left when D-045 changed the design.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no. See DRIFT-71 for the same stale docstring recorded from the chat side.

- **Drift ID**: DRIFT-34
- **Title**: SPEC §5.30.1's seven-field payload allowlist describes exactly one of twenty-three Bedrock payloads
- **Related claims**: SEC-03, SEC-06, REQ-01 / **Related decisions**: D-023, D-071, D-072 (wire-allowlist extensions), D-219, D-175 (AUD-L-05)
- **Intended state**: Bedrock payloads may carry only `grade`, `current_topic`, `skill`, `estimated_level`, `question`, `selected_answer`, `relevant_learning_fact`; seven named PII fields must never be sent.
- **Observed state**: **The denylist half fully holds** — none of SPEC's seven forbidden names appears in any of the 23 `*Payload` models, and the test denylist is a superset. The allowlist half describes one model: `BedrockTutorPayload` is SPEC's seven fields verbatim (`bedrock.py:91-109`). The other 16 governed models carry fields outside SPEC's list, including `StageNarrativePayload`'s **`attendance_status`** (`:1120-1137`) — a category SEC-01/REQ-01 name as MySQL-only — and `RagAnswerPayload`'s **`user_role`** (`:796-807`), a role string that D-219 removed from `ScopeAndIntentPayload` for prompt-authorization reasons while leaving it here. `ReportInterpretationPayload` carries 19 fields. No SPEC-listed field is missing: SPEC's list is a strict subset of what code sends. Each widening was decided; none was reflected back into SPEC. Secondary (SEC-06, LOW): TRACEABILITY's "every Bedrock payload … with an exact field list" is also wider than code — 11 of 23 payloads are under `extra="forbid"` only, by reasoned regime split, with `LlmJudgePayload` explicitly ungoverned with a written reason.
- **Evidence**: `docs/SPEC.md:2812-2836`; `packages/shared/src/intellichoice_shared/bedrock.py:91-109`, `:157-170`, `:796-807`, `:1120-1137`; `packages/shared/tests/test_bedrock_payload_pii_floor.py:60-240`, `:314-455`. Live limitation, not new drift: `:174-175` records that "the query text itself is not redacted before the wire is a separate, live finding (AUD-C-24)".
- **Severity**: MEDIUM
- **Likely explanation**: Each widening was justified per decision at the time; SPEC §5.30.1 was written for the tutor payload and never generalised.
- **Resolvable by Phase 3B?**: no — field-name diffing is static.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-35
- **Title**: SPEC-unmarked-departure family — five recorded decisions depart from SPEC text that carries no amendment marker
- **Related claims**: ARCH-25, WORK-31, REQ-35, REQ-37, REQ-43 / **Related decisions**: D-004, D-223, D-325, D-189, D-302, D-402
- **Intended state**: SPEC is the detailed contract; where a decision departs from it, the departure should be discoverable from SPEC.
- **Observed state**: Five departures are live in code or decided in DECISIONS with **no marker in the SPEC section they contradict**. SPEC's only amendment marker in the whole file is at `:1973` (D-351), for an unrelated section.
  - **ARCH-25 / §5.36** — the Final Technology Placement table runs to `SPEC.md:3462` with `| Kubernetes | EKS runtime |` and `| Enterprise-Level Product | … CI/CD, EKS |` unqualified; no banner, footnote, strikethrough or D-004 reference anywhere in or around it. See DRIFT-26 for §5.33's sibling defect and DRIFT-37 for the re-read that would have caught it.
  - **WORK-31 / §5.8.1** — `SPEC.md:784-796` still reads "Each topic contains 100 validated base templates:" with the 20-per-tier block, against D-223's 5–7 per occupied tier (`CONTENT_COVERAGE.md:169-181`) — a ≈3.4× divergence in content spend and review burden, with no cross-reference.
  - **REQ-35 / §5.11.2** — rule 4's ranking is deliberately inverted in code and the reason is measured: `study_plan.py:19-29` "**This is a deliberate departure from SPEC's stated ranking, and the reason is measured.** … On the dev database **57 of 201 study items did exactly that, 40 of them at the very first study item** … One tier off is a worse question, the same question is a worse measurement, so the preference yields" (implementation `:145-158`, `:164-173`); matches ROADMAP:2320's recorded departure. Also `base_problem_count=len(target_skill_ids)` (`:296`) can be < 5 on thin topics against `BASE_PROBLEM_COUNT = 5` (`:58`).
  - **REQ-37 / §5.13.1–.2** — two departures visible in code: (a) authored templates repeat the pre-exam rendering with options permuted (`variant_persistence.py:114-116` "**This is where the post-exam's parallel form is partly given up** (D-189, the user's call)", collision handling and `"static_variant_repeats_rendering"` logging at `:159-166`); (b) composition moved from "2 per tier 1-5" to "10 total" (`assessment_builder.py:23-37` "**Why the rule moved from '2 at every tier' to '10 in total.'**", D-302). Plus a locus correction: enforcement lives in `assessment_builder.py`/`variant_persistence.py`, **not** `exam_policy.py` as TRACEABILITY and the ledger locate it — `exam_policy.py:23-57` is 61 lines of per-session-type timer/navigation/hints/feedback config with no matching dimensions and no reuse check.
  - **REQ-43 / §5.19.5** — the `TurnReason` enum holds **ten** values, not nine: `outcomes.py:27-65` adds `CANCELLED = "cancelled"` (D-402, "Deliberately last and outside the 'worked -> did not work' ordering") while `SPEC.md:1988-1998`'s table still lists exactly nine rows with no `cancelled`. This is a client-visible reason code and weakens Phase-2 REQ-43's "nine-value taxonomy" as written. Secondary LOW: `chat-web/src/types.ts:67` types `reason?: string | null` rather than narrowing to the union, so the "clients branch on the reason" contract is untyped at the client.
- **Evidence**: as cited inline; `docs/SPEC.md:3411-3462`, `:784-796`, `:1988-1998`; `docs/DECISIONS.md:29-36`; `docs/ROADMAP.md:2320`; grep for `superseded|amended|D-004` in SPEC.md returns only `:48` and `:1973`.
- **Severity**: MEDIUM (grouped as one family entry per the adjudication's instruction). Sibling SPEC-unmarked instances kept as their own entries: DRIFT-26 (§5.33), DRIFT-27 (§5.33.4), DRIFT-32 (§5.5.2), DRIFT-33 (§5.19.3), DRIFT-34 (§5.30.1), DRIFT-16 (§5.1.4), DRIFT-55 (§5.25.2's thirteen types).
- **Likely explanation**: This project records decisions in DECISIONS.md and in code comments at the site of the departure — a strong practice that has no step writing the departure back into SPEC.
- **Resolvable by Phase 3B?**: no — every half is repository-evident.
- **Genuine decision required?**: no — a marker is editorial, not a product call.

- **Drift ID**: DRIFT-36
- **Title**: The mandatory counsel-review release gate has no consolidated launch-checklist home
- **Related claims**: REQ-30, INT-19, WORK-33 / **Related decisions**: D-114 §4, D-129
- **Intended state**: Review by U.S. education/child-privacy counsel is a mandatory production release gate.
- **Observed state**: No counsel-review record exists anywhere; all six non-ledger `counsel` hits state the gate prospectively, never as performed. The gate is represented as a launch gate in ROADMAP's §6.1 parallel-track block, but **there is no launch-checklist document**: the only file self-describing as a launch-checklist item is `ENROLLMENT_FAQ_APPROVAL.md`, which claims to be "the only launch-checklist item gating the guest journey's canonical question" — a narrower scope that does not enumerate the counsel gate. So a launch-blocking legal gate is discoverable only by grep across four narrative mentions in four documents.
- **Evidence**: `docs/SPEC.md:57`; `docs/ROADMAP.md:2148-2150`; `docs/FIRST_VISIT_NOTICE.md:10`, `:236`; `docs/INCIDENT_RESPONSE.md:185`; `docs/ENROLLMENT_FAQ_APPROVAL.md:1`, `:82`, `:88`.
- **Severity**: MEDIUM
- **Likely explanation**: The gate is real and repeatedly stated; no launch checklist artifact was ever created to hold it, because the §6.1 track that would own it has not started (DRIFT-11).
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-37
- **Title**: The owed human re-read of §5.3 and §5.36 never fired across at least three qualifying architecture changes
- **Related claims**: TEST-05, ARCH-25, TEST-06 / **Related decisions**: D-334, D-335, D-349, D-406, D-393, D-394
- **Intended state**: §5.3 and §5.36 are recorded as descriptive rather than traced, on the condition that a human re-reads them whenever the architecture changes.
- **Observed state**: Multiple qualifying changes landed after tranche 6 and no re-read record exists: D-334/D-335 (SSE bus replaced by Postgres `LISTEN`/`NOTIFY` fan-out, 2026-08-15), D-349 (same relay for chat-api), D-406/W14 (NAT topology moved, 2026-08-18), D-393/D-394 (observability/formatter). `docs/TRACEABILITY.md` **was** edited on 2026-08-17 (commits `2dd9e7e`, `7285951`) and the §5.32 row was updated for D-393/D-394, but the §5.3/§5.36 descriptive rows were not touched and no re-read is recorded. A corpus grep for re-read records against those two sections returns only the two places that state the obligation. §5.36 is independently known stale (DRIFT-35), so the mechanism the descriptive verdict substituted for did not fire.
- **Evidence**: `docs/TRACEABILITY.md:45-47`, `:622`, `:626-633`; `docs/ARCHITECTURE.md:610-631`; `docs/ROADMAP.md:3026`; git log for `docs/TRACEABILITY.md` → `7285951` (2026-08-17), `2dd9e7e` (2026-08-17).
- **Severity**: MEDIUM
- **Likely explanation**: The obligation is a human habit with no trigger, no owner and no threshold definition — "architecture change" is nowhere defined.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no — the obligation is already recorded; execution is owed.

- **Drift ID**: DRIFT-38
- **Title**: TRACEABILITY's launch-scope exclusion table attributes three specifics to decisions that do not contain them
- **Related claims**: TEST-06, TEST-07, SEC-17 / **Related decisions**: D-004, D-078, D-087
- **Intended state**: The exclusion table's three owning decisions say what the table attributes to them.
- **Observed state**: Two of three attributions are unsupported by the decision text and one is thin. **D-004** supports "EKS-only concepts" generically, but the words "Pod Security Standards" and "NetworkPolicy" **do not appear in D-004** — the row is an inference from its EKS deferral, not a quotation. **D-078**: `6.19` appears **nowhere in DECISIONS.md** (only `SPEC.md:3968` and `ROADMAP.md:466`), so the table's "§6.19 Phase 18 (D-078)" attribution has no supporting text in the decision. **D-087** does carry the WAF deferral in its body ("in-memory stopgap until a real WAF exists … WAF itself was deferred this session"), but **"S50" and "A7" appear nowhere in D-087** — the "tracked to S50 A7" half of the attribution is not in the decision, the same defect class as DRIFT-02. This matters because the exclusion table is the denominator of the 37-of-37 claim (DRIFT-39).
- **Evidence**: `docs/TRACEABILITY.md:55-68`; `docs/DECISIONS.md:29-36` (D-004), `:2025-2035` (D-078), `:2883-2896` (D-087, WAF at `:2895`).
- **Severity**: MEDIUM
- **Likely explanation**: The table was written from the author's working knowledge of each decision's intent rather than by quoting them, and the attributions were never checked back against the decision bodies.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-39
- **Title**: "37 of 37 launch-scope sections" is an off-by-one against the file's own scope table
- **Related claims**: TEST-07, TEST-01, TEST-06 / **Related decisions**: D-123, D-129, D-078
- **Intended state**: All launch-scope §5 sections carry a verdict, claimed as 37 of 37 and used as gate-criterion-1 evidence.
- **Observed state**: The sweep coverage is genuinely complete — every top-level section §5.0 through §5.36 receives a verdict — but the arithmetic label is wrong. The scope section states "§5 has **37 top-level sections** (§5.0–§5.36)" and then excludes "§5.17 Multimodal solution images (**all of it**)", leaving **36** launch-scope top-level sections. The Status line nonetheless claims "37 of 37 **launch-scope** sections". §5.17 does carry a verdict ("**Dispositioned** — the feature does not exist", tranche 1 rule 8, `:250-253`), so 37 is reachable only by counting the excluded section's disposition inside the launch-scope denominator. Separately, the tranche-5 running total at `:576` still reads "Sections swept: 21 of 37". §5.20 and §5.23 have zero standalone mentions and are covered only by the ranged headings `### §5.19–§5.21` and `### §5.22–§5.24`.
- **Evidence**: `docs/TRACEABILITY.md:57-58`, `:72`, `:99`, `:250-253`, `:576`, `:635`, `:759-773`; per-section presence check across §5.0–§5.36.
- **Severity**: MEDIUM — the defect is the arithmetic on a gate-criterion claim, not the underlying work.
- **Likely explanation**: The denominator was fixed at the section count before the exclusion table existed, and the exclusion's "all of it" scope was not subtracted.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-40
- **Title**: A bare `AUD-L-17` resolves to two live findings in two registers and the documented disambiguation heuristic does not work across documents
- **Related claims**: TEST-20, TEST-15, TEST-16, TEST-17 / **Related decisions**: D-174, D-178, D-183
- **Intended state**: The AUD-L-17 → AUD-L-19 renumber was applied per reference; ranges and P3 narrative were deliberately left, and pre-2026-08-04 documents still citing `AUD-L-17` for the P2 still resolve via the renumber note.
- **Observed state**: Per-reference application is confirmed — 41 surviving citations corpus-wide (36 excluding the ledger's own 5), of which the two P2-meaning hits are both explicitly historical (`AUDIT_FINDINGS.md:35`; `DECISIONS.md:11207`) and **no live, unqualified P2-meaning citation survives**. The unmitigated defect is a cross-document namespace collision: `AUDIT_LIVE_2026_08_17.md:43` carries its own `AUD-L-17` ("Child chooser has no sign-out or exit", P3) in a wholly separate register, and the disambiguation heuristic documented in AUDIT_FINDINGS explicitly does not reach across documents. The ledger's "33 places across five documents" is a 2026-08-04 snapshot; it is now 36 non-ledger hits across seven files as the reconciliation corpus added its own.
- **Evidence**: 41-hit `grep -rn "AUD-L-17" --include="*.md"`; `docs/AUDIT_FINDINGS.md:35`, `:43`, `:182-200`; `docs/AUDIT_LIVE_2026_08_17.md:43`; `docs/ROADMAP.md:744-745`, `:751`; `docs/DECISIONS.md:11191`, `:11205`, `:11207`, `:11311`.
- **Severity**: MEDIUM
- **Likely explanation**: The second register was created with the same id prefix scheme and no namespace, and the renumber's disambiguation note was written for the single-register case.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: yes — whether to namespace the AUDIT_LIVE register's ids. Cross-references the existing audit-ID-namespace risk already carried in the reconciliation corpus.

- **Drift ID**: DRIFT-41
- **Title**: "Zero blank/stuck states enforced at teardown" overstates what the e2e harness asserts
- **Related claims**: TEST-27, TEST-22, TEST-25 / **Related decisions**: D-355, D-383
- **Intended state**: `capture.ts` attaches console and network capture to every page and enforces zero console errors, zero 5xx and zero blank/stuck states at teardown, narrowable only via `audit.allow({...})`.
- **Observed state**: Most of it holds. `assertClean()` asserts `pageErrors === []`, `consoleErrors === []`, `serverErrors === []` (skippable via `allowances.serverErrors`) and `failedRequests === []`; narrowing goes through `AuditLog.allow()` and `ScopedConsoleError` requires a URL match, with D-355's lesson recorded in the docstring; `persist()` appends one JSONL line per test. But **"zero blank/stuck states" is not a distinct teardown assertion** — blank/stuck is carried by the `pageerror` listener and by per-spec helpers `expectNotBlank`/`expectNotStuck` imported from `e2e/fixtures/session.ts`, i.e. asserted in-test rather than over the whole run. Second nuance: the fixture teardown runs `persist()` then `if (testInfo.status === "passed") log.assertClean()`, so a failing test's criterion-3 evidence is reported but not enforced. `clientErrors` (4xx) is explicitly "reported, not enforced — no assertion reads it".
- **Evidence**: `e2e/fixtures/capture.ts:39-80`, `~:136-159` (`assertClean`), `~:236-260` (`persist`), `~:262-270` (`test.extend`); `e2e/tests/learning/journey-student.spec.ts:13`; `e2e/README.md`.
- **Severity**: MEDIUM
- **Likely explanation**: The three criteria were designed together and two were implemented centrally; the third stayed per-spec and the README described the intent.
- **Resolvable by Phase 3B?**: no — the assertion set is repository-evident.
- **Genuine decision required?**: no — a doc wording fix later.

- **Drift ID**: DRIFT-42
- **Title**: PROGRESS records the commit-vs-ignore choice as open for paths that are already committed
- **Related claims**: WORK-09 / **Related decisions**: D-417
- **Intended state**: `.agents/skills/` and `skills-lock.json` are untracked and unignored, appearing in every `git status`, with the commit-or-ignore choice left to the user.
- **Observed state**: **Contradicted — they are tracked.** `git status --short` returns exactly one line, `?? docs/reconciliation/` (this audit's own directory). `git ls-files skills-lock.json .agents` returns `.agents/skills/agent-browser/SKILL.md` and `skills-lock.json`, both tracked, committed in `a6da941` (D-417). `.gitignore` contains no `skills`/`agents` pattern, so "not ignored" is still literally true but no longer a problem. `PROGRESS.md:158-160` nonetheless records the open user-preference item for those paths, while `PROGRESS.md:83`'s "agent tooling committed ✅ done" is the accurate line.
- **Evidence**: `git status --short`; `git ls-files skills-lock.json .agents`; `git log --oneline -- skills-lock.json .agents` → `a6da941`; `.gitignore`; `docs/PROGRESS.md:83`, `:158-160`.
- **Severity**: MEDIUM — refutes Phase-2 WORK-09 as CURRENT.
- **Likely explanation**: The paths were committed as part of a twelve-decision milestone commit; the open-item line describing the choice was not retired.
- **Resolvable by Phase 3B?**: no — directly observable from git state.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-43
- **Title**: PROGRESS's C8 row is stale in both status and denominator, and 494 is unreproducible
- **Related claims**: WORK-11, WORK-07, WORK-08 / **Related decisions**: D-417 (C8), D-418
- **Intended state**: ROADMAP records C8 (`ruff format`) as done at 168 of 437; PROGRESS records it as "⏳ next" at 168 of 494.
- **Observed state**: **ROADMAP is right on all three counts and its 437 is exactly reproducible.** The mechanical commit is `5728b95 style: ruff format, mechanically, across 168 Python files (D-417/C8)` — `git show --numstat` confirms exactly **168** files changed, 795 insertions / 1118 deletions, a pure-format commit; enforcement landed separately as `f0d2cfe`. Denominator: at `5728b95` the repo had **473** tracked `.py` files and `[tool.ruff] extend-exclude = ["packages/db/alembic/versions"]` removes **36** of them → **437**. At HEAD: 477 tracked `.py` → 440 ruff-visible. **No count in repo history plausibly yields 494.** Wiring is in both places: `Makefile:120-124` `lint: uv run ruff check . ; uv run ruff format --check .` and a dedicated "Format check" step at `.github/workflows/ci.yml:81-82` ("this job - not the Makefile - is what the branch-protection rule requires"). `PROGRESS.md:84` remains stale; the same four-row queued block also marks A3/B4/B6 "⏳" against ROADMAP W25/W26/W27, so the repository supports treating the whole block as superseded.
- **Evidence**: `git show --stat 5728b95`; `git ls-tree -r --name-only 5728b95 | grep -c '\.py$'` → 473; `git ls-files 'packages/db/alembic/versions/*.py' | wc -l` → 37 (36 at that commit); `pyproject.toml:24-40`; `Makefile:120-127`; `.github/workflows/ci.yml:74-82`; `docs/PROGRESS.md:84`.
- **Severity**: MEDIUM — resolves the Phase-2 contradiction in ROADMAP's favour and refutes the PROGRESS side.
- **Likely explanation**: The PROGRESS block was written before the work landed and its denominator was estimated rather than derived from `ruff`'s own file set.
- **Resolvable by Phase 3B?**: no — reproduced from git history and tool config.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-44
- **Title**: learning-web's disconnect-banner condition carries two live statuses — decided-untested in code, open in PROGRESS
- **Related claims**: WORK-12 / **Related decisions**: D-417 / C7
- **Intended state**: One status for one gap.
- **Observed state**: **CONFLICT.** The gap itself is confirmed: learning-web has four unit test files and a grep for `banner|streamState` across them yields one hit, prose inside a test title (`api/stream.test.ts:148`), not an assertion; no learning e2e spec mentions `stream-banner` or `streamState`; the condition is `session.streamState === "error"` inline in `apps/learning-web/src/App.tsx:977-984`. chat-web by contrast has `screens/ChatScreen.test.tsx` (17 matches) plus `e2e/tests/chat/stream-disconnect-visible.spec.ts`. The disagreement is about status: `App.tsx:958-960` now reads "**This condition is deliberately untested, and that is a decision rather than an oversight (D-417 / C7). Do not re-file it as missing coverage.**" while `PROGRESS.md:107-117` carries it as an open carry-over after W21 ("still open after W21… price the real work or leave it").
- **Evidence**: `apps/learning-web/src/App.tsx:947-984`; `apps/learning-web/src/api/stream.test.ts:148`; `apps/chat-web/src/screens/ChatScreen.test.tsx`; `e2e/tests/chat/stream-disconnect-visible.spec.ts`; `docs/PROGRESS.md:107-117`.
- **Severity**: MEDIUM
- **Likely explanation**: PROGRESS is the likely-lagging side, but D-417/C7's scope (chat versus learning) must be settled from the decision text before saying so — both statuses are cited here rather than one being preferred.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: yes — which status stands, which requires reading D-417/C7's own scope.

- **Drift ID**: DRIFT-45
- **Title**: Checkpoint retention floors are chosen and implemented, and no job is scheduled to keep the promise
- **Related claims**: WORK-19, WORK-22, COST-18, ARCH-05 / **Related decisions**: D-331, D-333
- **Intended state**: U7 §9.1 and the ledger record the retention age floor as not yet chosen.
- **Observed state**: **Refuted as written — three floors are chosen and in code**: `COMPLETED_RETENTION_DAYS = 30`, `ABANDONED_RETENTION_DAYS = 90`, `CHAT_RETENTION_DAYS = 180` (`checkpoint_retention_cli.py:88-90`) with a rationale table at `:19-24` and D-331's byte measurement (completed 1.7%, abandoned 77%, chat 19%). The second, live drift is policy-without-enforcement: deletion is dry-run by default — `apply_enabled()` returns True only for an explicit `CHECKPOINT_RETENTION_APPLY=true` (`:97-99`), with the reason written in place ("A job whose failure mode is silently deleting a K-12 student's learning history does not get to delete by default", `:5-7`) — and the job is **absent from terraform entirely** (`grep -rn "checkpoint_retention" terraform/` → no matches), which `modules/scheduled-jobs/main.tf:46-51` explains as deliberate ("scheduling it before this one would be actively unsafe"). So a retention promise over minors' data has no scheduled keeper.
- **Evidence**: `apps/learning-api/src/learning_api/services/checkpoint_retention_cli.py:5-7`, `:19-24`, `:88-90`, `:97-99`; `terraform/modules/scheduled-jobs/main.tf:41-51`; zero-hit terraform grep; `docs/U7_CHECKPOINT_CONSOLIDATION.md:1-5`, `:281-292`.
- **Severity**: MEDIUM
- **Likely explanation**: The floors were decided and shipped one day after U7's question; the safety ordering (session-consolidate must have a firing record first) correctly delayed scheduling, and nothing re-raised it afterwards.
- **Resolvable by Phase 3B?**: no — the absence from configuration is repository-evident; a live check would confirm no schedule exists.
- **Genuine decision required?**: yes — scheduling and apply-enabling are user calls given D-333's dry-run posture. Same decision as DRIFT-46.

- **Drift ID**: DRIFT-46
- **Title**: The 180-day chat-checkpoint policy is implemented and not operative, so chat checkpoints remain unbounded in practice
- **Related claims**: WORK-21, WORK-19, SEC-13 / **Related decisions**: D-333
- **Intended state**: U7 §9.3 records chat checkpoints as unbounded and addressed by no policy.
- **Observed state**: A policy exists — `CHAT_RETENTION_DAYS = 180` inactivity (`checkpoint_retention_cli.py:90`, table row at `:23`), with `_process_chat_threads` deleting `checkpoint_writes`/`checkpoint_blobs`/`checkpoints` past the cutoff and `_chat_thread_ids` classifying "chat" by **two** positive conditions (`NOT EXISTS (... learning_sessions ...)` AND `NOT EXISTS (... p.checkpoint->'channel_values' ? 'phase')`) precisely so an unprojected learning thread cannot be deleted under the chat policy ("if the reconciler had never run, every learning thread past 180 days would be deleted here - under the chat policy, bypassing the consolidation gate entirely"). But the same dry-run default applies (`if not apply: counts.note("would_delete_chat"); continue`) and the job is unscheduled, so **chat checkpoints are in practice still unbounded** — a closure recorded on code presence alone would be wrong. Chat consolidation is separately documented as a structural no-op (`:28-34`).
- **Evidence**: `apps/learning-api/src/learning_api/services/checkpoint_retention_cli.py:23`, `:28-34`, `:90`, `_chat_thread_ids` docstring and SQL, `_process_chat_threads`; zero-hit `checkpoint_retention` terraform grep.
- **Severity**: MEDIUM
- **Likely explanation**: Same as DRIFT-45 — the policy shipped with the safety posture and the scheduling step is a separate, unowned decision.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: yes — same decision as DRIFT-45. Note the interaction with DRIFT-09: no retention job covers `checkpoint_writes.__resume__` rows for live threads either.

- **Drift ID**: DRIFT-47
- **Title**: U7_CHECKPOINT_CONSOLIDATION presents itself as pre-implementation with four open questions D-333 answered and shipped the next day
- **Related claims**: WORK-22, WORK-19, WORK-20, WORK-24 / **Related decisions**: D-331, D-333, D-336
- **Intended state**: U7 §9.4 asks whether abandoned-session retention deserves its own follow-up session.
- **Observed state**: No follow-up was scheduled because the recommendation was adopted directly one day later. D-333 records the user's decision in their own words ("Keep both chat and abandoned/pending checkpoints on a 90-day inactivity retention window") with a three-window table giving completed 30 days / abandoned-pending 90 days inactivity / chat 180 days inactivity; PROGRESS confirms "**✅ U7 IS COMPLETE (2026-08-15, D-333)**", merged (`8c86685`, #274) and deployed. **`U7_CHECKPOINT_CONSOLIDATION.md` itself was never updated** — its Status line still reads "design review, **measured**. Steps 1–2 of §8 are done; no deletion code written", and §9's four items are still posed as open questions with no completion banner pointing at D-333. A reader taking §9 at face value would re-open a settled policy decision.
- **Evidence**: `docs/U7_CHECKPOINT_CONSOLIDATION.md:1-5`, `:52-63`, `:265-279`, `:281-292`; `docs/DECISIONS.md:23837-23860` (user's words at `:23843`, table at `:23858`); `docs/PROGRESS.md:1238-1247`.
- **Severity**: MEDIUM
- **Likely explanation**: The decision was recorded where decisions live and the source document was treated as a historical working note without being marked as one.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no. Sibling stale sections in the same file: DRIFT-94 (§9.2) and DRIFT-95 (§10).

- **Drift ID**: DRIFT-48
- **Title**: QUESTION_GENERATION's trailing "Next:" still instructs a Mistral-Generator course of action
- **Related claims**: WORK-26, WORK-27 / **Related decisions**: D-273
- **Intended state**: The Anthropic-only roster of 2026-08-11 supersedes the earlier plan; no Mistral configuration exists.
- **Observed state**: **No Mistral model id is configured anywhere.** A repo-wide grep across `*.py`/`*.yaml`/`*.yml`/`*.toml`/`*.example`/`*.tf`/`*.json` (excluding `.venv`) yields five hits, all non-configuration: three prose comments citing `mistral-large-3` as historical evidence for a *rejected* behaviour (`review_loop.py:251`; `hint_solution_repair.py:138` "`mistral-large-3` rewrote **every** solution step"; `test_review_loop.py:267`) and two adapter test assertions about capability detection (`test_bedrock_provider.py:12`, `test_bedrock_gateway.py:749`). `.env.example` and `packages/curriculum/.../settings.py` contain zero Mistral references. The stale instruction survives at `docs/QUESTION_GENERATION.md:449`, contradicting `:243-282` of the same file and matching nothing in code — live, reader-facing and self-contradictory.
- **Evidence**: `docs/QUESTION_GENERATION.md:446-450` vs `:243-282`; `.env.example:26-39`; `packages/curriculum/src/intellichoice_curriculum/settings.py:23-33`; greps as described.
- **Severity**: MEDIUM
- **Likely explanation**: The roster section was rewritten in place when D-273 measured invocability; the document's trailing action item was not.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-49
- **Title**: `.env.example` configures the mirror image of the documented model roster, and the code defaults are an AccessDenied id
- **Related claims**: WORK-27, WORK-26 / **Related decisions**: D-273
- **Intended state**: `docs/QUESTION_GENERATION.md:266-271` records Generator = Sonnet 4.5, Solver A = Haiku 4.5, Solver B = Sonnet 4.5 (sharing the Generator's weights), Judge = Haiku 4.5.
- **Observed state**: The structural halves hold — two invocable models, the pigeonhole that two of three roles must share, and a fail-closed preflight comparing `underlying_model(solver_a) != underlying_model(solver_b)` ("their agreement would be one opinion counted twice", `pipeline_cli.py:735-745`) with both tests present (`test_authored_pipeline.py:1428`, `:1457`). But the slot→role mapping (`ai_pipeline.py:1329` Generator, `:1911` Solver A, `:1923` Solver B, `:1970` Judge; corroborated at `pipeline_cli.py:732-734`) means `.env.example:28-37` configures **Generator = Haiku 4.5, Solver A = Haiku 4.5, Solver B = Sonnet 4.5** — Generator sharing with **Solver A**, the mirror of the documented roster, so the "better Generator" gain the roster claims is not what the example configures. Separately `settings.py:23-33` defaults all four slots to `anthropic.claude-sonnet-5`, the id D-273's 1-token probe measured as AccessDenied ("anthropic.claude-sonnet-5 is not available for this account", `QUESTION_GENERATION.md:253`), which also collapses all four slots onto one model the preflight would reject.
- **Evidence**: `.env.example:10-39`; `packages/curriculum/src/intellichoice_curriculum/settings.py:16-33`; `ai_pipeline.py:967-968`, `:1247`, `:1329`, `:1911`, `:1923`, `:1970`; `pipeline_cli.py:732-745`; `docs/QUESTION_GENERATION.md:243-282`.
- **Severity**: MEDIUM
- **Likely explanation**: The roster was written from the intended design and the example file from what was invocable at the time; the settings defaults predate D-273's measurement.
- **Resolvable by Phase 3B?**: **no** — and explicitly: the operative `.env` is forbidden to read and stayed unread, so the operative roster is unresolvable in 3A and not resolvable by 3B either without the user.
- **Genuine decision required?**: yes — which roster is intended, the document's or the example's.

- **Drift ID**: DRIFT-50
- **Title**: HINT_SOLUTION_REVIEW says "the loop around them is not built" while `review_loop.py` exists, and three in-code docstrings are stale the same way
- **Related claims**: WORK-28 / **Related decisions**: D-251
- **Intended state**: The document describes the instrument as built and measured, the loop as not built, and "Still not built: any pipeline caller."
- **Observed state**: The operative halves are confirmed and the header is not. All three modules exist and are implemented: `review_panel.py` (`review_panel` at `:111`), `hint_solution_repair.py`, and `review_loop.py` (`run_review_loop` at `:131`, calling `review_panel` at `:191`, returning `LoopOutcome("accepted", ...)` on unanimity at `:209`). **No pipeline caller exists** — grep for `HINT_SOLUTION`, `review_loop`, `review_panel`, `hint_solution` against `ai_pipeline.py` and `pipeline_cli.py` returns zero hits in both — but a script caller does: `scripts/repair_authored_solutions.py:35` imports `run_review_loop` and invokes it at `:211`. Two drifts follow: (a) `docs/HINT_SOLUTION_REVIEW.md:1-18` states "the loop around them is not built" while naming `review_loop.py` in the same fifteen lines — it should read "built but uncalled"; (b) in-code docstrings are stale in the same direction — `review_loop.py:3` "**Nothing calls this.**" and `review_panel.py:5-6` "the repair loop … not built".
- **Evidence**: `packages/curriculum/src/intellichoice_curriculum/review_loop.py:1-15`, `:131`, `:191`, `:209`; `review_panel.py:1-15`, `:111`; `hint_solution_repair.py:1-10`; `scripts/repair_authored_solutions.py:35`, `:211`; zero-hit grep over `ai_pipeline.py` + `pipeline_cli.py`; `docs/HINT_SOLUTION_REVIEW.md:1-18`.
- **Severity**: MEDIUM — resolves the ledger UNKNOWN: the loop module is built; only the pipeline call site is not.
- **Likely explanation**: The modules were written in one sitting with docstrings recording the not-yet-called state; the script that calls the loop landed later and the docstrings and header were not revisited.
- **Resolvable by Phase 3B?**: no — import-graph evidence is static.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-51
- **Title**: CONTENT_COVERAGE still shows family B as needing the Phase R answer-model router, superseded the same day
- **Related claims**: WORK-30 / **Related decisions**: D-273
- **Intended state**: `route_answer` verifiers for the named answer models landed with Phase R, fail-closed and tested both directions.
- **Observed state**: The router landed and is explicitly fail-closed: `authored_validation.py:746-785` — "**Fail closed:** a form no model claims is an error, never a skip - an item whose answer nothing can check must not reach a student on the strength of nobody having checked it." Four of the five named models are real `DerivedAnswer` kinds (`multi_root:870`, `interval:888`, `tuple:942`, `symbolic:785`) plus `value:869`, with matching in `_option_matches:994-1060`. Both-directions tests exist (`test_answer_model_router.py:53`, `:70`, `:112`, `:136`, `:146`, `:341`), and `place_value_compare` is re-authored at 15/15 items. `docs/CONTENT_COVERAGE.md:96` nonetheless still shows family B as "⚠️ needs the Phase R answer-model router" and `:165` still routes it to "**Phase R**" as future work.
- **Evidence**: `packages/curriculum/src/intellichoice_curriculum/authored_validation.py:746-785`, `:869-942`, `:994-1060`; `packages/curriculum/tests/test_answer_model_router.py:30-146`, `:341-412`; `curriculum/internal_math/authored/place_value.yaml`; `docs/CONTENT_COVERAGE.md:96`, `:165`.
- **Severity**: MEDIUM
- **Likely explanation**: The status column was generated before the same day's work landed and the doc is not regenerated as part of the pipeline change.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no. See DRIFT-52 and DRIFT-96 for the same file's other drifts.

- **Drift ID**: DRIFT-52
- **Title**: CONTENT_COVERAGE's content-state figures are stale in three places
- **Related claims**: WORK-30, WORK-14 / **Related decisions**: D-273, D-342
- **Intended state**: The document reports current content state — grade-band coverage and family C's gating status.
- **Observed state**: The band figure has moved and family C is no longer gated. CONTENT_COVERAGE records 4 of 12 grade bands populated; `curriculum/internal_math/grade_topic_mapping.yaml:39-99` now populates **seven**: `"1-2"`, `"2-3"`, `"4-5"`, `"6-7"`, `"8-9"`, `"10-11"`, `"11-12"`. Family C is authored rather than gated: 40 items carry a non-null `figure_spec` across the bank of 958, e.g. `plane_figures.yaml:4-29` (`generator_model: authored-figure-script`, `figure_reading: null`), and the gate covers them through `check_figure_agrees_with_the_question` and `check_reading_matches_the_figure` (`authored_validation.py:1778`, `:1816`, both wired into `validate_authored_item`). The band-order trap the document warns about is real and independently pinned: `grade_topic_mapping.yaml:26-29` ("the §5.7.3 bands overlap and `topics_for_grade` returns the *first* match, so a '3-4' key placed above '4-5' would take grade 4 away from `fraction_operations`") with `test_adding_a_band_never_steals_a_grade_from_an_existing_one`.
- **Evidence**: `curriculum/internal_math/grade_topic_mapping.yaml:26-29`, `:39-99`; `curriculum/internal_math/authored/plane_figures.yaml:4-29`; `packages/curriculum/src/intellichoice_curriculum/authored_validation.py:1778`, `:1816`, `:1862-1901`; `docs/CONTENT_COVERAGE.md:96`, `:98`, `:102`, `:165`, `:169`.
- **Severity**: MEDIUM
- **Likely explanation**: The figures come from `scripts/build_content_coverage.py` over a live database and the document was not regenerated after subsequent authoring.
- **Resolvable by Phase 3B?**: no for the doc; the row-by-row census figures themselves are database-derived and were not re-derived in 3A.
- **Genuine decision required?**: no

### LOW

- **Drift ID**: DRIFT-53
- **Title**: The absolute "no PII in Postgres" rule is stated in three documents without D-050's four-column exemption
- **Related claims**: REQ-01, SEC-01, REQ-02 / **Related decisions**: D-050, D-104
- **Intended state**: CLAUDE.md rule 1, SPEC §5.4/§5.30 and INCIDENT_RESPONSE state that Postgres stores only `*_external_id` references and must never replicate names, emails, phones or addresses.
- **Observed state**: The floor's intent holds — a grep of every `mapped_column` for PII-shaped names returns exactly four hits, all org-published public website content: `org_branches.address/phone/email` (`models/org.py:22-24`) and `org_team_members.name`, each explicitly allowlisted in the purity test under D-050 (`test_schema_purity.py:17-53`), with `source_url`/`content_hash` columns confirming provenance from `packages/webcontent`. `BranchInfo.manager_email` comes from MySQL and is not persisted. The drift is that the three documents cited as the rule's source state it absolutely and carry no exemption, so a reader auditing the schema against them would find four apparent violations.
- **Evidence**: `packages/db/tests/test_schema_purity.py:6-11`, `:17-53`; `packages/db/src/intellichoice_db/models/org.py:18-33`; `packages/adapters/src/intellichoice_adapters/mysql_profile_adapter.py:44-46`, `:104-145`; `CLAUDE.md` rule 1.
- **Severity**: LOW, medium-adjacent (adjudicated LOW–MEDIUM).
- **Likely explanation**: The exemption was reasoned in the test docstring and D-050, where an implementer would meet it, rather than in the documents that state the rule.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-54
- **Title**: The log-boundary PII scanner is manual-invocation only; nothing runs it on a schedule
- **Related claims**: SEC-08, REQ-02 / **Related decisions**: D-104
- **Intended state**: The log boundary is enforced by `scripts/scan_logs_pii.py` (`make scan-logs`), which fails on truncation, an unreadable window or zero events.
- **Observed state**: The script exists and every named failure mode is a distinct non-zero exit — positive control first, returning 2 if any pattern cannot fire ("INVALID - these patterns cannot fire, so a clean result proves nothing"); missing log group → 3; unqueryable slice → 3 ("'I could not look' must not report as CLEAN"); any slice at the 10,000-record Insights cap → 3; zero events → 3. It imports the trace scanner's matcher rather than re-implementing it. But `make scan-logs` is the only entry point: no CI workflow and no scheduler invokes it, so "the log boundary is enforced" rests on someone choosing to run it.
- **Evidence**: `scripts/scan_logs_pii.py:45-52`, `:189-193`, `:203-212`, `:216-224`, `:226-235`, `:237-242`; `Makefile:243-250`; negative search for a workflow or schedule invoking it.
- **Severity**: LOW, medium-adjacent (adjudicated LOW–MEDIUM); posture known since criterion 9 and kept registered.
- **Likely explanation**: The scanner needs live AWS credentials and a chosen window, which is awkward to schedule; the single clean run was treated as sufficient evidence at the time.
- **Resolvable by Phase 3B?**: no for the absence of a schedule; a 3B run would produce a fresh result, not continuous assurance.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-55
- **Title**: Two of SPEC's thirteen structured-output artifact types have no Pydantic schema
- **Related claims**: REQ-17, REQ-16, COST-02 / **Related decisions**: D-024, D-020, D-022
- **Intended state**: A JSON-Schema/Pydantic model per each of thirteen artifact types, used at its boundary.
- **Observed state**: Eleven of thirteen have a model and a non-mock production call site. **Topic mapping**: `BedrockTask.TOPIC_MAPPING` exists at `bedrock.py:37` with no payload model, no response model and no caller anywhere in `packages`/`apps`/`scripts` — a reserved-but-unbuilt slot the ledger does not mention. **Email draft**: no Pydantic LLM response model; both email-draft paths are server-composed and deterministic (`learning_api/services/attendance.py:130 build_attendance_email_draft`; chat-api `state.email_draft`). Adjudication: both gaps are dispositioned — the topic resolver is deliberately a deterministic non-LLM builder (D-024, accepted 2026-07-16, `DECISIONS.md:415`) and deterministic email composition is the §5.6.4 pattern (D-020). SPEC's thirteen-type list was never amended, so the gap is doc-side. Two models are also production-dead: `GeneratedTemplateResponse` (`bedrock.py:317`) is referenced only by `mock_provider.py`, and `LlmCitation` (`:810`) has no reference outside `bedrock.py`.
- **Evidence**: `packages/shared/src/intellichoice_shared/bedrock.py:30-72`, `:74-1378`, `:317`, `:810`; `apps/learning-api/src/learning_api/services/attendance.py:130`; `docs/DECISIONS.md:415`; repo-wide `TOPIC_MAPPING` grep returning only the enum line and a docstring.
- **Severity**: LOW, medium-adjacent (adjudicated down from MEDIUM to LOW–MEDIUM documentation drift).
- **Likely explanation**: Both departures were decided and recorded in DECISIONS; SPEC's type list was not amended. Same pattern as DRIFT-35.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-56
- **Title**: The latency capacity plan implies five tasks against a configured `autoscaling_max_capacity` of three
- **Related claims**: ARCH-13, ARCH-12, COST-29 / **Related decisions**: D-136, D-153 §3 (purchase withdrawn)
- **Intended state**: The capacity/pricing table's "today" row is two tasks, and its plan states that at 25 concurrent a comfortable p95 costs three more tasks.
- **Observed state**: The pinned-2 configuration exists for learning-api (`desired_count = 2`, `autoscaling_min_capacity = 2`, `environments/staging/main.tf:446-447`), but `autoscaling_max_capacity` is at the module default **3** (`modules/ecs-service/variables.tf:193-197`, "Deliberately modest (Free Tier + solo-maintainer scale, not enterprise headroom)"), so an r=5 plan would need a configuration change nobody has made. chat-api is min 1 / max 3. Adjudication qualifier: **D-153 §3 withdrew that purchase**, so no active plan exceeds the configured ceiling — this is a latency-plan-versus-ceiling note for whenever capacity is revisited, not a live mismatch.
- **Evidence**: `terraform/environments/staging/main.tf:446-447`; `terraform/modules/ecs-service/variables.tf:187-197`; `docs/ARCHITECTURE.md:254-283`.
- **Severity**: LOW, medium-adjacent (adjudicated LOW–MEDIUM from the inspector's MEDIUM).
- **Likely explanation**: The plan and the ceiling were set at different moments and the plan was later withdrawn without the table being annotated.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-57
- **Title**: The zero-internet-egress invariant is a conditional default that the checked-in variables currently switch off
- **Related claims**: ARCH-28, ARCH-29, COST-28 / **Related decisions**: D-406, D-419
- **Intended state**: Private subnets carry no `0.0.0.0/0` route, AWS dependencies reach tasks via PrivateLink, and there are zero NAT gateways.
- **Observed state**: The PrivateLink half is confirmed — interface endpoints for `ecr.api`, `ecr.dkr`, `logs`, `secretsmanager` unconditionally, plus `bedrock-runtime` and `xray` when enabled, all in one subnet for the per-AZ cost reason quoted at `modules/vpc/main.tf:168-173`, plus an S3 gateway endpoint. So is the no-inline-default-route design: `aws_route_table.private` (`:96-100`) declares no inline route "so that flipping `nat_gateway_enabled` back to false removes the route and restores the no-egress property without recreating the route table." But the zero-NAT property is conditional and **off under checked-in defaults** (`langsmith_tracing_enabled` defaults true → NAT count 1). ARCHITECTURE's zero-egress framing is therefore baseline-with-exception rather than an invariant; the tense mixing was already registered in the reconciliation corpus.
- **Evidence**: `terraform/modules/vpc/main.tf:45-54`, `:73-110`, `:142-191`; `terraform/environments/staging/variables.tf:183-189`; `docs/ARCHITECTURE.md:2149-2152`.
- **Severity**: LOW, medium-adjacent (adjudicated LOW–MEDIUM).
- **Likely explanation**: The property was true when written and became conditional when tracing was turned on at the user's request on 2026-08-06.
- **Resolvable by Phase 3B?**: **yes** — the live NAT count and private route table settle the current state. See DRIFT-29.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-58
- **Title**: The e2e isolation finding is recorded as unresolved against a spec that now carries two dedicated fixture students
- **Related claims**: WORK-13 / **Related decisions**: D-288, D-365 §2, D-367
- **Intended state**: The ledger records UNKNOWN; the named remedies were a per-test fixture student or a `beforeEach` session clear.
- **Observed state**: The per-test-fixture remedy is present. `e2e/tests/learning/journey-student.spec.ts:117` signs in as `FIXTURES.studentJourney` with the comment "**Its own student, not `studentPresent`** (D-365 §2)", and `:427` uses `FIXTURES.studentResume` ("Staging's sessions persist, so a second test signing in as the full walk's student resumes that walk's exam mid-flight"). `e2e/config.ts:128-165` defines `studentPresent` (`student-ext-1`), `studentResume` (`student-ext-9`) and `studentJourney` (`student-ext-10`). No `beforeEach` or session-clearing hook exists — the second named remedy was not applied. PROGRESS's physically last entry on this item (2026-08-07) is stale against that code.
- **Evidence**: `e2e/tests/learning/journey-student.spec.ts:110-117`, `:421-427`; `e2e/config.ts:128-165`; `.github/workflows/ci.yml` (browser suite deliberately out of CI).
- **Severity**: LOW, medium-adjacent (adjudicated LOW–MEDIUM doc note).
- **Likely explanation**: The code-side remedy landed under a different decision id than the finding; the finding's own record was never re-measured, and the original observation was a three-run staging measurement.
- **Resolvable by Phase 3B?**: **yes** for the behavioural half — whether the walks now pass in combination is a live re-measure.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-59
- **Title**: OPEN_DECISIONS #10 records a `formatDateLabel` CDT fix that names no symbol, and the date-only shift is still armed
- **Related claims**: WORK-40 / **Related decisions**: D-324
- **Intended state**: OPEN_DECISIONS #10 is headed "ALL DECIDED", with three build consequences including a `formatDateLabel` fix settled as CDT.
- **Observed state**: Two of three items are built: `stage_narrative_stage: str | None = None` on five response models (`routers/sessions.py:274`, `:319`, `:351`, `:433`, `:458`) consumed at `StageTransitionScreen.tsx:39-45`, and the ladder-pause breadcrumb sink (`e2e/fixtures/learning-flow.ts:411-433`, "**Instrument only — this function's behaviour is deliberately unchanged.**") passed by three specs. The third: **no symbol named `formatDateLabel` exists** in either frontend; the actual formatter is `buildDateLabelFormatter(timeZone)` (`StudentDashboardScreen.tsx:80-82`, bound as `formatOrgDate` at `:427`) using the **server-supplied** `org_time_zone` with a fallback of `UTC` that is "deliberately **not** `America/Chicago`" (`:54-60`). Adjudication: the zone policy *is* implemented, via D-324's design — the server zone is America/Chicago, effectively the CDT the decision recorded — so #10's wording simply predates the mechanism. Residual: the date-only back-a-day shift (a date-only string parsed as UTC midnight then rendered in the org zone) remains unmitigated, i.e. still "armed", under a heading that reads ALL DECIDED.
- **Evidence**: `apps/learning-api/src/learning_api/routers/sessions.py:272-274`, `:456-458`; `apps/learning-web/src/screens/StageTransitionScreen.tsx:25-47`; `apps/learning-web/src/screens/StudentDashboardScreen.tsx:52-82`, `:424-427`; `e2e/fixtures/learning-flow.ts:411-441`; `docs/OPEN_DECISIONS.md:336-349`, `:342`.
- **Severity**: LOW, medium-adjacent (adjudicated LOW–MEDIUM: doc wording plus an armed edge case).
- **Likely explanation**: The decision was recorded before D-324 chose a server-supplied zone; the informal symbol name in the doc never matched code.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-60
- **Title**: TRACEABILITY's implementation line citations have drifted against current code
- **Related claims**: COST-03, COST-04, REQ-12, SEC-11, TEST-02, REQ-10 / **Related decisions**: —
- **Intended state**: Each traced row cites an implementation location a reader can open.
- **Observed state**: Five cited anchors are stale, all against unchanged behaviour. `gateway.py:58-110` no longer spans the four cost mechanisms (constructor defaults are at `:82-108`, circuit logic `:110-134`, token ceiling `:78`/`:236-243`, budget check `:244-263`, retry loop `:285+`) and `worst_case_cost_cents` is at **`:182-194`, not `:158`**. `attendance.py:71-80` for `check_attendance_gate` — the function now begins at line 96 and runs to 127. `authorization.py:39-43` for the parent link check — the block is now `:38-45`. TEST-02's row-5 implementation citation carries the same `attendance.py:71-80` staleness. Related secondary point on the same claim (COST-04): the public `worst_case_cost_cents` reads as "the pre-flight reservation bounding a call", but `generate_structured` recomputes the same expression inline at `:244` and the public method's only callers are tests — production reserves against per-surface constants that an unexecuted test asserts still bound the real worst case (`bedrock.py:1580-1586`). Also observed in the same class: the ledger's router symbol lines for REQ-10 (`respond_to_interrupt` at 1819, not 1120; `_pending_task_interrupt` at 797, not 414).
- **Evidence**: `docs/TRACEABILITY.md` cited rows; `packages/adapters/src/intellichoice_adapters/bedrock/gateway.py:78-134`, `:182-194`, `:236-263`; `apps/learning-api/src/learning_api/services/attendance.py:96-127`; `apps/learning-api/src/learning_api/authorization.py:38-45`; `apps/learning-api/src/learning_api/routers/sessions.py:797`, `:1819`; `packages/shared/src/intellichoice_shared/bedrock.py:1580-1586`.
- **Severity**: LOW
- **Likely explanation**: Line-number citations decay whenever code above them moves; nothing re-derives them.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-61
- **Title**: The measured spend undercount is 32.0% in the documents and 31% in the code, script and test that pin it
- **Related claims**: REQ-20, COST-05 / **Related decisions**: D-294
- **Intended state**: `TRACEABILITY.md:241` and the ledger state a measured 32.0% undercount from the omitted per-slot equation-design call.
- **Observed state**: The code says **31%** three times — `measure_spend_reconciliation.py:7`, `:22`, `:111` and the pinning test's docstring (`test_authored_pipeline.py:2471`, `:2475` "a median 1.26c against an accepted row's 2.67c, which is the 31%"). The script's own raw numbers (run summaries 1278c versus `question_validation_runs.cost_cents` 884c over the same window, 368 versus 378 candidates) compute to ≈**30.8%**. Both artifacts exist and match the D-294 story; the write-path fix is visible as `_row_cost()` (`ai_pipeline.py:1608+`, "What this attempt's row should say the slot has spent so far (D-294)… Distinct from `total_cost`, which is what the *caller* is told").
- **Evidence**: `scripts/measure_spend_reconciliation.py:1-33`, `:111`; `packages/curriculum/tests/test_authored_pipeline.py:2468-2540`; `packages/curriculum/src/intellichoice_curriculum/ai_pipeline.py:1600-1615`; `docs/TRACEABILITY.md:237-248`.
- **Severity**: LOW
- **Likely explanation**: One figure was rounded up when written into the documents and the other kept the measured value; neither was reconciled against the raw numbers.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-62
- **Title**: TRACEABILITY cites a test name that was renamed to assert the opposite routing
- **Related claims**: TEST-11 / **Related decisions**: D-226, D-249
- **Intended state**: `TRACEABILITY.md:313` cites `test_judge_flags_reject_and_borderline_score_sets_high_priority` among the authored route's rejection tests.
- **Observed state**: The substance holds — the authored route is traced, the shape route is deleted (no `test_ai_pipeline.py` anywhere; no `validation.py` in the curriculum package; `pipeline_cli.py:507` "One candidate function, since D-226 removed the shape route"), and six of seven named tests exist. But **that test name does not exist**: the file carries `test_judge_flags_reject_and_a_borderline_score_no_longer_sets_high_priority` (`:774`), a rename that inverts the second clause because D-249 removed the borderline→high-priority routing. An unresolvable citation inside the traceability register is the exact failure mode D-226 was written about.
- **Evidence**: `docs/TRACEABILITY.md:280-315`, `:313`; `packages/curriculum/tests/test_authored_pipeline.py:604`, `:632`, `:675`, `:725`, `:774`, `:872`, `:1306`; `pipeline_cli.py:507`.
- **Severity**: LOW (substance intact, single stale citation).
- **Likely explanation**: The test was renamed when its assertion was inverted; the register's citation was not updated.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no. Related citation-decay entry: DRIFT-60.

- **Drift ID**: DRIFT-63
- **Title**: TRACEABILITY's self-cited near-miss names the wrong commit
- **Related claims**: TEST-08 / **Related decisions**: —
- **Intended state**: The file reports that its "Open: none" line and a table still showing T-02 open were "both written in the same commit, `c44414f`".
- **Observed state**: The co-existence at `c44414f` is real — in that commit's file state `Open: none.` sits at L513 and the T-02 row reads `**Open.** Needs an explicit owner, not a fix.` at L518 — but **neither line was written by it**. In the `c44414f` diff the `Open: none.` line appears as an unchanged **context** line; `git log -S "Open: none" -- docs/TRACEABILITY.md` attributes its introduction to `7430810` (2026-07-30, tranche 2) and `git log -S` on the T-02 row text attributes it to `be6d22d` (2026-07-30, tranche 3). `c44414f` touched no T-02 table row at all. The lesson stands; the instrument-reliability citation does not.
- **Evidence**: `git show c44414f --stat` (4 files, 183 insertions / 10 deletions); `git show c44414f -- docs/TRACEABILITY.md` (context-line prefix); `git show c44414f:docs/TRACEABILITY.md` L72/L513/L518; `git log -S` provenance for both strings; claim text at `docs/TRACEABILITY.md:641-645`.
- **Severity**: LOW — but it is a citation inside the file's own reliability warning.
- **Likely explanation**: The commit where the contradiction was *noticed* was recorded as the commit where it was written.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-64
- **Title**: The "one row per finding" invariant is unheld in the reverse direction — six findings have Index rows and no detail section
- **Related claims**: TEST-17, TEST-15, TEST-16 / **Related decisions**: D-174, D-178
- **Intended state**: After D-174's backfill the invariant holds with zero exceptions.
- **Observed state**: The asserted direction holds — 94 `### AUD-` headings resolve to 93 unique ids (the one duplicate, `AUD-C-16`, is the known-benign two-section finding D-178 checked), Index rows give 100 unique ids, and `comm` of sections-minus-rows is **empty**: every section has a row. The unstated reverse direction does not hold: **7** row ids have no `### AUD-` detail section — `AUD-F-05` (folded into the combined heading `### AUD-F-04 / AUD-F-05`) plus `AUD-F-16, F-17, F-18, F-19, F-20, F-38` as rows only. The file itself flags the shape at `:105` ("The table above stops at AUD-F-20 /"). A section-derived reader misses those six exactly as a table-derived reader missed 27 before D-174.
- **Evidence**: `docs/AUDIT_FINDINGS.md:89-94`, `:103-123`, `:105`, `:131-150`, `:179-180`; `docs/ROADMAP.md:734-747`; scripted section/row id diff.
- **Severity**: LOW — all six are closed, so no count is affected today.
- **Likely explanation**: The backfill was written for the direction that had produced a wrong count; the inverse was never asserted.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-65
- **Title**: The error-vocabulary spec's own header still says "twelve rules, five different 409s" against ten
- **Related claims**: TEST-26, TEST-22 / **Related decisions**: D-375, D-383
- **Intended state**: learning-web's `errors.ts` carries 10 rules and chat-web 8 (18 total), with learning-web's 401 excluded for a stated reason.
- **Observed state**: The counts match exactly. `apps/learning-web/src/api/errors.ts:46-109` `RULES` has ten entries — six 409s, 401, 403, 404, 429 — with the removed `{status:400, detail:["attendance"]}` rule surviving only as a comment block at `:96-107` explaining why it could never fire, and `isSignedOut` exported at `:115-120` for the D-375 sign-out path. `apps/chat-web/src/api/errors.ts:50-96` has exactly eight. The drift is in the spec that owns the enumeration: `e2e/tests/learning/error-vocabulary.spec.ts:5-7` still describes the table as "twelve rules, five of them different 409s".
- **Evidence**: `apps/learning-web/src/api/errors.ts:46-109`, `:115-120`; `apps/chat-web/src/api/errors.ts:50-96`; `e2e/tests/learning/error-vocabulary.spec.ts:5-7`.
- **Severity**: LOW
- **Likely explanation**: Rules were consolidated after the spec was written and its header count was not re-derived.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-66
- **Title**: SPEC §5.26.3's internal NL2SQL pipeline is an unowned subsystem no plan or decision disposes of in either direction
- **Related claims**: REQ-06, REQ-05 / **Related decisions**: —
- **Intended state**: SPEC §5.26.3 prescribes an internal NL2SQL pipeline (plan → allowlist → parser → read-only role → EXPLAIN → timeout → row limit) for dev/eval/analytics only.
- **Observed state**: **No ROADMAP or DECISIONS entry disposes of the internal variant at all.** A corpus-wide `NL2SQL` grep returns 10 non-ledger hits and every one addresses only the *runtime* prohibition or the untestability of the SQL-parser eval item — none says the internal dev/eval/analytics variant is planned, dropped or partially present. `SPEC.md:2641-2643` carries no amendment or deferral marker. The runtime prohibition itself is separately confirmed: no `QueryIntent` model exists, every RAG query is a parameterized `select()`, and the only raw `text()` calls in runtime paths are advisory locks, `pg_notify` and a parameterized purge.
- **Evidence**: `docs/SPEC.md:2641-2643`; `docs/ROADMAP.md:489`; `docs/DECISIONS.md:2104`, `:3031`, `:6806-6809`; `docs/TRACEABILITY.md:164-165`, `:567-574`; `CLAUDE.md:92`; `packages/evals/src/intellichoice_evals/registry.py:108`.
- **Severity**: LOW (no user-facing claim), but it is an unowned spec requirement.
- **Likely explanation**: All attention went to the runtime prohibition, which is the safety-bearing half; the internal tooling variant was never scoped.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: yes — whether to build, scope or formally drop it.

- **Drift ID**: DRIFT-67
- **Title**: "Interrupts after every incorrect answer" is broader than the implemented routing predicate
- **Related claims**: REQ-11, REQ-10 / **Related decisions**: —
- **Intended state**: The learning graph interrupts after every incorrect answer for hint/solution/video.
- **Observed state**: Routing to `intervention_choice` requires three conditions — `phase == "study"` AND `last_is_correct is False` AND `last_study_attempt_id is not None` (`graph/build.py:66-70`) — so an incorrect *final pre-exam* answer, which flips phase to `study` while still incorrect, deliberately does not interrupt. A hint below the ladder's final level self-loops into a fresh `intervention_choice` interrupt (`:74-82`). Both interrupts resume through the same endpoint via an `interrupt_type`-discriminated union, and a resume is rejected unless `pending.value.get("type") == body.interrupt_type` (`sessions.py:1855`). The exclusion is documented in-code as deliberate.
- **Evidence**: `apps/learning-api/src/learning_api/graph/build.py:66-82`; `apps/learning-api/src/learning_api/graph/nodes.py:331`, `:1164`; `apps/learning-api/src/learning_api/routers/sessions.py:354-373`, `:1855`.
- **Severity**: LOW (documentation wording).
- **Likely explanation**: The claim summarised the feature; the predicate was narrowed for a real edge case and the summary was not.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-68
- **Title**: The synthesis-time chunk re-fetch applies no status or effective-window predicate
- **Related claims**: REQ-14, REQ-07, REQ-08, WORK-18 / **Related decisions**: AUD-C-11
- **Intended state**: No RAG answer without an approved, effective, citation-supported source.
- **Observed state**: Fail-closed behaviour is present at the answer boundary — `qa.py:311-313` `if not verified or raw.confidence < confidence_threshold: return _no_answer(NO_SOURCE_MESSAGE, [])` with `[]` citations deliberately per AUD-C-11, `CONFLICT_MESSAGE` on `raw.sources_conflict` at `:308-309`, and a zero-chunk short-circuit at `:243`. Approved/effective enforcement is pre-retrieval (`repositories/rag.py:47-84`, `status == "approved"` unconditional plus the effective window at `:79-82`). But `synthesize_answer` re-fetches chunk bodies via `RagRepository.get_chunks_by_ids` (`repositories/rag.py:245-253`), which applies **no** status or effective predicates — so the guarantee rests entirely on the earlier filtered query rather than being re-asserted at synthesis. Behavioural impact requires an approval or effective-window change inside one turn; that window is not asserted anywhere.
- **Evidence**: `apps/chat-api/src/chat_api/services/qa.py:243`, `:308-313`; `packages/db/src/intellichoice_db/repositories/rag.py:47-84`, `:245-253`; `apps/chat-api/src/chat_api/graph/nodes.py:526-528`.
- **Severity**: LOW
- **Likely explanation**: The re-fetch exists because `QAState` checkpoints ids not bodies (a deliberate PII/size decision) and was written as a body lookup rather than as a second access-control gate.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-69
- **Title**: CLAUDE.md states the solution-image deletion rule as active behaviour for a feature with no code
- **Related claims**: REQ-21, REQ-22, REQ-24, SEC-15 / **Related decisions**: D-078, D-022
- **Intended state**: CLAUDE.md rule 8 states that solution images are deleted immediately after analysis, success or failure, and never enter backups, traces or logs.
- **Observed state**: There is no subject for the rule. Zero source hits for `BlobStore`/`blob_store`, `MalwareScanner`/`malware`/`clamav`, `solution_image`, `image_url`, `base64`; no `multipart`/`UploadFile`/`File(` upload endpoint anywhere in `apps/` or `packages/`; the learning-api router package contains no upload router; the intervention choice enum is closed at `Literal["hint", "solution", "video", "continue"]` (`sessions.py:368`). `analyze_image` occurs once, in a docstring recording its absence (`bedrock.py:5`), and `registry.py:74` reads "No image-upload feature exists to emit this event." TRACEABILITY already records the disposition; CLAUDE.md states the rule in the present tense.
- **Evidence**: `CLAUDE.md:104-105`; `packages/shared/src/intellichoice_shared/bedrock.py:5`; `packages/evals/src/intellichoice_evals/registry.py:74`; `apps/learning-api/src/learning_api/routers/sessions.py:368`, `:390`; `docs/ROADMAP.md:465`; absence sweep as described.
- **Severity**: LOW (documentation only).
- **Likely explanation**: The rule was written into the standing instructions as a non-negotiable before S29 was deferred, and non-negotiables are not annotated per-feature.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-70
- **Title**: The consent-verification half of REQ-27 is enforced; the notice half is unbuilt and the ten claims are minted only by the dev fake
- **Related claims**: REQ-27, REQ-25, REQ-26 / **Related decisions**: D-152, T-02
- **Intended state**: The learning app verifies `parental_consent_verified=true` before showing an age-appropriate student notice, on a token carrying ten named claims.
- **Observed state**: `TokenClaims` carries exactly the ten named claims, no extras and no omissions (`auth.py:26-36`), and `parental_consent_verified` is read by `account_refusal_reason()` (`:106`) from four app-level sites (`learning-api/dependencies.py:122`, `learning-api/routers/stream.py:162`, `chat-api/dependencies.py:46`, `chat-api/routers/stream.py:73`). The gate fails closed: `AGE_BANDS_NOT_REQUIRING_PARENTAL_CONSENT` is a deliberately **empty** frozenset, so today every student needs verified consent. The two known gaps: no student-facing notice exists in either web app (grep for `parental|consent|under 13|guardian|age.appropriate` across both `src` trees returns only two unrelated comments), and the claim set is minted only by `packages/adapters/.../fake_auth.py` — production's real token is `{id, iat, exp}` only (`S42_DISCOVERY.md:260`), which is expected under D-152.
- **Evidence**: `packages/shared/src/intellichoice_shared/auth.py:26-36`, `:46-58`, `:99-108`; `apps/learning-api/src/learning_api/dependencies.py:122`; `apps/chat-api/src/chat_api/dependencies.py:46`; `docs/S42_DISCOVERY.md:260`.
- **Severity**: LOW — all halves are already tracked (T-02 for the notice, D-152 for the issuer).
- **Likely explanation**: The consuming half was buildable now and the notice half was scoped to S45 behind the §6.1 disclosure list.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no. See DRIFT-08 and DRIFT-11 for the notice's blocking decisions.

- **Drift ID**: DRIFT-71
- **Title**: The location-consent modal offers ZIP and city but not address, and `QAState`'s docstring still says S15 will add location fields
- **Related claims**: REQ-28, SEC-12, REQ-52 / **Related decisions**: D-045
- **Intended state**: SPEC offers a ZIP code, city **or address** alternative to geolocation; `QAState` is described as gaining `location_consent`/`ephemeral_location` at S15.
- **Observed state**: Two LOW drifts. (a) The API accepts `zip_code`/`city`/`address` (`chat-api/routers/sessions.py:863-869`) and `LOCATION_MISSING_MESSAGE` mentions all three, but the modal exposes only ZIP and city (`LocationConsentModal.tsx`). (b) `chat-api/graph/state.py:4-6` still says the location fields "are still not present — S15 adds them"; S15 shipped and D-045's resume-value design is what shipped, so the docstring describes an abandoned plan. The rest of the requirement holds: the notice copy is verbatim against `SPEC.md:104-106` and is delivered through the `interrupt()` payload before any collection (`nodes.py:218-221`, `:1134`); geolocation is called only on explicit button press; coordinates are function-local to `find_nearest_branches` ("Precise coordinates never leave this function"); MCP audit rows persist no arguments (`repositories/mcp.py:16-26`).
- **Evidence**: as cited; `apps/chat-web/src/screens/LocationConsentModal.tsx:31-66`, `:76`; `apps/chat-api/src/chat_api/services/branch_locator.py:64-115`.
- **Severity**: LOW ×2. The "not retained by default" clause is only satisfied via the purge that DRIFT-09 shows is incomplete.
- **Likely explanation**: The modal shipped the two inputs that geocode reliably; the docstring predates D-045.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-72
- **Title**: A seventh interim outcome label is persisted beside the six terminal ones, in an unconstrained column
- **Related claims**: REQ-31, REQ-33 / **Related decisions**: SPEC §5.11.7
- **Intended state**: Four escalating ladder steps and exactly six persisted terminal outcome labels.
- **Observed state**: The ladder is as claimed — `MAX_ATTEMPTS_PER_SKILL = 4` with `ladder_step()` branching `>= 4 → exhausted`, `== 3 → prerequisite`, `== 2 → retry_same` with the more-explicit-support message, else `retry_same`. The code persists a documented seventh value beside the six: `INCORRECT = "incorrect"  # interim: wrong answer, skill line still open`. The persisted column is `outcome_label: Mapped[str | None]` — a nullable unconstrained `String` documented at `models/mastery.py:70` as "one of the six §5.11.7", not a DB enum — so the taxonomy is Python-enforced only.
- **Evidence**: `apps/learning-api/src/learning_api/services/study_outcomes.py` (`MAX_ATTEMPTS_PER_SKILL`, `ladder_step()`, label constants); `apps/learning-api/src/learning_api/services/flow.py:777-792`; `packages/db/src/intellichoice_db/models/mastery.py:70`, `:106`.
- **Severity**: LOW (additive, documented in code).
- **Likely explanation**: An interim state was needed to represent an open skill line; the claim's "exactly six" describes the terminal set.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-73
- **Title**: "Difficulty label to be superseded by observed evidence" reads as a live mechanism; the judge label is final today
- **Related claims**: REQ-42, REQ-41 / **Related decisions**: SPEC §5.8.4, D-249
- **Intended state**: The LLM difficulty label is a bootstrap label, to be superseded by observed evidence including success after hints.
- **Observed state**: No recalibration from observed response data exists. A repo-wide grep for `recalibrat` returns only documentation (`SPEC.md:914` "As production data accumulates, recalibrate using:", `TRACEABILITY.md:329`, `PROGRESS.md:11015`) — zero code hits — and greps for `success_rate`, `p_value`, "observed difficulty", `item_difficulty` across non-test source return nothing. `difficulty_label` is read-only outside the authoring pipeline. The only re-labelling is generation-time and judge-driven (the retier path). Adjudication: this is correct — SPEC's own trigger ("as production data accumulates") has not occurred and `TRACEABILITY.md:329-332` dispositions it ("Not a gap; a requirement whose trigger condition has not occurred"). The drift is wording tension only.
- **Evidence**: greps as described; `docs/TRACEABILITY.md:329-332`; `docs/SPEC.md:914`; `apps/learning-api/src/learning_api/services/study_plan.py:94-156`, `:212`; `packages/curriculum/tests/test_authored_pipeline.py:2937`, `:3084`.
- **Severity**: LOW
- **Likely explanation**: The requirement is conditional on data that does not exist pre-launch; the phrasing does not signal the condition.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-74
- **Title**: The "no message restates its own reason code" sweep covers five of ten reasons
- **Related claims**: REQ-44, REQ-43, REQ-45, REQ-48 / **Related decisions**: —
- **Intended state**: The check is applied over the whole user-facing message set rather than the one message that was wrong.
- **Observed state**: The test does iterate a set — `apps/chat-api/tests/test_turn_reasons.py:46-55` loops `for reason, message in REASON_MESSAGES.items()` and asserts `reason.value.replace("_", " ") not in message.lower()`. But `REASON_MESSAGES` has five entries (`outcomes.py:134-140`: no_approved_source, sources_conflict, access_required, out_of_scope, system_error) against ten enum values, and the other user-facing strings — `UNAVAILABLE_INTENT_MESSAGES`, the `LOCATION_*` copy, `RATE_LIMITED_MESSAGE`, calendar copy — are node-local and outside the sweep. Its docstring's promise that "the next message added is covered by construction" is true only for messages added to `REASON_MESSAGES`.
- **Evidence**: `apps/chat-api/tests/test_turn_reasons.py:46-55`; `apps/chat-api/src/chat_api/services/outcomes.py:134-140`; message constants in `apps/chat-api/src/chat_api/graph/nodes.py`.
- **Severity**: LOW
- **Likely explanation**: The sweep was written against the default message map, which is where the original defect lived.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-75
- **Title**: The scheduled-jobs module header says four jobs are defined and three enabled; five are defined and four enabled
- **Related claims**: ARCH-04, ARCH-05, ARCH-06 / **Related decisions**: AUD-F-06
- **Intended state**: The module header describes the job set it defines.
- **Observed state**: `terraform/modules/scheduled-jobs/main.tf:13-20` says "**Four jobs are defined, three are enabled**" and lists chat-purge/memory-consolidate/retention-purge/youtube-sync — it predates `session-consolidate` and now understates the count the same file's `locals.jobs` block sets: **five defined, four enabled** (`session-consolidate` `cron(0 18 * * ? *)` at `:52`/`:60`; `chat-purge` `:65`/`:72`; `retention-purge` `:80`/`:87`; `memory-consolidate` `:91`/`:105`; `youtube-sync` `:108` with `enabled = var.youtube_sync_enabled`, default false).
- **Evidence**: `terraform/modules/scheduled-jobs/main.tf:13-20`, `:52-125`, `:196-198`; `terraform/modules/scheduled-jobs/variables.tf:63-77`.
- **Severity**: LOW (comment only, no functional effect).
- **Likely explanation**: `session-consolidate` was added later "first and alone" for a safety-ordering reason and the header count was not incremented.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-76
- **Title**: ARCHITECTURE.md uses "retention" for two different jobs in the same nine lines
- **Related claims**: ARCH-05, ARCH-04, WORK-19 / **Related decisions**: D-114 (AUD-L-04), D-333
- **Intended state**: L28 lists a scheduled `retention-purge`; L35-36 says "that retention job stays unscheduled".
- **Observed state**: Both statements are true because they name different jobs, and config resolves the ambiguity. `retention-purge` (= `retention_purge_cli`, the D-114 row-purge job) **is** scheduled and enabled at `cron(50 18 * * ? *)`; `checkpoint_retention_cli` has **no** schedule of any kind and appears nowhere in terraform (only `Makefile:106` and its own module). The four scheduled commands are `session_consolidation_cli`, `tutor_chat_purge_cli`, `retention_purge_cli`, `intellichoice_memory.consolidate_cli`. The drift is documentation clarity: one word for two jobs in adjacent lines.
- **Evidence**: `terraform/modules/scheduled-jobs/main.tf:41-51`, `:53`, `:66`, `:80-87`, `:92`; `grep checkpoint_retention_cli terraform/` → no hits; `docs/ARCHITECTURE.md:28-36`.
- **Severity**: LOW (documentation clarity, not config drift).
- **Likely explanation**: The two jobs were named independently and the summary lines were written for a reader who already knew both.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no. See DRIFT-45 for the unscheduled job itself.

- **Drift ID**: DRIFT-77
- **Title**: ARCHITECTURE's storage-split table under-describes Postgres by twelve shipped tables
- **Related claims**: ARCH-19, ARCH-21, ARCH-22 / **Related decisions**: —
- **Intended state**: The storage-split table is the canonical as-built layout — Postgres for everything but PII, MySQL read-only for PII.
- **Observed state**: Every Postgres-side row in the table is present as real models and migrations (curriculum, assessments, checkpoints, `mcp_tool_calls`, RAG + pgvector, youtube, org directory, `cost_reservations`, `rate_limit_events`, chat/memory/report, `learning_sessions`, `chat_turn_cancellations`, `chat_escalation_sends`). The table is an **under-count**: twelve shipped tables appear in no row of it — `study_sessions`, `study_items`, `study_attempts`, `mastery`, `learning_gain`, `hint_events`, `stage_transitions`, `interrupt_approvals`, `question_templates`, `question_variants`, `question_validation_runs`, `evaluation_results` — against 37 `__tablename__` declarations in total. The MySQL side is the four-table locally-provisioned fixture read via raw `SELECT`.
- **Evidence**: 37 `__tablename__` declarations across `packages/db/src/intellichoice_db/models/`; `packages/db/src/intellichoice_db/models/rag.py:3`, `:63`; `packages/adapters/src/intellichoice_adapters/mysql_profile_adapter.py:42-46`; 38 migrations under `packages/db/alembic/versions/`.
- **Severity**: LOW
- **Likely explanation**: The table was written when the study/mastery/question-bank families did not exist and was not regenerated as they landed.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-78
- **Title**: The ledger locates LangSmith masking in task definitions; it is enforced in application code
- **Related claims**: ARCH-30, COST-27, SEC-23 / **Related decisions**: D-242
- **Intended state**: The observability sink table locates PII masking at the task-definition layer alongside the four Bedrock metric filters and the per-task `otel-collector` sidecar.
- **Observed state**: The other three elements are in terraform — four Bedrock filters per service via `for_each = var.log_group_names` (`BedrockCostCents`, `BedrockCallDurationMs`, `BedrockCallFailed`, `BedrockCircuitOpen`) and a non-essential `otel-collector` container exporting OTLP→`awsxray`. Masking is **not** in terraform: `configure_langsmith()` assigns `LANGSMITH_HIDE_INPUTS`/`LANGSMITH_HIDE_OUTPUTS = "true"` unconditionally — assignment, not `setdefault`, unlike `LANGSMITH_PROJECT` — so an env var cannot opt out, with a test asserting it is not optional. A reader inspecting a task definition alone would not see the control.
- **Evidence**: `packages/observability/src/intellichoice_observability/langsmith_config.py:26-42`; `packages/observability/tests/test_langsmith_config.py:8-41`; `terraform/modules/observability/dashboard.tf:49-143`; `terraform/modules/ecs-service/main.tf:108-160`.
- **Severity**: LOW (documentation precision only).
- **Likely explanation**: The four sinks were described together at the infrastructure layer, where three of them live.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-79
- **Title**: "Health endpoints emit no telemetry at all" is true of traces; `/readyz` still emits one access-log line per poll
- **Related claims**: ARCH-32, COST-13 / **Related decisions**: AUD-F-30
- **Intended state**: Health endpoints emit no telemetry at all, so the scanned trace corpus is real traffic rather than ~97% ALB health checks.
- **Observed state**: Two-layer trace suppression is present exactly as described — `instrument_fastapi_app` passes `excluded_urls=HEALTH_ENDPOINT_URLS` = `"healthz,readyz"` with `/metrics` deliberately not excluded, and both apps wrap the whole `/readyz` body in `suppress_instrumentation()` ("AUD-F-30: suppressed at the handler, not per query"), pinned by six tests including `test_readyz_emits_no_spans_at_all_including_its_database_pings`. The scope word is the drift: the access-log middleware (`install_request_logging_middleware`) has **no path exclusion**, so `/readyz` still produces one JSON log line per poll. "No telemetry at all" is true of the trace leg, not of logs.
- **Evidence**: `packages/observability/src/intellichoice_observability/tracing.py:169-191`; `apps/chat-api/src/chat_api/main.py:342-348`; `apps/learning-api/src/learning_api/main.py:432-435`; `packages/observability/tests/test_health_endpoint_tracing.py:51`, `:87`, `:261`; `packages/observability/src/intellichoice_observability/request_logging.py`.
- **Severity**: LOW
- **Likely explanation**: The finding and the fix were both about the trace denominator; the sentence generalised to "telemetry".
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-80
- **Title**: `make image-check` is operator-invoked only, wired into neither CI nor the deploy workflow
- **Related claims**: ARCH-34, ARCH-33, WORK-07 / **Related decisions**: D-137, D-244, D-417 A3, D-418
- **Intended state**: `scripts/check_deployed_image_consistency.py` / `make image-check` exists, judges each service against its family's latest revision and reports the tfvars pin without failing on it.
- **Observed state**: All three properties confirmed — `image-check` is in `.PHONY` and defined at `Makefile:292-294`, the target comment records the D-417/A3 rename from `tfvars-floor-check` and the measurement ("with the pin two deploys stale, `terraform plan` moved the image **forward** to what was running"), and `adopt_deployed_image` defaults `true` (`variables.tf:213`) consumed by the `for_each` guard at `main.tf:12`. The unstated property is that nothing invokes it: it appears in neither `.github/workflows/ci.yml` nor `deploy-staging.yml`, so it is a manual pre-apply step with no automated enforcement point. `ARCHITECTURE.md:429-458` also does not mention it at all.
- **Evidence**: `Makefile:1`, `:280-294`; `scripts/check_deployed_image_consistency.py`; `terraform/environments/staging/variables.tf:201-214`; `terraform/environments/staging/main.tf:7-42`; negative grep over both workflows.
- **Severity**: LOW
- **Likely explanation**: The script needs live AWS credentials (`aws configure export-credentials`), which makes it awkward in CI.
- **Resolvable by Phase 3B?**: no for the wiring; the script's judgement against live state is 3B.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-81
- **Title**: A staging variables comment asserts there is no tfvars file in the environment, and the file exists
- **Related claims**: ARCH-28, ARCH-29, COST-23, ARCH-34 / **Related decisions**: —
- **Intended state**: The comment describes the environment's configuration inputs accurately.
- **Observed state**: `terraform/environments/staging/variables.tf:187` asserts "there is no tfvars file in this environment" while `terraform/environments/staging/terraform.tfvars` **exists** — gitignored, confirmed by `git check-ignore` against `.gitignore:55 *.tfvars` — and `main.tf:35` refers to "the tfvars pin" as if it exists. Its content was deliberately not read in Phase 3A, and it is the single unresolved dependency for the NAT-count, `youtube_sync_enabled`, `langsmith_tracing_enabled` and `informational_notification_email` conclusions elsewhere in this register.
- **Evidence**: `terraform/environments/staging/variables.tf:187`; `terraform/environments/staging/main.tf:35`; `.gitignore:55`; `git check-ignore` result.
- **Severity**: LOW
- **Likely explanation**: The comment was true when written; a tfvars file was added later and, being gitignored, is invisible to anyone reading the tracked tree.
- **Resolvable by Phase 3B?**: no for the comment; the variable-override questions it creates are 3B (DRIFT-29, DRIFT-89).
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-82
- **Title**: The trace-boundary redactor rebuilds span attributes and passes span events through untouched
- **Related claims**: SEC-07, REQ-02, SEC-05, SEC-06 / **Related decisions**: D-104
- **Intended state**: A `RedactingSpanExporter` redacts at the span-export boundary, pinned by a test that drives real instrumentation with a negative arm and a vacuity guard.
- **Observed state**: All four elements are confirmed at the cited lines, and the exporter wraps **both** branches of `build_tracer_provider` with the reason stated ("Wrapping only the production branch would make the test path structurally unable to catch a regression"); three redaction patterns cover `?token=`/`access_token`/`api_key`, a bare `eyJ...` JWT and `Bearer <x>`. The scope drift: redaction covers span **attributes** only — `_redacted` rebuilds the span with cleaned attributes but passes `events=span.events` through untouched — so a credential inside a span event would not be redacted, and "redacts at the span-export boundary" reads broader than the implementation.
- **Evidence**: `packages/observability/src/intellichoice_observability/tracing.py:55-61`, `:72-89`, `:119-138`; `packages/observability/tests/test_tracing.py:62-97`, `:91` (vacuity guard), `:100-111` (negative arm).
- **Severity**: LOW
- **Likely explanation**: The measured leak was a query string in an attribute; events were not part of the failure mode being fixed.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-83
- **Title**: LangSmith retention has no in-repo expression, so nothing in the repository would detect its absence
- **Related claims**: SEC-23, COST-27, ARCH-30 / **Related decisions**: D-242, SPEC §5.32.1
- **Intended state**: LangSmith needs a PII-masking policy, retention configuration, and separate per-environment projects, expressed as configuration rather than as a required-account row.
- **Observed state**: Two of three are configured. Masking is forced in code and asserted by a test (DRIFT-78). Per-environment project is real and env-driven: `LANGSMITH_PROJECT = var.name_prefix` in terraform (i.e. `intellichoice-staging`) overriding the code's `setdefault("LANGSMITH_PROJECT", "intellichoice")`. **Retention is not expressed anywhere** — no terraform, env or code setting governs LangSmith run retention; it is a LangSmith-side account setting. Secrets themselves are ARN-only in terraform and `*.tfvars`/`*.tfplan` are gitignored with the reason written out.
- **Evidence**: `packages/observability/src/intellichoice_observability/langsmith_config.py:26-42`; `terraform/environments/staging/main.tf:149-178`; `.gitignore` Terraform block; negative grep for a retention setting.
- **Severity**: LOW
- **Likely explanation**: Retention is only settable in the SaaS console, so it has no natural in-repo home.
- **Resolvable by Phase 3B?**: **yes/external** — the account setting is observable outside the repository.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-84
- **Title**: The two exposed staging token secrets have no rotation mechanism configured anywhere
- **Related claims**: SEC-26, SEC-35, SEC-25 / **Related decisions**: D-097, D-310
- **Intended state**: Evidence of whether the two staging `/dev/token` shared secrets were rotated after the 2026-08-13 process-table exposure; the "bounded exposure" premise rests on that.
- **Observed state**: **No evidence of rotation and no rotation mechanism.** `git log -S"staging_token_shared_secret" -- terraform` returns exactly one commit ever — `168de30`, the original creation. The two `random_password` resources carry no `keepers` and no rotation trigger, and no `aws_secretsmanager_secret_rotation` resource exists anywhere in `terraform/`. The block comment at `main.tf:355-360` plans **deletion at S44, not rotation** — and S44 is frozen. Rotation in place would not require a repo change, so absence of a commit is weak negative evidence; the absence of any in-repo control is not.
- **Evidence**: `git log -S"staging_token_shared_secret" -- terraform`; `terraform/environments/staging/main.tf:355-389`; negative grep for `aws_secretsmanager_secret_rotation` across `terraform/`.
- **Severity**: LOW
- **Likely explanation**: The secrets are staging-only with a planned S44 deletion, so rotation was treated as unnecessary rather than automated.
- **Resolvable by Phase 3B?**: **yes** — live secret version history would show whether a rotation occurred.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-85
- **Title**: The I7 unknown-role metric is named as an invariant's evidence with no plan text anywhere in the S43 scope
- **Related claims**: SEC-34, INT-12 / **Related decisions**: D-153 §5
- **Intended state**: The Tutor/Manager allowlist constraint is designed into S43/S44 work, with the I7 unknown-role metric as part of it.
- **Observed state**: The constraint is present and consistently stated in four documents. `ROADMAP.md:1465-1491` carries a `⛔ Security constraint (D-153 §5, rationale updated in §7)` sub-block reproducing all three grounds verbatim and closing with "Map Student/Parent from production; gate `Tutor`/`Manager` behind an allowlist the new stack controls", and the S43 header lists "fail-closed role mapping" and the I12 deploy-time schema smoke probe. But **no allowlist schema, storage or admin path is specified**, and the I7 unknown-role metric is named only as an id — no I7 metric plan text exists in the S43 region. An invariant with a named metric that nothing specifies.
- **Evidence**: `docs/ROADMAP.md:1465-1491` (constraint at `:1482-1489`); `docs/S42_SECURITY_REPORT.md:167-170`; `docs/INTEGRATION_PLAN.md:521-522`, `:572-573`; `docs/S42_OPEN_QUESTIONS.md:33-37`; `docs/S42_DISCOVERY.md:238-241`.
- **Severity**: LOW (severity from the inspector; the adjudication recorded no override).
- **Likely explanation**: The constraint was written to bind S43's implementation; the metric was named as a downstream deliverable of a session that has not run and is frozen.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-86
- **Title**: The cost-anomaly runbook's "scale desired_count to 0" lever is not literally effective on a live service
- **Related claims**: COST-16 / **Related decisions**: —
- **Intended state**: The cost-anomaly playbook lists lowering the Bedrock session budget or scaling `desired_count` to 0 as response levers.
- **Observed state**: The controls it names all exist — `aws_budgets_budget.monthly` with ACTUAL > 80% and FORECASTED > 100% notifications to `var.notification_email` (`monthly_budget_usd` default 20), and `bedrock_session_budget_cents = 50.0`, `bedrock_circuit_failure_threshold = 5`, `bedrock_circuit_cooldown_s = 30.0` declared in both app Settings and six package settings modules. But `desired_count` is inside `ignore_changes = [task_definition, desired_count]` (`modules/ecs-service/main.tf:370`) and autoscaling owns capacity once the service exists, so the operative knob is `autoscaling_min_capacity` — the terraform comment says so directly ("it is `autoscaling_min_capacity` that actually moves a live service off 1 - the desired_count below only matters to a from-scratch apply"). A runbook-accuracy defect against INCIDENT_RESPONSE and the cost playbook.
- **Evidence**: `terraform/modules/observability/main.tf:1-23`; `terraform/modules/observability/variables.tf:5-18`; `terraform/environments/staging/main.tf:443-447`; `terraform/modules/ecs-service/main.tf:370`; `apps/learning-api/src/learning_api/config.py:119-121`; `apps/chat-api/src/chat_api/config.py:80-82`.
- **Severity**: LOW
- **Likely explanation**: The lever was written when `desired_count` was the live knob, before `ignore_changes` and autoscaling took ownership.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-87
- **Title**: A fifth scheduled-job entrypoint reports only via `print()` and is itself unscheduled
- **Related claims**: COST-18, WORK-19, WORK-21 / **Related decisions**: D-377, D-333
- **Intended state**: The P1-6 finding (nightly jobs report only in unstructured `print()`) is closed.
- **Observed state**: Closed and itemized in code for the four enabled jobs — each entrypoint calls `report_job_complete(...)` immediately after its `print()`, emitting a structured record whose message becomes the JSON `"event"` field with counts as `extra`, keyed by a `job` dimension that is deliberately the verbatim Terraform job key. The `print()` calls are retained on purpose for humans running jobs by hand. The residual: `checkpoint_retention_cli` does **not** call `report_job_complete` and reports only via `print()` — and that job is also unscheduled (DRIFT-45). Note the reporting helper swallows all exceptions by design, so a silent reporting failure would leave only the `print()`.
- **Evidence**: `apps/learning-api/src/learning_api/services/session_consolidation_cli.py:174`; `tutor_chat_purge_cli.py:53-55`; `retention_purge_cli.py:104-106`; `packages/memory/src/intellichoice_memory/consolidate_cli.py:161-172`; `packages/observability/src/intellichoice_observability/scheduled_jobs.py:39-43`, `:58-64`; `logging_config.py:136`.
- **Severity**: LOW
- **Likely explanation**: The instrumentation was added to the jobs EventBridge actually runs; the unscheduled one was out of the finding's scope.
- **Resolvable by Phase 3B?**: **yes** for the separate question of whether structured lines actually reach CloudWatch (a Logs Insights query against the ops-task log group).
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-88
- **Title**: `ATTENDANCE_CHECKS{result="unknown"}` means "adapter threw", while a genuine UNKNOWN attendance block counts as "blocked"
- **Related claims**: COST-20, REQ-12, REQ-13, INT-23 / **Related decisions**: D-377, D-152 §2
- **Intended state**: P1-8 is closed — the counter is incremented before the except-return and the `"unknown"` label is actually emitted.
- **Observed state**: The fix is present and the original defect is preserved as an in-code narrative: the increment now sits above the `return` inside the except block, it is the `"unknown"` label, and a `logger.warning("attendance_check_failed", ...)` was added on the same path (`graph/nodes.py:379-395`). All three declared labels are now emitted somewhere. The label semantics are the drift: `"unknown"` is emitted **only** on the adapter-exception path, while a legitimate `AttendanceStatus.UNKNOWN` gate result increments `result="blocked"` (`:397`). So the metric cannot separate the routine D-152 §2 production path (`signups.attended = null`) from a recorded absence; only adapter failure is separable. That is a narrower fix than the label name suggests.
- **Evidence**: `apps/learning-api/src/learning_api/graph/nodes.py:379-395`, `:397`; `packages/observability/src/intellichoice_observability/metrics.py:26-30` (`labelnames=("result",)  # "present" | "blocked" | "unknown"`); exhaustive `ATTENDANCE_CHECKS` grep (three non-test sites).
- **Severity**: LOW
- **Likely explanation**: The label was declared for the failure mode the audit found and reads as the domain status.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no. Related: no alarm reads this metric (DRIFT-21).

- **Drift ID**: DRIFT-89
- **Title**: The alarm-severity split is real at the topic layer and still single-address at the inbox layer by default
- **Related claims**: COST-23, COST-24, COST-26 / **Related decisions**: D-377, D-401, D-419
- **Intended state**: The "all 26 alarms delivered to a single email address" finding is superseded by the two-topic split.
- **Observed state**: Superseded in configuration: two SNS topics exist (`${prefix}-alerts`, `${prefix}-alerts-info`), each with its own email subscription, and alarm→topic routing is complete (15 alarm resources → ~30 instances at staging cardinality, every one carrying `alarm_actions`, none carrying both topics), enforced by a terraform-parsing test. But delivery is single-address by default: the info subscription endpoint is `coalesce(var.informational_notification_email, var.notification_email)` and `informational_notification_email` has `default = null` with no setter in the staging module call. The module's own comment concedes it ("Both default to the same address, so nothing about delivery changes until a second endpoint is configured"). The audit's "26" is a pre-D-377 count that does not match today's config.
- **Evidence**: `terraform/modules/observability/main.tf:45-73`; `terraform/modules/observability/variables.tf:20-27`; `terraform/environments/staging/main.tf:750-836`; `packages/observability/tests/test_alarm_severity_routing.py:1-106`.
- **Severity**: LOW
- **Likely explanation**: The split was landed at the routing layer first; configuring a second mailbox is a separate operator action.
- **Resolvable by Phase 3B?**: **yes** — `terraform.tfvars` (unread) could set the second endpoint, and live subscription state including COST-26's PendingConfirmation is observable.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-90
- **Title**: The enrollment-FAQ content-doc citation omits the `documents/` path segment
- **Related claims**: INT-29 / **Related decisions**: —
- **Intended state**: The enrollment FAQ is still `status: draft` with its DRAFT banner intact, cited by path.
- **Observed state**: The substance is confirmed: `knowledge-content/manifests/public.yaml:68-79` carries `document_id: public-enrollment-faq`, `version: 1`, `status: draft` at line 78, with the preceding manifest entry showing `status: approved` at `:65` so the value is a live discriminator; the DRAFT banner is intact at `content.md:3-5` ("DRAFT — NOT APPROVED FOR PRODUCTION"), and the four draft facts are unchanged. The manifest's `source_path` is `public/enrollment-faq/content.md` while the file lives at `knowledge-content/documents/public/enrollment-faq/content.md`, and the claim cited `knowledge-content/public/...`, which does not exist — the loader presumably roots at `documents/`.
- **Evidence**: `knowledge-content/manifests/public.yaml:65`, `:68-79`; `knowledge-content/documents/public/enrollment-faq/content.md:1-15`.
- **Severity**: LOW (citation precision only).
- **Likely explanation**: The manifest stores a loader-relative path and the citation reproduced it as a repo-relative one.
- **Resolvable by Phase 3B?**: no for the citation; whether the deployed knowledge store still holds the draft is 3B.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-91
- **Title**: One app module imports `current_week_key` from the MySQL adapter module rather than from shared org_time
- **Related claims**: INT-35, INT-15, INT-32 / **Related decisions**: D-152 §1, D-082, D-083
- **Intended state**: The dev fake's structural mismatches stay behind the `ProfileAdapter` seam, and no app-level decision depends on the fake's schema.
- **Observed state**: The seam's substance is intact and was adjudicated as confirmed. All raw MySQL SQL and every fake table/column name is confined to `packages/adapters/src/intellichoice_adapters/mysql_profile_adapter.py`; `grep "FROM users|FROM attendance|FROM branches|FROM accounts"` across `apps/` returns **zero** hits in app source; all 21 app-level consumption sites go through Protocol methods and receive SPEC-derived Pydantic types; attendance is coerced at the seam (`row is None → AttendanceStatus.UNKNOWN`). The housekeeping drift: `apps/learning-api/src/learning_api/services/attendance.py:7` imports `current_week_key` **from the MySQL adapter module** — a module-level helper outside the Protocol — and uses its value at `:103` as the `week_id` written into Postgres. The value itself is org/SPEC-derived (it delegates to `intellichoice_shared.org_time.resolve_org_time().week_key()`), so the helper simply belongs in shared org_time. Both apps also construct `MySQLProfileAdapter` directly in `main.py` rather than behind a factory.
- **Evidence**: `packages/adapters/src/intellichoice_adapters/mysql_profile_adapter.py:56-59`, `:104-131`; `packages/shared/src/intellichoice_shared/profiles.py:7-51`; `apps/learning-api/src/learning_api/services/attendance.py:7`, `:103`; `apps/learning-api/src/learning_api/main.py:101`; `apps/chat-api/src/chat_api/main.py:78`.
- **Severity**: LOW (housekeeping).
- **Likely explanation**: The week-key helper was written next to its first consumer, the attendance query, and never moved when app code needed it.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-92
- **Title**: "Citations carry `effective_to`" is imprecise — the chunk and document rows do, the citation DTOs do not
- **Related claims**: WORK-04, REQ-14 / **Related decisions**: —
- **Intended state**: PROGRESS records that citations carry `effective_to`, so a cached answer could outlive its sources; no answer cache exists.
- **Observed state**: No answer cache exists — the only `cache` constructs in chat-api and knowledge are `functools.lru_cache` on settings and dependency singletons (`config.py:194`, `dependencies.py:25`, `knowledge/settings.py:26`); no Redis/ElastiCache client, no answer-keyed store, no TTL logic. But `effective_to` lives on `RagDocument`/`RagChunk` (`models/rag.py:27`, `:60`) and is enforced as a retrieval predicate, while the `Citation` model (document_title/document_version/page_number/section_title/source_reference/supporting_quote_hash) and the API's `CitationResponse` (`routers/sessions.py:130-136`) carry **no** `effective_to`. The named fix — clamp each cache entry's TTL to its earliest citation expiry — would need an extra lookup, which strengthens rather than weakens the "this is a decision, not an optimisation" conclusion.
- **Evidence**: as cited; `packages/db/src/intellichoice_db/models/rag.py:27`, `:60`; `apps/chat-api/src/chat_api/routers/sessions.py:130-136`.
- **Severity**: LOW
- **Likely explanation**: The note was written about the data model's expiry semantics and generalised to the citation object a cache would hold.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-93
- **Title**: PROGRESS carries D-401/D-406 as unblocked-but-unapplied against a commit titled "applied"
- **Related claims**: WORK-08, COST-24, COST-28, WORK-07 / **Related decisions**: D-401, D-406, D-419
- **Intended state**: Resolve whether the alarm split and the consumer-keyed NAT are applied; ROADMAP W25 says applied, `PROGRESS.md:155-156` says unblocked but unapplied.
- **Observed state**: Both are fully present in configuration and both were committed before the disputed date. D-401: `aws_sns_topic.alerts_info` plus its email subscription exist, three alarms route to it, and the enforcing test exists. D-406: `local.private_egress_consumers` and `needs_private_egress` exist and drive `nat_gateway_enabled`. Git dates the code changes — `15bb6b3 W14: the NAT gateway follows its consumers, not one of them (#328)` and `73e29c6 W8/W9: spend attribution needed a query, and the alarms are split by severity (#323)` — with `2e301d6 D-419: D-401/D-406 applied, …(#341)` recording the apply. The repository therefore tilts toward ROADMAP and makes `PROGRESS.md:155-156` the likely-stale side, but a commit title is a *claim* of an apply, not the apply.
- **Evidence**: `terraform/modules/observability/main.tf:45-73`; `terraform/environments/staging/main.tf:100-138`; `git log --oneline` (`15bb6b3`, `73e29c6`, `2e301d6`).
- **Severity**: LOW
- **Likely explanation**: PROGRESS's line was written between the config landing and the apply, and was not revisited after D-419.
- **Resolvable by Phase 3B?**: **yes** — applied-versus-unapplied is precisely a live-state question (`terraform plan` / AWS).
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-94
- **Title**: U7 §9.2 still asks whether `learning_sessions` gets built; it is built, migrated and has a scheduled producer
- **Related claims**: WORK-20, WORK-19, WORK-22 / **Related decisions**: D-331, D-333
- **Intended state**: U7 §9.2 poses the question as open, and OPEN_DECISIONS #4 competes with it.
- **Observed state**: **Built.** Migration `6538a95bc990_d331_learning_sessions.py` creates the table with five indexes and sits in the live chain (`down_revision = "d4b81f6c2e70"`, and `4cfc45b7c5ff_d333_memory_consolidated_at.py` has `down_revision = "6538a95bc990"`); a SQLAlchemy model exists with `checkpoint_deleted_at` and `memory_consolidated_at`. The earlier `f3d82932ed10_drop_learning_sessions_superseded_by_.py` is **not** a later reversal — it revises `05a193bc739b` (2026-07-15) and drops the S5 stand-in, long before the D-331 re-creation. A producer exists (`session_consolidation_cli` → `LearningSessionRepository.upsert`) and its schedule is enabled. The U7 document's open question is documentation lag only.
- **Evidence**: `packages/db/alembic/versions/6538a95bc990_d331_learning_sessions.py:26-34`; `4cfc45b7c5ff_d333_memory_consolidated_at.py:27`; `f3d82932ed10_drop_learning_sessions_superseded_by_.py:5`, `:21`; `packages/db/src/intellichoice_db/models/learning_session.py:50-51`, `:87`, `:100`; `terraform/modules/scheduled-jobs/main.tf:52-60`.
- **Severity**: LOW (documentation lag).
- **Likely explanation**: Same as DRIFT-47 — the U7 document was not updated when the next day's decision shipped its answers.
- **Resolvable by Phase 3B?**: no for the doc; whether the migration is applied to the deployed database is 3B.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-95
- **Title**: U7 §10 still records the duplicate `learning_gain` observation as un-investigated four days after it was diagnosed and closed
- **Related claims**: WORK-24, WORK-22 / **Related decisions**: D-331, D-336
- **Intended state**: U7 §10 notes one completed thread with two `learning_gain` rows as out of scope and recorded as a carry-over rather than investigated.
- **Observed state**: It was investigated and closed twice over. D-336 (2026-08-15) chased it: "Chased now, it is a real parent-visible defect with a one-line cause" — `POST /exam/finalize` carries no `Idempotency-Key` (only `/answers` does), so a retry, double-submit or reconnect recomputes and re-inserts; two byte-identical rows 46 seconds apart, and `services/history.py` returned 10 session summaries for 9 real cycles. Status: "cause fixed; **the existing duplicate row is left alone** (a deletion, and therefore the user's call)." PROGRESS then closed the carry-over by measurement: staging holds "**9 gain rows and 0 duplicate pre-assessment ids**". `U7_CHECKPOINT_CONSOLIDATION.md:291-297` still reads "Out of U7's scope and recorded as a carry-over rather than investigated here", with no pointer to D-336.
- **Evidence**: `docs/U7_CHECKPOINT_CONSOLIDATION.md:291-297`; `docs/DECISIONS.md:24160-24185`; `docs/PROGRESS.md:976-977`, `:1080`, `:2356`.
- **Severity**: LOW (the work is done; only the stale record misleads).
- **Likely explanation**: As DRIFT-47 and DRIFT-94 — the source document is treated as a historical note without being marked as one.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

- **Drift ID**: DRIFT-96
- **Title**: CONTENT_COVERAGE names `selection` as an answer model the code never implements under that name
- **Related claims**: WORK-30, REQ-41 / **Related decisions**: D-273
- **Intended state**: `CONTENT_COVERAGE.md:96` and `:165` name `selection` (11 rows) as its own answer-model family needing a "predicate verifier over stated objects".
- **Observed state**: **`selection` is not a distinct answer model.** A grep for `"selection"`/`'selection'` across `packages/curriculum` returns zero hits. The capability landed under a different design: comparison questions are expressed through the **`value`** model, as the router's own tests state — `test_answer_model_router.py:40-43` parametrizes `("Eq(x, Max(34, 43))", "value")` with the comment "It is `value` because the answer *is* a value - the point is that `Max` does the selecting", likewise `("Eq(x, gcd(12, 18))", "value")`. Worth naming so a future reader does not search for a missing verifier.
- **Evidence**: `packages/curriculum/tests/test_answer_model_router.py:30-53`; `packages/curriculum/src/intellichoice_curriculum/authored_validation.py:746-785`, `:869-942`; `docs/CONTENT_COVERAGE.md:96`, `:165`; zero-hit `selection` grep.
- **Severity**: LOW
- **Likely explanation**: The document predicted a family shape from the item census; the implementation found a simpler expression and the predicted name was never retired.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no. See DRIFT-51 and DRIFT-52 for the same file's MEDIUM drifts.

- **Drift ID**: DRIFT-97
- **Title**: OPEN_DECISIONS #6 is "parked, not blocking" while PROGRESS still lists it as blocked on the YouTube key
- **Related claims**: WORK-37, WORK-14, ARCH-07 / **Related decisions**: D-326, D-337, D-342, D-390
- **Intended state**: One answer about whether the video-catalog item blocks launch.
- **Observed state**: Two documents give opposite answers: `docs/OPEN_DECISIONS.md:32-33` describes #6 as "parked, not blocking" while `docs/PROGRESS.md:105` still lists it as "blocked on the YouTube key, which only you can supply". The underlying guard is confirmed verbatim and is sound: `packages/youtube/src/intellichoice_youtube/sync_cli.py:77` reads `return covered == 0 and deferred == 0` inside `saw_whole_channel(covered: int, deferred: int) -> bool`, with the loss event recorded in the docstring ("On staging 2026-08-15 a run with `covered=72, deferred=0` evaluated this as 'saw everything' and marked **182 videos inactive** … Net coverage still rose 72 -> 76 skills, which is precisely why it was easy to miss"), the two independent reasons enumerated at `:61-65`, and a regression test targeting the *computation* rather than the effect: `test_sync_preflight.py:166` `assert saw_whole_channel(covered=72, deferred=0) is False`.
- **Evidence**: `packages/youtube/src/intellichoice_youtube/sync_cli.py:58-77`, `:80-90`; `packages/youtube/tests/test_sync_preflight.py:162-166`; `packages/youtube/tests/test_catalog_sync.py:356-369`, `:398-409`; `docs/OPEN_DECISIONS.md:23-33`; `docs/PROGRESS.md:105`.
- **Severity**: LOW (severity from the inspector; both are deferral states and the practical consequence is identical — MEDIUM would be defensible if #6 fed a launch checklist).
- **Likely explanation**: The item was re-characterised as parked in OPEN_DECISIONS and the PROGRESS line describing it as blocked was not updated.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no

### Late additions — inspector W10's coverage-gap closure (severity is the Severity field, not the id)

- **Drift ID**: DRIFT-98
- **Title**: ARCHITECTURE.md's declared scope understates a month of work the same file already documents
- **Related claims**: ARCH-01, ARCH-26, ARCH-05, ARCH-06 / **Related decisions**: D-404–D-423 (Milestones 12–15), D-416, D-421, D-423
- **Intended state**: `docs/ARCHITECTURE.md:3-13` declares the file a map of "what exists now" documenting the system as built **through S0–S34 plus the S36–S43 audit/stabilization work and the §2.6 launch gate**, with "Session provenance … tagged in each node (e.g. `(S6)`)".
- **Observed state**: The claimed range **is** present in code and infra — spot-verified per named block (S8 `packages/shared/.../bedrock.py`; S9/S20–S23 `packages/curriculum/.../{authored_bank,adjudications}.py` plus `learning-api/services/{exam_policy,grading,hint_personalization_scheduler}.py`; S11/S16 both SPAs; S12–S13 `packages/knowledge/.../{ingest,retrieval,reembed}.py`; S14–S15 `packages/shared/.../mcp.py` + the fake adapters; S24–S28 `packages/memory` and `services/{report,stage_narrative}.py`; S30 `packages/evals/`; S31 `packages/observability/`; S32–S35 `terraform/environments/staging/` and `deploy-staging.yml`), with S29 absent exactly as the file's own "not built" list says. The drift is in the "up to" direction: the same file documents work well past S43 — `:1106-1107` (D-404/D-405), `:1119` (D-409), `:1147` (D-416), `:1163` (D-421), `:1177` (D-423), `:2072` (`chat_escalation_sends`, D-421), 15 lines matching `D-4xx|W2x|U7` — while `PROGRESS.md:9-11` records "MILESTONE 15 IS CLOSED — six sessions, seven PRs … (2026-08-18, D-416 → D-423 … W22–W27)". Provenance tagging is also uneven against the ":3-13" claim: `grep -oE "\(S[0-9]+\)"` yields `(S1)…(S22) (S24)…(S29) (S34) (S37) (S39) (S48)` — no tags for S23, S30–S33, S35, S36, S38, S40–S43, i.e. exactly the deployment/audit range the header claims to cover, and **no tag scheme at all for the W-milestones**. The file self-flags this rot class at `:49-54` ("A 'not yet built' list is the fastest part of an architecture doc to rot").
- **Evidence**: `docs/ARCHITECTURE.md:3-13`, `:19-23`, `:26-36`, `:49-54`, `:1106-1107`, `:1119`, `:1147`, `:1163`, `:1177`, `:2072`; `docs/FINAL_ARCHITECTURE.md:3-12`; `docs/PROGRESS.md:9-11`; `git log --format=... -- docs/ARCHITECTURE.md` → `344f016` (2026-08-18); `packages/` and `apps/` listings.
- **Severity**: MEDIUM
- **Likely explanation**: The per-node content is updated as work lands (the D-4xx references prove it), but the header's declared range is a one-line summary nothing re-derives. **DRIFT-01 is the same rot in the opposite direction** — `FINAL_ARCHITECTURE.md:6` still says ARCHITECTURE.md documents "what exists now (through S31, S29 deferred)" and asks for regeneration "once S32–S34 actually land", which they have.
- **Resolvable by Phase 3B?**: no — the divergence is between the file's header and its own contents. (§5.3's other half, the deployed topology, is 3B and is not this entry's subject.)
- **Genuine decision required?**: yes — which scope wording is authoritative, and whether the "(Sn)" provenance convention extends to W-milestones. This is the same decision family as DRIFT-01 (whether FINAL_ARCHITECTURE is retired or regenerated) and is recorded in §3.2 as one cross-referenced row, not a duplicate.

- **Drift ID**: DRIFT-99
- **Title**: The ledger's "§6.1 track not started" temporal note is superseded — the T-02 enumeration shipped 2026-08-15
- **Related claims**: SEC-20, REQ-25, REQ-26, WORK-32 / **Related decisions**: D-129 (T-02)
- **Intended state**: The eleven-disclosure first-visit notice does not exist in `apps/learning-web/src`; D-129 dispositioned it as S45-builds / §6.1-track-enumerates-first, with the order load-bearing, and the claim notes the track had not started at writing.
- **Observed state**: The claim's substance holds exactly — **no notice component and no first-visit gate** in `apps/learning-web/src`. The full inventory is thirteen `components/*.tsx` and eight `screens/*Screen.tsx`, none named notice/disclosure/consent; a case-insensitive grep for `first.?visit|disclosure|privacy.?notice|consent` returns only forward-looking comments (`main.tsx:38` "§5.1.2's first-visit disclosures are route-aware, which is why this exists"; `App.tsx:39,56,87`), and no `localStorage`/`sessionStorage` first-visit flag exists — the only keys are the dev token/sub/role (`App.tsx:61-63`, `:383-399`). The sibling pattern does exist in the chat app (`LocationConsentModal.tsx`). The superseded field is temporal: the §6.1 track **has** started and its T-02 gating deliverable is complete — `docs/FIRST_VISIT_NOTICE.md` (237 lines, `da2549f`, 2026-08-15) enumerates all eleven as copy in two registers, titled "SPEC §5.1.2's eleven disclosures, enumerated (T-02)" with `:5-6` "**S45 transcribes this; it does not draft it**". S45 itself remains unbuilt inside the frozen S43–S47 block.
- **Evidence**: `apps/learning-web/src/` inventory; `apps/learning-web/src/main.tsx:38`; `App.tsx:39`, `:56`, `:61-63`, `:87`; `apps/chat-web/src/screens/LocationConsentModal.tsx:1-75`; `docs/FIRST_VISIT_NOTICE.md:1-14`, `:203-222`, `:233-237`; `docs/ROADMAP.md:1502-1504`, `:2148-2157`; `docs/PROGRESS.md:978-982`; `git log -- docs/FIRST_VISIT_NOTICE.md`.
- **Severity**: LOW — the load-bearing prerequisite is now discharged while the build is not.
- **Likely explanation**: The claim recorded the track's state at the moment it was written; the deliverable landed four days later under a different decision id.
- **Resolvable by Phase 3B?**: no for the repository halves; whether counsel review has occurred is off-repo.
- **Genuine decision required?**: no new decision — the eight-versus-eleven question the deliverable itself raises (`FIRST_VISIT_NOTICE.md:203-222`, `:235-237` "The three gaps in §5 need a product decision before S45 starts, because they change how many disclosures there are") is already carried by DRIFT-08. Track ownership is DRIFT-11.

- **Drift ID**: DRIFT-100
- **Title**: TRACEABILITY's structural row counts 31 `extra="forbid"` models against 41, and its named mechanism protects only the Bedrock subset
- **Related claims**: TEST-04, SEC-06, SEC-03 / **Related decisions**: —
- **Intended state**: A *structural* verdict requires (a) a citable artifact location and (b) something mechanical that fails if the artifact disappears; with no mechanism it is a gap, not a fourth verdict (`docs/TRACEABILITY.md:43-45`).
- **Observed state**: Six of six named artifacts exist and four of six name a mechanism that exists; the two rows declared "nothing mechanical — **descriptive**" (§5.3, §5.36) are consistent with the fence and are recorded as such at `:629-633`. Confirmed mechanisms: `Makefile:129-130` `typecheck:` → `uv run pyright`, and `.github/workflows/ci.yml:9` job `lint-typecheck-test` with `:85 run: uv run pyright` / `:88 run: uv run pytest`; `ci.yml` defines exactly the claimed four jobs (`:9`, `:90`, `:119`, `:151`); `deploy-staging.yml` deploys exactly two APIs and two SPAs (`:118`, `:135`, `:651`, `:659`, `:667`, `:672`). Two defects in the §5.27 row (`:623`): the count is stale — `model_config = ConfigDict(extra="forbid")` now appears **41** times in non-test source (`packages/shared/.../bedrock.py` 35, `curriculum/adjudications.py` 2, `curriculum/authored_bank.py` 2, `adapters/bedrock/smoke_cli.py` 2), not 31 — and the mechanism is weaker than stated: **pyright does not fail if an `extra="forbid"` is deleted**, so clause (b) is satisfied only for the Bedrock-payload subset that the PII-floor and generation-schema tests pin (`test_bedrock_payload_pii_floor.py:26-32`, whose `test_every_bedrock_payload_is_governed_by_one_regime` "fails on a *new payload class*"), and not for the other six models.
- **Evidence**: `docs/TRACEABILITY.md:43-51`, `:618-633`; `Makefile:129-130`; `.github/workflows/ci.yml:9`, `:85`, `:88`, `:90`, `:119`, `:151`; `.github/workflows/deploy-staging.yml:118`, `:135`, `:651`, `:659`, `:667`, `:672`; `packages/shared/tests/test_bedrock_payload_pii_floor.py:1-32`; `apps/learning-api/src/learning_api/config.py:9`, `:39`; `grep -rc 'model_config = ConfigDict(extra="forbid")' apps packages --include="*.py"` → 41.
- **Severity**: LOW — refutes the ledger's "31 models" figure; the fence's own bookkeeping is otherwise honoured.
- **Likely explanation**: The count was correct when written and grew with the payload set; the mechanism was described by the job that runs, not by what that job can actually fail on.
- **Resolvable by Phase 3B?**: no for the count and the mechanism-strength wording. Two of the row's runtime halves are 3B: whether a container actually fails on a missing required env var (§5.35's validator presence is repo-provable only) and the deployed topology behind §5.3.
- **Genuine decision required?**: no — refresh the count and narrow the mechanism wording.

- **Drift ID**: DRIFT-101
- **Title**: TRACEABILITY's T-02 block still asserts the §6.1 track has not started and that none of the eleven is enumerated anywhere
- **Related claims**: TEST-10, SEC-20, TEST-05 / **Related decisions**: D-129
- **Intended state**: T-02 is dispositioned and split — the §6.1 track enumerates the eleven disclosures as a written deliverable, S45 builds the notice, and the ordering is load-bearing.
- **Observed state**: The disposition text is present as claimed (`docs/TRACEABILITY.md:650` "**Dispositioned 2026-07-30 (D-129): S45 builds it; the §6.1 track enumerates the eleven disclosures first.** Scheduled, not shipped", the split at `:655-662`, `:664-665` "**Still not built**, and the disposition does not pretend otherwise"), the notice component is still absent, and **the order held** — the list landed before any build, which is what the claim says must happen. Two statements inside the block are now false of the repository: `:680` "**None of the eleven is enumerated as a deliverable anywhere in ROADMAP.md.**" and `:685-690` "The §6.1 legal & policy parallel track, which 'gates the pilot' and has **not started**". `ROADMAP.md:2148-2157` now enumerates them and `docs/FIRST_VISIT_NOTICE.md` writes them out. Both sit under an explicit preservation marker at `:668` ("*(The finding as filed, kept because the reasoning is the record:)*"), which softens the reading — but the block never adds a "since superseded" pointer, and **TRACEABILITY contains no reference to `docs/FIRST_VISIT_NOTICE.md` at all**: a grep for `FIRST_VISIT_NOTICE` across `docs/` hits only `PROGRESS.md:978` and `:2246`. So the traceability document does not cite the artifact that discharged its own prerequisite.
- **Evidence**: `docs/TRACEABILITY.md:650`, `:652-698` (esp. `:655-665`, `:668`, `:680`, `:685-690`); `docs/FIRST_VISIT_NOTICE.md:1-14`; `docs/ROADMAP.md:2148-2157`; `docs/PROGRESS.md:978-982`, `:2246`; `grep -rn "FIRST_VISIT_NOTICE" docs/ --include="*.md"`.
- **Severity**: LOW
- **Likely explanation**: The block was deliberately preserved as filed, and the preservation convention has no companion convention for adding a forward pointer when a prerequisite is later discharged.
- **Resolvable by Phase 3B?**: no.
- **Genuine decision required?**: no — the decision that unblocks S45 is the eight-versus-eleven ruling at DRIFT-08, not more documentation.

- **Drift ID**: DRIFT-102
- **Title**: The scheduled-jobs header comment still says three jobs are enabled while its own `locals.jobs` enables four
- **Related claims**: WORK-35, ARCH-04, ARCH-05, WORK-19, WORK-20 / **Related decisions**: D-331, D-332, D-333, D-356, OPEN_DECISIONS #4 option D
- **Intended state**: OPEN_DECISIONS #4 chose option D — consolidate the checkpoint into long-term durable memory, then keep it there — reusing `packages/memory`'s already-scheduled entrypoint, with design review before code.
- **Observed state**: The design is built as chosen. `session-consolidate` sits in the same `locals.jobs` map as `retention-purge`, enabled and ordered first: `schedule = "cron(0 18 * * ? *)"`, `command = ["python", "-m", "learning_api.services.session_consolidation_cli"]`, `description = "Project completed learning threads into learning_sessions (U7/D-332)."`, `retry_attempts = 2`, `enabled = true` (`terraform/modules/scheduled-jobs/main.tf:40-61`), with the ordering rationale in place ("**First in the daily order, and the ordering is the point (D-356)**"). Schedules are generated (`:182-183` `for_each = local.jobs`, `:198` the ENABLED/DISABLED expression) and wired into alarming (`environments/staging/main.tf:777-782`). The full chain exists — CLI, two migrations, model/repo, the `JOB_SESSION_CONSOLIDATE` constant, four test files — and the "then keep it there" half is honoured by omission: `checkpoint_retention_cli.py` exists with a manual `Makefile:106` target and is deliberately **not** in `locals.jobs`. Design review before code is documented at `U7_CHECKPOINT_CONSOLIDATION.md:1-30`. The drift is one stale comment in the operative file: `terraform/modules/scheduled-jobs/main.tf:13-20` still reads "Four jobs are defined, **three are enabled**… `chat-purge`, `memory-consolidate` - enabled. `retention-purge` - enabled…" against **five** defined and **four** enabled in its own locals; `ARCHITECTURE.md:28-30` has the correct count. This is the same operative comment recorded at DRIFT-75 from the ARCH-04 claim — one defect, two claims, cross-linked rather than counted twice as an underlying finding.
- **Evidence**: `terraform/modules/scheduled-jobs/main.tf:13-20`, `:40-61`, `:74-88`, `:89-106`, `:182-183`, `:198`; `terraform/environments/staging/main.tf:772-782`; `apps/learning-api/src/learning_api/services/session_consolidation_cli.py:1-40`; `apps/learning-api/src/learning_api/services/checkpoint_retention_cli.py:3`; `Makefile:106`; `packages/db/alembic/versions/{6538a95bc990_d331_learning_sessions,4cfc45b7c5ff_d333_memory_consolidated_at}.py`; `docs/U7_CHECKPOINT_CONSOLIDATION.md:1-30`; `docs/ARCHITECTURE.md:26-36`; `docs/OPEN_DECISIONS.md:171-215`.
- **Severity**: LOW (comment-only, inside the operative file).
- **Likely explanation**: `session-consolidate` was added "first and alone" for the D-356 safety ordering and the header count was not incremented.
- **Resolvable by Phase 3B?**: **yes** for the job's runtime half — Terraform proves the schedule is *declared* ENABLED, not that AWS holds it or that it has fired; the claimed idempotency numbers (36,929 rows, 0 written on a second run, 40 s versus 4m00s) and criterion 6's ≥1-week unattended clock are live facts. The comment defect itself is repository-evident.
- **Genuine decision required?**: no

## 3. Index tables

### 3.1 By severity (counts)

| Severity | Count | Drift IDs |
|---|---|---|
| HIGH | 8 | DRIFT-01 … DRIFT-08 |
| MEDIUM | 45 | DRIFT-09 … DRIFT-52, **DRIFT-98** (DRIFT-10, DRIFT-11 are high-adjacent) |
| LOW | 49 | DRIFT-53 … DRIFT-97, **DRIFT-99 … DRIFT-102** (DRIFT-53 – DRIFT-59 are medium-adjacent) |
| **Total** | **102** | — |

Ids are insertion-ordered within severity bands, so the numbering is not strictly severity-ordered
across the whole file: DRIFT-98 (MEDIUM) and DRIFT-99–DRIFT-102 (LOW) are inspector W10's late
additions, appended after DRIFT-97 rather than renumbered into their bands. Read the **Severity**
field, not the id.

Consolidated family entries: DRIFT-03 (SEC-32 + INT-13 + INT-25), DRIFT-04 (SEC-33 + INT-22 + INT-33),
DRIFT-05 (INT-06 + INT-07, cross-referencing the sibling files at DRIFT-06/DRIFT-07), DRIFT-17
(REQ-09 + SEC-09 + ARCH-18), DRIFT-35 (ARCH-25 + WORK-31 + REQ-35 + REQ-37 + REQ-43),
DRIFT-53 (REQ-01 + SEC-01), DRIFT-60 (COST-03 + COST-04 + REQ-12 + SEC-11 + TEST-02),
DRIFT-61 (REQ-20 + COST-05), DRIFT-28 (ARCH-29 + COST-28), DRIFT-71 (REQ-28 + SEC-12).

### 3.2 Genuine decisions required

| Drift ID | Decision needed (named, not made) | Plausible owner | Blocked by D-152? |
|---|---|---|---|
| DRIFT-04 | Who signs off §7-R1 now that its only occasion is frozen, and who owns R8/R9 expiry monitoring | user + org | yes — R1's occasion is S42, R8's closures are S43/S46 |
| DRIFT-05 | Whether INTEGRATION_PLAN is preserved as a pre-freeze artifact or carries a freeze banner | user | no |
| DRIFT-06 | Whether S42_ORG_ASKS gets a freeze banner or is marked historical | user | no |
| DRIFT-07 | Which of S42_OPEN_QUESTIONS' contradictory C3 statements wins, and whether the action list is rewritten or dated in place | user | no |
| DRIFT-08 | Eight versus eleven first-visit disclosures | user + counsel | yes — owned by frozen S45 |
| DRIFT-10 | Add an alarm on `learning_checkpoint_repairs_total`, or accept a human-review cadence as R9's detector | user | no |
| DRIFT-11 | Scheduling and owning the §6.1 legal track | user + counsel | partly — the track is non-coding and not frozen, but S45 depends on it |
| DRIFT-12 | Define the admin role's fate or amend SPEC §5.30.2's matrix | user | no |
| DRIFT-13 | Adopt Bedrock Guardrails / an approved safety policy for a minors platform, or amend §5.12.2 | user (counsel input plausible) | no |
| DRIFT-14 | Adopt Bedrock Guardrails or amend SPEC §5.25.1's gateway feature list | user | no |
| DRIFT-15 | Build a dead-letter queue and a smaller-model fallback, or amend SPEC §5.29's common-mechanism list | user | no |
| DRIFT-16 | Whether "sensitive information in an email" was ever meant as a gate distinct from `email_approval` (doc-side reading of SPEC §5.1.4) | user | no |
| DRIFT-19 | A gateway-level input bound, or a per-caller convention recorded as the answer | user | no |
| DRIFT-20 | Raise the product-KPI floor once real traffic exists, or record the disabled state as the accepted answer to P1-10 | user | partly — "real traffic" arrives with the pilot |
| DRIFT-30 | Ship the "Current estimated level" wording or disposition the requirement | user | no |
| DRIFT-40 | Whether to namespace the AUDIT_LIVE register's finding ids | user | no |
| DRIFT-44 | Which status stands for learning-web's banner condition (requires reading D-417/C7's own scope) | user | no |
| DRIFT-45 | Schedule and apply-enable the checkpoint retention job | user | no |
| DRIFT-46 | Same as DRIFT-45, for the 180-day chat window | user | no |
| DRIFT-49 | Which model roster is intended — the document's or `.env.example`'s | user | no |
| DRIFT-66 | Build, scope or formally drop SPEC §5.26.3's internal NL2SQL pipeline | user | no |
| DRIFT-98 | Which architecture-scope wording is authoritative, and whether the `(Sn)` provenance convention extends to W-milestones — **the same decision family as DRIFT-01** (retire or regenerate FINAL_ARCHITECTURE); one row, cross-referenced, not two | user | no |

### 3.3 Resolvable by Phase 3B

| Drift ID | What 3B must observe |
|---|---|
| DRIFT-29 | The **live NAT gateway count** first; only if it disagrees with the checked-in defaults does the `terraform.tfvars` override question arise. Recorded hypothesis: D-419 may describe the plan diff, not NAT absence. |
| DRIFT-57 | Live private route table and NAT count, to say whether the zero-egress baseline currently holds. |
| DRIFT-83 | The LangSmith account's run-retention setting (external to the repository). |
| DRIFT-84 | Secret version history for the two staging token secrets, to say whether an out-of-band rotation occurred after 2026-08-13. |
| DRIFT-87 | A Logs Insights query against the ops-task log group, to confirm structured `*_job_complete` lines actually reach CloudWatch. |
| DRIFT-89 | Live SNS subscription state (including COST-26's PendingConfirmation) and whether a second informational endpoint is configured. |
| DRIFT-93 | Live `terraform plan` / AWS state, to settle applied-versus-unapplied for D-401 and D-406. |
| DRIFT-58 | A re-run of the learning e2e walks in combination, to say whether the isolation defect is behaviourally resolved. |
| DRIFT-102 | Whether AWS actually holds the `session-consolidate` schedule and whether it has fired: Terraform proves only that the schedule is *declared* ENABLED. The claimed idempotency numbers (36,929 rows, 0 written on a second run, 40 s versus 4m00s) and criterion 6's ≥1-week unattended clock are live facts. |
| DRIFT-80, DRIFT-90, DRIFT-94, DRIFT-100 | Partial only: the script's judgement against live AWS (DRIFT-80), whether the deployed knowledge store still holds the draft FAQ (DRIFT-90), whether migration `6538a95bc990` is applied to the deployed database (DRIFT-94), and — for the structural fence — whether a container actually fails on a missing required env var (§5.35) plus the deployed topology behind §5.3 (DRIFT-100). The documentation halves of all four are settled here. |
