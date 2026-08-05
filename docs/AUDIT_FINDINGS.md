# Audit Findings — Phase 0A (S36–S39)

The findings register for the four audit sessions defined in
[INTEGRATION_PLAN.md §2.3](INTEGRATION_PLAN.md). One row per finding, with reproduction and
evidence, so §2.6's criteria 1 and 2 can be evidenced rather than asserted.

**Severity (§2.4).** P0 authorization bypass / PII leak / data corruption / child-safety
failure / uncontrolled spend — stops the line, fixed immediately with a regression test.
P1 a launch journey broken, fail-open behavior, cost or latency out of bounds — fixed and
re-verified before the gate. P2 degraded UX or quality with a workaround. P3 polish.

**Disposition rule.** Fixes land in Phase 0B (S40–S41), *not* mid-audit — except P0s. Every
finding needs a disposition here; "won't fix" needs a written reason.

**Areas audited with no finding are recorded too**, at the bottom of each session's section.
An audit whose output is only its defects can't be told apart from an audit that stopped
early, and traceability (criterion 1) needs the negative results as much as the positive
ones.

---

## Index

| ID | Area | Severity | Status | Summary |
|---|---|---|---|---|
| **AUD-L-02** | **Money** | **P0** | **Fixed in S36** | `POST /students/{id}/report` had no cost ceiling of any kind — it passed `session_spend_cents=0.0`, so the gateway's budget check could never fire, and one authenticated caller could drive unbounded Bedrock spend |
| **AUD-L-04** | **Minors / PII** | **P1** | **Fixed 2026-07-29 (D-114)** — schedule applied and ENABLED | D-072 accepted "names in free text may survive" *because* that text lived in a 90-day-purged table; S25 then derived permanent, never-purged `semantic_memory.fact_text` from it, and those facts reach parent-visible reports |
| AUD-L-05 | Minors / PII | P2 | ✅ fixed 2026-08-04 (D-175) | `MemoryConsolidationPayload` carries free text but was never added to the PII-floor allowlist test, contrary to D-072's own stated rule. **Fixed wider than filed**: the file claimed to cover "every payload type that crosses the gateway" and covered **6 of 20**, so the four chat payloads and `VideoClassificationPayload` were ungoverned too. Two structural changes rather than seven rows — the denylist now **recurses into nested models** (without which the fix would have been decoration on this very payload: its own field names are `events`/`existing_facts`/`allowed_fact_types` while the student text is in `MemoryEventSummary.summary`), and a completeness test fails when a **new payload class** is added, not just a new field. 17 models allowlisted, 7 in the generation regime, 1 excluded with a written reason |
| AUD-L-06 | Minors | P3 | **Decided** — delete in Phase 0B | `tutor.generate_hint` is dead code that omits the leak check its live sibling applies — a trap for whoever wires it up |
| AUD-L-03 | Money | P2 | **Decided** — Phase 0B | `pre_intro` stage-narrative spend is never folded back into the session total, so the per-session ceiling is permanently one call short |
| **AUD-L-07** | **Authorization** | **P1** | **Accepted residual risk 2026-07-30 (D-123) — §7-R8**; still open as a finding, closes at S43/S46; **write half closed in S40** (D-107) | **The read half is now an accepted, written, expiring risk rather than an undecided open P1** — the product call the gate had been carrying for several sessions. Fixing it needs the tutor-assignment model `ProfileAdapter` gains at S43, which is after the gate; failing closed now was rejected because S40 showed it ends tutor report generation outright until S46. Acceptance is scoped to the no-real-users pilot window. Original: S40 closed the mutating surface via AUD-X-05's `access="write"` refusal, so what remains is the original read-scope gap: a tutor token can still read any student's dashboard/history and generate reports about them. Unchanged disposition — it needs the assignment/branch-roster model `ProfileAdapter` gains in S43, with the formal disposition at S46. The stale "lands with Q&A authorization (Session 13)" comment is fixed. Original: D-086's known tutor/branch_manager scope gap now reaches further than when it was written: it covers the S28 dashboard and report surface, so a tutor token can read any student's data and generate reports about them |
| **AUD-L-09** | **Correctness** | **P2** | ✅ **fixed in D-172 §1 (2026-08-04)** | D-098's mitigation 1 implemented: `grounding_failure` rejects an explicit `from X to Y` transition stating the known `pre_raw_score`/`post_raw_score` pair in reverse, with the two failure modes now logged apart (`inverted_score_pair` vs `ungrounded_number`). **Deliberately incomplete, and the incompleteness is in the code** (`numeric_grounding`'s docstring): swapped skills, a mastery figure on the wrong skill, and any inversion phrased without `from`/`to` still pass. One known false rejection — hints 6 → 4 while scores go 4 → 6 — fails closed and is pinned by a test. **Mitigation 2 was already satisfied**: stage payloads are per-stage by construction, now asserted from the AST of the real construction sites (`test_stage_payloads_stay_narrow.py`, watched failing against a widened payload); narrowing the *report* payload was rejected as D-163's false-rejection class. Original: numeric grounding verifies a number's *provenance*, not its *attribution*, so a report can invert a real result ("fell from 6 to 4") and still pass |
| **AUD-L-10** | **Data integrity / scoring** | **P1** | **Fixed in S42** (D-110 §1) | Uniqueness on `assessment_attempts` tightened from `(session, variant, idempotency_key)` to `(session, variant)`, so one attempt per item is a database invariant rather than a check — the check alone is the same read-then-act shape this cluster exists to remove, and the concurrent arm proves it: with the constraint dropped, four simultaneous answers all return 200 while the sequential test still passes. A `flow` pre-flight turns the ordinary duplicate into a 409 before a graph turn starts, kept because a refused duplicate that reaches `ainvoke` measurably left **+2 `checkpoints` / +4 `checkpoint_writes`** behind. Original: The server marks an exam item `answered` and then accepts more answers for it; exam scores are computed over the *attempt* count, so one changed answer rescores a 10-item exam as 10/11 and silently removes the `not_applicable_pre_max` flag. Enforced client-side only |
| **AUD-L-11** | **Robustness / contracts** | **P2** | **Fixed in D-159** | `UnknownQuestionVariantError` carries a required `reason`, and `POST /answers` answers each case deterministically: **400** for an id not in the bank, **409** for a real variant this session is not serving. Both are pre-flighted off session state before `graph.ainvoke`, so a stale tab that keeps resubmitting no longer leaves checkpoint rows per attempt (asserted). Original: raised at four sites, caught nowhere — an unhandled **500** on the error rate the S34 alarms watch |
| **AUD-L-19** *(was `AUD-L-17` until 2026-08-04 — renumbered by D-174 to resolve an id collision; D-159 minted an id that S36 already held. Cited as `AUD-L-17` in documents written before that date)* | **Data integrity / scoring** | **P2** | **Found and fixed in D-159** | Found while fixing AUD-L-11: the exam answer paths checked that a variant *exists* but never that it belongs to this exam, so a real variant from another exam was **graded and inserted into `assessment_attempts` for this one** (200, and `_mark_item_answered` silently no-ops) — an 11th attempt on a 10-item exam, moving the attempt-counted scoring denominator AUD-L-10 was fixed to protect. The study path already checked membership; the exam paths did not. Now `flow.ensure_item_is_served`, pre-flighted in the route and re-checked in the service |
| **AUD-L-18** | **Correctness / parent-visible** | **P1** | **Found and fixed in D-163** | **The parent-report narrative had never once shipped under a real model.** `is_grounded` rejected **15 of 15** real generations across three payload shapes, so every parent got the facts-only fallback while the Bedrock call was made and paid for. None of the 94 rejected numbers was an invention: **85** were percent renderings of proportions the evidence carries as decimals (`0.8333` → "83%"), 8 were thousands-separated counts the tokenizer split (`"1,284"` → `1` and `284`), and the rest were numbers living inside evidence *strings* the collector never walked (`date_range_label`, and the "70%" the prompt tells the model to cite). Fixed in the checker (percent rule bounded to evidence proportions in [0,1], grouped-number parsing, strings walked) plus a prompt that forbids derived numbers and advice quantities. Re-measured **15/15 grounded**. Found only because D-162 §4 saw `generated: false` twice on staging; no test could have, since `MockBedrockProvider` is grounded by construction |
| AUD-L-12 | SPEC conformance | P2 | ✅ **Fixed in D-169 (2026-08-03)** — wired, with the behaviour limit stated rather than hidden | `recommended_difficulty` now narrows *template choice within the chosen skill* (`study_plan._closest_to_recommended`: exact tier → ±1 → whole pool, never empty), on the base path only; the retry ladder passes `None` because it already owns its difficulty movement. Threaded at all three serve sites, including `flow._serve_next_base_or_complete`, which re-reads the mastery row *after* recomputation rather than carrying a stale value. **⚠️ Provably inert on today's content and tested as such:** the live bank is 1:1 skill↔difficulty (5 skills × 10 templates, one tier each), so every branch returns the full pool and the finding's own evidence still reproduces — a student whose weakest skill is tier 5 with a tier-4 recommendation is still served tier 5, because tier 5 is all that skill has. The user's decision was to keep SPEC rule 1 (weakest skill) above rule 2 rather than reorder skills by the recommendation. Original: computed, stored and displayed but routed nothing; two docstrings claimed it seeds `starting_difficulty` and it did not. Masked only by the 1:1 skill↔difficulty bank |
| **AUD-L-13** | **Minors / correctness** | **P2** | **Fixed in D-156** | `_contradicts_measured_mastery` screens `strength`/`weak_skill` candidates against `mastery.weighted_score` at `WEAK_SKILL_THRESHOLD`, on the add path **and the reconfirm path** — the latter is the one that matters, since reconfirmation is the promotion path and repetition was the promotion criterion. Abstains when no mastery row exists (nothing to contradict); the other ten fact types are deliberately unscreened (they describe *how* a student works, which a score cannot contradict). Refusals counted (`mastery_conflicts`), logged, and printed in the CLI summary. `WEAK_SKILL_THRESHOLD` moved to `intellichoice_shared.mastery_policy` so the floor and the study plan cannot drift. Original: consolidation verified provenance and repetition, never the claim against the measured score in the same database — a `strength` fact coexisted with `weighted_score = 0.0` |
| **AUD-L-14** | **Correctness / parent-visible** | **P2** | **Fixed in D-162** | Measured before fixing, as the filing demanded: a browser-driven journey populates **both** sources within ~7% of each other (1,453 ms summed `response_time_ms` vs 1,354 ms summed item-state for one full pre-exam), so S36's "140 rows summing to 0 ms" was an artifact of driving the journeys through the API with no browser — the client half was never broken (AUD-F-01/D-107). The reliability asymmetry is what stands: item-state is a fire-and-forget tick a hard refresh or non-browser client silently drops; `response_time_ms` is **required** by `SubmitAnswerRequest` on every accepted answer. `build_dashboard` now sums `response_time_ms` from the attempt rows it already fetched (same rows as `attempts_count`, so the two figures can no longer disagree about which attempts exist); the repo's telemetry-summing query and its half-true docstring are deleted. Telemetry itself stays, as the autosave/resume signal, guarded by AUD-F-01's regression spec. Original: `time_spent_minutes` summed the telemetry column and ignored the always-populated server-required one — `0.0` minutes beside `attempts_count: 26`, inside `verified_facts` |
| **AUD-L-15** | **Correctness / parent-visible** | **P2** | **Fixed in D-156** | Three parts, two of them behaviour changes the user decided: **(a)** mastery now includes the post-exam (`_recompute_all_skill_mastery` gained `post_assessment_session_id` and is now called on post-exam finalize, where it never was) — this also fixes `topic_resolver` choosing the next cycle's targets from a score that had never seen how the last one ended; **(b)** "skills to strengthen" now uses the study plan's own cut (`mastery.weighted_score < WEAK_SKILL_THRESHOLD`) instead of a hardcoded 0.8 on post-exam accuracy, so a report cannot recommend work the system will not do; **(c)** every figure states its window, in the report payload, the prompt, and as `GET /dashboard` chart captions. **Still true and now stated rather than implied:** mastery is not date-filtered. Original: mastery excluded the post-exam while "skills to strengthen" was post-exam-derived, both shown under `date_range_label: "all time"` — one skill reading mastery 1.000 *and* "needs work" |
| AUD-L-08 | Correctness | P3 | ✅ fixed 2026-08-04 (D-176) | `normalized_gain` has no bound in either direction and derives its denominator from the pre *attempt count*. **Reachability corrected in the S36 continuation:** −200% reached on an ordinary journey, and >1 reachable via AUD-L-10's duplicate attempts. **Fixed as the user decided (D-175 §5): denominator is now the declared item count, and a quotient still outside [-1, 1] is flagged `unmeasurable_out_of_range`, never clamped** — the raw value survives for diagnosis, and `post_outro`'s narrative payload suppresses any flagged gain. 8 tests, one per row of the reproduction table |
| AUD-L-16 | Design integrity | P3 | ✅ **fixed in D-174 §6 (2026-08-04) — wired, on D-169's precedent (user's call)** | `services/effective_policy.py` reads both snapshots back and the chat gate now asks it instead of testing `phase == "study"`. **Behaviour is deliberately unchanged** under the shipped constants (pre/post refuse, study allows, every other phase refuses); what changed is that retuning `exam_policy._POLICIES` can no longer alter an in-flight session's rules — the guarantee `AssessmentSession.policy`'s own comment promises and did not implement. **`policy` is nullable** (pre-S22 rows were never backfilled), so a `constant_fallback` path is real and is *reported* rather than passed off as the snapshot's answer — "the snapshot decided" and "the snapshot was missing" are the same boolean and different guarantees. **10 tests, and they are masking tests by construction:** all 10 fail against a stub of the old phase-string mechanism, including the two load-bearing ones (a study snapshot that *disables* hints, and an exam snapshot that *enables* them, each obeyed against the opposite constant). Fails closed on an unknown phase and on an id that no longer resolves. Original: | Both policy snapshots (`assessment_sessions.policy`, `study_sessions.intervention_policy`) are written at creation and never read back; only `time_limit_seconds` governs behavior, via a separate column |
| AUD-L-17 *(keeps the id — it held it first; D-159's P2 was renumbered to `AUD-L-19` by D-174)* | Test integrity | P3 | **Fixed in S36 continuation** | The default mock's own hint boilerplate (`Level 1`) tripped the runtime answer-leak check whenever the served answer was `"1"`, making a hint test fail 8 times in 60 runs; `hint_events.was_personalized` still records no reason code, so the real rate is unmeasurable |
| AUD-L-01 | Auth surface | P3 | ✅ fixed 2026-08-04 (D-175) | A gated-off `/dev/token` still discloses that it exists, and the S35 deploy gate's stated rationale is wrong about why it 404s. **Fixed in HTTP middleware, not by conditional registration** — the finding's own recommended fix (register the route only when enabled) would have moved `Settings` to import time and broken the monkeypatch-after-import approach every existing test and the gate's own reasoning depend on; middleware runs before routing, so all shapes 404 with a byte-identical body while the decision stays per-request. Asserted on both apps against a genuinely-absent-path control, over 5 request shapes — including `no_body` and `PUT`, which the finding's table never listed. **The quoted false sentence no longer existed**: the gate comment had been rewritten before this session, so only the mechanism claim was live. **Live rows measured at the D-176 deploy: GET and no-body POST → 404 on both public edges** (D-171's 405/422 rows are gone). Residual, infra-level not app-level: CloudFront's *behavior* config still routes `/dev/token` to the API (JSON 404) while `/dev/nonexistent` falls through to the SPA, so the CDN discloses the path exists — a Terraform surface, and the same fact is visible in this public repo, so noted here rather than re-opened |
| **AUD-C-01** | **Authorization** | **P1** | **Fixed in S40** (D-107) | Both halves, fixed independently so neither relies on the other being correct: `_assert_session_access` now runs in `/messages` (folded into the one place that already reads the checkpoint, so a future caller cannot pick up the paused check and leave the access check behind), and `resolve_role` no longer downgrades an existing `user_external_id` to `None` on an anonymous turn. Landed with AUD-C-04 as D-101 requires. Original: `POST /messages` has no thread-ownership check *and* an anonymous turn erases the owner that `/respond` and `/stream` do check. Live-verified on staging: an unauthenticated caller continued a tutor's thread, received the tutor's answer and citation, and resolved its interrupt. Locally, tutor-audience text reached the anonymous response verbatim |
| **AUD-C-02** | **Launch journey** | **P1** | **Fixed and live-verified 2026-07-28 (D-111 + D-112)**: D-111's topic fix alone was **measured insufficient** — with it live, "What is IntelliChoice?" was still refused or bounced to clarification 3/3 on real Bedrock. Closing it took D-112's intent *definitions* + pinned examples in the same prompt. Post-fix: **3/3 grounded answers citing About IntelliChoice** ("Who leads…" 3/3, "people who run…" 3/3, from an `admin_contact` misroute). Static guards: `test_scope_prompt_spec_coverage.py` (topics) + `test_scope_prompt_defines_intents` (definitions); behaviour: `paraphrase` eval cases on the real-Bedrock runner | Original: The `SCOPE_AND_INTENT` prompt's topic list omits SPEC §5.19.4's first supported topic ("IntelliChoice organization"), so live staging refuses **"What is IntelliChoice?"** as out of scope, 5/5. The mock's keyword list contains `"intellichoice"`, so no test could see it |
| **AUD-C-03** | **Minors / PII** | **P1** | **Fixed 2026-07-28 (D-113), verified live on staging 2026-07-29**: `purge_resume_writes` deletes the thread's `__resume__` rows immediately after a `location_consent` resume completes — the finding's own targeted delete, keeping crash-safety for exactly the window it covers. Regression test drives the real endpoints + real `AsyncPostgresSaver` and decodes blobs with LangGraph's own serializer (msgpack-aware, honoring the finding's method note); watched failing pre-fix with the audit's exact two `__resume__` rows. **Post-deploy staging probe (deploy `9467c78`): a real-coordinates locator turn answered with distances, then an ops-task query found 0 `__resume__` rows and the coordinates' raw float64 bytes absent from every surviving blob** | Original: A caller's precise coordinates persist indefinitely in `checkpoint_writes.__resume__`, contradicting the consent notice's verbatim promise not to store them. D-045 called this "briefly"; nothing purges it, and D-045's "not eliminable" is wrong — a targeted delete works |
| AUD-C-04 | Correctness / UX | P2 | **Fixed in S40** (D-107) | Last turn's result is cleared in `resolve_role`, the one node every turn passes through first — reset on entry rather than in each pausing node, because there are several and the next one added would have to remember. `ics_content` included. **The regression test needed a genuinely paused turn:** a first version using two ordinary turns passed with the fix removed, because an ordinary turn overwrites every field on its way through. Original: A turn that pauses on `interrupt()` returns the *previous* turn's answer, citations and access hint (pausing nodes never return, so nothing resets them); `ics_content` is never cleared by anything and sticks to every later turn. The leak vehicle in AUD-C-01 |
| AUD-C-05 | Test integrity | P2 | **Partly addressed in S37** | The golden Q&A eval measures `MockBedrockProvider`, not retrieval: a real model rejects 10 of its 14 gating cases before retrieval runs, and `no_answer` scores 0/8 under the mock vs 8/8 real. Fixture extended and re-scored this session; the mock's quality categories are now measured, not gated |
| AUD-C-06 | SPEC conformance | P2 | ✅ **fixed across D-164 + D-165 (2026-08-03)** — routing widened *and* the probe can match; **2/3** live, the third case is answered by a public doc so it never reaches the probe | SPEC §18-C3's access-aware refusal fired **0 times in 8** under a real model: its precondition is zero-row retrieval, which real hybrid search essentially never produces. A parent gets "no approved source" instead of "log in to see the parent handbook" |
| **AUD-C-07** | **Robustness** | **P2** | **Fixed 2026-08-02 (D-155)** — `answer_document_qa` and `calendar_extract` (both `retrieve()` call sites, both reproductions) catch `BedrockGatewayError` and route to a new `service_unavailable` node; a narrow `BedrockGatewayError` handler on `app` makes any future gateway call a **503**, not a 500. Watched failing first: the raw exception escaped the node. | An embedding-provider failure or an exhausted budget on the retrieval path is an unhandled **500** — `retrieve()`'s `create_embedding` is the one uncaught gateway call, and chat-api has no exception handler. Violates §5.29's Bedrock-timeout row |
| **AUD-C-08** | **UX / diagnosability** | **P2** | **Fixed 2026-08-02 (D-155)** — `scope_guard`'s fail-closed branch is unchanged in *behaviour* and changed in *words*: it now yields the temporarily-unavailable message with `scope: null` (no classification happened) instead of the out-of-scope refusal, plus a `qa_service_degraded` warning log and a `stage`-labelled counter, so an outage no longer reads as a surge of off-topic questions. | A total Bedrock outage, or an exhausted cost ceiling, answers every in-scope question with the *out-of-scope* refusal — fail-closed but user-misleading, and indistinguishable from a genuine refusal in logs |
| AUD-C-09 | SPEC conformance | P2 | **Dispositioned — not applicable (D-170, 2026-08-03)** | **The predicate does not apply to this corpus** (user's call): the handbook set is unified, not partitioned by academic year, so retrieval scopes on approved/effective document state plus role access instead of an academic-year equality filter. Recorded at both layers so it is not re-filed — `role_access_filter`'s docstring now says "five of six predicates, by decision", and `ChunkFilters.academic_year` says it is deliberately unset by the access path and kept only for ingestion-time queries. Original: §5.21.3's sixth predicate is never applied at query time; a 2019-2020 chunk was retrievable by every audience. Fully masked while the corpus holds one academic year |
| **AUD-C-10** | **Frontend contract** | **P2** | **Fixed 2026-08-02 (D-155)** — `ChatTurn` gained an `error` field, so a turn has three states instead of two; a failed turn renders a retryable error bubble and `Thinking…` is gated on *not* having failed. The e2e documented-defect test was inverted into a regression test exactly as it said it should be, and watched failing against the pre-fix render gate. | Any API error leaves chat-web's turn stuck on `Thinking…` permanently — the transcript entry keeps `response: null` and nothing clears it. A §2.6 criterion-3 blank/stuck state, reachable from AUD-C-07 |
| AUD-C-11 | Correctness / UX | P2 | ✅ **fixed in D-164 (2026-08-03)** | The low-confidence branch returns the "I don't have an approved source" message *with* verified citations attached, so the UI shows a source beside a sentence denying one exists. Observed live |
| **AUD-C-19** | **UX / diagnosability** | **P3** | **Fixed in D-156** | Returns `SERVICE_UNAVAILABLE_MESSAGE` with `escalation_recommended = False` and `missing_information = None`. The deferred product call, decided: escalation is itself a Bedrock-and-MCP path, so recommending it during an outage walks the user into a second failure and books a branch manager for a question the corpus can answer — and the message already offers the human path *conditionally*, after a retry. Matches `graph.nodes.service_unavailable`, so the two outage paths are indistinguishable to the client. Original: the synthesis-failure path answered a Bedrock outage with `NO_SOURCE_MESSAGE` when a source demonstrably existed |
| **AUD-C-12** | **SPEC conformance** | **P3** | ✅ **fixed in D-172 §3 (2026-08-04)** | `retrieve` cuts at `MIN_RERANK_RELEVANCE_SCORE = 0.35` instead of `> 0.0`, so an empty result *is* the §5.21.8 trigger firing and the graph routes it to the no-source/access-hint path without paying for synthesis. **Measured, one real-model run at 38.49c** (`scripts/measure_retrieval_score_floor.py`): no unanswerable case scored above 0.30, the weakest answerable case's own document scored 0.60, so any floor in [0.30, 0.60) empties 24/24 unanswerable while keeping 20/20 answerable — 0.35 for margin, and the band is asserted by a test. Not applied on the reranker-degraded path (no scores ⇒ discarding everything would make an outage a corpus-wide "no approved source"). **The mock run keeps floor 0.0 by decision** — its reranker returns query-word coverage, a different quantity on the same scale (D-172 §4) |
| **AUD-C-13** | **Grounding** | **P3** | ✅ **fixed in D-172 §2 (2026-08-04)** | `MIN_CITATION_QUOTE_CHARS = 20`, applied to the AUD-C-18-normalized quote. **Measured over the real 144-chunk corpus** (`scripts/measure_citation_quote_floor.py`): a 1-char span occurs in a median of **140** chunks (0% unique), 2 in 74, 4 in 10, 8 in 2; at 20 the median is 1 and the p90 is 2, and 24/32/40 buy nothing more. The floor's *cost* was measured too — the five approved chunks under 20 chars are all bare markdown headings, asserted by `test_the_quote_floor_excludes_only_heading_chunks` so a future short standalone fact fails loudly instead of becoming uncitable. "≥20 or the whole chunk" was rejected: it re-admits exactly the heading-only citations. The prompt states the requirement and the drop is logged (`citation_quote_below_floor`, counts only). Original: the verbatim check accepts any non-empty substring, so a one-character quote verifies against nearly any chunk |
| AUD-C-14 | Contracts | P3 | ✅ **fixed in D-174 §5 (2026-08-04)**: `scope`/`intent` added to `RespondResponse` and populated from `result` exactly as `/messages` already did — the two builders were otherwise identical. Regression test asserts the field on the response **and** on the `SessionSnapshotEvent` re-validated from it, since the snapshot is what clients receive; it uses `/messages`' own values as a control that can fail, so a null cannot pass as "this journey never classifies". Watched failing pre-fix. **D-058's rule is now bidirectional:** keep `MessageResponse`, `RespondResponse` and `SessionSnapshotEvent` in step | Original: | `RespondResponse` omits `scope`/`intent`, so every SSE snapshot published after a `/respond` nulls them for connected clients — D-058's class, in the direction that decision did not name |
| AUD-C-15 | Audit trail | P3 | ✅ **fixed in D-174 §4 (2026-08-04)**: `start` moved above the lookup and the unknown-tool path now writes a `success=False` / `error_type="McpToolError"` row before raising. **Plus a second half the finding did not name:** an unknown `tool_name` is caller-controlled and lands in an *indexed* `mcp_tool_calls.tool_name` column with no length limit, so a long enough name makes the INSERT itself raise (Postgres btree entries cap at ~2704 bytes) — the audit write would fail on exactly the malicious input it exists to record. Bounded to 128 chars on **every** path, so the invariant does not depend on which branch audited. Two tests, both watched failing first (the first on `0 = len([])`, the defect's own signature) | Original: | `McpToolRegistry.call` raises on an unknown tool *before* any audit write, so the one call shape a wiring bug or injection would produce is the one that leaves no `mcp_tool_calls` row |
| **AUD-C-16** | **Launch journey / data integrity** | **P3 → P1** | **Fixed and live-verified 2026-07-28 (D-112)**: provenance columns stamped at ingest (NULL = unknown = mismatch), idempotent `make knowledge-reembed`, a deploy-step re-embed, and the load-bearing part — chat-api `/readyz` (the ALB health check) **fails closed** on corpus/runtime provenance mismatch, so this class can never again run silently. Staging re-embedded: **159/159 real Titan, 0/159 mock-like by S38's own discriminator** (max cos 0.078, was 159/159 at 1.0), 0.0224¢; the next deploy's re-embed was a 0-chunk/0-cent no-op. Paraphrase probes went from no-source refusals to **9/9 grounded answers with citations** | Stored embeddings are provider-specific with no provenance column and no re-embed path. **Settled by S38: staging's corpus is 159/159 `MockBedrockProvider` hash vectors** while both deployed services query with real Titan v2, so staging's semantic channel returns noise (peak cosine +0.074 vs +0.41 with real vectors) and hybrid search there has always been lexical-only. Live paraphrase citation rate **1/7** |
| **AUD-C-20** | SPEC conformance | P2 | ✅ **fixed in D-165 (2026-08-03), with a named limit** — semantic arm added and deployed; `role_gated_question` 0/3 → **2/3**. The threshold it ships with is too tight for human phrasing → **AUD-C-21** | The §18-C3 access probe matches with `websearch_to_tsquery`, which **ANDs every content word** of the question, so one absent word voids it — the parent chunk says "student" not "child", the branch-manager chunk has neither "escalation" nor "path". This is why the feature still scores **0/3** after AUD-C-06's routing fix: §18-C3 has never fired for a realistically-worded question on *either* entry path |
| **AUD-C-23** | Instrument / product correctness | P2 | ✅ fixed 2026-08-04 (D-177), **live-verified 2026-08-04 (D-178): 0/10 hints, control 3/3** | **The paid real-Bedrock coverage eval fails, and has been failing since D-168 landed** — nobody knew, because it is opt-in and was not re-run after that change. `wrong_role_hints` reports `no-answer-missed-1`: an anonymous caller asking *"What happens to a student who misses three sessions in a row?"* — a plausible in-scope question **nothing** answers — is told to log in as some role. **This is D-168's own recorded residual**: `access_probe_policy`'s table shows the shipped rule at **1 false hint on the unanswerable class** in the corpus-phrasing arm (0 in the human arm), and the eval asserts **zero on every category**. So the assertion and the accepted decision disagree, and one of them has to move. **Not caused by D-172** — reproduced identically with `CHAT_RETRIEVAL_MIN_RELEVANCE_SCORE` at 0.35 and at 0.0. **⚠️ Re-scoped 2026-08-04 (D-173): "observed live" was wrong, and the correction changes the fork.** Probed anonymously against the *deployed* edge three times, this question returns **`access_hint: null`** and refuses correctly — the deployed system does not exhibit it. Verified against a control that can fail (a question known to trigger a hint still returns `required_role: "parent"` there, which incidentally confirms AUD-C-22's fix live against D-166's recorded `"branch_manager"`). So this is a property of the **local eval fixture corpus**, and the first question is why the two corpora disagree — not which of the two original forks to take, since tuning the rule on the eval's evidence would tune it against a corpus no user meets. **⚠️⚠️ Re-scoped again 2026-08-04 (D-175), and this time in the other direction: it DOES reproduce live, 6 times in 10.** The corpora were then measured identical (D-174), and 10 anonymous probes of the deployed edge — the sample D-174 said three could not substitute for — returned `required_role: "branch_manager"` on **6** and a correct `null` refusal on **4**, same question, same corpus, same config. So the eval was right all along, the "deployed system does not exhibit this" claim was a **sampling artefact**, and **hypothesis (1) harness-vs-route is dead as an explanation while (2) nondeterminism is confirmed**. The original fork reopens with much worse numbers: 60% of real anonymous askers of an ordinary unanswerable question are told to go get a branch-manager account. **Needs a rule decision (tighten the margin vs. tolerate a named case) plus a re-measurement, not a quiet tune** **✅ Fixed 2026-08-04 (D-177), and the re-measurement moved the fix off the knob the fork named.** The user chose re-measure-and-tighten; the new `--stability` sweep (10 reranks per case per arm, sample size fixed before the run) showed the tier margin never applied on this case (runner-up at 0.2–0.3) — the winner's score straddles the 0.8 **floor** (0.75–0.90 observed, max 0.90). Raising the floor alone resurrects AUD-C-22 (corpus-arm attendance control: bm 0.95/parent 0.90, floor-first truncation names the wrong tier 3/10), so the fix is both: `ACCESS_PROBE_RERANK_MIN_SCORE` 0.8→0.9 **and** the margin computed over pre-floor per-audience bests (`probe_access`). Both arms: 0 wrong tiers, 0 FP on both negative classes, 0/40 stability fires; cost 2–3 rights (of 38) become silences. The paid eval's `wrong_role_hints` assertion — red since D-168 — passed (`no_answer` 8/8, incl. this case; the one `role_gated_question` miss is a silence). Total measurement cost 55¢. Live behavior changes only at deploy; the owed live check is 10 anonymous probes of this question **✅ Live-verified 2026-08-04 (D-178), and this is the only evidence that covers production's *composed* path** (floor + margin + lexical arm together — see AUD-C-25 for why no offline table did). Against `chat-api:63` / `gha-e1ab0adbacb4`: **0 of 10** anonymous probes returned an `access_hint`, all 10 a correct `null` refusal (`scope=in_scope`, `citations=0`), where D-175 measured **6/10 `required_role: "branch_manager"`**. The control fired **3/3** with the correct `required_role: "parent"`, so the instrument was live and the run is not a silent-everything artefact — three rather than D-173's one, because this rule converts 2–3 of 38 hints into silences and a single silent control could not be told from a control the rule legitimately retired. **What 0/10 does and does not establish, stated so nobody re-reads it as "never":** under the old 60% rate, 0/10 has probability **0.01%**, so the 6/10 behaviour is refuted decisively; but 0/10 bounds the residual flip rate only at **<26% (one-sided 95%)** — a 10% residual would still produce 0/10 about 35% of the time. The sample size that was adequate to *detect* a 60% rate is not adequate to *certify* a low one, which is the second half of D-175's lesson and the direction it did not state |
| **AUD-C-22** | SPEC conformance | P2 | ✅ **fixed in D-168 (2026-08-03), not deployed** — the probe became the reranked pipeline it was paraphrasing: **29/38 and 28/38** correct audiences across both phrasings with **zero wrong tiers on either**, against 23/38 with 1 and 4. The filed fix shape ("pick the closest") was measured and scores *identically* to the rule it replaces. The motivating question now returns **silence** rather than the wrong tier — two tiers legitimately compete for it | `build_access_hint` picks the highest-**priority** tier (`branch_manager, tutor, parent, student`), never the **closest** one, and the probe hands it counts rather than distances so the information is already gone. Live, on AUD-C-21's own motivating question, a parent asking about their child's attendance is now told to *"log in with a branch manager account"* — the chunk that answers it is the parent one, measured at 0.499. **Widening the ceiling cannot fix this**: at any ceiling ≥0.499 priority still answers branch_manager |
| **AUD-C-21** | SPEC conformance / instrument | P2 | ✅ **fixed in D-166 (2026-08-03)** — ceiling **0.40 → 0.45** against a blind-rewrite fixture: **17/38 → 23/38** correct roles with **zero** false hints on either negative class, verified live (`no_answer` 8/8, and 8/8 false hints at a loosened 0.95, so the check can fail). **⚠️ The probe now fires and the live case names the wrong tier → AUD-C-22** | `access_probe_max_distance = 0.40` is too tight for how people actually phrase questions: the *fixture's own* parent-attendance case sits at **0.418** and a human wording of the same question at **~0.60**, both misses, while the correct chunk is at 0.499. Root cause is the instrument, not the code — a question **generated from** a chunk sits closer to it than a person's phrasing does, so 25/43 at ≤0.40 was true of the fixture and optimistic about users. Needs a human-phrased validation set before the ceiling moves; ≤0.55 already produces false hints on unanswerable questions, so this is a real trade, not a free widening |
| **AUD-X-01** | **Authorization** | **P1** | **Fixed in S40** (D-107) | Fixed in `graph/nodes.py: resolve_student`, which now refuses to move a session to a different student — applied before the role split, so it covers the tutor branch that took `requested_student_id` unvalidated. The legitimate parent rebind is untouched: it pauses at `await_child_selection`, which re-checks the live link on resume. Re-verified live on staging with a before/after pair. Original: `POST /sessions/{id}/student` never checks who already owns the session: a different student claimed an in-progress exam session, the owner was **locked out with 403**, and their `in_progress` assessment row was orphaned. Same structure as AUD-C-01 — the one route that *writes* the identity field all 17 others read is the one that does not check it |
| **AUD-X-02** | **Minors / child safety** | **P1** | **Fixed in S40** (D-107) | Fixed via `intellichoice_shared.auth.account_refusal_reason`, consumed by both apps' `get_current_claims` **and both SSE routes** — the streams verify `?token=` directly and never pass through the dependency, so the gate had to be repeated rather than inherited (AUD-F-13's split-path shape). 403, not 401. The age-band exempt set is deliberately **empty** until S42 measures the real vocabulary, so every student needs verified parental consent today: stricter than §5.1.2's literal "under 13" wording, and the right way round to be wrong. AUD-X-02's warning that this sits in the S44/S45 seam is addressed by landing the *consuming* side first, so neither session can ship without something already reading its output. Original: SPEC §5.1.2's *"should verify `parental_consent_verified=true`"* has no implementation: that claim plus `account_status` and `consent_status` are carried in every token and read by **nothing**. A `suspended`/`revoked`/unverified/`under_13` token behaved identically to a consented one on all 18 learning routes |
| **AUD-X-03** | **Data integrity** | **P2** | **Fixed in D-159** | `flow.is_topic_selection_replay` decides what a second `/topics` means from session state alone: a replay of the same topic while still in `pre_exam` is served **from the existing exam, item for item**; a different topic, or a phase that has advanced, is **409**. Pre-flighted in the route (no graph turn, no checkpoint rows) and re-checked in the node. The guard is "a pre-exam exists", not "the phase is pre_exam" — the damage was worse after finalize, where the rebuild repointed `pre_assessment_session_id` while a study session was live off the old exam. The **blocked** path builds nothing and stays fully replayable, which is what keeps D-152 §2's routine UNKNOWN attendance recoverable. Original: a replay built a whole second exam (+1 session, +10 items, different variants) and orphaned the first |
| **AUD-X-04** | **Money / correctness** | **P3** | **Fixed in D-159** | `POST /students/{id}/report` requires `Idempotency-Key`, as `POST /answers` already did. Three layers: a replay lookup ahead of the cost reservation (so a replay spends nothing), `uq_student_reports_student_audience_key` for the concurrent arm, and a **409** when one key is reused for a different date range (serving the stored row would put last month's numbers under this month's heading). Scoped to (student, audience, key), never to a time window — this table is history a parent re-opens. **Not fixed:** two *truly concurrent* calls under one key both reach Bedrock before either inserts, so the duplicate row is prevented and the duplicate spend is not; AUD-L-02's ceiling bounds it. Original: two clicks, two paid calls, two rows |
| **AUD-X-05** | **Authorization** | **P1** | **Write half fixed in S40** (D-107); read half stays with AUD-L-07/D-086 → S43/S46 | `resolve_target_student` now takes a **required** `access: Literal["read","write"]` and refuses `write` for these two roles; all 14 call sites are classified, 9 write / 5 read. Required rather than defaulted because the recurring defect in this codebase is a route quietly getting the permissive branch (AUD-C-01, AUD-X-01, AUD-X-05 are each "the one route nobody classified"). **`POST /students/{id}/report` is classified `read` despite being a POST** — the existing suite caught the "write" version, which would have ended tutor report generation outright; AUD-L-07 files report generation under the read-scope gap S43/S46 own, so that stays their decision, not a side effect of this fix. Original: AUD-L-07's tutor/branch_manager fall-through extends to **writes**: a tutor token answered and **finalized another student's exam** (200), and can bind any session to any student id. Fabricated attempts are indistinguishable from the student's own and feed scoring, mastery and learning-gain |
| **AUD-X-07** | **Data integrity / launch journey** | **P1** | **Partially fixed in S42** (D-110 §3); remaining halves **accepted as residual risk 2026-07-30 (D-123) — §7-R9**, void if `learning_checkpoint_repairs_total` moves | Fix shape (2) landed for **seam (a) only**: `services/checkpoint_reconcile.py` detects a checkpointed row id whose row does not exist and rolls the checkpoint *backwards* to what the database supports, wired into `_get_state_values` and `/resume` and counted by `learning_checkpoint_repairs_total`. S38's mid-finalize reproduction is now a test asserting recovery, and fails `'study' == 'pre_exam'` with the fix disabled. **Seam (b) (mid-interrupt) is not fixed and no detection code for it shipped** — the session is paused on a LangGraph task and recovery means completing that node, not editing channel values. **Fix shape (1), the commit ordering itself, is untouched.** Original: The checkpoint commits inside `ainvoke` while domain rows commit at FastAPI dependency teardown, so any failure between them keeps the graph's state and discards the database's. Reproduced at both seams: mid-finalize leaves a scored exam `in_progress` with a dangling `study_session_id` (a reloading client is served a study question, then **500s forever**), and mid-interrupt leaves a pending `intervention_choice` for an attempt row that does not exist (`/respond` **500s** and the interrupt never clears). A task stop during any deploy enters this window with no bug required |
| **AUD-X-08** | **Money** | **P1** | **Fixed in S42** (D-110 §2) | `cost_reservations` + `pg_advisory_xact_lock`: the worst-case cost is reserved in its own immediately-committed transaction before the model call and settled with the real cost after, so an in-flight call is visible to concurrent callers. Both ceilings (report, tutor chat) converted; the two spend readers that were the defect are deleted. **Re-measured with a concurrent arm as D-102 required: 10/10 generated at 10.0× the ceiling → 1/10 at 1.0×.** Note the reproduction itself needed fixing first — with `MockBedrockProvider`'s ~0 ms call the race window nearly vanishes and the *unfixed* code measured 1/10, i.e. it looked already fixed. **Still open:** the per-session gateway budget, stateless by design (D-072). Original: Every per-day cost ceiling is read-then-act with the cost row committed at teardown. **10 concurrent reports produced 8 generated reports and 8.0× the ceiling**, while the sequential control correctly degraded — a correct check with no serialization. Weakens AUD-L-02's P0 fix; a single caller can drive it since AUD-X-04 leaves the route non-idempotent |
| AUD-X-06 | Test integrity | P3 | **Fixed in S38** | A hint test asserted a plain substring where the product's `answer_text_leaked` is boundary-aware, so it demanded more than the product guarantees and the mock's own `hint lN` prefix collided whenever the drawn answer was `"1"`–`"3"` (**17.9%** of the bank; measured **15/70**). Fixed by asserting the product's own rule: **0/40**, and three consecutive green suites. **AUD-L-17 did not regress** — it pinned a *different* test, still 0/20; its mock change *unmasked* this one |

| **AUD-F-01** | **Cost / latency** | **P1** | **Fixed in S41** (D-109) | `App.tsx` now destructures `fetchExamOverview`/`recordItemTime` by name and passes the memoized functions through — reading them off `session` at the call site would have re-created the `useCallback` every render and reintroduced the defect, since the hook returns a fresh object each time. **Re-verified by counting requests, per D-103 §2, not by checking the screen still works.** Same 15-second single-question dwell, current code, fresh servers: **899 → 1 `POST .../time`** (longest report 68 ms → **15,009 ms**, i.e. the actual dwell) and **903 → 2 `GET /exam/overview`**. Both counts are now asserted by `tests/learning/time-telemetry.spec.ts`, promoted from a `test.fail()` probe and confirmed to fail with the fix reverted (**849 / 849** on the control run). Original: `App.tsx` passes `onFetchOverview` and `onRecordTime` as **inline arrows**, so they are new identities on every render, and both sit in `ExamScreen` effect dependency arrays — every render tears the effect down and re-runs it. Measured: **885 `POST /exam/items/{id}/time` in a 15-second dwell on one question (~59/s)**, each carrying the ~20 ms gap between two renders; and **76 `GET /exam/overview` for a single 10-item exam, median 30 ms apart against the declared `OVERVIEW_POLL_MS = 20000`** — a ~667× amplification. Both are database writes/reads on the main journey's hot path |
| **AUD-F-02** | **Frontend contract** | **P2** | **Fixed in S41** (D-109) | **Not the same root cause as AUD-F-01 after all, and the measurement is what showed it.** Fixing AUD-F-01 took the burst from **35 × 409 to 1** — the survivor is the view-time autosave flushing on unmount, and the screen unmounts *because* the exam was finalized. `ExamScreen` now tracks the finalize in a ref that suppresses both the flush and the poll tick. **The ref must be raised *before* awaiting `onFinalize`:** `finalizeExam` calls `setSnapshot` inside the awaited request, so React flushes that render — unmounting the screen and running the cleanup — in a microtask that lands before the `await` resumes. Setting it after the await left the 409 in place on every run; browser instrumentation reported `phase=pre_exam finalized=false` for the last item each time. Now **0 × 409, 0 console errors**; `tests/learning/post-finalize-poll.spec.ts` is promoted from `test.fail()` and was confirmed to fail again with the ref moved back after the await. Original: After `POST /exam/finalize` returns 200 the client keeps calling the exam endpoints: **35 × 409 in a 96 ms burst** (33 `exam/overview` + 2 `exam/items/{id}/time`), zero after 5 s, with no exam screen even mounted. Each failed fetch is a browser console error, so **§2.6 criterion 3's "zero console errors" cannot be met while this exists**. Same root cause as AUD-F-01 |
| **AUD-F-03** | **Launch journey** | **P2** | ✅ **fixed in D-173 §1 (2026-08-04)** | `ExamScreen` derives the opening position from the exam overview — the first item whose `status` is not `answered`, applied **once per phase** via a phase-valued ref. Not persisted: the overview endpoint's own docstring says it exists to "restore item statuses after a mid-exam refresh", so the server already answered this and a `sessionStorage` copy would have been a second source of truth. The one-shot is load-bearing, not tidiness — re-deriving on each 20 s poll would yank a student off an answered question they had navigated back to review, which is worse than the defect; `exam-position-refresh.spec.ts` is that scenario. **Residual stated in the code:** this restores *the first item still needing an answer*, not literally the last question on screen, because nothing server-side records view position (`time_spent_ms` is cumulative and unordered); they differ when a student skips forward. The existing `test.fail()` probe in `journey-student.spec.ts` was promoted exactly as its own marker instructed, and watched failing pre-fix. Original: measured going from **"Question 3 of 10" to "Question 1 of 10"** |
| AUD-F-04 | Frontend contract | P3 | ✅ **fixed in D-173 §2 (2026-08-04)** | Both narrative gates moved into `useNarrativeGate` — one `sessionStorage` record keyed by **learning session id**. **The finding named one door and there were two:** `dismissedNarrative` is the explicit one, but `interactedPhase` (AUD-F-21's "drop a narrative once the student has started working") was also React state, so after a reload a narrative the student had worked past returned without ever having been dismissed. Persisting only the named field would have left the defect reproducible through the other path. The session-id key is not optional either: dismissal is keyed by narrative *text* (S26), and the welcome narrative is frequently identical across sessions, so text alone would have made a new session's first narrative arrive pre-dismissed. `narrative-refresh.spec.ts` asserted the defect by design and its assertion is now inverted; watched failing pre-fix with the exact recorded text. Original: dismissal was React state while `stage_narrative` persists in the snapshot |
| AUD-F-05 | Frontend contract | P3 | ✅ **already fixed by AUD-F-21; status corrected 2026-08-04 (D-173 §3)** | **No new code — this was fixed as collateral and the table never said so.** AUD-F-21 restructured `App.tsx` so the narrative renders *above* the phase screen in a two-slot Fragment instead of returning `StageTransitionScreen` as a sibling branch, which is precisely this finding's mechanism ("gates it ahead of every phase branch"). It also already has a passing regression test written to this finding's own subject — `narrative-displacement.spec.ts` arm 3, "when a narrative shows before the student has acted, the screen beneath it survives", which asserts the topic list is visible *beneath* the narrative. The severe half (unmount, detached buttons mid-click, `useState(0)` re-running) is therefore gone; what remains is a layout shift as the narrative pushes the screen down, which is not what this finding describes. Verified by reading the fix and running the arm, not by re-measuring the ~26 ms window. Original: the narrative displaced the screen already in use |
| **AUD-F-06** | **Operations** | **P2** | **Fixed in S40** (D-105) — `chat-purge` + `memory-consolidate` schedules live since 2026-07-26; criterion 6's one-week clock started then | Original: **No scheduled jobs exist at all**: zero EventBridge rules and zero EventBridge Scheduler schedules in the account. The four jobs are `make` targets a human runs — and only **three** of them are schedulable at all: `webcontent-sync` rewrites tracked `knowledge-content/` files and asks for a human diff review, so §2.5's work item should be re-scoped to three. §2.6 criterion 6 ("all scheduled jobs ran on schedule for ≥ 1 week with zero manual intervention") is therefore not merely unmet but **unstartable** — the one-week clock cannot begin until the schedules land, so **the earliest possible gate pass is one week after that Phase 0B item ships**. A scheduling fact about the whole milestone, not just a defect |
| **AUD-F-07** | **Money** | **P2** | **Closed in S40 — premise false on staging** (D-105): staging has zero `loadtest-` rows (`semantic_memory` there was empty); the 150 fixtures are local-dev-only, so no scheduled run spends real money on them. Local cleanup stays optional | Original: `make memory-consolidate` processes **160 students and reports 145.97 cents in one unattended run**, and **150 of the 159 students with memory rows are `loadtest-student-N` fixtures left behind by S34's load test** — 94% of the job's paid work is synthetic. Locally the provider is the mock, so the figure is the accounting layer's projection rather than a real charge; against staging's real Bedrock it would be real money, recurring on every scheduled run. Must be resolved *before* AUD-F-06's schedules are created, not after |
| AUD-F-08 | CI coverage | P3 | **Fixed 2026-07-28 (D-111)**: `ci.yml` gained a `chat-web` job (lint + `tsc -b` build, mirroring `learning-web`) and an `e2e-typecheck` job (`tsc --noEmit`, no browser). Criterion 4's "CI builds and tests every deployable" is now met to the depth the packages offer — neither frontend has a test script; typecheck rides inside `build` | Original: CI builds and tests `learning-web` but has **no job for `chat-web`** (already on the Phase 0B list) and none for the new `e2e/` harness. Two of the four deployables are therefore unbuilt by CI, against §2.6 criterion 4's "CI builds and tests every deployable" |
| AUD-F-09 | Deploy pipeline | P2 | **Fixed in S39** | `deploy-staging.yml` rewrote the image tag on **every** container in the task definition. Harmless with one container — but the moment the OTel sidecar was added it would have rewritten `aws-otel-collector:v0.43.3` to `aws-otel-collector:gha-<sha>`, an image that does not exist, and every deploy would have crash-looped into a circuit-breaker rollback. Caught while adding the sidecar, before it shipped; the patch is now scoped to the app container by name, with an assertion that exactly one matches |

| **AUD-F-15** | **Retention / deployment config** | **P1** | **Fixed in S40** | **`chat-purge` could not reach the database in the deployed environment at all, so the 90-day retention promise had never once executed against real data.** It called `create_engine(get_settings().database_url)`, and `learning_api.config` uses `env_prefix="LEARNING_"` — so inside the ops task, which supplies D-092's *unprefixed* components, `settings.database_url` silently stayed at its hardcoded `localhost` default. The first scheduled run died with `ConnectionRefusedError: Connect call failed ('127.0.0.1', 5432)`. Invisible locally by construction: on a developer's machine localhost **is** the database, so every `make chat-purge` and every unit test passed. **Third instance of this exact shape** (`create_engine`'s own docstring records the S32/D-084 `curriculum-load` one), so the fix ships with a guard test over every standalone CLI plus a negative arm asserting the two FastAPI apps still pass their URL explicitly |

| **AUD-F-14** | **Capacity / latency** | **P1** | **Fixed and live-verified 2026-07-28 (D-113)**: chat-api's scaling signal is now ALB `TargetResponseTime` p95 step scaling (out: >3 s ×2 min, +1/+2 by severity; in: <1 s *or no traffic* ×15 min, −1), **replacing** CPU tracking for that service — target-tracking's scale-in would read this incident's ~5% CPU as idleness and undo the scale-out, so the policies cannot coexist. Verified under sustained 5-concurrent live load: ALARM within 2 min, desiredCount **1 → 3 in one step**, 0 errors across 114 turns. **But the re-baseline found the baseline gone**: a single unloaded grounded turn now costs ~29 s (the audit's 1.6 s predates D-112's real corpus), so criterion 7's 3 s threshold leg needs recalibration — or better, the undiagnosed ~26 s embedding→answer gap (no rerank log line) removed first. Learning-api stays on CPU tracking: no measurement says otherwise | Original: **Five concurrent chat turns take ~30 s each, and the autoscaling policy cannot see it.** Measured live: 1.62 s unloaded → p50 **26.92 s** / p95 **32.14 s** at concurrency 5, all 200s (it queues, it does not fail). ALB p95 per minute 3.56 → 31.97 → 30.96 → 30.98 s against a 3.0 s threshold. The defect is not the capacity fact but that **nothing can react**: Application Auto Scaling is a single `ECSServiceAverageCPUUtilization` target-tracking policy at 70%, and this workload waits on Bedrock rather than computing — CPU **peaked at 15.19%** during the 31 s window, so `desiredCount` never left 1. **Criterion 7's "≥2 tasks under load" is unreachable as configured.** Sharpens D-095: S34 diagnosed the single-worker bottleneck correctly and added autoscaling that the bottleneck cannot trigger — invisible from a docker-compose run against the mock |

| **AUD-F-38** | **Deploy pipeline** | **P2** | ✅ **fixed in D-173 §6 (2026-08-04)**: the gate now asserts what it actually needs — the PRIMARY task definition serves this commit's image and `runningCount ≥ 1` — and bound-retries `rolloutState` for 300 s instead of requiring `COMPLETED` at one instant. **Narrower, not weaker:** `FAILED` fails immediately and is never retried into a pass, a wrong image tag fails immediately *including while IN_PROGRESS* (waiting cannot fix a stale image, so that check sits ahead of the retry), and `runningCount < 1` fails since it is the one state that would make the tag check vacuous. Only `runningCount == desiredCount` was dropped, because during a legitimate scale-out `running(2) < desired(3)` says nothing about the deploy. If the rollout is still in progress at the deadline with the right image, it passes with a `::warning`. **Verified before shipping, against 7 stubbed deployment states** (the harness extracts the step from the YAML exactly as the runner sees it): healthy→pass, wrong-tag-completed→fail, `FAILED`→fail, wrong-tag-while-pending→fail **in 0 s**, AUD-F-38's own 2/3-then-completed→pass via one retry, past-deadline→pass with the warning, `runningCount 0`→fail. Original: | **An autoscaling event during a rollout fails the deployed-version gate, and the pipeline then skips every remaining verification while leaving the new image live and un-rolled-back.** Run [30884342749](https://github.com/lucasjeongsikpark/IntelliChoice/actions/runs/30884342749) failed with `intellichoice-staging-chat-api: deployment is PRIMARY/IN_PROGRESS, not PRIMARY/COMPLETED` — after `aws ecs wait services-stable` had already returned successfully for that service. Cause, from `describe-scaling-activities`: `chat-api-p95-latency-scale-out` fired at **06:29 and 06:33 UTC**, taking desiredCount **1 → 3**, and the deploy dispatched at 06:32. `wait services-stable` saw a momentarily consistent state and returned; autoscaling then raised desiredCount underneath it and the rollout re-entered `IN_PROGRESS`, which the gate reads at 06:47 as a failed deploy. **The gate is not wrong about what it measured — it is measuring the wrong thing:** it conflates "this rollout is not finished" with "this deployment is bad". The artifact was in fact correct (both services `gha-70a764315664`, revisions 59/58, both `PRIMARY/COMPLETED` minutes later). **The consequence is a half-verified deploy that looks like a failed one:** the security gate, the canary bake, the frontend build/S3 sync and the smoke test all `skipped`, and so did the rollback — so nothing watched for alarms while the new code served traffic. All four were completed by hand for this deploy (4/4 `/dev/token` → 404, 0/4 canary alarms breached, both edges 200, no frontend delta to sync). **What makes this more than a flake: the load came from the project's own recommended practice.** D-171 §(a) tells a session to run any verification whose evidence a deploy overwrites *before* the deploy; those probes are real-Bedrock chat turns, which are I/O-bound and slow (AUD-F-14: CPU 15% while p95 sat at 31 s), so they trip the p95 scale-out policy. Pre-deploy verification therefore *causes* this failure, and will keep causing it. **Same family as AUD-F-33** — an autoscaling signal read as a deploy signal, which is why `chat-api-capacity-above-floor` was deliberately kept off the canary list. Fix shape: gate on the PRIMARY task definition's **image tag** plus `runningCount ≥ 1`, and either tolerate `IN_PROGRESS` or bound-retry it, rather than requiring `COMPLETED` at one instant |
| **AUD-F-16** | **Audit integrity / harness** | **P2** | ✅ **fixed and live-verified 2026-07-29 (D-116); this row read `Open — before the gate` until 2026-08-04, D-174** | **⚠️ Status corrected, and the mechanism has been supplying evidence the whole time.** D-116 built the identity check on **ECS** rather than an HTTP self-report — `/healthz` is deliberately excluded from CloudFront, so the first staging run fetched `index.html` and said so — and read the image tag off the running task definition, which is stronger evidence than a self-report. `e2e/fixtures/build-identity.ts` + `global-setup.ts` are that fix, and D-173's staging run printed `[build-identity] learning-api sha=d3b9d3ede59c` / `chat-api sha=d3b9d3ede59c`, which is how the deployed commit got its third independent confirmation. **Every backlog count since has carried this finding as open, including the post-D-173 pointer's "8, 9 counting AUD-F-16".** Original: | **The browser audit silently measured two-day-old application code.** `playwright.config.ts` sets `reuseExistingServer: true`, and the `uvicorn` processes on 8001/8002 had been up since **2026-07-25 21:31** — started before S40's four authorization fixes and D-106 merged. Playwright starts and tears down the two vite dev servers each run, so the *frontends* were always current while the *APIs* were frozen, which is the worst version: nothing looks stale. Every S39 and S40 e2e result against `local` is therefore of an unknown application version. A run needs to record, and preferably assert, what it is testing — the API build/boot identity belongs in `journeys.jsonl` alongside the console and network evidence. **Related, dev-only:** both apps raise every error response *outside* `CORSMiddleware` (the rate limiter is registered after it, and unhandled exceptions bypass it), so a 429 or 500 reaches the browser with no `Access-Control-Allow-Origin` and is reported as an opaque `net::ERR_FAILED` CORS violation rather than its status. Two such teardown failures were seen against the stale servers and none across five full runs on fresh ones — consistent with the stale-server reading, not proof of it. Staging is same-origin (D-084), so the CORS half does not apply there |
| **AUD-F-17** | **Audit integrity / harness** | **P2** | **Fixed in S42** (D-110 §4) | **`make e2e-staging` did not point at staging, and never had.** `E2E_TARGET=staging` selects the auth path (out-of-band token minting, D-097) but does *not* retarget the browser: `e2e/config.ts` defaults `LEARNING_WEB`/`CHAT_WEB` to `localhost:5173`/`5174` regardless of target, and only `LEARNING_WEB_URL`/`CHAT_WEB_URL` move them — which the Makefile target never set. Run against the deployed stack it produced **2 passed, everything else `net::ERR_CONNECTION_REFUSED` at `http://localhost:5173/`**; the 2 that passed are the two specs that never open a page. Supplying the two CloudFront URLs makes the same smoke spec go **0/4 → 4/4**. This is why criterion 3's staging half stayed open across S39–S41 while being described as one command away: the command did not work, and its failure mode (connection refused to localhost) reads as a local-environment problem rather than a harness defect. Fixed by setting both URLs in the Makefile target, defaulted to `deploy-staging.yml`'s own `LEARNING_CF_DOMAIN`/`CHAT_CF_DOMAIN` and overridable per environment |
| **AUD-F-18** | **Audit integrity / harness** | **P2** | **Fixed in S42** (D-110 §4) | **The staging target's auth path existed but no journey used it.** `fixtures/session.ts` has described out-of-band token minting as *the* staging path since the harness was written — staging's `/dev/token` is secret-gated (D-097) and the frontend sends no header, so the dev-login screen renders **`Not Found`** under its Sign in button there. But all ten journey specs called `signInViaUi`, which drives that screen. First time the staging suite actually ran (after AUD-F-17): **34 passed, 18 failed, and every one of the 18 was this.** Fixed by having `signInViaUi` delegate to `mintToken` + `seedSession` when `TARGET === "staging"`. The one test whose *subject* is the login screen now skips on staging with a stated reason rather than passing vacuously through the shortcut — a skip that should disappear with S44's real login. **Pairs with AUD-F-17:** two independent defects between the documented command and a working staging run, on a criterion described for three sessions as one command away |
| **AUD-F-19** | **Launch journey / chat correctness** | **P1** | **Fixed and live-verified 2026-07-28 (D-112)**: the two mechanisms were different. **(b)'s three-different-products was AUD-C-16's retrieval noise** — with real vectors it routes `document_qa` 3/3; the remaining no-source is the date filter failing closed **correctly** (`public-student-participation-guide` is `effective_from` 2026-08-01, re-check then). **(a) was the intent list naming intents without defining them** — fixed with definitions + pinned examples (D-112 §2, with AUD-C-02's verification leg); post-fix "What are the Saturday hours?" answers **3/3 with a Branch Directory citation** (was 0/6 across S42 + the same-day baseline). Guards: `test_scope_prompt_defines_intents` + two `paraphrase` eval cases | **On real Bedrock the guest launch journey's canonical question is never answered, and a second one routes three different ways in three consecutive calls.** Measured directly against staging, not through the browser. **(a) "What are the Saturday hours?" → `location_consent` interrupt, 3/3**, `answer: null` — the guest is shown a location-consent modal instead of opening hours, so the rendered bubble sits on "Thinking…" forever. **(b) "How do I enroll a student?" over three identical calls returned a scope refusal, then a no-approved-source refusal, then an `email_approval` interrupt** — same question, same guest, three different products. Accounts for all 5 chat failures in the first real staging run. **Neither is visible locally:** `MockBedrockProvider`'s keyword routing is deterministic and does not misroute these, which is AUD-C-02's lesson repeating on a second surface. (b) is plausibly downstream of **AUD-C-16** — staging's corpus is 159/159 mock hash vectors, so retrieval is noise and the graph falls to whichever ungrounded branch it reaches first. Chat latency is **not** the cause and was ruled out: a guest turn completes in **1.4 s** |
| **AUD-F-20** | **Environment / audit integrity** | **P2** | **Fixed 2026-07-28 (D-111), effective on next dispatched deploy**: `deploy-staging.yml` re-runs the idempotent seeder via the ops task after migrations, and `mysql_fixtures.py` now computes `week_key` at call time instead of import time. Until a deploy runs, staging stays blocked (seeded week has passed) | Original: **Staging's launch journey expires weekly.** `mysql_fixtures.seed()` writes attendance for `current_week_key()` *at seed time*, and staging was seeded in an earlier week, so `student-ext-1` — the "present this week" fixture — now has no attendance row for the current week. The gate fails closed exactly as SPEC §5.4.4 requires and returns `phase=blocked`, which is **correct behaviour on stale data, not a bug in the gate**. Consequence for the gate criteria: every learning journey on staging fails until the fixtures are re-seeded, and any criterion-3 evidence gathered on staging is only valid **within the week it was seeded**. Needs either a re-seed step in `deploy-staging.yml` or a scheduled re-seed; until then "two consecutive passes against live staging" has a silent expiry date |
| **AUD-F-13** | **Credential in observability store** | **P1** | **Fixed in S39 continuation** | **A bearer JWT is recorded in `http.url` on every SSE connection.** `EventSource` cannot set an `Authorization` header, so the stream authenticates as `?token=<JWT>`, and `FastAPIInstrumentor` records the full URL — a 455-character live token into X-Ray. The app's own access logger was unaffected (templated path, query string dropped), which is exactly why S38's log scan was clean: **the same request is sanitized in one store and not the other**, so a PII floor has to be re-established per store rather than inherited. Bounded impact (1-hour TTL, AWS access required, the captured token was already expired) so held at P1 — but it captures live credentials the moment authenticated traffic runs with tracing on. Fixed at the export boundary rather than in a request hook, with a regression test driving the real instrumentation and confirmed to fail without the fix |

| **AUD-F-11** | **Deploy pipeline / security** | **P2** | **Fixed in S39 continuation** | `terraform.tfvars` pinned `learning/chat_api_image_tag = "gha-6cc4a27430bd"` while both services were running `gha-d1899a483d06` — pushed six hours later, and **the commit that fixed `/dev/token` being signed with the public dev constant instead of the real secret**. So `terraform apply` registered task-definition revisions that silently reverted a security fix, and any operator who applied and then pointed a service at the new revision (rather than letting CI patch the tag) would have deployed it. Terraform cannot detect this: the tag exists and pulls fine. Only diffing the registered revision against what is *running* shows it. Found by doing exactly that before deploying the sidecar |

| **AUD-F-12** | **Observability / infrastructure** | **P2** | **Fixed in S39 continuation** | **The OTel collector accepted every span and discarded every one**, because the VPC has no `xray` interface endpoint and no NAT — AUD-F-10's root cause one layer further in. `Exporting failed. Rejecting data. {"name": "awsxray", "error": "Post \"https://xray.us-east-1.amazonaws.com/TraceSegments\": context deadline exceeded", "rejected_items": 64}`, repeating. **Nothing detected it**: the collector is `essential: false` and starts perfectly healthy, the app's export succeeds into it, both services stayed green, and no alarm watches export failures. Fixed with a single-AZ `xray` endpoint wired to `enable_otel_tracing` (~$7.30/mo, matching the existing five endpoints' cost posture); traces went from **0 to 650** on the next traffic run |

| **AUD-F-10** | **Infrastructure** | **P2** | **Fixed in S39 continuation** | **The ECS tasks cannot pull from `public.ecr.aws`.** They run in private subnets with `ecr.dkr`/`ecr.api` interface endpoints and an S3 gateway but **zero NAT gateways** (D-084's cost posture), and no interface endpoint exists for *public* ECR. Found live on the first sidecar deploy: `CannotPullContainerError ... dial tcp 75.2.101.78:443: i/o timeout`, retried 7×, services rolled back to the pre-sidecar revision and verified healthy. Fixed by mirroring the collector into this account's private ECR (`scripts/mirror-otel-collector.sh`, repository created, Terraform rewired) — **the mirror push itself did not complete before the AWS session expired**, so the image is not yet in ECR. **Live hazard while that is true:** the latest task-definition revision (18) still references the unreachable public image, and `deploy-staging.yml` patches whatever the *latest* revision is — so **the next CI deploy would fail the same way** until the mirror is pushed or `enable_otel_tracing` is set false and re-applied |

### Index continuation — S43 and later (backfilled 2026-08-04, D-174)

**⚠️ Read this before counting anything from the Index.** The table above stops at AUD-F-20 /
AUD-C-16 / AUD-X-08. Findings kept being filed after that with a detail section and **no row**, so
the register's own stated invariant — "One row per finding" — was broken for **27 findings**, and
the disposition rule ("Every finding needs a disposition here") along with it. Anything derived by
reading the table therefore under-counted: 89 findings have a section, only 68 had a row.

**What that cost, concretely.** Two open findings were invisible to every backlog count taken this
way — **AUD-F-22** (P2, a parent cannot reach the dashboard) and **AUD-F-33** (P2, scale-in stops
working; deferred by user call, not closed) — while **five** findings whose fixes are recorded in
DECISIONS.md or ROADMAP.md still read "not fixed" or "filed" in their own section heading
(AUD-F-21, F-25, F-27, F-34, X-13; all five headings corrected the same day). Separately,
**AUD-F-16** *had* a row and it said `Open` two weeks after D-116 fixed it.

**Method, so this block is not mistaken for a re-audit.** Severity, status and summary are taken
from each finding's own section and from the decision that closed it — cited inline, never inferred.
The **Area** column is a one-phrase characterization of the section's stated subject, since the
S43-and-later sections do not carry the `**Area:**` bullet the earlier ones do. No finding was
re-opened, re-scoped or re-severitied here; where evidence disagreed with a heading, the heading was
corrected and the correction is marked in it.

| ID | Area | Severity | Status | Summary |
|---|---|---|---|---|
| AUD-X-09 | Gateway / model caps | P1 | ✅ Fixed in S43 | The rerank output cap truncates every real rerank, and the failure is invisible |
| AUD-X-10 | Gateway / resilience | P2 | ✅ Fixed in S43 | A schema-validation failure trips the shared circuit breaker, failing every task closed |
| AUD-X-11 | Gateway / observability | P2 | ✅ Fixed in S43 | The gateway logs successes only, so a call failing 100% of the time is invisible |
| AUD-X-12 | RAG / model caps | P1 | ✅ Fixed in S43 | `rag_answer`'s fixed cap turns ~1 grounded turn in 30 into a false "no approved source" refusal |
| AUD-X-13 | Alarms / deploy pipeline | P2 | ✅ Fixed and live-verified in the S43 continuation (D-116) — **heading said only "filed in S43" until D-174** | The chat p95-latency alarm fires on healthy traffic, and the canary bake rolls back deploys when it does |
| AUD-X-14 | Model caps | P2 | ✅ Fixed in the S43 continuation (D-116) | `memory_consolidation`'s output cap is flat over a response that is one item per existing fact |
| AUD-X-15 | Model caps | P2 | ✅ Fixed in the S43 continuation (D-116) | The parent report's output cap was below what its own prompt asks for |
| AUD-X-16 | Process / checklist integrity | P2 | ✅ Fixed 2026-08-01 (D-150) | The three-times-failed checklist step lives in a gitignored file — now `make tfvars-floor-check` |
| AUD-C-17 | RAG / test integrity | P1 | ✅ Fixed 2026-08-01 (D-144) | The adversarial containment cases were passing over an empty-in-practice corpus, and broke the moment 11 documents became effective |
| AUD-C-18 | RAG / retrieval | P2 | ✅ Fixed and live-verified 2026-08-01 (D-150) | Four of the six newly-effective public documents are unretrievable on staging, while the same corpus answers them locally |
| AUD-F-21 | Launch journey / frontend | P1 | ✅ Fixed 2026-07-29 (D-117) — **heading said "not fixed" until D-174** | A late stage narrative unmounts the screen the student is already using. Also the fix that closed AUD-F-05 as collateral |
| **AUD-F-22** | **Launch journey / UX** | **P2** | **✅ fixed 2026-08-04 (D-176)** | **A parent cannot reach their child's progress dashboard without finishing a whole pre/study/post cycle** — the dashboard button exists only on `StartScreen` (which needs a `studentId` a parent gets by starting a session) and `ResultsScreen`. **Fixed per the user's UX call (D-175 §5 → D-176): the child resolves at login** — one child silently, several via the existing `ChildSelectionScreen`, via new parent-only `GET /learning/parents/me/children`; the choice is login-scoped (survives `endSession`, forgotten on logout) and the in-session interrupt is now the server-side fallback. Also closes the S11 carry-over. The `test.fail()` probe is promoted to a regression test asserting the stronger property: dashboard + report with **zero** sessions |
| AUD-F-23 | Audit integrity / harness | P3 | ✅ Found and fixed in the S43 continuation (D-117) | A conditional skip made an untested journey look tested for four sessions |
| AUD-F-24 | Launch journey / frontend | P1 | ✅ Found and fixed in the S43 continuation (D-118) | A conditional wrapper remounts the screen below it, so AUD-F-21's first fix truncated the dwell anyway |
| AUD-F-25 | Launch journey / staging content | P2 | ✅ Fixed 2026-07-29 (D-119 §3) — **heading said "not fixed" until D-174** | chat's suggestion chips have never been seeded on staging, and the seeder cannot run there (a dangling editable install in the ops-task image) |
| AUD-F-26 | Launch journey / SSE contract | P1 | ✅ Found and fixed in the S43 continuation (D-118) | The initial SSE snapshot serves state captured before a seconds-long Bedrock call, pushing the client backwards |
| AUD-F-27 | Launch journey / frontend | P1 | ✅ Fixed 2026-07-29 (D-120) — **heading said "not fixed" until D-174** | The client silently drops any mutation attempted while another is in flight, and tells the student it succeeded |
| AUD-F-28 | Capacity / latency | P1 | ✅ Fixed 2026-07-30 (D-122) | learning-api cannot serve criterion 7's 150 concurrent sessions: one task, 100% CPU, and the ALB kills it. The failure mode is gone and capacity is 3× higher; the p95 leg at 150 remains a **documented capacity gap with a price on it**, not a defect |
| AUD-F-29 | Availability | P2 | ✅ Fixed 2026-07-30 (D-122, same session) | A CPU-saturated learning-api task fails its own readiness check and gets killed, turning a latency problem into an availability one |
| AUD-F-30 | Observability / cost | P3 | ✅ Fixed 2026-07-31 (D-132, on the third attempt) | 97% of every trace this project has ever scanned is a health check, and X-Ray's free tier stopped covering it |
| AUD-F-31 | Latency | P2 | ✅ Fixed 2026-07-30 (D-131); verified on staging 2026-07-31 (D-132) | `select_topic` spends its 1.6 s on ~50 sequential SQL round-trips, and none of them are checkpoint writes |
| AUD-F-32 | Latency / capacity | P2 | **Dispositioned — measured, deliberately not fixed** (D-132, re-measured D-134) | The learning app's latency ceiling is ~726 ms per answer request that is neither SQL nor graph work. The re-measurement refuted the premise: the ~726 ms is **queueing, not work**, so there is no hidden fixed cost to remove — it is a capacity statement, not an optimization target |
| **AUD-F-33** | **Autoscaling** | **P2** | **Open — detection added, mechanism unknown; deferred by user call, not closed** (found D-132, reproduced and re-scoped D-134) | **Step scaling intermittently stops scaling in while its alarm stays in ALARM, on both services.** Observed at 3 tasks for 84 minutes with `p95-latency-scale-in` in ALARM the whole time, against a `-1` step and a 300 s cooldown. Raised P3→P2 the same day. Same family as AUD-F-38 and the reason `chat-api-capacity-above-floor` is deliberately kept off the canary list — an autoscaling signal must not be read as a deploy signal |
| AUD-F-34 | Scheduled jobs / model caps | P1 | ✅ Fixed, deployed and verified 2026-07-31 (D-141) — **heading still said "blocks gate criterion 6" until D-174** | `memory-consolidate` has never once worked: every model call fails on prompt length, and it exits 0. Criterion 6 is met behind the fix |
| AUD-F-35 | Personalization correctness | P2 | ✅ Fixed 2026-08-01 (D-150) | `promote_if_eligible` applies no evidence bar, so plan §9's stability rule is enforced at creation and bypassed on the next reconfirmation |
| AUD-F-36 | Launch journey / interrupts | P2 | ✅ Fixed 2026-08-01 (D-145), deployed; criterion 3 re-met behind it (D-147) | The parent's child-selection interrupt hangs forever when `/respond` beats the SSE subscription |
| AUD-F-37 | Deploy pipeline | P2 | ✅ Fixed 2026-08-03 (D-158) | Nothing verified that the deployed code is the code that was built |
| **AUD-C-26** | **Product correctness — access hint** | **P2** | **Open — filed 2026-08-04 (D-179), needs a product decision** | **A question the public corpus answers is told to log in as a parent, on the probe branch no rule table ever modelled.** Found by AUD-C-25's fix on its first run, at zero cost. When *nothing* is within `ACCESS_PROBE_CANDIDATE_MAX_DISTANCE`, `probe_access` returns at its `if not candidates` branch — no reranker call, **no relevance floor and no tier margin** — and `_lexical_only` decides alone. With no score to rank by, `build_access_hint` falls back to tier **priority**, which is the exact rule AUD-C-22 was filed against; the D-165/D-168/D-177 constants are not implicated because none of them runs on this path. **Not a knife edge, and not rare:** the branch is reached on **18 of 58** cases in the human-phrasing arm (11 public, 4 unanswerable, 3 gated) and 17 of 58 in the corpus arm — "no candidate within 0.60" is the ordinary case for a question phrased unlike the corpus. The keyword arm is quiet across almost all of it (1 fire in 35 empty-pool cases over both arms), and the one fire is wrong: **`probe-public-025`**, *"How do I get or delete my kid's school records?"*, nearest non-public chunk at distance **0.7251** against the 0.60 ceiling, keyword arm returning `{parent: 1, student: 3}` → **`required_role: "parent"`** for an answer the **public** Privacy Notice carries. So a caller is told to authenticate for public information. **Severity P2, argued both ways:** milder than AUD-C-22's wrong tier on gated content (the user probably *is* a parent) but the same defect class — a user-visible instruction that cannot help, on a negative class the recorded table showed as clean. **Why it needs a decision rather than a patch:** the obvious fix (skip the lexical arm when the candidate pool is empty) collides with D-165's reason for keeping the arm at all — `MockBedrockProvider`'s embeddings are hash-seeded vectors with no semantic content, so this is the **only** arm the entire mock-backed suite can exercise, and removing it makes the probe structurally unobservable offline. Candidate fixes: (a) require ≥2 matched audiences to disagree before the priority fallback names one, (b) give the keyword arm a minimum-match bar (`probe-public-025` fires on a single chunk), (c) keep the arm for tests but gate the *hint* on a scored signal, (d) accept and record it. All four are measurable for free with `--shipped` |
| **AUD-C-25** | **Audit integrity / measurement harness** | **P2** | ✅ **fixed 2026-08-04 (D-179) — and it found AUD-C-26 on its first run** | **`measure_access_probe_rules.py` does not measure the rule it is used to choose.** Every access-probe constant since D-165 was set from this script's tables, and the script **reimplements** the rule (`rerank_prefloor_margin_hint`) rather than calling `probe_access`. The reimplementation differs from production in two ways, and no test compares them. **(i) The branch order is reversed:** the harness checks the floor first (line 558) then the margin; `probe_access` checks the margin first ([retrieval.py:187](../packages/knowledge/src/intellichoice_knowledge/retrieval.py#L187)) then the floor. **(ii) The harness has no lexical arm at all** — neither `_lexical_only` nor `count_matching_by_audience` appears in it — so where production falls through to a keyword match that *can* return a hint, the harness returns `None` and scores it as silence. The two disagree exactly when `winner ≤ floor` **and** `winner − runner_up ≥ margin`, which is **AUD-C-23's own failing case** (winner 0.75–0.90 against the 0.9 floor, runner-up 0.2–0.3). So D-177's headline "0 wrong tiers, 0 false hints, 0/40 stability fires" is a true statement about the harness's rule that **does not cover** production's composed path on the decisive question. **Bounded, and the bound is why this is P2 not P1:** D-178's 10 live probes measured the composed path directly at **0/10 hints with a 3/3 control**, so no user-facing damage exists today, and the lexical arm was separately measured clean on both negative classes. The exposure is the *instrument*: the next rule decision will be made on tables that model a rule nobody ships. Same class as AUD-F-16 (a harness measuring something other than what it claimed) and as D-175's config-parity gap — whose `ast` guard checks the harness passes the same `Settings` **fields** as the route, while nothing checks the rule has the same **structure**. **Two candidate fixes, neither costing a paid re-measurement:** have the harness call `probe_access` with an injected score map, or add a parity test that runs both over the saved dumps and asserts identical hints per case. Also unresolved and cheap to settle from the same dumps: production's pre-floor margin now **gates** the lexical arm (two audiences at `0.0` → `matches={}`, `lexical_calls=0`, verified), which the "strictly additive, gets the last word" comment at [retrieval.py:196](../packages/knowledge/src/intellichoice_knowledge/retrieval.py#L196) no longer describes, and which plausibly accounts for part of the 29→27 drop D-177 attributed to the floor raise **✅ Fixed 2026-08-04 (D-179), arm (a) — the harness now calls `probe_access` instead of restating it.** `--shipped` replays the real function per case: rerank scores come from the dump (the paid, nondeterministic input, and `--load`'s whole purpose is comparing rules against identical model output), while the **lexical arm is real**, delegated to `RagRepository.count_matching_by_audience` against local Postgres — it takes no embedding, so it is faithful offline even with mock vectors stored, which is exactly why it could have been modelled for free at any point and never was. The table gains a `SHIPPED probe_access` row and a parity section against `pf_f09_m01`, its transcription. **It paid for itself immediately:** the first run reported **FP public 1** where D-177 recorded 0, and the parity section named the one disagreeing case out of 58 — now filed as **AUD-C-26**. **My own prediction on this row was wrong in two ways, which is why the fix and not the reasoning is what closed it:** the divergence that bites is the *empty candidate pool* branch, not the sub-floor one (reached on 18 of 58 cases, at distance 0.72 against a 0.60 cut — nowhere near a knife edge), and the unmodelled arm *adds* false hints as well as costing recall. 7 regression tests in `test_access_probe_harness_parity.py`, one per branch, including one that fails if the shipped column is ever re-transcribed and one asserting the replay errors rather than returning `{}` when it cannot reach the lexical arm — returning an empty match set there would be this finding, reintroduced by its own fix |
| **AUD-C-24** | **Minors / PII floor — chat free text** | **P2** | ✅ fixed 2026-08-04 (D-177) | **The chat app sends the user's typed question to Bedrock unredacted, and no decision ever covered that surface.** `redact_free_text` has **exactly one call site in the repository** — learning-api's chat router, at the request boundary (D-072) — while chat-api has none, so a question typed into `chat.intellichoice.org` reaches four payloads verbatim: `ScopeAndIntentPayload.standalone_query`, `RerankPayload.query`, `RagAnswerPayload.query`, `CalendarExtractionPayload.query`. D-072's own "How to apply" clause requires the pass for "any future free-text-accepting Bedrock task". **Bounded, and the bound is what holds it at P2**: chat queries are **not persisted** — there is no chat-message table (`chat_suggestions.prompt_text` is hand-authored seed content, checked), so this is the wire and traces, not storage or backups. **Not an accepted risk, an unexamined one**: D-018's prompt-injection scope call names chat-api's surface deliberately and defers PII to "S24/D-072 already judged that surface", which judged the *learning* surface. Needs a decision (redact at the chat request boundary as learning-api does, vs. accept and write the acceptance down), not just a patch — a minor typing "my mum's email is …, when is class?" is the realistic case **✅ Fixed 2026-08-04 (D-177), as the user decided: redact at the boundary.** `redact_free_text(body.query)` in chat-api's `post_message` — the one place free text enters the graph (`/respond`'s free text is location data that goes to geocoding and is purged per AUD-C-03; `/stream` takes no input) — so the four payloads, the checkpointed `QAState`, **and** the escalation email draft all carry the redacted text. Two HTTP tests: the raw email absent from the escalation draft and from serializer-decoded `checkpoint_writes` (the AUD-C-03 lesson), and an email-bearing in-scope question still classifies and answers. D-072's "How to apply" clause now holds on both apps |

**Open findings, counted from both halves of the Index (2026-08-04, D-174; recounted D-175,
D-176, D-177, D-178 and D-179): 2.** Arithmetic, written out because this line has now been wrong
three times: 1 open after D-177, **plus** AUD-C-25 (filed in D-178 while landing D-177's work),
**minus** AUD-C-25 (fixed in D-179), **plus** AUD-C-26 (filed in D-179, found *by* that fix on its
first run) = **2**. Confirmed by running ROADMAP's anchored `awk`, not by counting the sentence
below. `Open`: **AUD-F-33** (deferred by the user's call — detection exists, mechanism unknown)
and **AUD-C-26** (a public-corpus question told to log in as a parent, on the probe branch no rule
table modelled — needs a product decision, all four candidate fixes measurable for free).
**AUD-L-01, AUD-L-05, L-08, L-16, C-14, C-15, C-23, C-24 and F-22
are now fixed** — C-14/C-15/L-16 in D-174, L-01/L-05 in D-175, L-08/F-22 in D-176, C-23/C-24 in
D-177 (C-23 live-verified in D-178: 0/10 hints, control 3/3). **AUD-F-16 is
not among the open ones** — it was fixed in D-116. AUD-F-32 is dispositioned rather than open.
**The pre-D-174 count of "8, 9 counting AUD-F-16" was wrong in both directions**: it carried a
closed finding and missed two open ones.

**✅ One id used to name two different findings: `AUD-L-17`. Resolved 2026-08-04 (D-174) — D-159's P2
is now `AUD-L-19`.**

- **`AUD-L-19` — "variant ownership" (P2)** — the exam answer paths never checked that a variant
  belongs to *this* exam. Found under AUD-L-11 and fixed the same session, **D-159**. **This one was
  renumbered**, because D-159 minted an id S36 already held and the later minting is the one that
  should move. **Documents written before 2026-08-04 cite it as `AUD-L-17`** — ARCHITECTURE.md,
  ROADMAP.md, TRACEABILITY.md, D-159 itself and its PROGRESS entries were all updated, so a surviving
  `AUD-L-17` in a narrative passage means the P3 below.
- **`AUD-L-17` — "mock hint boilerplate" (P3)** — `MockBedrockProvider`'s `Level 1` prefix tripped the
  runtime answer-leak check whenever the served answer was `"1"`. **S36 continuation.** **Keeps the
  id** as the original holder.

**Why it mattered enough to renumber rather than annotate.** The id was ambiguous in **33 places**
across five documents, and a count by unique id silently merges two findings into one — which is how
the register came to show 89 sections for 90 findings. The renumber was applied **per reference, not
by global replace**: each of the 33 was classified as P2, P3, or a range like `AUD-L-10..AUD-L-17`
(the S36 audit span, which correctly still ends at the P3), and only the 11 pure P2 citations moved.
Ranges and P3 narrative passages were deliberately left alone.

---

## S36 — AUD-L (learning product correctness)

### AUD-L-02 — `POST /students/{id}/report` had no cost ceiling at all (P0, fixed)

- **Severity:** P0 — §2.4 lists uncontrolled spend explicitly. Stopped the line and was
  fixed in-session with regression tests, per the audit's own rules.
- **Area:** money / Bedrock cost ceilings
- **Found by:** tracing every `session_spend_cents` argument to
  `BedrockGateway.generate_structured` back to its caller, rather than reading the gateway
  and concluding the ceiling exists
- **Status:** **fixed in S36**, live re-verification pending the Phase 1 deploy

**What.** The gateway is stateless about spend: it enforces the per-session budget against a
`session_spend_cents` value its *caller* supplies. Two callers supplied nothing, relying on a
`= 0.0` default — and one of them,
[routers/students.py](../apps/learning-api/src/learning_api/routers/students.py)'s
`POST /{student_id}/report`, is an on-demand endpoint with **no idempotency key**: one fresh
`student_reports` row and one fresh Bedrock call per click. So on every single call the check
evaluated `0.0 + worst_case > 50.0`, which is false, and the ceiling never applied. Not a
weakened ceiling — an absent one.

The only remaining limit was the global per-IP rate limiter, raised to 6,000 requests/60s in
S34 for a completely unrelated reason (real branches share an egress IP). A request cap is not
a spend cap.

**Reproduction.** Authenticate as any role permitted to reach a student's report (student-self,
linked parent, tutor, branch_manager) and repeat `POST /learning/students/{id}/report`. Every
request performs a real Bedrock `PARENT_REPORT` call. No counter, ledger, or ceiling is
consulted, and the response is not cached or deduplicated.

**Evidence.** Cost arithmetic from the gateway's own rate table, for the model actually
deployed (`us.anthropic.claude-haiku-4-5-20251001-v1:0`, 0.1/0.5 cents per 1K in/out) and the
report task's real `_MAX_OUTPUT_TOKENS = 500`: roughly **0.45 cents per call** (0.2 in + 0.25
out), doubling if the structured-output repair retry fires. At the per-IP limiter's ceiling
that is ~$27/minute, ~$1,600/hour, from one IP holding one valid token. Even at a rate a plain
browser script achieves without effort, it is hundreds of dollars a month of pure waste. The
only backstop was the AWS Budget alarm — a lagging notification, not an enforcement mechanism.

The bug class is already recognized in this codebase: S24 built
`tutor_chat.DAILY_COST_CEILING_CENTS` precisely because chat is a surface where one student can
trigger many separate LLM calls in a day. Report generation is the same shape and never got the
same control.

**Fix (in this session).** Mirrors the chat precedent rather than inventing a mechanism:

1. `StudentReportRepository.get_spend_cents_since` — sums `cost_cents` over a 24h window. No
   migration: `student_reports` already stores `cost_cents` and `created_at`.
2. `report.DAILY_REPORT_COST_CEILING_CENTS = 50.0`, checked *before* the Bedrock call. On
   exceed the endpoint degrades to the deterministic facts-only template that a gateway failure
   or a failed grounding check already produces — the caller still gets their real verified
   numbers, just without LLM prose. That reuses SPEC §5.25.3/§5.27's deterministic-fallback
   rule instead of erroring.
3. `session_spend_cents` is now **required** on both `generate_student_report` and
   `generate_stage_narrative`. A cost parameter with a permissive default *is* a fail-open
   default — the same class as D-096's `ecr:DescribeImages` check and D-085's environment-string
   gate. Removing the default immediately surfaced all five call sites that had been relying on
   it, which is the point.

**Regression tests** (3): the ceiling short-circuits *before* the gateway is called (an
`_ExplodingGateway` fails the test if Bedrock is reached at all); a call just below the
threshold still generates normally (a ceiling that blocks legitimate use is a different bug, so
the threshold is pinned from both sides); and the spend query counts only this student's reports
inside the window, so neither another student's spend nor last week's can deny a legitimate
report.

**Residual, deliberately not fixed here.** The endpoint is still not idempotent — the ceiling
bounds the *cost* of hammering it, not the hammering. Per-caller request-rate limiting on
LLM-calling endpoints specifically (as opposed to the global per-IP cap) is a Phase 0B item and
belongs with the same work for chat.

### AUD-L-04 — An accepted PII risk lost its mitigation when S25 made the text permanent (P1)

- **Severity:** P1 — a data-protection promise about minors that the code no longer keeps.
  Not P0: it needs a student to type a name, the model to copy it into a fact, and that fact to
  pass the pattern screen, and there are no real student users yet. But it must be closed before
  the §2.6 gate, not in the backlog.
- **Area:** minors / PII floor / retention
- **Found by:** following `relevant_learning_fact` — an *allowlisted* field on the tutoring
  payloads — backwards to where its text is authored, instead of stopping at the allowlist
- **Status:** **fixed 2026-07-29 (D-114)** — `retention_purge_cli` purges `semantic_memory`
  (90d on `last_confirmed_at`), `stage_transitions` (90d) and `student_reports` (365d) on a
  daily EventBridge schedule, applied and confirmed ENABLED in staging the same day; the
  §6.1 privacy-text line is recorded in D-114 §4 for the legal track

**What.** D-072 (S24) explicitly accepted that name detection in free text is unreliable and is
not attempted: `redact_free_text` removes emails, URLs and phone numbers only. So a student
typing "my mom Sarah said to skip this" leaves a name in `tutor_chat_messages.
redacted_student_message`. That was accepted as a bounded risk, and the boundary was real:
**that table is the only one in this codebase with a retention job** (`purge_older_than`,
`make chat-purge`, 90 days, SPEC §15).

S25 (D-074) then built memory consolidation on top of that same text, and the boundary quietly
disappeared:

1. `consolidation.py:185` reads `redacted_student_message` and folds it into
   `MemoryEventSummary.summary`.
2. That goes to Bedrock, which authors `MemoryFactCandidate.fact_text`.
3. `fact_text` is screened with `contains_pii_pattern` — the *same* email/URL/phone patterns,
   which by D-072's own admission do not catch names — and stored in `semantic_memory`.
4. `semantic_memory` has **no purge, no retention job, and no `make` target.** Verified: grepping
   `purge_older_than` across every repository in `packages/db` returns exactly one hit,
   `tutor_chat.py`.
5. `fact_text` then flows outward — into `relevant_learning_fact` on `BedrockTutorPayload` and
   `HintPersonalizationPayload`, and into `ReportInterpretationPayload.relevant_learning_facts`,
   which is rendered in **parent-visible reports**.

So a name a child typed can outlive the 90-day window indefinitely, in Postgres, and surface to a
different human than the one who typed it. Neither D-072 nor D-074 records this: D-072 reasoned
about a purged table, and D-074 reasoned about consolidation quality.

**Reproduction (structural, and that is the honest description).** The chain above is verifiable
by reading it, and every link is unconditional code. What cannot be reproduced deterministically
is step 2 — whether the model copies a name into a fact — because that depends on real model
behavior, and the dev fake does not attempt it. I did not manufacture a "leak" with a scripted
fake gateway, because that would only prove the fake does what I told it to; it would be evidence
about my test, not about the system.

**Evidence.** `consolidation.py:185` and `:250`/`:324` (the screen, using the same insufficient
pattern set); the single-hit `purge_older_than` grep; `report.py`'s `relevant_learning_facts`
reaching the parent audience in `build_report_facts`.

**Disposition — DECIDED (user, S36 close-out; see D-098).** Add a retention job for
`semantic_memory`, and a line in the §6.1 privacy text. Rejected: stopping raw chat text reaching
consolidation (removes the risk at source but spends the consolidation quality D-074 deliberately
bought, and would partly supersede a settled decision); and accept-and-disclose (zero cost but
makes "we delete chat after 90 days" misleading for a product whose primary users are minors).

The chosen option restores exactly the boundary D-072 already reasoned about and approved, rather
than re-opening a settled trade-off. Phase 0B work, before the §2.6 gate:

1. `SemanticMemoryRepository.purge_older_than` + a `make memory-purge` CLI, mirroring
   `TutorChatMessageRepository.purge_older_than` / `make chat-purge` exactly.
2. Fold in the `stage_transitions` and `student_reports` retention jobs already on the standing
   carry-over list — same pattern, same session, so this is done once rather than three times.
3. The retention window must be **stated in the §6.1 privacy notice**, and the notice must not
   imply that deleting chat after 90 days removes everything derived from it.
4. All of these must run on a schedule, not by hand — the EventBridge item already seeded in
   §2.5 covers it. A retention promise that depends on someone running `make` is not a retention
   promise, which is the same reasoning §2.5 already applied to `chat-purge`.

### AUD-L-05 — `MemoryConsolidationPayload` was never added to the PII-floor allowlist (P2)

- **Severity:** P2 — no live leak today; a missing guard rail, not a broken one
- **Area:** minors / PII floor
- **Status:** ✅ fixed 2026-08-04 (D-175) — see the closing subsection

**What.** D-072's own "How to apply" clause states the rule: *"any future free-text-accepting
Bedrock task must run `redact_free_text` (or a stricter successor) before the wire and before
storage, **and its payload must appear in `test_bedrock_payload_pii_floor.py`'s allowlist set**."*
`MemoryConsolidationPayload` is a free-text-accepting payload (`MemoryEventSummary.summary`,
`MemoryExistingFact.fact_text`) added one session later, and it is not in that test.

**Reproduction / evidence.** The test covers exactly six payload types — `BedrockTutorPayload`,
`HintPersonalizationPayload`, `LearningChatIntentPayload`, `TutorChatPayload`,
`StageNarrativePayload`, `ReportInterpretationPayload` — confirmed by extracting every
`*Payload` symbol referenced in the file. `MemoryConsolidationPayload` is absent.

**Why it matters despite P2.** The payload's *current* fields are clean, so nothing leaks now.
The value of that test is that it fails when someone adds a field — it is the mechanism by which
the PII floor survives future sessions. An uncovered payload silently opts out of that
protection, and this one is the payload closest to real student free text.

**Disposition.** Phase 0B: add the allowlist case. Also worth checking the other uncovered
payloads in the same pass (`VideoClassificationPayload`, `LlmJudgePayload`, and the
curriculum-pipeline payloads); the chat-app payloads belong to AUD-C/S37.

#### ✅ Fixed 2026-08-04 (D-175) — and the one-row fix would not have worked

**Adding the row the disposition asks for would have left this payload unprotected.**
`MemoryConsolidationPayload`'s own field names are `events` / `existing_facts` /
`allowed_fact_types`; the student's chat text lives in `MemoryEventSummary.summary` and
`MemoryExistingFact.fact_text`, one level down. The test's denylist compared *top-level*
`model_fields` only, so the payload the finding was filed about — "the payload closest to real
student free text" — would have passed a scan that never looked at the fields carrying the text.
Verified rather than reasoned: the completeness assertions were run against the pre-fix registry
*with* `MemoryConsolidationPayload` added, and the nested check still failed, naming both models.

**Scope, measured.** The module docstring claimed coverage of "every payload type that ever crosses
the Bedrock gateway". Actual: **6 of 20**. `test_generation_payload_schemas.py` governs 7 more under
a deliberately narrower `extra="forbid"`-only regime (documented, and correct — curriculum content,
not student data), and `LlmJudgePayload` carries a written exclusion at its definition site. That
left **6 genuinely ungoverned**: `MemoryConsolidationPayload` and the four chat payloads
(`ScopeAndIntentPayload`, `RerankPayload`, `RagAnswerPayload`, `CalendarExtractionPayload`) plus
`VideoClassificationPayload`. The chat payloads were never anybody's follow-up — this entry's own
disposition assigned them to "AUD-C/S37", and no AUD-C finding picked them up.

**What was built.** 17 models on exact field allowlists (nested models are first-class rows), the
denylist recursing one hop through field annotations, and two structural tests: every `*Payload` in
`intellichoice_shared.bedrock` must sit in exactly one of three named regimes, and every nested model
reachable from an allowlisted payload must itself be allowlisted. The first fails on a **new payload
class**, which is the level D-072's clause was violated at; both were watched failing against the
pre-fix registry, naming exactly the 7 and the 2. Suite: 25 → 68 tests in the two files.

**Found while doing it, filed separately as AUD-C-24:** the four chat payloads carry the user's typed
question verbatim, and **nothing in chat-api redacts it** — `redact_free_text` has exactly one call
site in the repository, in learning-api's router. These allowlists pin field *names*; they say nothing
about the text inside them.

### AUD-L-06 — `tutor.generate_hint` is unreachable and omits the leak check its sibling applies (P3)

- **Severity:** P3
- **Area:** minors / tutoring guardrails
- **Status:** open, Phase 0B

**What.** `tutor.generate_hint` performs a real Bedrock `TUTOR` call and returns
`result.value` directly — no `leak_phrase_present`, no `answer_text_leaked`, and it ignores
`HintResponse.answer_revealed` even though the field exists. Its live sibling
`generate_personalized_hint` applies all three checks plus a ladder-monotonicity check, and
`tutor_chat.generate_chat_reply` applies the leak checks too. `generate_solution` correctly has
none (revealing the answer is its job) but does cross-check the model's `final_answer` against
the real one.

**Reproduction / evidence.** `generate_hint` has **no caller in application code**: grepping the
whole repository finds it referenced only from `apps/learning-api/tests/test_tutor_service.py`
and one comment in `packages/evals`. The live hint path is `graph/nodes.py:788` →
`generate_personalized_hint`. So this is dead code, and there is no reachable defect today.

**Why log it at all.** It reads exactly like a supported entry point, it is covered by three
tests that assert it works, and it is the only LLM-output path in the learning app that trusts
the model unverified. A future session adding a "plain hint, no personalization" flow would
reasonably call it and inherit an unguarded path.

**Disposition — DECIDED (user, S36 close-out; see D-098): delete it**, along with its three tests.
There is no caller to migrate, and the live path (`generate_personalized_hint`) already has every
check. If a non-personalized hint flow is ever wanted, writing it fresh with the checks in place is
easier and safer than remembering that this one lacked them. Rejected: keeping it and adding the
checks, which would preserve unreachable code and the false impression that it is exercised.

### AUD-L-03 — `pre_intro` spend is never folded back into the session total (P2)

- **Severity:** P2 — bounded, but it means the per-session ceiling is structurally wrong
- **Area:** money / cost accounting
- **Status:** open, Phase 0B

**What.** `routers/stream.py`'s `pre_intro` narrative fires on SSE connect, outside the graph.
S26/D-075 deliberately records its cost on the `stage_transitions` row rather than in the
checkpoint's `bedrock_spend_cents`, because that path never takes a graph turn. That choice was
recorded as an *accounting* decision; its consequence for *enforcement* was not: every later
call in that session evaluates the ceiling against a total that is permanently missing this
call's cost. The same is true of chat's out-of-band spend (S24/D-073 records that one).

**Reproduction / evidence.** Structural, and visible in the code: `_maybe_fire_pre_intro`
returns only `(narrative_text, evidence_summary)` — there is no cost in its return type, so no
caller could fold it in. Bounded by the stage-narrative idempotency check (one real Bedrock call
per session per stage), so the undercount is one call's worth per session, not unbounded.

**Fixed in this session only in part:** the call now passes the checkpoint's real running total
instead of the 0.0 default (as part of AUD-L-02's fix), so the ceiling at least applies. The
write-back is the remaining half.

**Disposition — DECIDED (user, S36 close-out; see D-098): fold out-of-band spend into the
checkpoint**, settling the question D-073 and D-075 each deliberately left open. Both `pre_intro`
(SSE connect) and chat's own spend get a path to write their cost back into `bedrock_spend_cents`,
so the per-session ceiling means what its name says and there is one authoritative number instead
of two partial ones.

The cost is understood and accepted: this means writing to the checkpoint from outside a graph
turn, which is exactly what those two decisions avoided. The reason to accept it now is AUD-L-02 —
this session has already produced one P0 from a ceiling that silently did not apply, so a ceiling
that is merely *approximately* right is no longer a comfortable place to leave things. Phase 0B;
the per-day ceilings remain the real bound on those surfaces in the meantime.

### AUD-L-07 — D-086's authorization gap has grown since it was recorded (P1)

- **Severity:** P1. Already known and already launch-blocking (D-086, S33); this finding is the
  *scope update*, not the discovery.
- **Area:** authorization
- **Status:** **accepted residual risk, §7-R8 (D-123, 2026-07-30)** — the finding stays open and
  still closes at S43/S46; what changed is that the gate no longer waits on it. See the
  disposition below.

**What.** `authorization.resolve_target_student` verifies students against their own `sub` and
parents against a live linked-children lookup, then returns `requested_student_id` unchecked for
tutor and branch_manager. D-086 recorded this in S33. What is new is the *reach*: S28 added the
dashboard and report surface after D-086 was written, so the unchecked path now includes
`GET /students/{id}/dashboard`, `POST /students/{id}/report`, and `GET /students/{id}/reports` —
meaning a tutor token can read any student's mastery, accuracy and usage data and generate
LLM-written reports about a student they have no relationship to. D-086's text reasons about
session history, which was the surface that existed at the time.

Also stale: the code comment says the check "land[s] with Q&A authorization (Session 13)". S13
shipped without it. A pointer to work that already happened without doing the thing is worse than
no pointer.

**Reproduction.** Mint a tutor token for any `sub`, call
`GET /learning/students/<any-student-id>/dashboard`. No relationship is required or checked. Not
independently exploitable today — obtaining a tutor token requires the `/dev/token` path, which is
secret-gated as of this session — but that is a property of the current deployment, not of the
authorization code.

**Evidence.** [authorization.py:34-36](../apps/learning-api/src/learning_api/authorization.py#L34-L36)
is the whole check for these two roles. All 17 learning routes were enumerated and traced: every
route that names a student or a session does call `resolve_target_student`, so the gap is
uniformly *this function's* gap, not a per-route omission — which is the good news, since one fix
closes all of them.

**Disposition.** Unchanged from D-086: blocked on a tutor-assignment / branch_manager-branch data
model that `ProfileAdapter` does not have yet, which S42's discovery and S43's `IcProfileAdapter`
are what unblock. This finding adds two things to that record: the dashboard/report surface is in
scope, and the formal disposition is already scheduled for S46 (§5's "D-086 disposition
recorded"). Fix the stale comment whenever the file is next touched.

**Disposition decided 2026-07-30 (D-123): accepted as documented residual risk §7-R8**, which is
what let §2.6 criterion 2 be claimed. The choice was between failing closed now — refusing
tutor/branch_manager *reads* of dashboards and reports — and accepting the exposure in writing.
Failing closed was rejected on the merits: S40 already demonstrated it ends tutor report
generation outright until S46, so it removes a shipped feature to satisfy a checklist item,
against an exposure that is a tutor reading students they are not assigned to in a system with no
real users and a secret-gated token path. **The acceptance is scoped to that window and expires at
first real traffic** — it is not a decision to ship this to production unfixed.

### AUD-L-09 — Numeric grounding checks provenance, not attribution (P2)

- **Severity:** P2 — degraded quality in parent-facing text, with a workaround (the facts-only
  template always shows the correct numbers)
- **Area:** correctness / stage-narrative and report grounding
- **Status:** open, Phase 0B

**What.** `numeric_grounding.is_grounded` returns False only if the narrative contains a number
that appears nowhere in the evidence dict. It does not check what the number is *claimed to mean*.
So for a student who improved from 4 to 6, the sentence "your score fell from 6 to 4" is fully
grounded — both numbers are in the evidence — and is accepted and shown. Same for swapped skills,
inverted gains, or a pre-exam figure presented as a post-exam one.

**Reproduction / evidence.** Structural, and visible in the nine-line function: it iterates
`extract_numbers(narrative_text)` and asks only whether each has *some* match anywhere in the
flattened evidence values. Direction, pairing, and field identity are never consulted.

**Why it matters more than P2 suggests, and why it is still P2.** This is the last check between
an LLM and a parent reading about their child's progress, and the product's whole framing is
growth-oriented language (SPEC §5.10.3) — a narrative that inverts a real gain is worse than no
narrative. But it is genuinely bounded: the deterministic fallback always contains the correct
figures, the numbers themselves can never be invented, and both parent-facing surfaces show
`verified_facts` alongside the prose, so a wrong claim sits next to the right data.

**Disposition — DECIDED (user, S36 close-out; see D-098).** Phase 0B, two partial mitigations,
with the incompleteness stated rather than papered over:

1. **A directional check.** When the evidence carries a known gain, reject narrative text that
   pairs those two numbers in the wrong order — this is what stops "your score fell from 6 to 4"
   for a student who went 4→6, which is the damaging class.
2. **Narrow the evidence dict per stage**, so each narrative is only given the fields it needs and
   there are fewer unrelated numbers available to misattribute at all.

Rejected: accept-and-rely-on-displayed-facts (defensible at current volumes, but it leaves
unverified LLM prose as parent-facing text about a child); and real semantic verification, which is
the only *complete* answer but is a project rather than a fix, adds a paid call per narrative, and
would itself need a cost ceiling given AUD-L-02. **Neither chosen mitigation makes the check
sound** — that limitation should be recorded in the code, not just here, so nobody later mistakes
the directional check for full verification.

**✅ Closed 2026-08-04 (D-172 §1), both mitigations resolved — one implemented, one found already
satisfied.**

Mitigation 1 shipped as `grounding_failure`: an explicit `from X to Y` transition that states the
known `pre_raw_score`/`post_raw_score` pair in reverse is rejected, matched with the same rounding
tolerance as provenance so a rounded rendering cannot sidestep it. `from`/`to` is the only phrasing
judged — the order is asserted by the connective, so no verb list has to be maintained against a
product that rewords for growth-oriented tone. The unsoundness is now recorded **in
`numeric_grounding`'s docstring**, as this entry asked: swapped skills, a mastery figure on the
wrong skill, a pre-exam number presented as post-exam, and inversions phrased without `from`/`to`
all still pass.

One false rejection is accepted and pinned by a test rather than discovered later: with scores
4 → 6 and hints 6 → 4, a faithful sentence about hints is indistinguishable from an inverted one
about scores, because numbers carry no field identity — which is this finding restated. It fails
closed, and the fallback keeps the correct figures.

Mitigation 2 needed no code: every `StageNarrativePayload` already carries only its own stage's
fields, so a `study_outro` narrative is never shown a score to misattribute. A fix with nothing to
implement is the kind that regresses silently, so `test_stage_payloads_stay_narrow.py` asserts it
from the AST of the real construction sites and was watched failing against a deliberately widened
`study_step` payload. Narrowing the *report* payload was rejected: it is broad by audience
authorization, and trimming it would show the model less than the parent is entitled to see, which
is exactly the false-rejection class D-163 measured.

### AUD-L-08 — `normalized_gain` is unbounded, and its denominator comes from the attempt count (P3; ✅ fixed 2026-08-04, D-176)

- **Severity:** P3 — but see the reachability correction at the end of this entry; "not reachable
  today" was wrong in two ways.
- **Area:** correctness / learning-gain math (SPEC §5.13.3)
- **Status:** ✅ fixed 2026-08-04 (D-176) — declared-count denominator, out-of-range flagged
  `unmeasurable_out_of_range` and never clamped, narrative payload suppresses any flagged gain;
  see the closing subsection at the end of this entry

**What.** `learning_gain.compute_learning_gain` sets `max_score = float(len(pre_graded)) or 1.0` —
the *count of resolved pre attempts*, not the assessment's declared item count — and then computes
SPEC §5.13.3's `(post - pre) / (max - pre)` with no clamp on the result. If the post form ever
carries more items than the pre form, or pre attempts are ever missing while post attempts exist,
the quotient exceeds 1.0 and is stored and displayed as a normalized gain. The `or 1.0` guard
protects against ZeroDivisionError but converts a zero-pre-attempt case into a denominator of 1,
which is worse than an error: it produces a plausible-looking number.

**Reproduction (empirical).** Called the real function with a fake question repo:

| Case | `raw_gain` | `normalized_gain` | `status` |
|---|---|---|---|
| normal 10-item, pre 4 → post 6 | 2.00 | 0.333 | `None` |
| post form longer than pre (12 vs 10) | 8.00 | **1.333** | `None` |
| no pre attempts, post 6 correct | 6.00 | **6.0** | `None` |
| pre 1 item wrong, post 10 correct | 10.00 | **10.0** | `None` |

Note `status=None` in every row — a 1000% gain is not flagged as anomalous, it is reported as a
valid normalized gain. It would then pass the report's numeric-grounding check, because the number
*is* in the evidence; grounding verifies provenance, not plausibility.

**Why it is nevertheless P3.** I traced whether any of those inputs can occur:
`assessment_builder.build_post_exam` builds the post form by iterating `pre_items` and generating
one fresh variant per pre item, so the post length **always** equals the pre length; and
`build_pre_exam` is a fixed 5 difficulties × 2 questions with a hard `AssessmentBuildError` if any
difficulty lacks approved templates, so a zero-item pre exam cannot be created either. S22's
finalize grades every unanswered item incorrect, so the attempt count matches the item count. The
bad inputs are unreachable through the real flow.

**Why it is still worth fixing.** Nothing *states* that invariant where the arithmetic lives, and
nothing tests it. The protection is a property of a different module's loop shape. An adaptive or
variable-length post form — a plausible future change, and the kind of thing SPEC §5.13.2's
"parallel form" language does not forbid — would silently start producing >100% gains in
parent-facing reports, with no error and no flag. A one-line clamp plus a comment naming the
invariant costs nothing and converts a latent correctness bug into an impossible one.

**Reachability correction (S36 continuation).** The "not reachable today" claim above was wrong
in two independent ways, both found by driving real journeys through the real API rather than
calling the function with fabricated inputs:

1. **The negative direction is reachable right now, with no unusual setup.** A student driven
   8/10 → 4/10 through the ordinary flow was stored with
   `normalized_gain = -2.0` and `normalized_gain_status = NULL` — a −200% "normalized learning
   gain", flagged valid. The entry above only considered the `> 1` direction, so the *unbounded*
   framing was right and the *unreachable* framing was not.
2. **The `> 1` direction is reachable too, via AUD-L-10.** The reasoning above ("the post length
   always equals the pre length") is true of *item* counts, but this arithmetic uses **attempt**
   counts, and AUD-L-10 shows attempts are not one-for-one with items: a second answer to one
   post-exam item pushes `post_raw` above `max_score`. The stated invariant does not protect the
   quantity the code actually divides by.

Also worth recording, because it is the opposite of the expected failure: an extra *pre* attempt
takes the `pre_raw >= max_score` branch **off**, so a genuine 10/10 pre-exam stops reporting
`not_applicable_pre_max` and starts reporting a computed `normalized_gain` instead. The flag that
exists to mark this case unmeasurable disappears exactly when it applies.

**Bound on user exposure (checked, not assumed).** `normalized_gain` appears in
`apps/learning-web/src/types.ts` but is rendered by **no screen or component**, so −200% is not
displayed today. It *is* passed into `StageNarrativePayload` (`nodes.py:650`), so it can shape the
`post_outro` narrative text a student reads.

**Closed 2026-08-04 (D-176), implementing D-175 §5's recorded decision.**
`compute_learning_gain` now takes `declared_item_count` — the pre form's item count read from
`assessment_items` by `_complete_post_exam`, the level the invariant actually lives at — and a
quotient still outside [-1, 1] keeps its raw value and sets
`normalized_gain_status="unmeasurable_out_of_range"`. Flag, never clamp: clamping converts a −200%
into a plausible −100%, which is this finding's own core complaint. The `or 1.0` guard is gone (a
zero-item form lands in `not_applicable_pre_max` instead of fabricating a denominator), and the
one student-facing consumer is cut at the seam: `post_outro`'s payload gets `None` whenever any
status flag is set. 8 tests in `test_learning_gain_bounds.py`, one per row of the reproduction
table above plus the reachability correction — including the live −200% (now flagged, unclamped)
and the extra-pre-attempt case that used to turn `not_applicable_pre_max` off exactly when it
applied.

### AUD-L-01 — A gated-off `/dev/token` discloses its own existence; the S35 gate's rationale is incorrect

- **Severity:** P3 (information disclosure only — no token can be minted)
- **Area:** auth surface / deploy-time security gate
- **Found by:** reading [.github/workflows/deploy-staging.yml](../.github/workflows/deploy-staging.yml)'s
  gate comment while extending it for S36/D-097, then probing the claim instead of trusting it
- **Status:** ✅ fixed 2026-08-04 (D-175) — see the closing subsection

**What.** The gate comment asserts: *"with the endpoint gated off, the route is never
registered on the app at all."* That is not how the code works. `@app.post("/dev/token")` is
registered unconditionally at module import; the 404 is raised from *inside* the handler after
FastAPI has already matched the route and validated the request body. So request shapes that
fail before the handler body runs return something other than 404, and reveal that the path
exists.

**Reproduction.** Both apps, settings in staging's real posture
(`environment="staging"`, `dev_token_endpoint_enabled=False`, no shared secret):

| Request | Actual | A genuinely absent route |
|---|---|---|
| `POST /dev/token` valid body | 404 | 404 |
| `POST /dev/token` `{"role": "not-a-role"}` | **422** | 404 |
| `POST /dev/token` `{}` | **422** | 404 |
| `GET /dev/token` | **405** | 404 |

**Evidence.** Probed directly against both apps' real ASGI app via `TestClient` with settings
monkeypatched to staging's posture; the table above is that run's output. `POST /dev/nonexistent`
returns 404 in the same run, which is the control that makes 422/405 a disclosure rather than
FastAPI's normal behavior for any unknown path.

**Why it matters.** Two distinct consequences, one small and one worth more than its severity:

1. The disclosure itself is minor. No token is issued, and an attacker learning that
   `/dev/token` exists on a FastAPI service learns very little — the endpoint's name is in a
   public-shaped codebase pattern anyway.
2. The gate is *load-bearing security infrastructure written in response to a P0*, and its
   stated reason for trusting a 404 is false. It happens to still work, because it probes with
   a valid body, which is exactly the shape that does reach the handler's gate. That is luck
   rather than design: nothing recorded anywhere says the probe body must stay valid for the
   gate to mean anything, so a later well-intentioned edit ("send an empty body, we only care
   about the status code") would silently turn the gate into decoration that always fails.
   This is the same class as D-096's `ecr:DescribeImages` finding — a check that appears to
   assert something stronger than it does.

**Live status, 2026-08-04 (D-171).** Still open, and now confirmed on **both** public CloudFront
edges rather than one: `POST /dev/token` with no body → **422** (with FastAPI's
`{"type":"missing","loc":["body"]}` body), `GET` → **405**, both with no credential, on
`d35dfnjzmgrm01` (learning) and `d222glidpp4azv` (chat). The chat edge was already recorded in the
S37 live section; the learning edge had only been measured via `TestClient`, so this closes that
gap. Survives the D-169/D-170 deploy. The security property is intact — a valid body with a missing
or wrong secret still returns 404 and mints nothing — so the deploy gate is right to pass.
**Retire the shorthand, though:** "`/dev/token` is 404 on both public edges", used in several
PROGRESS.md entries, describes the gate's *one probe shape*, not the endpoint.

**Disposition.** Phase 0B. Two changes, neither urgent: correct the comment to describe the
real mechanism and state that the probe body must remain valid; and register the route
conditionally rather than gating inside the handler, so a disabled endpoint is genuinely
absent for every request shape. The second is the real fix but touches how both apps'
`Settings` are read at import time, and the existing tests monkeypatch `get_settings` on the
module *after* import — so it needs a small test-approach change, which is Phase 0B work, not
mid-audit work.

#### ✅ Fixed 2026-08-04 (D-175) — in middleware, because the recommended fix was the wrong one

**The disposition's own reservation was the answer, not an obstacle.** Conditional registration
would force `Settings` to be read at import time, and both apps' tests — and the deploy gate's
reasoning — depend on `get_settings` being monkeypatchable *after* import. HTTP middleware runs
**before routing**, so it closes every request shape while leaving the decision per-request:
`install_dev_token_gate_middleware` (in `intellichoice_shared.auth`, next to
`staging_secret_matches`, following `install_global_rate_limit_middleware`'s established shape)
returns a 404 with a byte-identical body to a path that was never registered. The handler keeps its
own 404 as defence in depth, and both now call **one** predicate
(`_dev_token_endpoint_is_open`), so the gate and the handler cannot drift.

**Asserted, on both apps, over five request shapes** — the finding's three (`invalid_role_body`,
`empty_body`, `wrong_method`) plus `no_body` and an unregistered `PUT`. Each row is compared against
`/dev/nonexistent` as a genuinely-absent control, so the assertion is *indistinguishability* rather
than "returns 404"; the control is separately asserted non-vacuous. A sixth test pins the other
direction: a caller **holding** the secret still gets FastAPI's ordinary 422 for a malformed body,
because a gate that swallowed validation for everyone would be a different defect. All five failed
against the un-gated app first (405/422 vs 404).

**Two corrections to this entry.**

1. **The false sentence it quotes no longer exists.** *"With the endpoint gated off, the route is
   never registered on the app at all"* is not in `deploy-staging.yml` today — the comment was
   rewritten at some point between S35 and now, and the current text already treats 422 as a
   *symptom of reachability* rather than an impossibility. Only the mechanism half of the finding was
   still live. Grepped for the exact phrasing across the workflow, both apps and the docs: one hit,
   in this entry.
2. **The gate comment is updated for what actually changed**, which is subtler than "the disclosure
   is closed": a 422 from those probes now means the app considered the caller **authorized**, since
   nothing else can get past the middleware. That is a stronger and more alarming signal than the
   comment's previous reading, and the latent trap the finding correctly predicted — "send an empty
   body, we only care about the status code" quietly turning the gate into decoration — is gone,
   because body validity no longer has anything to do with what the gate proves.

**Live re-verification is owed at the next deploy**, and cheaply: the gate itself probes both edges,
and a `GET`/no-body probe by hand would confirm the 405/422 rows are gone from the public edges where
D-171 measured them. Not done here — this fix is not deployed yet.

## S36 continuation — the four uncovered audit areas (2026-07-25)

The S36 session covered money, minors/PII, authorization and the data-integrity pattern sweep,
and ran out. This continuation covers the rest: §3.4's scoring / re-grade-consistency /
policy-snapshot remainder, §3.5's mastery + hint ladder + generation pipeline + memory work, and
all of §3.6 (independent recomputation). Method note: §3.6 could not be done against the existing
database because every learning table except `student_reports` and `stage_transitions` was empty,
so **four complete journeys were driven through the real local API first** — improving (3→9), flat
(6→6), regressing (8→4) and pre-max (10→9) — and every number below is recomputed from those raw
rows with SQL that never calls the code under audit.

### AUD-L-10 — The server marks an exam item `answered`, then accepts more answers for it; scores are attempt-counted (P1)

- **Severity:** P1 — fail-open on a data-integrity invariant the server already has the state to
  enforce. Not P0: there is no production traffic, and the shipped UI closes the common path.
- **Area:** data integrity / deterministic scoring (SPEC §5.9.2, §5.13.3)
- **Status:** open, fix before the gate

**What.** `_mark_item_answered` sets `assessment_items.status = "answered"` on every submission and
`GET /exam/overview` reports it, so the server knows an item is done. Nothing on the answer path
reads it. Idempotency is keyed `(assessment_session_id, question_variant_id, Idempotency-Key)`, so a
second submission for the same item under a *different* key grades and inserts a second attempt —
it does not replace the first, and both count.

**Reproduction (live, local API).**

```
answer item 0 wrong  (Idempotency-Key: change-1) -> 200
answer item 0 right  (Idempotency-Key: change-2) -> 200
attempt rows for that one item                   -> 2      (a,d,f / d,d,t)
answer the other 9 items once each, finalize     -> 200
pre-exam totals                                  -> 11 attempts / 10 correct   (10 items served)
```

and without any phase manipulation:

```
answer an item, confirm overview reports status=answered
answer it again with a new key -> 200, attempt rows = 2
```

Of every assessment session in the local database, exactly one has `attempts > items`, and it is
this probe — so this does not otherwise occur, it is simply unguarded.

**Why it corrupts scores.** `learning_gain.compute_learning_gain`:

```python
pre_raw   = count(correct pre attempts)
max_score = len(pre_graded)            # ATTEMPT count, not item count
normalized_gain = (post_raw - pre_raw) / (max_score - pre_raw)
```

One changed answer on a 10-item exam gives `pre_raw=10, max_score=11`: the exam scores 10/11, and
the `pre_raw >= max_score` branch stops firing, so `not_applicable_pre_max` is silently replaced by
a computed `normalized_gain`. A duplicate *post* attempt pushes `post_raw` above `max_score`,
producing AUD-L-08's `> 1` case. Changing an answer from wrong to right therefore *lowers* the
score, which is the opposite of what a student would expect.

**Why the shipped UI mostly hides it, and why that is not enough.**
`ExamScreen` gates on `isReadOnly = isExamPhase && currentOverviewItem?.status === "answered"` and
renders "You've already answered this question - it's locked in and can't be changed." But the
optional chaining makes the guard default to **permissive**: when `currentOverviewItem` is
undefined — overview not yet fetched, or its fetch failed — re-answering is allowed. And
`submitAnswer` mints `crypto.randomUUID()` per call, so SPEC §5.9.2's idempotency key can never
match a prior submission and is inert for the purpose the spec cites it for. `busy={false}` is
hardcoded at all six screen call sites in `App.tsx`, so there is no in-flight guard either;
double-click is prevented only incidentally, by `setSelected(null)` disabling the button on
re-render. Any non-browser client is unguarded entirely.

**Recommendation.** Reject (or treat as idempotent) an answer for an item already `answered`,
server-side, in the same place the status is written; and derive `max_score` from the declared item
count rather than the attempt count. The second half also closes AUD-L-08's reachable path.

### AUD-L-11 — `UnknownQuestionVariantError` is caught nowhere: unhandled 500 (P2)

- **Severity:** P2 · **Area:** robustness / API contracts · **Status:** open, Phase 0B

Raised at `flow.py` lines 295, 416, 422 and 697; `grep` finds no `except` for it in any router, in
the graph, or in `main.py`. Live: `POST /answers` with `question_variant_id="does-not-exist"` →
**500 Internal Server Error**. Also reached by answering a valid variant that is not the currently
served study item — a stale tab, or a retry landing after the phase advanced (observed while
probing AUD-L-10).

The correct pattern already exists one file away: `POST /sessions/{id}/chat` validates the same
thing and returns 400. 500s inflate error-rate metrics and can trip the CloudWatch alarms S34
added, so this is noise in exactly the signal S39 will rely on.

**✅ Fixed 2026-08-03 (D-159).** The exception carries a required `reason` — `"unknown"` → **400**,
`"not_served"` → **409** — required rather than defaulted on
`record_assessment_attempt_idempotent`'s reasoning, so a new raise site fails typecheck instead of
picking a status code by accident. `pyright` caught six call sites the moment it became required,
which is the convention working.

Both cases are **pre-flighted off session state** before `graph.ainvoke`, for exam *and* study
phases, so the stale tab this finding describes no longer leaves checkpoint rows per resubmission
(asserted, using AUD-L-10's `_checkpoint_row_counts` probe). The existence read that separates 400
from 409 runs only on the failing path — membership already implies existence, so the happy path
pays nothing for the distinction.

### AUD-L-19 *(renumbered from `AUD-L-17` on 2026-08-04, D-174 — D-159 minted an id S36 already held; anything older citing `AUD-L-17` for variant ownership means this finding)* — the exam answer paths never checked that a variant belongs to this exam (P2, found in D-159)

- **Severity:** P2 · **Area:** data integrity / scoring · **Status:** ✅ **found and fixed in D-159**

Found while writing AUD-L-11's tests, and the reason its 409 case needed a test of its own: for a
pre/post-exam answer, `flow` checked only that the variant *exists*. A real variant belonging to
some other exam was therefore **graded and inserted into `assessment_attempts` for this session** —
`200 OK`, and `_mark_item_answered` silently no-ops because there is no matching item to mark.

Measured before the fix: a variant selected by `SELECT ... FROM question_variants WHERE
question_variant_id NOT IN (this exam's items)` returned 200 and left an attempt row behind. That is
an 11th attempt on a 10-item exam, i.e. the same attempt-counted scoring denominator
(`learning_gain.compute_learning_gain`'s `max_score`) that **AUD-L-10 was fixed to protect** — its
unique constraint is per `(session, variant)`, so a foreign variant slips straight past it.

The study path had this check already (`_record_study_attempt` looks the item up in
`study_items`); only the two exam paths lacked it. Now `flow.ensure_item_is_served`, pre-flighted in
the route and re-checked in the service, raising `UnknownQuestionVariantError(..., "not_served")`
→ 409.

### AUD-L-12 — `recommended_difficulty` is computed, stored and displayed, but routes nothing (P2)

- **Severity:** P2 · **Area:** SPEC conformance (§5.11.2 rules 2–3) · **Status:** ✅ **fixed in
  D-169 (2026-08-03)**

**Fix.** `study_plan._closest_to_recommended` narrows a skill's approved templates to the
recommended tier, widening to ±1 and then to the whole pool — a recommendation can narrow the
choice but never empty it. The unused-template rule (rule 4) applies *within* that narrowed pool
rather than across it, because SPEC ranks rules 2–3 above it: a used template at the recommended
tier beats an unused one two tiers away. That ordering is the one assertion an implementer is
likeliest to get backwards, so it has its own test.

Threaded at all three serve sites, each saying what it means: `build_study_plan` passes the first
target's own recommendation; `flow._serve_next_base_or_complete` gained `mastery_repo` and re-reads
each later base skill's row at serve time (its sole caller runs `_recompute_all_skill_mastery`
first, so the row reflects the attempt just graded — carrying the plan-time value on the session
would have been staler); and the retry ladder passes `None` **deliberately**, since same-skill
retry → prerequisite one tier down is already an explicit difficulty policy, and layering the
bootstrap recommendation on top could pull a deliberate step-down back up. The parameter is
required, not defaulted, so a new call site has to state which it wants — defaulting is how the
value went unused in the first place.

**⚠️ The behaviour limit, stated because the fix does not remove it.** The live bank is 1:1
skill↔difficulty (verified against the dev database: 5 approved skills, 10 templates each, one
tier apiece), so all three branches return the same full pool for every possible recommendation.
**The finding's own evidence still reproduces**: `aud-student-regressing` is still served tier 5
for `linear_distribute` with a tier-4 recommendation, because tier 5 is all that skill has. What
changed is that the mechanism exists, is tested, and the docstrings are true; what did not change
is any student's experience today. The user's decision was to keep §5.11.2 rule 1 (lowest mastery
skill) above rule 2 — the alternative, reordering target skills by the recommendation, would have
overridden a higher-ranked SPEC rule to make the number visibly matter.

**Tests, watched failing pre-fix.** Nine unit tests in
`test_study_plan_difficulty_routing.py` against synthetic multi-tier templates — the only way to
exercise a mechanism no real content can reach — including one that asserts the masking itself
(`test_the_live_bank_shape_makes_the_narrowing_inert`), so the day content grows a second tier per
skill, that test fails and says so. Plus
`test_learning_flow.py::test_difficulty_recommendation_reaches_template_selection`, which records
what reaches `_select_template` during a real flow and asserts all three contracts (routed base,
unrouted remediation, re-read next base). It deliberately asserts no served tier: on 1:1 content a
tier assertion passes with the value still discarded, which is precisely how this survived.

**Original finding below.**

`mastery_bootstrap.recommended_difficulty` implements the rule correctly (modal assessed tier,
nudged ±1 by accuracy, clamped 1–5) and `flow.py:233` stores it per skill. Two docstrings claim it
drives routing — `mastery_bootstrap.py:7` ("for difficulty routing (§5.11.2 rules 2-3)") and
`study_plan.py:5-7` ("`recommended_difficulty` (from bootstrap mastery) **seeds the session's
`starting_difficulty`**"). Neither is true: `build_study_plan` reads it into `recommended`
(line 133), packs it into the ranking tuple (138), and drops it — line 142 unpacks only `skill_id`.
`starting_difficulty` is assigned `first_item.difficulty` (line 169). Its only other readers are
display surfaces (`students.py:130`, `history.py:110`).

**Evidence.** `aud-student-regressing`'s weakest skill `linear_distribute` has
`weighted_score = 0.0` and `recommended_difficulty = 4` — stepped *down* from tier 5 because
accuracy was 0 — yet the study session was created with `starting_difficulty = 5`. The student was
served the tier they had just failed, with the model's step-down recommendation unused in the same
transaction.

Masked today because the bank is 1:1 skill↔difficulty (the D-060/A6 collinearity, which
`study_plan.py:7-8` acknowledges: "a skill *is* its difficulty tier"), so ranking by weakest skill
accidentally yields a defensible tier. It stops being accidental the moment real content has more
than one skill per tier. Either wire it up or delete it and correct both docstrings — a computed,
stored, displayed number that influences nothing is worse than an absent one.

### AUD-L-13 — Memory consolidation verifies provenance and repetition, never the claim against measured mastery (P2)

- **Severity:** P2 · **Area:** minors / correctness · **Status:** ✅ **fixed in D-156 (2026-08-02)**

**Fix.** `_contradicts_measured_mastery` in `consolidation.py` refuses a `strength` candidate for a
skill whose `mastery.weighted_score` is below `WEAK_SKILL_THRESHOLD`, and a `weak_skill` candidate
for one at or above it. Applied on the add path **and on the reconfirm path** — the latter is the
branch this finding actually turns on, because reconfirmation is the promotion path and the
finding's own point is that the promotion criterion is repetition rather than consistency.

Three deliberate boundaries, each with a test: only the two fact types a score can contradict; it
abstains when there is no mastery row (a never-assessed skill has no measurement to be wrong
about); and the cut is strictly-below, matching `topic_resolver` and `learning_gain` exactly —
`WEAK_SKILL_THRESHOLD` moved to `intellichoice_shared.mastery_policy` so a package and an app share
one definition instead of two copies. Refusals are counted on `ConsolidationResult
.mastery_conflicts`, logged as `memory_fact_contradicts_mastery` (fact type and score, no student id
and no fact text — the text is a claim about a minor's ability, SPEC §5.30), and printed per-student
and in the run summary, because a screen whose cost is invisible is a screen nobody tunes.

**Original finding below.**

`consolidation.py` verifies that a candidate fact's cited `evidence_event_ids` exist, demotes an
opposite-polarity fact to `contested` rather than replacing it, and requires ≥2 sessions of
evidence before promoting `provisional` → `active`. It never compares the fact against
`mastery.weighted_score` for the same skill, which is in the same database and the same transaction.

**Evidence.** `aud-student-regressing` has `mastery.weighted_score = 0.0` for `linear_distribute`
and an accepted `strength` fact for that same skill — *"Shows independent strength in this
skill."* — citing real events. Across all four journeys **all 20 facts are `strength` and zero
`weak_skill` facts exist**, including for the student who went 8→4 and whose own
`learning_gain.unresolved_skills` names `linear_distribute`.

**Bound, and it is a real bound.** `_resolve_relevant_fact` uses `top_fact_for_skill`, which
excludes `provisional`/`contested`/`superseded`/expired, so only `active` facts reach tutoring
payloads and parent-visible reports — and everything here is `provisional`. Nothing prevents it
after a second session, though, because the promotion criterion is repetition, not consistency.

Same class as AUD-L-09 (provenance verified, attribution not), one layer earlier in the pipeline,
and it concerns claims about a child's ability that AUD-L-04 already showed reach parents.
A deterministic floor — refuse a `strength` fact for a skill whose measured mastery is below
`WEAK_SKILL_THRESHOLD`, and vice versa — is cheap and does not depend on model quality.

### AUD-L-14 — `time_spent_minutes` reads best-effort client telemetry and ignores the always-populated server column (P2)

- **Severity:** P2 — a wrong parent-visible number, presented as a *verified fact*. Fails low.
- **Area:** correctness / reporting · **Status:** ✅ **fixed in D-162 (2026-08-03)**

**Measurement first (the filing's own condition), then the fix.** A browser-driven full journey
(`journey-student.spec.ts` against the local stack, rows isolated by run timestamp) populated both
sources within ~7%: **1,453 ms** summed `response_time_ms` across 10 attempts vs **1,354 ms**
summed item-state across 10 rows for the same pre-exam. So the zero was S36's API-driven journeys
never running the browser telemetry — consistent with D-107's 15,591 ms for a 15,000 ms dwell —
and the finding reduces to the reliability asymmetry: the telemetry tick is fire-and-forget
(`.catch(() => {})`, dropped by hard refresh, closed tab, or any non-browser client) while
`response_time_ms` is a **required field of `SubmitAnswerRequest`** — an attempt row cannot exist
without it, by construction. Both are client-reported (same `viewStartRef`); only one is load-bearing.

**Fix.** `build_dashboard` sums `response_time_ms` over the attempt rows it already fetches for
`attempts_count` — one query fewer, and the two figures now derive from the same rows so they
cannot disagree about which attempts exist. `total_assessment_time_ms_in_range` and its half-true
docstring ("the only populated per-question timing source") are deleted with it, per the
delete-the-second-definition precedent D-159 set. The dashboard tests now seed item-state rows at
`time_spent_ms = 0` — AUD-L-14's live shape — and assert a non-zero `time_spent_minutes` from the
attempts. Telemetry itself is untouched: it remains the exam screen's autosave/resume signal, and
AUD-F-01's regression spec still guards its volume and honesty. Study time remains genuinely
unavailable (`study_attempts` has no response-time column), now stated on the `DashboardData` field.

**Original finding below.**

`build_dashboard` computes `time_spent_minutes = total_time_ms / 60000`, where
`total_assessment_time_ms_in_range` sums `AssessmentItemState.time_spent_ms` — populated only by
S23's autosave tick (`POST /exam/items/{id}/time`), sent by the frontend. Meanwhile
`assessment_attempts.response_time_ms` is `NOT NULL` and written on every answer.

**Evidence.** The four journeys produced **140 `assessment_item_state` rows with
`sum(time_spent_ms) = 0`**, while the same students' attempts hold 41,250 ms per exam (≥82.5 s
each across both exams). `POST /students/{id}/report` accordingly returned, inside
`verified_facts`: `attempts_count: 26` and `time_spent_minutes: 0.0`. `verified_facts` is the
grounding set the narrative is checked against, so "0.0 minutes" is presented as verified.

The repository docstring claims item-state is "the only populated per-question timing source in
this schema". Half true: `study_attempts` genuinely has no response-time column, so study time
really is unavailable — but for exams an always-populated source exists and is ignored.

Frontend fragility compounds it: `ExamScreen` records time in a `useEffect` **cleanup** (fires on
item/phase change or unmount), gated on `currentOverviewItem?.assessment_item_id` being present,
and `useLearningSession.recordItemTime` swallows every failure with `.catch(() => {})`. A hard
refresh, a closed tab, a failed overview fetch, or any non-browser client yields 0.0.

### AUD-L-18 — numeric grounding rejected every real generation, so the parent narrative never shipped (P1, found and fixed in D-163)

- **Severity:** P1 — a paid-for feature that has never worked in production, silently. Fails
  closed, which is why it went unnoticed: every parent got a correct, verified, un-personalized
  report and no error was ever raised.
- **Area:** correctness / parent-visible · **Status:** ✅ **fixed in D-163 (2026-08-03)**

**How it was found.** D-162 §3's live AUD-X-04 exercise saw `generated: false` on both of its
Bedrock-backed generations — the model call succeeded (`repaired: false`, real spend settled) and
then `is_grounded` refused the output. D-162 §4 named it, suspected staging's load-test-polluted
aggregates (`attempts_count: 7371` inviting "7,371"), and required a local reproduction before any
fix.

**The measurement refuted that suspicion.** `scripts/measure_report_grounding.py` ran the deployed
model (Haiku 4.5) five times each over three payload shapes — staging's polluted aggregates, an
ordinary 26-attempt month, and a variant with every repeating decimal replaced by a clean one:

| arm | ungrounded | causes |
|---|---|---|
| staging (`attempts_count: 7371`) | **5/5** | percent 27, thousands-separator 8, evidence-string 1 |
| control (`attempts_count: 26`) | **5/5** | percent 30 |
| integers (clean decimals) | **5/5** | percent 28, evidence-string 1 |

The control arm contains no number a thousands separator could reach and still failed every time.
So the polluted data was a red herring and the real finding is larger than D-162 §4 supposed: the
feature had **never** worked, on any data, since S28 shipped it.

**Three causes, none of them the model inventing anything.**

1. **Percent rendering (85 of 94).** Evidence carries `mastery_by_skill: 0.8333`; a parent-facing
   writer renders that "83%". Nothing in the checker understood scale, so the single most natural
   phrasing of a proportion read as fabrication.
2. **Thousands separators (8).** `-?\d+(?:\.\d+)?` tokenized `"1,284"` as `1` and `284`. A
   tokenizer bug, not a policy question.
3. **Numbers inside evidence strings (2, but structural).** `_collect_evidence_numbers` walked
   only `int`/`float` values, so `date_range_label` ("2026-07-01 to 2026-07-31") and the "70%"
   interpolated into `weak_skill_window_label` were invisible — while the prompt (AUD-L-15/D-156)
   *instructs* the model to name the window each figure comes from. Two fixes were fighting.

**The fix, and where it is deliberately not loose.** The percent rule applies only when the
evidence value is itself a proportion in `[0, 1]`, so `raw_gain: 3.0` still does not ground
"improved 300%" — without that bound the rule would be a 100× fail-open. The tolerance is an
absolute half percentage point rather than `round()`, because Python rounds halves to even
(`round(62.5) == 62`) and would have rejected the equally correct "63%" for `0.625`. Strings are
walked as evidence on the reasoning that a number the model was shown *is* evidence; that is a
false-negative fix, not a loosening.

**What still fails, verified in the same harness.** The re-measurement caught the real model
summing `6` hints and `2` solutions into "accessed hints or solutions **8** times", and dividing
18.5 minutes by 26 attempts into "about **40** seconds per problem" (which is also simply wrong —
it is 42.7). Both were correctly rejected. The prompt now forbids deriving numbers, and separately
forbids advice quantities ("even 5–10 minutes a few times per week") — those are not claims about
the student, but the check cannot safely exempt `recommendations_text`, where "improve by 20
points" would also live. **Final re-measurement: 15/15 grounded.**

**Why no test could have caught this.** `MockBedrockProvider._report_interpretation_json` builds
its output from the payload's own fields, so it round-trips `is_grounded` by construction. The
local suite is structurally incapable of observing a grounding failure, and always was. The
harness is committed for that reason.

**Bearing on AUD-L-09**, which stays open and gets slightly more load-bearing: grounding verifies a
number's *provenance*, not its *attribution*, so "fell from 6 to 4" still passes when the real
movement was 4 → 6. Widening provenance does not widen attribution, but it does mean more model
prose now reaches parents, so the attribution gap is worth more than it was.

### AUD-L-15 — Mastery and "skills to strengthen" use different windows and are shown together as "all time" (P2)

- **Severity:** P2 · **Area:** correctness / reporting · **Status:** ✅ **fixed in D-156 (2026-08-02)**

**Fix, in three parts — and the finding's "decide deliberately whether mastery should include the
post-exam" was put to the user and answered yes.**

1. **Mastery includes the post-exam.** `_recompute_all_skill_mastery` gained
   `post_assessment_session_id`, and `_finalize_post_exam` now calls it — it never did, so the
   post-exam reached mastery through no path at all. The second consequence was the bigger one:
   `topic_resolver` picks the *next* cycle's target skills from `mastery.weighted_score`, so it was
   choosing them without ever seeing how the last cycle ended. The gain stays a clean instrument —
   `compute_learning_gain` reads raw attempts and never consults mastery.
2. **One definition of "weak".** The report's hardcoded `0.8` on post-exam accuracy is gone;
   `weak_skill_names` now reads `mastery.weighted_score < WEAK_SKILL_THRESHOLD`, the same cut the
   study plan uses. Only correct *because of* part 1. `learning_gain.unresolved_skills` keeps its
   post-exam-only computation on purpose: it is a frozen record of one cycle, not current standing.
3. **Every figure states its window** — `MASTERY_WINDOW_LABEL`/`PRE_POST_WINDOW_LABEL` in
   `services/dashboard.py`, carried into the report payload (audience-gated with their figures),
   into `_SYSTEM_PROMPT`, and into `GET /dashboard` as chart captions the client renders.

**Deliberately still true:** mastery is not date-filtered (`mastery_repo.list_for_student` takes no
range). That is now stated in the label rather than implied by silence — "current standing" is the
right thing for a mastery chart to show.

**Original finding below.**

`_recompute_all_skill_mastery` accepts only `pre_assessment_session_id` and `study_session_id`;
the post-exam is **structurally excluded**, and its docstring says so ("every skill touched by the
pre-exam or study phase"). `unresolved_skills` / `weak_skill_names` come from `learning_gain`,
which is post-exam-derived. Both land in one report payload.

**Evidence** — `aud-student-premax` (10/10 pre, 9/10 post):

| skill | `mastery_by_skill` | listed in `unresolved_skills` |
|---|---|---|
| `linear_distribute` | **1.000** | **yes** |

The same report's `interpretation_text` reads *"Skills to strengthen: Solve linear equations
requiring distribution and combining like terms"* while `mastery_by_skill` gives that skill 1.0,
and `verified_facts.date_range_label` says **"all time"** — which misdescribes mastery, since
mastery never sees the post-exam. A parent sees 100% mastery and "needs work" for one skill in one
view, both labeled verified.

**The arithmetic is correct.** Recomputing mastery from raw rows restricted to the pre+study window
reproduces all five skills exactly (`linear_both_sides` 1.0000, `linear_distribute` 0.0000,
`linear_neg_frac_coeff` 1.0000, `linear_one_step` 1.0000, `linear_two_step` 1.0000). This is a
windowing and labeling defect, not a computation defect — the fix is to state each number's window,
and to decide deliberately whether mastery should include the post-exam.

### AUD-L-16 — Both policy snapshots are write-only (P3)

- **Severity:** P3 (no behavioral defect today) · **Area:** design integrity (SPEC §5.9/§5.13)
- **Status:** open, Phase 0B

`assessment_sessions.policy` and `study_sessions.intervention_policy` are written at creation and
**never read back anywhere**. The only consumers of `exam_policy` in either app are the two
`get_policy()` calls in `assessment_builder`, both at creation time. Only `time_limit_seconds`
governs runtime behavior, and it does so through its own denormalized column
(`flow.py:142-144`), not through the snapshot.

`hints_allowed`, `navigation` and `feedback_visibility` are enforced — where at all — by hardcoded
phase-string checks: chat returns 409 unless `phase == "study"` (its comment says it is "matching
`exam_policy`'s `hints_allowed=False`", i.e. the policy is documentation, not the mechanism), and
intervention interrupts are only ever created on the study path. Those checks agree with the
snapshot today, but a policy change would apply retroactively to in-flight sessions — the one thing
snapshotting exists to prevent. `intervention_policy` is a hardcoded `{"hints_enabled": True}`
literal at `study_plan.py:152`.

### AUD-L-17 *(keeps the id as the original holder; D-159's colliding P2 was renumbered to `AUD-L-19` by D-174)* — The default mock's hint boilerplate tripped the runtime leak check; `was_personalized` records no reason (P3, mock half fixed in-session)

- **Severity:** P3 · **Area:** test integrity + observability · **Status:** mock fixed; the
  observability half is open, Phase 0B

D-097's addendum recorded the long-standing
`test_hint_reflects_the_students_actual_wrong_option` flake as unseeded-RNG-driven at ~1 in 4 and
prescribed "seeding the fixture's RNG". The mechanism was RNG-driven; the attribution was wrong,
and no fixture RNG exists to seed — `_turn_context` constructs `random.Random()` per request
inside the route handler.

**Real cause.** `tutor.generate_personalized_hint` discards any hint in which
`answer_text_leaked` finds the served question's correct answer standing alone, substituting the
canonical ladder text. `MockBedrockProvider`'s personalization stand-in prefixed its output with
`Level {level} hint`, and `answer_text_leaked("Level 1 hint…", "1")` is `True` — a bare `1` with
non-alphanumerics on both sides. ~6% of this bank's variants have the answer `"1"`, and the
unseeded per-request RNG chooses the variant, so the test failed whenever that variant was served.
Measured **8 failures in 60 standalone runs** (13%), not 1 in 4; every failure returned the level-1
canonical text verbatim, confirming the fallback path.

**Fixed** by changing the marker to `Hint L{level}` — gluing the digit to a letter satisfies the
check's lookarounds — with the reason written into the docstring so it is not "tidied" back.
**60/60 passing** afterwards, against 52/60 before. Pinned by a new deterministic guard,
`packages/curriculum/tests/test_mock_hint_is_leak_clean.py`, which asserts the mock's output is
leak-clean for every reachable short answer at every level of every shape ladder, and that it still
names the misconception and varies by level.

**The half that is not fixed, and matters more.** `hint_events.was_personalized` is a single
boolean with no reason code, so *gateway failure*, *leaked answer*, *ladder monotonicity violation*
and *model set `answer_revealed`* are indistinguishable after the fact. `answer_text_leaked` is a
boundary-anchored substring match and roughly 54% of this bank's variants have a single-digit
answer, so any real model hint whose prose contains that digit standing alone ("Step 1", "try 2
more") is silently downgraded to the canonical hint. It fails safe — the student gets a generic
hint, never a leaked answer — but the rate is unmeasurable from what is stored, which means the
quality cost of a safety check cannot be observed in production.

### Areas audited with no finding

**Money — no Bedrock call bypasses the gateway.** Grepped every `raw_generate` / `raw_embed` /
`invoke_model` / `boto3` reference across `apps/` and `packages/`: the only hits outside
`adapters/bedrock/` are two comments. Every paid call in both apps really does go through
`ResilientBedrockGateway`, so the timeout, bounded retry, `_HARD_MAX_OUTPUT_TOKENS = 4000` cap,
circuit breaker, and cost accounting are unavoidable rather than conventional. This is the
premise AUD-L-02 depends on, so it was checked rather than assumed.

**Money — every other `session_spend_cents` call site passes a real accumulated value.** All 20+
call sites traced. The graph nodes thread `bedrock_spend_cents` (persisted in the checkpoint, so
it survives a process restart) and correctly pass `bedrock_spend_cents + cost` where several
calls happen inside one node; `video_catalog`, `tutor`, `tutor_chat`, and chat's own nodes all
receive a real total. The two defaults were the only two gaps, and both are now closed or logged.

**Money — bounded-by-design behaviors, noted but not findings.** The pre-flight budget check
estimates input at a hardcoded 2,000 tokens, so a call whose real payload is larger can overshoot
the ceiling by one call's worth; and a `generate_structured` call can make up to four provider
calls (three attempts plus one repair) while the budget is checked only once, at entry. Both are
bounded overshoots of a ceiling rather than absent ceilings, and the circuit breaker limits
sustained failure spend (verified with a real concurrency test in S34). Recording them so a
future session doesn't have to re-derive that they were considered.

**Money — no account-level enforcement exists**, only the AWS Budget *alarm*. This is
infrastructure rather than learning-product code, so it belongs to S39/AUD-F's operations audit
(§2.6 criterion 8 already requires proving alarms reach a human); noted here as a cross-reference
so it is not lost between the two sessions.

**Authorization — every learning route enforces the check; the coverage is uniform.** All 17
routes across `questions.py`, `sessions.py`, `stream.py` and `students.py` were enumerated and
each traced to its authorization call. Student-scoped routes call `resolve_target_student` with
the path's `student_id`; session-scoped routes call it with the *checkpoint's*
`student_external_id` rather than anything client-supplied, which is the right source. The four
`exam/items/...` routes share one helper, so they cannot drift apart. `POST /sessions` (create)
deliberately has no student yet and says so (`del claims  # authentication only`). No route was
found missing a check — the only authorization defect is AUD-L-07, which lives in the shared
function, not in any route.

**Authorization — the SSE `?token=` path verifies audience and ownership.** `stream.py` verifies
the token against `Audience.LEARNING` explicitly (a chat-audience token is rejected), then applies
`resolve_target_student`, and for a session that has no student selected yet falls back to
comparing `claims.sub` against the checkpoint's `user_external_id` — so a brand-new session cannot
be attached to by a different caller either. `/resume` has the same two-branch check. Deeper
SSE/thread-hijack work is AUD-X/S38's, but these two properties hold.

**Data integrity — the D-071 checkpoint-overwrite bug class does not recur in the learning app.**
Swept every explicit `": None"` channel write in both graphs. The learning app has exactly two,
and both are correct *because* they erase: `"last_items": None` when attendance blocks a start (a
stale question batch must not sit beside a blocked message) and `"last_message": None` when
entering the pre-exam with fresh items. Neither is the S23 shape, which was writing `None` to mean
"nothing new to report". The chat app has ~40, including 12 writes of `"access_hint": None` — not
audited here (AUD-C/S37 owns it) but flagged as a cross-reference, since `access_hint` is the field
in the known S22.5 blank-turn bug and that combination deserves a deliberate look.

**Data integrity — finalize is genuinely idempotent, at both layers.** `flow.finalize_exam`
returns `None` when the target `AssessmentSession` already has `finalized_at`, and the node then
returns `{}` — which under LangGraph's default merge preserves every channel, the same
"omit to preserve" convention D-071 established. The route additionally allows the `study` and
`completed` phases through on purpose, so a retry arriving after the phase has visibly moved still
re-serves the same result instead of 409ing, and it 409s explicitly when no student is selected
rather than relying on a downstream failure.

**Test signal — the known RNG flake is characterized more precisely than before, and it matters
for the gate.** `test_hint_reflects_the_students_actual_wrong_option` failed once in a full run and
once standalone this session, then passed three consecutive standalone runs and two full runs.
PROGRESS.md's prior sessions describe confirming it "via an immediate clean standalone rerun" — but
it reproduces standalone too (roughly 1 in 4 attempts here), so it is **purely unseeded-RNG driven,
not test-order dependent**. That is good news for whoever fixes it: seeding the RNG in the fixture
is sufficient, and no ordering investigation is needed. It is bad news for §2.6 criterion 4, which
requires three consecutive green full runs — at this failure rate that is a coin flip, so the
criterion would be met by luck rather than by signal. Fix the seed before attempting the gate.

**Question bank — what is actually `approved` and deliverable today, measured.** Queried the real
dev Postgres rather than reasoning from the seed scripts: **1 topic, 5 skills, 50 templates**, all
`validation_status=approved` and `active_status=active`, exactly 10 templates at each difficulty
1–5. `build_pre_exam` needs 2 per difficulty, so exam construction is satisfiable with 5× headroom
— the bank is *sufficient*, which is worth stating separately from being *broad*. It is not broad:
one topic, and **exactly one skill per difficulty level**, so skill and difficulty are perfectly
collinear in this data. Any "skill-level gain" is also a difficulty-level gain, and no test using
this bank can distinguish the two. That is the known A6/D-060 content gap (which gates the pilot,
not the build), now quantified.

**Two known carry-overs re-measured, both materially worse than last recorded** — numbers handed
to Phase 0B rather than left as "worsening": `question_variants` is at **42,023 rows across 50
templates**, with a worst single template at **1,559** (S23 recorded 610 on one template, so ~2.5×
growth in one session's worth of elapsed work); the `checkpoints` table is at **264,475 rows**
(S34 recorded 249,250). Both confirm the accumulation is ongoing rather than a one-off, which is
the assumption the seeded backlog items were written under.

**Correctness — the retry ladder matches SPEC §5.11.7 exactly, including the part that looked
wrong.** `study_outcomes.ladder_step` maps attempt counts to moves precisely as the spec's table
does (1st → retry, 2nd → retry with more explicit support, 3rd → easier prerequisite, 4th →
unresolved + tutor review), all six final outcome labels exist, and mastery is recomputed only
*after* the label is final so an assisted or unresolved answer can never inflate independent
mastery. There is also a sensible unspecified degradation: the prerequisite drop only happens if
the prerequisite actually has approved templates, otherwise it retries the same skill rather than
serving nothing.

I went in expecting a real bug here and did not find one. The escalation counts attempts on a
"line" filtered by the item's `target_skill_id`, so dropping to an easier prerequisite looked like
it would start a fresh line and make the 4th-attempt tutor-review escalation unreachable — a
student could fail forever without ever being flagged. It does not: `create_study_item` takes
`target_skill_id` (the base skill whose line the item belongs to) *separately* from `skill_id` (the
skill the question is drawn from), so a prerequisite question keeps the original line's identity
and the counter keeps climbing to the tutor-review threshold. Recording this as a negative result
specifically because the correct behavior depends on a two-parameter distinction that is easy to
misread as a bug, and the next person to look will otherwise re-derive the same false alarm.

**Correctness — the learning-gain formulas match SPEC §5.13.3 exactly.** `Raw Gain = Post − Pre`
and `Normalized Gain = (Post − Pre) / (Max − Pre)` are implemented literally, and the perfect-pre
case sets `normalized_gain_status = "not_applicable_pre_max"` with `normalized_gain = None` as the
spec requires (rather than emitting a division-by-zero or a misleading 0.0). All twelve fields
§5.13.3 says to store are present and populated: pre/post raw, raw gain, weighted gain, normalized
gain, skill-level gain, difficulty transition, independent-correct rate, hint dependency, solution
dependency, unresolved skills, and response-time change. AUD-L-08 is a missing bound on the result,
not a wrong formula.

### Areas audited with no finding — S36 continuation

**Scoring is deterministic, and stored rather than re-derived.** All 93 stored
`assessment_attempts` satisfy `is_correct == (selected_option == correct_option)` — zero
disagreements. `resolve_graded_attempts` uses `attempt.is_correct` for assessment attempts, so a
later edit to a variant cannot retroactively re-grade a past exam. Zero attempt rows disagree with
their variant's *current* `correct_option`, so no drift has occurred either. Every field SPEC §5.9.3
requires on an attempt is present, including `correct_option` frozen at submission time.

**Template edits cannot retroactively move historical analytics.** `skill_id` and
`difficulty_label` *are* read live from `question_templates` when grading attempts for mastery and
gain, which looked like a re-grade-consistency hole. It is not: templates are versioned by creating
new rows, and `supersede_template` only flips `validation_status` while keeping the prior row — so
the fields the analytics read are immutable per row.

**Unanswered items fail closed.** A skipped item and a never-visited item both received attempts
with `selected_option = NULL, is_correct = false` under a `finalize-unanswered-*` key; totals stayed
10 attempts / 8 correct on a 10-item exam. Unknown is not treated as correct.

**Exam assistance cannot leak in, matching `hints_allowed=False`.** During `pre_exam`: `/respond`
with `intervention_choice` → 409 "no interrupt is pending"; `/chat` → 409 "chat is only available
during study"; a wrong answer produces no interrupt and withholds correctness (`is_correct: null`,
matching `feedback_visibility=hidden_until_finalize`). The enforcement is structural rather than
policy-driven (AUD-L-16), but it holds.

**SPEC §5.9.1 exam composition is exact.** Every pre- and post-exam served 2 questions per
difficulty tier 1–5, total 10, verified by joining `assessment_items` through `question_variants` to
`question_templates.difficulty_label` for two students across four exams.

**SPEC §5.10.1's weights and formula are literal.** `DIFFICULTY_WEIGHTS = {1: 1.0, 2: 1.4, 3: 1.9,
4: 2.5, 5: 3.2}` matches the spec's example exactly, and `weighted_score` is exactly
`Σ(weight where correct) / Σ(weight)`.

**SPEC §5.11.1's `base_problem_count = 5` holds.** The 6 study items per journey are 5 base + 1
remediation; §5.11.1 says remediation is "tracked separately", so 6 is conformant, not off-by-one.

**The hint ladder is correct end-to-end, driven live.** Three levels served in order, all texts
distinct, `answer_revealed=False` throughout, none containing the question's real answer text, and a
fourth request closes the ladder with 409 rather than looping or re-serving. All three rounds landed
in `hint_events`.

**Question-bank integrity is clean** across 50 templates / 43k variants: zero duplicate option sets,
zero `correct_option` outside `a–d`, zero null option text, zero empty `rendered_question`, zero
difficulty outside 1–5, zero templates without variants.

**Dashboard and report numbers reconcile against independent SQL.** `overall_accuracy` recomputed
bit-identically (`0.9230769230769231`, 24/26); `accuracy_trend` matched (17/26 = 0.6538);
`mastery_by_skill` matched all five skills exactly once restricted to its real window;
`pre_post_by_skill` reconciled item-by-item against difficulty tiers. The only report numbers that
did **not** reconcile are AUD-L-14 and AUD-L-15.

**`starting_difficulty` is not inverted** — I suspected it was, since a 10/10 student got tier 1
while an 8/10 student got tier 5. That is §5.11.2 rule 1 (lowest mastery first) working: the 8/10
student's two misses were both tier 5, and a perfect scorer ties on every skill so the documented
curriculum-order tie-break decides. Recorded because it reads like a bug.

**My own first recomputation was wrong, not the API.** An initial independent mastery calculation
disagreed with the dashboard on two skills (0.6 vs 1.0) because it summed *all* attempts while
mastery covers pre+study only. Recorded so the next session does not repeat it — and it is what led
to AUD-L-15.

**Note, not a finding:** `accuracy_trend` and `overall_accuracy` count hint-assisted corrects as
correct, while mastery counts only `independent_correct`. Both appear on one dashboard. Defensible
(one is "accuracy", the other "independent mastery") but the labels do not say so.

_(Still **not** covered: the browser-driven adversarial runs — refresh mid-exam, concurrent tabs,
expired timers, dropped SSE — and the live-staging half of §2.3. See PROGRESS.md for the explicit
list, rather than leaving the absence to be inferred from this file. The API-level adversarial
probes that *were* run are the ones evidenced above and in AUD-L-10/11.)_

---

## S37 — AUD-C (chat product correctness)

Method as §2.3 requires: traceability over SPEC §5.19–§5.24, §5.25.3, §5.29's chat rows and
§5.30.2/§5.30.4; defect-pattern sweeps for every class this project has already produced; and
adversarial runs — local against the real graph and real Postgres, plus a bounded pass against
**live staging** (`d222glidpp4azv.cloudfront.net`). Retrieval quality was measured twice, once with
`MockBedrockProvider` and once against **real Bedrock** (Haiku 4.5 + Titan v2, 76.7¢, 13m17s), which
is what made AUD-C-05 and AUD-C-06 visible at all.

### AUD-C-01 — `/messages` has no thread-ownership check, and an anonymous turn *erases* the owner the other two endpoints check (P1)

- **Severity:** P1. §2.4 lists authorization bypass under P0; this is held at P1 only because
  exploitation requires the thread's `uuid4` session id, which is never published, never in a URL
  bar, and not enumerable. The P0 argument is recorded below — it is not a comfortable margin.
- **Reproduction (live staging, deployed config, this session):**
  1. `POST /chat/sessions` → session id.
  2. `POST /chat/sessions/{id}/messages` with a **tutor** bearer token → grounded answer, and the
     thread's checkpointed `user_external_id` becomes `aud-c-tutor`.
  3. `POST /chat/sessions/{id}/messages` with **no Authorization header at all** → **HTTP 200**.
     The response body carries the tutor's previous answer *and* its citation
     (`public-organization-overview`) verbatim.
  4. `POST /chat/sessions/{id}/respond` with no token → **HTTP 200**. It succeeds because step 3
     rewrote `user_external_id` to `None`.
- **Locally, with a tutor-audience chunk that only a tutor could retrieve**, step 3's response
  contained the tutor-only text verbatim (`"Confidential tutor procedure: … the pager rota and the
  incident register are kept behind the lanyard cabinet"`), i.e. content the pre-retrieval filter
  had correctly withheld from anonymous callers one turn earlier. The same text was then served
  again by `GET /stream`'s initial snapshot, and every *subsequent* tutor turn was pushed to an
  event-bus subscriber that attached while the thread was owner-less — the SSE access check runs
  once, at connect time, and is never re-evaluated when ownership returns.
- **Two independent defects compose here.** The leak vehicle is AUD-C-04 (stale presentation
  fields); the authorization hole is this one. Either alone is much less serious. Fixing only
  AUD-C-04 would still leave an unauthenticated caller able to drive, and resolve interrupts on,
  someone else's thread.
- **Why it is asymmetric, and therefore unintentional.** `respond_to_interrupt` and
  `_initial_snapshot` contain the *same* five-line owner check. `post_message` does not — and it is
  the only one of the three that *writes* the field the other two read.
- **P0 argument, recorded rather than acted on.** Content that SPEC §5.21.3 requires be filtered
  before retrieval reaches a caller who may not retrieve it, and a documented access boundary is
  removable by an unauthenticated request. What holds it at P1: the attacker must already hold a
  128-bit session id, staging has no real users, and `/dev/token` is secret-gated. §2.4 reserves
  mid-audit fixes for P0s, so this is logged, not fixed — but it is the first item of Phase 0B, and
  both halves must land together.
- **Fix shape:** apply the existing owner check in `post_message`, and make `resolve_role` refuse to
  *downgrade* a thread's `user_external_id` from a value to `None`.

### AUD-C-02 — The scope guard's own topic list omits the organization, so "What is IntelliChoice?" is refused as out of scope (P1)

- **Severity:** P1 — a launch journey is broken for what is plausibly the most common question an
  anonymous visitor asks, on the deployed system, today.
- **Reproduction (live staging, 5/5):**

  | query | scope | intent | citations |
  |---|---|---|---|
  | `What is IntelliChoice?` | **out_of_scope** | clarification | — |
  | `Who leads IntelliChoice, and what did they do before?` | **out_of_scope** | document_qa | — |
  | (same query, repeated) | **out_of_scope** | document_qa | — |
  | `Who is on the IntelliChoice leadership team?` | **out_of_scope** | clarification | — |
  | `Tell me about the people who run IntelliChoice` | **out_of_scope** | clarification | — |

  Each returns SPEC §5.19.4's refusal — *"I cannot answer unrelated general-purpose questions"* —
  while `public-organization-overview` and `public-our-team` are approved, effective today, and
  ingested (the same corpus answers other questions with citations in the same session).
- **Root cause, and it is one line.** SPEC §5.19.4's supported-topic list begins with
  **"IntelliChoice organization"**. The `SCOPE_AND_INTENT` system prompt in
  `chat_api/graph/nodes.py` enumerates *"branches, schedules, volunteering, student learning, parent
  information, tutor/branch procedures, the academic calendar, and learning-app support"* — the
  organization itself is missing, as is §5.19.4's "student participation". A real classifier obeys
  the list it was given.
- **Why no test caught it.** `MockBedrockProvider._scope_and_intent_json` keys on a keyword tuple
  that *does* contain `"intellichoice"`, so every mock-backed test scores these queries in scope.
  The prompt text is never asserted against SPEC's list anywhere.
- **Note:** two of the five runs returned `in_scope=false` alongside `intent=document_qa` — the
  model contradicting itself within one structured response. The pipeline resolves that toward
  refusal (fail-closed, correct), but it is a signal the prompt is confusing the classifier.

### AUD-C-03 — The caller's precise coordinates are stored indefinitely in `checkpoint_writes`, contradicting the consent notice shown to them (P1)

- **Severity:** P1 — minors' precise location, against an explicit promise. Same shape as AUD-L-04:
  an accepted residual risk whose mitigating assumption stopped holding.
- **What the product promises**, verbatim in `LOCATION_CONSENT_NOTICE` (SPEC §5.1.3):
  *"IntelliChoice will not permanently store your precise location."*
- **What is stored.** After one locator turn with `latitude=32.9876543, longitude=-96.7654321`,
  decoding the checkpoint tables with LangGraph's own serializer finds the coordinates in
  **`checkpoint_writes`, channel `__resume__`**, twice:
  `{'approved': True, 'zip_code': None, 'city': None, 'address': None, 'latitude': 32.9876543,
  'longitude': -96.7654321}`. They are still present after **two further turns** on the thread, and
  no job deletes them — `chat-purge`'s 90-day retention covers `tutor_chat_messages`, not the
  checkpoint tables, and PROGRESS.md already tracks ~268k checkpoint rows accumulating unswept.
- **D-045 anticipated the mechanism and understated the duration.** It records that the saver
  "persists the raw `Command(resume=…)` value … so the location transits Postgres **briefly** at the
  framework level". Measured, "briefly" is "for the lifetime of the thread, which nothing bounds".
- **D-045 also overstates the difficulty.** It concludes removal "would mean disabling checkpointing
  for one specific node". It would not: `DELETE FROM checkpoint_writes WHERE thread_id = :t AND
  channel = '__resume__'` immediately after the locator node completes removes the value while
  keeping crash-safety for the window it exists to cover. A retention job over the checkpoint tables
  (already on the Phase 0B list for volume reasons) would bound it as a backstop.
- **Method note:** the first version of this check used `CAST(blob AS text) LIKE '%32.98%'` and
  reported zero hits. Checkpoint blobs are msgpack, so a float is eight binary bytes and a bytea
  cast renders as hex — that check would have certified a database full of coordinates as clean. It
  is recorded because it is the kind of PII probe that silently passes.

### AUD-C-04 — A turn that pauses on `interrupt()` returns the *previous* turn's answer, citations and access hint; `ics_content` never clears at all (P2)

- **Reproduction (local, real graph):** ask a document question (grounded answer + citation
  `public-organization-overview`), then on the same thread ask to contact an administrator. The
  second turn's response repeats the first turn's answer *and* its citation, with
  `pending_interrupt: email_approval` beside them. In chat-web that renders the previous answer, its
  citation chip, and any escalation/access-hint banner as if they answered the new question, while
  the approval modal sits on top.
- **Root cause.** Every terminal node explicitly resets the presentation fields (`answer`,
  `citations`, `confidence`, `missing_information`, `escalation_recommended`, `access_hint`). A node
  that pauses via `interrupt()` **never returns**, so nothing is reset and `ainvoke` hands back the
  channels as the previous turn left them. All three interrupt paths are affected
  (`admin_escalation`, `calendar_action`, `branch_locator_consent`). On a session's *first* turn the
  same code path returns `answer: null` — harmless only because a modal happens to cover it.
- **`ics_content` is worse: it is never reset by anything.** Measured across a real sequence —
  calendar turn → `.ics` choice → two unrelated document questions — `ics_content` was still
  populated on every later turn. chat-web renders a "Download .ics" button on each of those answers,
  all serving the original event.
- **Fix shape:** clear the presentation fields in `resolve_role`, which already runs first on every
  turn and already sets `query`/`standalone_query`.

### AUD-C-05 — The golden Q&A eval measures `MockBedrockProvider`, not retrieval; a real model rejects 10 of its 14 gating cases before retrieval runs (P2)

- **What the suite reported before this session:** refusal correctness 100%, no-hallucination 100%,
  citation grounding 100% (9/9) — all gated in CI.
- **The same fixture against real Bedrock:**

  | category | mock | real Bedrock |
  |---|---|---|
  | `grounded` | 100% (9/9) | **11.1% (1/9)** |
  | `role_gated` (marker-based) | 100% (5/5) | **0% (0/5)** |
  | `out_of_scope` | 100% | 100% |
  | `no_source` | 100% | 100% |
  | `adversarial` (added S37) | 100% | 83.3% |
  | `paraphrase` (added S37) | 28.6% | 42.9% |
  | `no_answer` (added S37) | **0% (0/8)** | **100% (8/8)** |
  | **grounded_citation_rate** | 68.8% | 25.0% |
  | **correct_refusal_rate** | 79.5% | 87.2% |

- **The collapse is not retrieval quality — it is the fixture.** Per-case diagnosis shows 7 of 9
  `grounded` cases and all 5 `role_gated` cases never reached retrieval: the real classifier returned
  `clarification` or `out_of_scope` and the graph refused first. That is *correct behavior* on those
  inputs. `"Baton Rouge Carver Public Library Terrace Street Saturday hours"` is a keyword list, not
  a question; `"zqxveval1 handbook"` is gibberish. Both were written that way deliberately — the
  fixture's own docstring explains that literal words from the target chunk were required to survive
  the mock's word-overlap reranker, and that nonsense markers were required to avoid coincidental
  matches. The suite was reverse-engineered into the mock's shape until a real model rejects it.
- **The two suites are close to inverted.** `no_answer` — plausible in-scope questions the corpus
  cannot answer — scores 0/8 under the mock and 8/8 under the real model. The mock cannot ever pass
  it: `_rag_answer_json` always answers from the first context chunk with a fixed confidence of 0.8,
  so every unanswerable question is answered from an unrelated document with a *verified* citation
  ("Does IntelliChoice provide transportation?" → a branch manager's biography, cited).
- **What this means for the §2.6 gate.** The 100% figures certify the mock, not the product. This
  session left the mock run in place as a deterministic CI gate for the categories it can genuinely
  decide (routing, filtering, deterministic citation verification, adversarial containment) and moved
  the retrieval-quality categories to measured-not-gated, with the real-Bedrock run as the instrument
  — see `apps/chat-api/tests/test_qa_coverage_eval_real_bedrock.py` (opt-in, three spend ceilings).
- **One genuine pipeline result inside the noise:** `grounded-overview-2` did run end to end under
  the real model — 8 chunks retrieved including the correct document — and still produced no citation
  and confidence 0.0. n=1, but it is the only case where the real pipeline was actually exercised and
  it declined to cite a document it had in hand.

### AUD-C-06 — SPEC §18-C3's access-aware refusal never fires under a real model (P2)

- **Status: ✅ fixed across D-164 (routing) + D-165 (matching). 2 of 3 live; the third is answered by a public document, so it never reaches the probe.**

**What was fixed.** The precondition is no longer `retrieved_chunk_ids == []` but the
*outcome*: a synthesis that ended in the no-source refusal now also routes to
`explain_access` (`QAState.no_source_refusal`, set by `synthesize_answer`). This finding's
own "fix shape" line called for exactly that, and it works — verified deterministically
(tests watched failing pre-fix) and observed live: a turn retrieved **3** chunks, refused,
and reached the probe, which pre-fix it could not do.

**Why the score is still 0/3.** A *third* cause, filed as **AUD-C-20**: the probe matches
with `websearch_to_tsquery`, which ANDs every content word of the question. Both entry paths
reach a probe that then finds nothing. Re-measured against the real deployed model with
`CHAT_EVAL_CATEGORIES=role_gated_question`, the three realistic cases score 0/3 unchanged —
so the user-visible symptom in this entry is **not yet gone**, and this stays open until
AUD-C-20 lands.

**Original finding below.**

- **Measured 0 for 8.** Five marker-based `role_gated` cases and three newly written as real
  questions against seeded gated content ("How many sessions can my child miss before losing their
  place?", with a parent-audience chunk that answers exactly that). Under real Bedrock **not one**
  produced an `access_hint`.
- **Two distinct causes, both structural.** The marker cases are refused as out of scope before
  retrieval. The realistic ones reach `document_qa` and retrieve **8 chunks** — all public, because
  the pre-retrieval filter correctly withheld the gated ones — so retrieval is *non-empty* and
  `_route_after_answer_document_qa` sends them to `synthesize_answer`, never to `explain_access`.
  The feature's entire precondition is `retrieved_chunk_ids == []`, a lexical-emptiness condition
  that real hybrid search over a non-trivial corpus essentially never produces.
- **User-visible effect:** a parent asking a question the parent handbook answers is told *"I don't
  have an approved source for that yet"* rather than *"that's in the parent handbook — log in"*, even
  though `count_matching_by_audience` would have found it. The refusal is safe but unhelpful, which
  is precisely the outcome S19 built the feature to avoid.
- **Safety half held:** no gated content leaked in any of the 8 (consistent with the phase-B result
  below).
- **Fix shape:** run the access probe whenever the answer is a no-source refusal, not only when
  retrieval returned zero rows.

### AUD-C-07 — An embedding failure or an exhausted budget on the retrieval path is an unhandled 500 (P2)

- **Reproduction:** with the generation provider healthy and the embedding provider raising,
  `POST /messages` returns **HTTP 500** for both a `document_qa` query and a `calendar` query.
- **Cause.** `scope_guard` catches `BedrockGatewayError` and `retrieve`'s *rerank* call catches it,
  but `retrieve`'s `create_embedding` call is unguarded, and no exception handler exists in
  `chat_api.main`. `CostBudgetExceededError` and `CircuitOpenError` are the same exception family, so
  a budget exhausted at exactly that point produces a 500 too.
- **Reachability is not exotic:** generation and embeddings are different models from different
  families (`AnthropicBedrockProvider` vs `TitanEmbeddingProvider`) with separate quotas and separate
  model-access enablement. Titan throttling, or Titan access lapsing in the region, takes out every
  document question while classification keeps working. The shared circuit breaker also allows a
  half-open window where generation succeeds and the embedding call re-fails.
- **§5.29 requires "bounded retry and smaller-model fallback" for a Bedrock timeout.** A 500 is
  neither. Same class as AUD-L-11, and it is the most likely real-world trigger of AUD-C-10.

### AUD-C-08 — A total Bedrock outage answers every in-scope question with the out-of-scope refusal (P2)

- **Reproduction:** with every provider call failing, `POST /messages` returns 200 and SPEC §5.19.4's
  *"I cannot answer unrelated general-purpose questions."* Same for an exhausted session budget,
  which trips on the first `scope_guard` call.
- This is `scope_guard`'s deliberate fail-closed branch, and failing closed is right. The problem is
  the *message*: during an outage the product tells a user their in-scope question was off-topic, and
  a user who has exhausted the cost ceiling is told the same thing. §5.29's common mechanisms list
  "user-safe error message"; this is a user-*misleading* one. There is no operator-visible difference
  either — the response is identical to a genuine refusal.

### AUD-C-09 — §5.21.3's `academic_year` predicate is not implemented (P2)

- **Status: dispositioned — not applicable, 2026-08-03 (D-170).**

**The user's call: the predicate does not apply to this corpus.** The handbook set is unified
rather than partitioned by academic year, so retrieval scopes on approved/effective document
state plus role-based access, and an `academic_year` equality filter is the wrong instrument for
it. Nothing was implemented.

**What was done instead, so the finding cannot be re-filed as an oversight.** The absence is now
recorded at both layers it would be read from: `role_access_filter`'s docstring states that it
implements five of §5.21.3's six predicates by decision and names where each comes from, and
`ChunkFilters.academic_year` states that the access path leaves it `None` on purpose.

**`ChunkFilters.academic_year` is kept rather than deleted**, which is the opposite of D-159's
call on `flow.select_topic`, and the difference matters: `select_topic` was a *second definition of
live behaviour* that could drift from the real one, while this is an unused query option on a
filter object, exercised by `packages/db/tests/test_rag_search.py` and useful for ingestion-time
and verification queries. Deleting it would remove a working, tested capability to make a point
that a docstring makes better.

**The original evidence stands as a fact about the code, and is no longer read as a defect:** a
2019-2020 chunk is retrievable by every audience, because year is not an access dimension here.

**Original finding below.**

- SPEC §5.21.3 lists six pre-retrieval predicates. Five are enforced. `academic_year = requested_year`
  is not: `ChunkFilters.academic_year` exists and `_apply_filters` honours it, but
  `role_access.role_access_filter` never sets it and no caller does.
- **Measured:** a chunk seeded with `academic_year = "2019-2020"` was retrieved by every audience
  including anonymous, in the same run where draft, future-dated, expired and other-branch chunks
  were all correctly excluded.
- **Entirely masked today** — all 23 documents and 159 chunks are `2026-2027` — and unmasks the first
  time a second year is ingested, which is inherent to a yearly-refreshed handbook corpus. Same shape
  as AUD-L-12: correct code, never wired, hidden by uniform data.

### AUD-C-10 — chat-web leaves a permanent "Thinking…" bubble on any API error (P2)

- `sendMessage` appends `{query, response: null}`, then awaits `postMessage`. On any throw, `run`'s
  catch sets the error banner and **the transcript entry keeps `response: null` forever**;
  `ChatScreen` renders `!turn.response` as a `Thinking…` bubble with no timeout and no retry. A 500
  (AUD-C-07), a 409, a 401 or a dropped connection all land here.
- §2.6 criterion 3 requires "zero blank/stuck states" on every launch journey. This is one, and it is
  reachable from the most ordinary failure there is.
- **Same class as the S22.5 blank-turn bug**, which is the seeded Phase 0B exemplar: a render gated
  on a field that is legitimately absent. The full response-shape × render enumeration this session
  ran is below; this and AUD-C-04 are the two shapes that render wrongly.

### AUD-C-11 — The no-source refusal is returned *with* citations attached (P2)

- **Status: ✅ fixed in D-164 (2026-08-03).**

**Fix.** `qa.answer_question`'s low-confidence branch passes `[]` to `_no_answer` instead of
`verified`. The **conflict** branch still passes `verified`, and `_no_answer`'s docstring now
records that asymmetry as deliberate with the reason for each side, because the obvious
future "cleanup" is to make them the same: "the documents I found disagree with each other"
is a claim about specific documents and naming them is the point, while "no approved source
exists" is contradicted by attaching one. Both arms are asserted, the conflict one as the
negative control, and the low-confidence test was watched failing pre-fix.

**It also had a second, load-bearing effect.** Passing `[]` is what makes the refusal
*detectable* one layer up, which is the precondition AUD-C-06's routing fix needed — the two
findings were fixed as one cluster for that reason.

**⚠️ The e2e test named for this finding could not verify the fix and never will:**
`response-shapes.spec.ts` renders a hardcoded stub shape, so it passes whether the bug exists
or not. It did not flip from documented-defect to regression the way AUD-C-04 and AUD-C-10
did. Both the test and the fixture now say so and point at
`test_qa_service.py::test_the_no_source_refusal_carries_no_citations`, which is the real
guard. Same class of trap as D-163's `MockBedrockProvider`.

**Original finding below.**

- **Observed live:** turn 1 of the staging session returned
  `answer: "I don't have an approved source for that yet…"` together with
  `citations: ["public-organization-overview"]` and `confidence: 0.4`.
- **Cause:** `qa.answer_question`'s low-confidence branch is `_no_answer(NO_SOURCE_MESSAGE, verified)`
  — it passes the verified citations *into* the no-answer result. chat-web then renders the refusal
  text with a citation chip under it. A reader is being shown a source next to a sentence saying no
  source exists. (The conflict branch does this deliberately and correctly; the low-confidence branch
  appears to have inherited it.)

### AUD-C-20 — The access probe ANDs every content word, so it never matches a real question (P2)

- **Severity:** P2 · **Area:** SPEC conformance (§18-C3) · **Status:** ✅ **fixed in D-165 (2026-08-03)**

**Fix: a semantic arm, unioned with the keyword arm, at a measured cosine ceiling of 0.40.**
`count_matching_by_audience` takes an optional `query_embedding`; `explain_access` embeds the
question and degrades to keyword-only if that call fails (it runs *because* the turn already
failed, so it must never raise). The keyword arm is **kept, not replaced** — an exact-wording
match is free, and `MockBedrockProvider`'s hash-seeded vectors carry no semantic content, so a
semantic-only probe would be structurally unobservable in the whole mock-backed suite (D-163's
trap in new clothes). Re-measured against the real deployed model: **`role_gated_question`
0/3 → 2/3.** The third case never reaches the probe at all — the model answers it from
`public-contact-guide` at confidence 0.85, which is a public document genuinely answering it,
not a probe failure.

**⚠️ The recommendation in the table below is the one that lost, and the reason it lost is the
most useful thing in this entry.** Keyword coverage ≥2/3 measured 8/8 against the *hand-written*
cases and **10 of 43** against a corpus-derived fixture, because the three hand-written
questions were written beside the chunk they target and shared 5/6, 5/7 and 4/6 content words
with it. A question written by whoever wrote the answer flatters any keyword rule. The
corpus-derived fixture (mean lexical overlap **0.486**) put semantic ≤0.40 at **25 of 43 with
zero false hints on either negative class**, against keyword ≥2/3's 10. **The fixture was the
fix; the rule followed from it.**

- **Found while fixing AUD-C-06 (D-164, 2026-08-03).** It is the reason that fix did not move
  the score, and the two together are why §18-C3 has **never** fired for a realistically
  worded question on either entry path.

**What.** `RagRepository.count_matching_by_audience` matches with
`websearch_to_tsquery('english', query)`, which **ANDs** the query's lexemes. A
natural-language question carries 6–7 content words, and the chunk that answers it almost
never contains all of them, so the probe returns `{}` and `build_access_hint` has nothing to
work with. Retrieval's keyword arm has the same semantics, but there it is harmless: hybrid
search compensates with the semantic channel, and the probe has no semantic channel by design
(text-only, no embedding call on a refusal path).

**Evidence — the tsquery, and the one word that voids each (free, pure Postgres):**

| case | `websearch_to_tsquery` output | absent from the chunk that answers it |
|---|---|---|
| parent | `mani & session & child & miss & lose & place & program` | `child` (the chunk says "student"), `mani` |
| branch_manager | `escal & path & session & cancel & short & notic` | `escal`, `path` |
| tutor | `procedur & tutor & report & safeguard & concern & student` | `procedur` only — 5 of 6 matched |

**Measured candidate fixes**, scoring the 8 gated cases on the *role* `build_access_hint`
names (not merely "some gated audience matched") and splitting negatives, because 18 of them
are nonsense markers (`"zqxveval6 handbook"`) that collide with seeded marker chunks at cosine
0.14 and would measure the fixture rather than the rule:

| rule | right role | wrong role | FP on 42 real-prose | FP on 18 marker |
|---|---|---|---|---|
| AND (today) | 5 | 0 | 0 | 0 |
| keyword coverage ≥ 3/4 | 6 | 0 | 0 | 0 |
| **keyword coverage ≥ 2/3** | **8** | **0** | **1** | **0** |
| keyword coverage ≥ 1/2 | 5 | 3 | 8 | 16 |
| semantic ≤ 0.40 | 5 | 3 | 1 | 16 |
| semantic ≤ 0.65 | 5 | 3 | 13 | 18 |

**Recommendation: keyword coverage ≥ 2/3, as an exact rational ratio.** `ceil(0.67·n)` rejects
4-of-6, which *is* two thirds, and that arithmetic alone is the difference between 7/8 and 8/8.
`≥3/5` gives identical numbers, so 2/3 is not on a knife edge; the cliff is at 1/2. Its single
false hint is real and should be stated rather than tuned away: *"Are tutoring sessions
available in Spanish for parents who prefer it?"* matches 4/6 lexemes of a student Code of
Conduct chunk about reporting concerns → "log in as a student".

**Why not the semantic probe**, which is the more elegant design and was the first choice: it
needs an embedding call on the refusal path (a new failure mode on a path that runs *because*
something already failed), it cannot be tested with `MockBedrockProvider` at all (hash-seeded
random vectors carry no semantic content, so no mock test could ever observe a positive —
D-163's trap in reverse), and on this corpus it names the wrong tier 3 times in 8. Worth
recording that it is **not** hopeless on prose: it found the three seeded chunks at 0.101 /
0.293 / 0.344 and named the right role each time. Its failures are nonsense tokens.

**A better instrument is the real next step (user's point, this session).** The negative set
conflates "a public doc answers it" with "nothing answers it", and the one false hint above
comes from the second class — a question no document addresses, where the probe is being
scored on a question that was never well-posed. A fixture derived *from* the corpus (for each
gated chunk, a question it genuinely answers → expect a hint naming that audience; for public
chunks → expect a grounded answer and no hint) makes the measurement well-posed and much
larger than 8 cases. **The discipline it needs:** questions must be answerable from the chunk
while lexically *diverging* from it, or keyword coverage is trivially high and the fixture is
measuring its own paraphrase — ROADMAP.md's S30 correction, again. Keep a small
honestly-unanswerable set, because real users ask things the corpus does not cover.

**Method corrections that nearly produced a wrong decision here**, both worth remembering:
Postgres `now()` is *transaction*-scoped while production filters on a per-request Python
`ChunkFilters.as_of`, so sweep SQL using `now()` silently excluded every fixture chunk seeded
after the transaction began — two of three gated chunks were invisible, which is what made the
semantic probe first appear unusable. And scoring "some gated audience matched" as a hit
flatters every rule, since `build_access_hint` picks by priority and naming the wrong tier is a
failure.

### AUD-C-23 — The paid coverage eval has been red since D-168, on D-168's own accepted residual (P2; ✅ fixed 2026-08-04, D-177)

- **Severity:** P2 — a user is directed to log in for an answer that does not exist, which is the
  damage D-166 and D-168 both name explicitly ("a wrong tier is worse than silence"); bounded to 1
  of 8 unanswerable fixture cases · **Area:** access probe + eval instrument · **Status:** open,
  Phase 0B, filed 2026-08-04 by D-172's verification run

**What.** `apps/chat-api/tests/test_qa_coverage_eval_real_bedrock.py` fails its
`wrong_role_hints(outcomes) == []` assertion on `no-answer-missed-1` — *"What happens to a student
who misses three sessions in a row?"*, an ordinary question in a supported topic that the corpus
does not answer. The access probe names a role for it, so the anonymous caller is told to go log in.

**Two findings in one, and the second is the more useful.**

1. **The behaviour is already recorded and was already accepted.**
   `intellichoice_shared.access_probe_policy`'s measurement table gives the shipped D-168 rule **1
   false hint on the unanswerable class** in the corpus-phrasing arm and 0 in the human-phrasing arm.
   This live observation is that 1. So this is not new behaviour and not a regression — it is a
   documented residual meeting an assertion written to a stricter standard (`== []`, every category).
   **One of the two has to move**, and that is a decision, not a bug fix: either the residual gets
   closed (the margin rule tightened, re-measured with `measure_access_probe_rules.py`), or the
   assertion is relaxed to the standard D-168 actually accepted — in which case it must name the case
   it tolerates, or it stops being able to detect a new one.
2. **The eval was red for a whole day of sessions and nothing said so.** D-168 landed 2026-08-03 and
   was verified with live staging probes, not with this eval; S56 and S57 both ran and neither
   touched it. Same shape as AUD-F-15 (`chat-purge` had never once run against the deployed
   database): an opt-in instrument that costs money is an instrument that silently stops being
   evidence. Worth deciding whether this run belongs in a per-deploy checklist at a bounded
   `CHAT_EVAL_CATEGORIES=no_answer` subset — **that subset is 10 cents and 72 seconds**, and it is
   the arm that carries this risk.

**Reproduction (2026-08-04, real Bedrock, anonymous caller).** `CHAT_EVAL_CATEGORIES=no_answer`:
`no_answer` 8/8 and `correct_refusal_rate` 8/8 — the refusals themselves are correct — with
`wrong_role_hints == ['no-answer-missed-1']` at **both** `CHAT_RETRIEVAL_MIN_RELEVANCE_SCORE=0.35`
(10.0c) and `=0.0` (11.6c). **The floor-0.0 arm is what rules out D-172 as the cause**, and it was
run for exactly that reason.

**~~Not yet known:~~ which role is named — and the live answer is "none" (measured 2026-08-04, D-173).**
Probed anonymously against the **deployed** chat edge, twice pre-deploy and once post-deploy:
`no-answer-missed-1` returns **`access_hint: null`**, refuses correctly with
*"No verifiable, non-conflicting source supports an answer"*, and sets
`escalation_recommended: true`. **So the deployed system does not exhibit this finding.** Identical
at both retrieval floors, which also re-confirms D-172 is not involved.

**The control can fail, which is the only reason that null is worth anything (D-171 §2).** A null
hint is also what an *empty restricted corpus* would produce, so the hint machinery was checked
against a question known to trigger it: `"What happens if my child's attendance hasn't been
recorded yet?"` returns `required_role: "parent"` on the same deployed edge. The path is live.

**Two consequences, and the second reshapes the fork.**

1. **That control probe incidentally verifies AUD-C-22's fix live, against a recorded prior
   value** — D-166 measured this exact question returning `"branch_manager"` (the wrong tier, which
   is what AUD-C-22 was filed about) and it now returns `"parent"`, the tier D-165 measured as
   correct at 0.499. That is a genuine before/after pair from the record rather than from a test.
2. **The finding is now scoped to the *local eval fixture corpus*, not to the product.** The eval
   runs against the dev corpus; staging's is loaded separately, and they disagree on this question.
   So the fork is no longer "close the residual or relax the assertion" — it is first **"why do the
   two corpora disagree?"**, because until that is known, the eval is asserting a property of a
   corpus no user meets. Deciding between the original two forks on the eval's evidence alone would
   be tuning a rule against the wrong corpus.

Both halves of the original finding survive unchanged: the eval was red for a day of sessions with
nothing saying so (AUD-F-15's shape), and the bounded `CHAT_EVAL_CATEGORIES=no_answer` arm is
10 cents and 72 seconds.

#### ⚠️ The corpora do **not** disagree — the fork above rests on a premise that measurement refuted (2026-08-04, D-174)

**"Why do the two corpora disagree?" was the right question to ask first and it has no answer,
because they are the same corpus.** Read directly from staging's RDS via the `ops-task` `run-task`
override (read-only, a few Fargate seconds, no model calls — the whole check was free) and compared
against the dev Postgres:

| Compared | Result |
|---|---|
| Documents by audience × status × effective-now | **identical** (23 docs; 9 public / 3 bm / 2 parent / 3 student / 3 tutor approved, 3 drafts) |
| Document ids present | **identical**, all 23, including both attendance documents |
| Chunks by audience, approved + effective | **identical** — 89 public / 15 bm / 10 parent / 15 student / 15 tutor = **144** |
| Chunks by their **own** `status`/`audience`/`access_level`/`academic_year` | **identical** (159 total incl. drafts; every chunk `2026-2027`) |
| Chunk rows disagreeing with their document's gating | **0 on both** |
| `branch_external_id` spread | **identical** (`branch-ext-1` 5, null 154) |
| `md5(chunk_text)` for sampled chunks | **identical**, same order |
| Chunks with a NULL embedding | **0 on both** |

**The chunk-level rows are the ones that matter, and the first pass got this wrong.** `rag_chunks`
carries its *own* `status`, `audience`, `access_level`, `academic_year` and `effective_*` columns and
`ChunkFilters` applies them at **chunk** level — so a document-level comparison can agree while the
retrievable set differs. It was re-run at chunk level for that reason, and agrees there too.

**Both of the pointer's named candidates are therefore dead**: it is not which chunks are
approved/effective, and not the audience mix.

**And the eval is aligned with production on every axis checked, more tightly than assumed:**

- **Same models.** `test_qa_coverage_eval_real_bedrock._gateway` defaults to
  `us.anthropic.claude-haiku-4-5-20251001-v1:0` for `RERANK`/`SCOPE_AND_INTENT`/`RAG_ANSWER` and
  `amazon.titan-embed-text-v2:0` for `EMBEDDING` — the **same ids the deployed chat-api runs**.
  (A promising false lead, recorded because the next reader will have it too: `chat_api.config`'s
  `bedrock_rerank_model_id` default *is* `anthropic.claude-sonnet-5`, which differs from the deployed
  Haiku 4.5 — but the eval never reads it, and `measure_access_probe_rules.py` also defaults to
  Haiku 4.5, so **no access-probe rule was measured through the wrong reranker**. D-165/D-166/D-168
  are unaffected. Checked before being believed: `anthropic.claude-sonnet-5` is also a *valid*
  Bedrock id here, so "the default silently fails and degrades" is not what happens either.)
- **Same thresholds.** The deployed chat-api task definition sets **no** retrieval, access-probe,
  rerank or citation threshold env var at all (20 env vars, none matching), so staging runs the code
  defaults the eval also runs.
- **Same vectors, effectively.** The dev corpus is mock-embedded (AUD-C-16 above), but the eval
  `reembed_corpus`es all 144 approved chunks with the real embedding model inside its rolled-back
  transaction, so the provenance difference is neutralised before a single case runs.

**What the fork actually is now.** Corpus, config, thresholds and models are all eliminated, so only
two candidates remain, and they need different instruments:

1. **The harness is not the route.** The eval invokes the graph in-process (`build_graph`,
   `InMemorySaver`, `FakeProfileAdapter`) while staging serves the HTTP route. If the two apply the
   access probe differently, the eval's 1 false hint measures the harness — AUD-F-16's family, and
   the reason this is worth ruling out before touching the rule.
2. **Nondeterminism, and the live evidence is thinner than it reads.** "Does not reproduce on the
   deployed corpus" rests on **three** anonymous probes. D-172 recorded this same model moving
   6 → 5 → 4 citations across runs on an unchanged corpus, which is exactly the regime where three
   samples cannot establish "never". The honest statement is *"not observed in 3 probes"*, not
   *"the deployed system does not exhibit it"* — and the sentence above that says the latter is
   overstated by its own evidence.

**Recommendation, unchanged in direction but now on evidence:** do not tighten the margin and do not
relax the assertion yet. Discriminate (1) from (2) first. Neither instrument is free — a staging
probe is a real-Bedrock chat turn billed to the staging account, and the
`CHAT_EVAL_CATEGORIES=no_answer` arm is 10 cents / 72 s — but both are cheap, and *this* comparison
was the free one, which is why it was done first. Tuning a rule to reconcile a harness artefact, or
to chase a sampling artefact, would both be worse than leaving it red and named.

**A note for whoever runs the staging probes:** they trip `chat-api-p95-latency-scale-out`, which is
what AUD-F-38 was about. That gate is fixed (D-173 §6), so probing before a deploy is now safe — but
expect the desired count to move, and do not read it as a deploy signal.

#### ⚠️⚠️ The probes were run, and the finding reproduces on the deployed edge 6 times in 10 (2026-08-04, D-175)

**Every "it does not reproduce live" sentence above is a sampling artefact, and the fork has
resolved.** 10 anonymous probes of `no-answer-missed-1` against the deployed chat edge
(`/chat/sessions` → `/chat/sessions/{id}/messages`, no credential, ~14c of real Bedrock turns):

| Probes | `access_hint` | `escalation_recommended` | What the user gets |
|---|---|---|---|
| **6 / 10** | `{"required_role": "branch_manager", …}` | `false` | *"That's part of branch management materials — available to branch managers. Log in with a branch manager account to see it."* |
| 4 / 10 | `null` | `true` | the correct refusal, plus the offer to escalate |
| control (1) | `{"required_role": "parent", …}` | `false` | the hint machinery is live and can fail — D-171 §2 |

**What this settles.**

1. **Hypothesis (2), nondeterminism, is confirmed. Hypothesis (1), harness-vs-route, is dead as an
   explanation** — the route exhibits the same defect the eval measured, more often. The eval was
   never measuring a harness artefact or a corpus no user meets; it was measuring this.
2. **The three-probe claim was wrong, and D-174 had already said why it could not be trusted.** It
   corrected the wording to *"not observed in 3 probes"* and named the remaining risk exactly right.
   Taking the sample was the cheap step that resolved a fork two sessions had reasoned about — and at
   60% reproduction, three probes returning null has a ~6% chance, so this was not bad luck so much
   as an under-powered instrument being read as an answer.
3. **The severity is worse than the eval showed.** The eval's residual was 1 of 8 unanswerable cases
   in the corpus-phrasing arm. Live, for this question, it is 6 of 10 — and the damage is the one
   D-166 and D-168 both named in as many words: *a wrong tier is worse than silence*. A parent or
   student asking an ordinary question about missed sessions is told to go get a branch-manager
   account for an answer that **does not exist at any tier**.

**Mechanism, inferred and not yet verified.** AUD-C-22/D-165 made the access probe run *the reranked
pipeline* rather than a paraphrase of it, so an LLM rerank now sits inside the probe — and an LLM
score is not reproducible. Near the margin, two runs land on opposite sides. That is consistent with
D-172 watching this same model return 6 → 5 → 4 citations on an unchanged corpus, and it predicts the
flip rate should depend on how close this question sits to the threshold. **Not measured here**: no
per-probe rerank scores were captured, so this remains a hypothesis with a mechanism rather than a
demonstrated cause.

**Still open, and deliberately not fixed in D-175.** The fork is now the original one — tighten the
margin, or accept and *name* the tolerated case — and both arms are rule changes to a component whose
current rules were each chosen from a measured table (D-165/D-166/D-168). Tuning it from this session's
10 samples, without re-running `measure_access_probe_rules.py`, would repeat in miniature the mistake
this finding has already made twice: acting on the evidence that happened to be cheap. It also carries
a product judgment that is the user's — whether a hint that is sometimes wrong beats silence — so it is
recorded with numbers and left for a decision.

### AUD-C-24 — The chat app sends the user's typed question to Bedrock unredacted (P2, filed 2026-08-04, D-175; ✅ fixed 2026-08-04, D-177)

- **Severity:** P2 — a real gap in a stated rule, bounded by the fact that nothing persists the text
- **Area:** minors / PII floor (SPEC §5.30.1, CLAUDE.md rule 1), chat-api
- **Found by:** extending the PII-floor allowlist to the chat payloads for AUD-L-05, then asking what
  the allowlisted `query` field actually *contains* — the allowlist pins field names, not text
- **Status:** open, needs a decision

**What.** `intellichoice_shared.pii_redaction.redact_free_text` has **exactly one call site in the
repository**: `apps/learning-api/src/learning_api/routers/sessions.py:1188`, at the request boundary,
where D-072 put it. **chat-api never calls it.** So a question typed into `chat.intellichoice.org`
crosses the Bedrock wire verbatim in four payloads:

| Payload | Field | Task |
|---|---|---|
| `ScopeAndIntentPayload` | `standalone_query` | `SCOPE_AND_INTENT` |
| `RerankPayload` | `query` | `RERANK` |
| `RagAnswerPayload` | `query` | `RAG_ANSWER` |
| `CalendarExtractionPayload` | `query` | `CALENDAR_EXTRACTION` |

D-072's "How to apply" clause is explicit that this is required of *"any future free-text-accepting
Bedrock task"* — the same clause whose allowlist half was AUD-L-05.

**Why it is P2 and not higher — the bound, checked rather than assumed.** The text is **not stored**.
There is no chat-message table: `packages/db/.../models/chat.py` holds only `chat_suggestions`, whose
`prompt_text` is hand-authored seed content (`suggestions_seed`), and `tutor_chat_messages` belongs to
the *learning* app and stores `redacted_student_message` — already redacted, and the only table with a
retention job. So this is the Bedrock wire and whatever traces carry it, not Postgres, not backups.
Contrast AUD-L-04, which is P1 precisely because the derived text landed in a table with no purge.

**Why it is nevertheless worth a decision.** The users are minors. The realistic input is not exotic —
*"my mum's email is … , when is the next parent meeting?"* is an ordinary thing for a 12-year-old to
type into a chat box, and the learning app already treats that exact shape as requiring a pass.

**It is an unexamined gap, not an accepted risk, and that distinction is the finding.** Two decisions
look like they cover it and neither does:

- **D-072** judged "free text reaching an LLM, mandatory PII redaction before it does" for the
  *learning* tutor/hint surface, and installed the pass there.
- **D-018**'s prompt-injection scope call is *deliberately* scoped to chat-api's Q&A/RAG/tool-call
  surface and explicitly defers the PII question with *"S24/D-072 already judged that surface's
  specific risk … and made its own scope call at the time"* — but the surface D-072 judged was
  learning-api's. Each decision points at the other, and chat-api's own free-text input falls between
  them.

**Recommended disposition, for the user's call.** Apply `redact_free_text` at chat-api's request
boundary the way learning-api does — one call in the message route, before the query reaches
`TurnContext` — since redaction removes emails/URLs/phones and not question words, so an answer is
still answerable (learning-api is the existence proof). The alternative is to accept it and write the
acceptance down with its reasoning, which is the outcome D-072 would have produced if this surface had
been considered. **Not fixed in D-175**: it is outside the confirmed cluster, it changes what crosses
the wire on a live user path, and "which pass, at which boundary" is a decision rather than a patch.

**Not investigated here:** whether traces carry the query. `LANGSMITH_HIDE_INPUTS/HIDE_OUTPUTS=true`
is recorded as the mitigation for a related concern (D-093-era), and AUD-F-13 established that a PII
floor has to be re-established per store rather than inherited — so "the trace is clean" needs its own
check and does not follow from this entry.

### AUD-C-26 — A public-corpus question is told to log in as a parent, on the probe branch no rule table modelled (P2, filed 2026-08-04, D-179)

- **Severity:** P2. A user-visible instruction that cannot help, on a negative class every
  recorded table showed as clean. Milder than AUD-C-22's wrong tier on gated material — the
  caller here probably *is* a parent — but the same defect class, and the corpus it gatekeeps is
  **public**, so the instruction is not merely unhelpful, it is backwards.
- **Area:** chat product correctness. `intellichoice_knowledge.retrieval.probe_access`'s
  `if not candidates` branch, `_lexical_only`, `role_access.build_access_hint`.
- **Found by:** AUD-C-25's fix, on its first run, at zero cost. Not by review — three sessions
  of careful reading of this rule missed it, because the instrument they were reading agreed
  with them.

**The path.** `probe_access` fetches candidates within `ACCESS_PROBE_CANDIDATE_MAX_DISTANCE`
(0.60). When that pool is **empty** it returns immediately — deliberately, to avoid paying for a
model call that has nothing to score — and `_lexical_only` answers alone. Nothing on that path
applies a relevance floor or a tier margin, so `build_access_hint` has no score to rank by and
falls back to its fixed tier **priority**: the precise rule AUD-C-22 was filed against. None of
the D-165/D-168/D-177 constants is implicated, because none of them executes here.

**It is neither rare nor marginal.** Measured over D-177's dumps with `--shipped`:

| arm | empty pool | public | unanswerable | gated | lexical arm fires |
|---|---|---|---|---|---|
| human phrasing | **18 of 58** | 11 | 4 | 3 | 1 |
| corpus phrasing | 17 of 58 | 11 | 4 | 2 | 0 |

"No candidate within 0.60" is the *ordinary* outcome for a question phrased unlike the corpus,
which is how real users phrase questions (D-166's own finding). The reassuring half is that the
keyword arm is quiet across almost all of it — 1 fire in 35 empty-pool cases across both arms,
because `websearch_to_tsquery` ANDs every content word. The unreassuring half is that the one
fire is wrong:

```
probe-public-025   category=public   expected_required_role=null
  query   : "How do I get or delete my kid's school records?"   (human phrasing)
  nearest non-public chunk : distance 0.7251   (ceiling 0.60 -> 0 candidates)
  lexical arm             : {parent: 1 chunk, student: 3 chunks}
  build_access_hint       : required_role = "parent"      <- FALSE HINT
  source of the answer    : Privacy Notice, audience=public
```

**Why this is a decision and not a patch.** The obvious fix — do not consult the keyword arm
when the candidate pool is empty — collides with the reason the arm exists. D-165 kept it
because `MockBedrockProvider`'s embeddings are hash-seeded vectors with no semantic content, so
the keyword arm is the **only** arm the entire mock-backed suite can exercise; delete it and the
probe becomes structurally unobservable in every offline test, which is D-163's trap wearing
different clothes. Four candidates, all measurable for free with `--shipped` over the existing
dumps:

- **(a) Require disagreement before priority decides.** Name a tier only when exactly one
  audience matches lexically; `probe-public-025` has two (`parent`, `student`), so priority is
  doing the deciding and that is the thing AUD-C-22 established it must not do.
- **(b) A minimum-match bar.** The false hint rests on a **single** chunk. `count >= 2` would
  drop it; needs checking against how many true positives the arm contributes at all (measured:
  1 and 3 across the two phrasings, so the margin here is thin).
- **(c) Keep the arm for retrieval, gate the hint on a scored signal.** Most faithful to
  AUD-C-22's principle — no score, no named tier — and it costs the arm's entire live
  contribution while keeping the mock suite observable.
- **(d) Accept and record it.** Defensible at 1 case in 58: the caller is over-directed toward
  authentication for public content, which is annoying rather than harmful.

Recommendation is **(a)**: it targets the actual mechanism (priority deciding an ambiguous
match) rather than the symptom, keeps the arm's single-audience true positives, and leaves the
mock suite exercising the same code path.

**A note on the instrument, since it is the second lesson here.** This finding was invisible for
as long as the rule table was a transcription, and it became visible on the first run after the
table started calling the code. The generalizable form: *a measurement that omits a branch will
report that branch as its most flattering outcome* — here, silence scored as a correct refusal.

### AUD-C-25 — `measure_access_probe_rules.py` does not measure the rule it is used to choose (P2, filed 2026-08-04, D-178; ✅ fixed 2026-08-04, D-179)

- **Severity:** P2. No user-facing damage exists today — D-178's live probes measured production's
  composed path at 0/10 hints with a 3/3 control — so this is not P1. It is held *at* P2 rather than
  P3 because every access-probe constant since D-165 was chosen from this script's tables, the next
  rule decision will be too, and this project has been burned twice by an instrument measuring
  something other than what it claimed (AUD-F-16's stale API servers; D-173's three-probe sample).
- **Area:** audit integrity / measurement harness. `scripts/measure_access_probe_rules.py`,
  `intellichoice_knowledge.retrieval.probe_access`.
- **Found by:** landing D-177 and reading the shipped `probe_access` against the harness function
  whose table justified it — not by a test, because no test compares them.

**The harness reimplements the rule instead of calling it.** `rerank_prefloor_margin_hint` is
referenced only inside the measurement script; `probe_access` appears nowhere in it. The
reimplementation differs from what ships in two ways:

1. **The branch order is reversed.** The harness checks the floor first (`if winner_score <= floor:
   return None`, line 558) and the margin second. `probe_access` checks the margin first
   (retrieval.py:187) and the floor second.
2. **The harness has no lexical arm.** Neither `_lexical_only` nor `count_matching_by_audience`
   appears in it. Where production falls through to an all-terms keyword match that *can* return a
   hint, the harness returns `None` and the case is scored as silence.

Writing both out, with `w` = winner's pre-floor score, `r` = runner-up, `F` = floor, `M` = margin:

| case | harness | production |
|---|---|---|
| `w > F` | hint(winner), or silence by margin | same |
| `w ≤ F` and `w − r < M` | silence | silence (margin path; lexical skipped) |
| `w ≤ F` and `w − r ≥ M` | **silence** | **`_lexical_only` → possibly a hint** |

**The third row is AUD-C-23's own failing case** — winner 0.75–0.90 against the 0.9 floor, runner-up
0.2–0.3, so it fails the floor and clears the margin easily. On the exact question the fix was chosen
for, production takes a path the harness never modelled. D-177's "0 wrong tiers, 0 false hints on both
negative classes, 0/40 stability fires" is therefore a true statement about the harness's rule that
does **not** cover production's composed behaviour on the decisive case.

**Why it did not bite, and why that is luck rather than design.** The lexical arm was measured
separately as clean on both negative classes ("1 and 3 correct audiences across the two phrasings,
zero wrong, zero false hits"), and D-178's 10 live probes exercised the composed path directly at
0/10. But those are two measurements never composed, and the live sample bounds the residual rate
only at <26% (one-sided 95%). Nothing structural prevents the next floor or margin change from being
chosen off a table whose sub-floor branch does something production does not.

**This is the same shape as D-175's config-parity gap, one level up.** That session built
`test_qa_coverage_runner_config_parity.py` to `ast`-parse both construction sites and fail when the
harness omits a `Settings` field the route passes — a guard on the *inputs*. Nothing guards the
*rule*. A harness that reads the same config and then applies a differently-shaped rule passes that
test and still measures the wrong thing.

**Two candidate fixes, neither needing a paid re-measurement** (the D-177 dumps carry per-case,
per-repeat rerank scores and re-score offline via `--load`):

- Have the harness call `probe_access` with an injected score map and a fake repo, so there is one
  implementation of the rule and the tables are of the shipped code by construction. Strongest, and
  the lexical arm needs a repo double to be modelled rather than skipped.
- Or add a parity test that replays the saved dumps through both the harness rule and `probe_access`
  and asserts identical hints per case. Cheaper, and it fails loudly on the next divergence.

**A second, smaller thing this exposed, unresolved and settleable from the same dumps.** Production's
pre-floor margin now *gates* the lexical fallback: with two audiences whose bests are within the
margin, the turn returns `matches={}` without consulting it. Verified against the shipped rule —
`bm=0.0/parent=0.0 → lexical_calls=0`, `0.25/0.20 → 0`, `0.30/0.10 → 1`, `0.90/0.30 → 1`. Two
audiences at `0.0` is the most likely shape on a question nothing answers, so the arm is bypassed in
its most common trigger case. Consequences: the "strictly additive, so it gets the last word here"
comment at retrieval.py:196 no longer describes the code; the silence-reason comment at
retrieval.py:188 ("two tiers the reranker cannot separate") does not describe two `0.0` scores; and
part of the 29→27 drop D-177 attributed to the floor raise is plausibly this bypass instead. The
direction is toward silence, which AUD-C-22 prices as the safe trade, so this is a recall and
record-accuracy issue rather than a wrong-tier one.

### AUD-C-22 — The access hint names the highest-*priority* tier, never the closest one (P2)

- **Severity:** P2 — a user-visible instruction that is wrong, replacing one that was merely
  unhelpful · **Area:** SPEC conformance (§18-C3) · **Status:** **New — Phase 0B (found in D-166's
  post-deploy verification, 2026-08-03)**

**Found by the deploy that was supposed to close AUD-C-21, on AUD-C-21's own motivating question.**
Against the deployed edge, anonymously, before and after:

| | `"What happens if my child's attendance hasn't been recorded yet?"` |
|---|---|
| at 0.40 (pre-deploy) | `access_hint: null` — *"I don't have an approved source for that yet. I can pass this on to a branch manager if you'd like."* |
| at 0.45 (post-deploy) | `access_hint.required_role: "branch_manager"` — *"That's part of branch management materials… Log in with a branch manager account to see it."* |

The probe now fires, which is what AUD-C-21 was about. **But the tier it names is wrong**, and for
this question the outcome is arguably worse than the silence it replaced: a parent asking about their
own child's attendance is told to log in as a *branch manager*. D-165 measured the chunk that
actually answers it as the **parent** "If Attendance Is Unknown" chunk, at 0.499.

**What.** `build_access_hint` iterates `_ACCESS_HINT_PRIORITY = ("branch_manager", "tutor",
"parent", "student")` and returns the first non-accessible audience with a non-zero count. Selection
is by **tier rank**, never by how close that audience's nearest chunk actually was. The probe hands
it counts, not distances (`count_matching_by_audience` returns `dict[str, int]`), so the information
needed to choose the *relevant* tier is discarded one layer earlier.

**Two causes are consistent with the observed response and it cannot separate them**, which is worth
stating rather than guessing: either the parent chunk is still outside 0.45 (0.499 > 0.45) and only a
branch_manager chunk matched, or both matched and parent lost on priority. **The second is not
fixable by widening the ceiling** — at any ceiling ≥0.499 this question still answers
"branch_manager", because priority does not consult distance. So AUD-C-21's remedy cannot reach this
case, and that is the finding.

**Bound, and it is real.** No content leaks — the hint is backend-authored, names a tier and nothing
else, and the audit/rate-limit path is untouched. D-166's sweep predicted exactly **1 wrong-tier hint
in 38** at this ceiling with zero false hints on both negative classes, so this is inside the
measured budget; it simply landed on the one question the finding was filed about. The unanswerable
class stayed clean live (`no_answer` 8/8).

**Disposition — DECIDED (user, 2026-08-03).** **0.45 stays deployed and this is fixed as its own
piece of work**, rather than reverted. The deployed state is a net improvement on the measurement
that exists (23 vs 17 correct roles, zero false hints on either negative class, `no_answer` 8/8
live), so reverting would trade six correct hints for one wrong-tier one and re-open AUD-C-21. The
wrong tier is real and bounded: backend-authored, names a tier and nothing else, no content leaks,
audit and rate-limit paths untouched.

**Fix shape, unmeasured and therefore a hypothesis** (D-158's rule): return per-audience *distances*
from the probe and pick the closest non-accessible audience, keeping tier priority only as the
tie-break. That inverts the current rule, so `scripts/measure_access_probe_rules.py` must re-score it
before it ships — its `build_access_hint`-based scoring is exactly what would change. Note D-164
already recorded that scoring "some gated audience matched" instead of the named role flatters every
rule; this is the same lesson pointing at the selector rather than the threshold.

**✅ FIXED in D-168 (2026-08-03) — and the hypothesis above was measured and is wrong.** "Return
distances, pick the closest" scores **identically** to the rule it replaces at the shipped ceiling
(23/38 right, 1 wrong): at 0.45 the parent chunk (0.499) is not in the candidate set, so there is no
second audience to compare. The label "hypothesis" earned its keep.

What fixed it is making the probe the pipeline it was paraphrasing — candidates under 0.60 →
`BedrockTask.RERANK` (the same reranker real retrieval uses) → audiences scoring above 0.8 → name one
only if it beats the runner-up tier by 0.10. Measured over both phrasings: **29/38 and 28/38 correct
with zero wrong tiers on either**, against 23/38 with 1 and 4 wrong. The margin is what buys the
zero — reranking alone reaches 33–36 right but keeps 2–5 wrong tiers, because on attendance questions
the parent handbook and the branch-manager procedure both genuinely answer.

**The motivating question is fixed in the sense that matters and not in the sense one might hope:**
on the fixture it produces **silence** rather than `"log in with a branch manager account"` — two
tiers legitimately compete for it and the probe declines to guess.

**✅ Deployed and verified live (2026-08-03).** PR #98, CI 9/9, merge `b4228aa4`, run
[30866202911](https://github.com/lucasjeongsikpark/IntelliChoice/actions/runs/30866202911), every
gate green, rollback skipped. **The live result beat the prediction:** the motivating question
returns `required_role: "parent"` — the *correct* tier, not silence — **stable across four
consecutive runs**. Live retrieval separates the two tiers by more than the fixture did, so the
sweep's margin suppressions are pessimistic and 29/38 is a floor. A second tier confirmed live
(`student`), and the one predicted regression (`no-answer-missed-1`) **does not reproduce** on the
deployed edge. The reranked path is confirmed by behaviour: the 0.45 distance-only fallback *is* the
old rule, which answers branch_manager here, so a `parent` hint is reachable only through reranking.

### AUD-C-21 — The access probe's distance ceiling was chosen against questions the corpus wrote (P2)

- **Severity:** P2 · **Area:** SPEC conformance (§18-C3) / instrument · **Status:** ✅ **fixed in
  D-166 (2026-08-03)**

**Fix: 0.40 → 0.45, and the fixture that decided it is the real deliverable.** D-165's questions
were generated *from* the chunk they target, under an instruction not to reuse its vocabulary. That
instruction reduces lexical echo and cannot remove the semantic pull of a passage the generator is
reading while it writes — so the ceiling it chose was tight enough to fail on the first real
question anyone asked.

**The instrument, and why it is structural rather than a better prompt.**
`scripts/generate_probe_eval_fixture.py --from-fixture` adds a `human_query` written by a pass whose
**only input is the question** — it never sees the passage, so it cannot borrow from it by
construction. Two controls keep that honest:

- **An answerability judge.** Passage + rewrite → does this passage still answer it? 5 of 55 cases
  drifted and were dropped. A drifted case is not a harder case, it is a case in the *wrong class* —
  it belongs to "nothing answers it", and keeping it would have flattered every wider ceiling.
- **`human_lexical_overlap` recorded per case**, as before.

**Measured, over the same 38 gated / 12 public / 8 unanswerable cases:**

| ceiling | right role | wrong role | silent | FP public | FP unanswerable |
|---|---|---|---|---|---|
| 0.40 (D-165) | 17 | 0 | 21 | 0 | 0 |
| **0.45** | **23** | 1 | 14 | **0** | **0** |
| 0.50 | 26 | 3 | 9 | 0 | **2** |
| 0.55 | 27 | 5 | 6 | 1 | 3 |

Distance from a question to the chunk it came from: chunk-derived **p50 0.379 / mean 0.395**,
human-phrased **p50 0.433 / mean 0.434**. The bias is real at **+0.054 (p50)** — and about a third
of the ~0.18 gap D-165's single anecdote implied, which is why the fix is one notch rather than a
jump to 0.55.

**Two negative results worth keeping.** A **relative-margin** rule ("also measurably closer than the
nearest chunk the caller can already read") was the obvious way to widen the ceiling without buying
false hints, and it does not work here: on unanswerable questions nearest-gated (0.623) and
nearest-readable (0.667) are only **0.044** apart, so the margin is satisfied by noise about half the
time. Its best variant trades 5 more correct hints for 4 false ones. And the **union** of the keyword
and semantic arms — the rule production actually applies — measured *identical* to the semantic arm
at every ceiling, so the keyword arm's only remaining justification is D-165's: mock observability.

**⚠️ `role_gated_question` stays at 2/3 live, and 2/3 is this fixture's ceiling.** Verified rather
than assumed this time: `role-gated-question-tutor` is answered from `public-contact-guide` at
confidence 0.85 with a real citation ("contact your branch manager immediately by phone"), so it
never reaches the probe. A public document genuinely answering it makes the case mis-classed, not
the feature broken — the same "public-answered vs unanswerable" conflation D-165's generator was
built to remove, sitting in the fixture that measures the feature. Rewording it is carry-over.

**⚠️ Found while making the new assertion fail on purpose: the eval never read the configured
ceiling.** `qa_coverage_runner.ask` built `TurnContext` without `access_probe_max_distance`, so it
used the dataclass default while the real route (`routers/sessions.py`) passes `Settings`'.
`CHAT_ACCESS_PROBE_MAX_DISTANCE=0.95` therefore changed nothing and the run passed, which read as an
inert assertion. No past measurement was wrong — the two values agreed — but an eval that cannot see
a tuned config cannot be used to tune one. Now fixed, which is what let the loosened-ceiling run
produce 8 false hints and fail.

### AUD-C-12 — §5.21.8's "retrieval score below threshold" has no implementation (P3)

- SPEC §5.21.8 lists "Retrieval score is below threshold" as a do-not-answer trigger. The only
  score-based filter in the pipeline is `retrieve()`'s `rerank_score > 0.0` (D-052), and the only
  threshold is `groundedness_confidence_threshold` (0.4), which gates the *model's self-reported
  confidence about its own answer*, not retrieval. A chunk the reranker scored 0.01 is passed to
  synthesis exactly like one scored 0.99. No minimum-relevance setting exists.

**✅ Closed 2026-08-04 (D-172 §3): `MIN_RERANK_RELEVANCE_SCORE = 0.35`, measured against the real
reranker.** `scripts/measure_retrieval_score_floor.py` (new; the dump/`--load` shape of
`measure_access_probe_rules.py`, so re-scoring any floor afterwards is free) scored the coverage
fixture's 20 answerable and 24 unanswerable cases with real Titan embeddings and the real
reranker — the approved corpus re-embedded inside a rolled-back transaction, because without that
step a real query vector meets the dev database's mock vectors and the semantic arm is noise
(AUD-C-16). **One run, 38.49 cents, no synthesis calls:**

| floor | answerable keep their document | unanswerable emptied | passages per answerable turn |
|---|---|---|---|
| 0.00 (shipped until now) | 20/20 | 7/24 | 9.9 |
| 0.10 | 20/20 | 13/24 | 5.7 |
| 0.30 | 20/20 | **24/24** | 3.5 |
| 0.35 | 20/20 | 24/24 | 3.5 |
| 0.60 | 19/20 | 24/24 | 2.9 |

No unanswerable case scored above 0.30; the weakest answerable case's own document scored 0.60. Any
floor in [0.30, 0.60) makes the same trade, so 0.35 was chosen for margin — one 0.05 quantization
step above the noise ceiling, 0.25 of headroom under the weakest real signal, and the same passage
count 0.30 keeps. A test asserts the band, so moving the constant means re-running the sweep.

**Two deliberate limits.** The floor is not applied when the reranker is unavailable: with no
scores it would discard every candidate and turn an outage into a corpus-wide "no approved source"
(AUD-C-08/AUD-C-19's class), and that path is already loud. And the **mock-backed eval keeps floor
0.0 by decision** — `MockBedrockProvider`'s reranker returns the fraction of query words present in
the chunk, so any floor ≥ 0.25 drops `grounded-team-3` and takes the gated `grounded` category from
88.9% to 77.8% without anything being broken. The two numbers measure different quantities on the
same scale (D-172 §4). Consequence: `make test` does not exercise the shipped floor end to end —
`packages/knowledge/tests/test_retrieval.py` covers it with explicit scores (watched failing at
0.0), and the real-Bedrock run reads it from `Settings`. **Run 2026-08-04 in three bounded arms (10.0c + 11.6c + 30.1c), and it corrected the framing:** a
real model already refuses all 8 `no_answer` cases (8/8 at floor 0.35 *and* at 0.0, matching S37's
record), so this floor's payoff on this fixture is **the paid synthesis call avoided and the refusal
made one stage earlier — not accuracy**. No answerable turn was lost: `paraphrase` 11/11,
`grounded_citation_rate` 17/20, and the three `grounded-branch-*` failures keep their expected
document at 0.95-1.00 (free attribution from the sweep dump), failing instead for the keyword-list
reason S37 documented.

### AUD-C-13 — The citation verbatim check accepts a one-character quote (P3)

- `qa._verify_citations` accepts a citation when `quote.lower() in chunk.chunk_text.lower()` and the
  quote is non-empty. There is no minimum length and no requirement that the quote overlap the
  answer, so `"a"` verifies against nearly any chunk. Only the quote's **hash** is stored
  (`supporting_quote_hash`, per SPEC's Citation schema), so nothing downstream can re-examine what
  was actually quoted. The defense is real but its floor is one character.

**✅ Closed 2026-08-04 (D-172 §2) with a measured floor, `MIN_CITATION_QUOTE_CHARS = 20`.**
Quantified first, over the real 144-chunk approved corpus
(`scripts/measure_citation_quote_floor.py`, seeded, free): a 1-character span occurs in a **median
of 140 chunks** (0% of sampled spans unique), 2 chars in 74, 4 in 10, 8 in 2 (44% unique). At 20
chars the median is 1 and the p90 is 2; 24, 32 and 40 chars barely improve on that, so 20 is the
knee rather than a preference. Length is measured on the AUD-C-18-normalized quote, so padding a
bare word with newlines is not a longer quote.

**The overlap-with-the-answer half of this finding was deliberately not implemented.** A faithful
answer legitimately paraphrases its source ("classes run 9am-6pm" over "operating hours are
09:00-18:00"), so a lexical-overlap requirement would drop real citations; the length floor is the
part that can be measured against the corpus rather than guessed.

**The cost was measured, not assumed.** A flat floor makes any shorter chunk uncitable, and
refusing an answer the corpus contains is AUD-C-08's defect. The five approved chunks under 20
normalized characters are all bare markdown headings (`# our team`, `## administration`), which
support no answer — asserted by `test_the_quote_floor_excludes_only_heading_chunks`, with a
chunk-count control so an unloaded corpus fails instead of passing vacuously. The alternative
"≥ 20 chars **or** the entire chunk" was rejected for admitting exactly those heading-only
citations. The synthesis prompt now states the requirement (asserted), and drops are logged as
`citation_quote_below_floor` with counts only — chunk text is org content and nothing redacts a log
line. **Measured 2026-08-04, same day:** across 20 answerable cases on real Bedrock producing **17
verified citations**, `citation_quote_below_floor` fired **zero** times — a real model never
under-quoted, and the 17 citations are the control that keeps that zero meaningful. The floor is free
on this evidence. (The mock quotes 80 characters, so the mock-backed eval scores identically at floor
1 and floor 20.)

### AUD-C-14 — `RespondResponse` omits `scope` and `intent`, so the post-resume SSE snapshot nulls them (P3)

- `MessageResponse` and `SessionSnapshotEvent` both carry `scope`/`intent`; `RespondResponse` does
  not. `_publish_snapshot` validates the snapshot from `response.model_dump()`, so every broadcast
  after a `/respond` sets both to `null` for any connected client. Exactly the class D-058 was written
  to prevent ("any field added to `MessageResponse` must also be added to `_initial_snapshot`"), in
  the one direction that decision did not name. chat-web does not currently render either field, so
  the impact today is nil — logged because the next field added here may not be inert.

### AUD-C-15 — An unknown-tool call raises without writing an audit row (P3)

- `McpToolRegistry.call` raises `McpToolError(f"unknown tool {tool_name!r}")` **before** `start` is
  set and before any `_audit` call. Every other failure path (permission, validation, timeout,
  execution) writes an `mcp_tool_calls` row with `success=False`. A call to an unregistered tool —
  the shape a prompt-injection or a wiring bug would produce — leaves no trace at all.

### AUD-C-16 — Stored embeddings are provider-specific, with no provenance and no re-embed path (P3)

- `rag_chunks.embedding` records no model or provider. Switching `BEDROCK_PROVIDER` between `mock`
  and `bedrock` silently invalidates every stored vector: a real Titan query vector compared against
  `MockBedrockProvider`'s hash-based vectors is noise, and nothing detects it — keyword search keeps
  working, so the system degrades to lexical-only retrieval while appearing healthy.
- This session hit it directly: the real-Bedrock eval had to re-embed all 144 approved chunks inside
  its rolled-back transaction to measure anything meaningful. ~~There is no `make` target for that and
  no way to tell from the database which provider produced what.~~ **Both halves of that sentence were
  fixed by D-112 (2026-07-28): `make knowledge-reembed` / `reembed_cli` is the target, and
  `rag_chunks.embedding_provider` / `.embedding_model_id` are how you tell. Struck 2026-08-04 (D-174
  §3a) after the stale text below cost a session an unnecessary inference.**
- **~~Not yet checked against staging~~ (RDS is in private subnets and this session's live pass was
  black-box over the API): whether staging's corpus was ingested with real Titan vectors or mock ones
  is unknown, and if it were mock, staging's semantic half is currently noise. Recorded as the first
  thing S38's live pass should settle.**
- **✅ SETTLED 2026-08-04 (D-174), five sessions after it was asked: staging is real-Titan embedded,
  and its semantic half is not noise.** Two independent lines of evidence, and the private-subnet
  obstacle was not an obstacle — the `ops-task` `run-task` override path (S32/D-084, the same
  mechanism the deploy workflow uses for Alembic) reads RDS directly, read-only, for the cost of a
  few Fargate seconds:
  1. **Vector fingerprints.** For chunks with **identical `md5(chunk_text)`**, `md5(embedding::text)`
     **differs** between the dev corpus and staging (e.g. `parent-attendance-policy`'s
     `900349c9…` chunk: local `3f884fd3…`, staging `d0ec47fe…`; 8/8 sampled chunks differ). That is
     decisive because `MockBedrockProvider._deterministic_vector` is a **pure function of the text**
     — sha256-seeded, `del model_id`, then L2-normalised — so identical text under the mock would
     give a **byte-identical** vector. Staging's therefore did not come from the mock.
  2. **The deployed task definition** sets `CHAT_BEDROCK_PROVIDER=bedrock` and
     `CHAT_BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0`.
  Both sides are dim **1024** and L2-norm exactly **1.0000** over all **159** chunks, so neither
  dimension nor normalisation discriminates — the fingerprint is what does.
- **⚠️ Correction, same day (D-174 §3a): the bullet above answered a question this finding had already
  closed, and its closing claim was wrong.** It said "the provenance gap this finding names is still
  real — `rag_chunks` records no model or provider". **It does record both.** `D-112` fixed this
  finding on **2026-07-28** and this row's own status says how: *"provenance columns stamped at ingest
  (NULL = unknown = mismatch)"*. `rag_chunks.embedding_provider` and `.embedding_model_id` exist,
  `intellichoice_knowledge.reembed_cli` re-embeds any row whose provenance does not match the
  configured provider, the staging deploy runs it on **every** deploy, and chat-api's `/readyz`
  **fails closed** on a mismatched corpus. So the answer was one `SELECT` away the whole time:
  **staging reads `embedding_provider = 'bedrock'` on all 159 chunks; the dev corpus reads `'mock'`
  on all 159** (both `amazon.titan-embed-text-v2:0`).
  **Why the mistake was possible, which is the part worth keeping:** the "Not yet checked against
  staging" bullet was written at filing time and **was never struck when D-112 fixed the finding**, so
  a stale open question sat inside a closed finding's body and read as live work. That is precisely the
  defect class the rest of this session was about (D-174 §1's 27 unrowed findings and five stale
  headings) — found here in the body text rather than in a heading or the Index, which is where nobody
  was looking. **The lesson is narrower than "read the status":** the status *was* read, and it says
  fixed; what was not checked is whether an inline question predates the fix.
  **The measurement stands as an independent cross-check** and is worth keeping for that reason — the
  fingerprint argument confirms, from the vectors themselves, what the provenance column asserts, so
  the column is not merely self-reporting. But it was the hard way round.

### Areas audited with no finding — S37

**Pre-retrieval filtering holds for every audience, on real content.** Five audiences (anonymous/
public, student, parent, tutor, branch_manager) × eight queries drawn from the real documents' own
wording, run twice: once against the corpus as it stands, and once inside a rolled-back transaction
with every `effective_from` pulled back a day so the 19 date-gated real documents become live. **No
role retrieved a chunk outside `{public, its own role}` in either pass** — anonymous saw only public
in all 51 hits; student, parent, tutor and branch_manager each saw only public plus their own tier.
This is the check that most needed real content rather than synthetic seeds, and it passed cleanly.

**Four of §5.21.3's other five predicates verified individually**, with purpose-built chunks that
differ in exactly one attribute: a `draft` chunk, a chunk with `effective_from` 30 days in the
future, one with `effective_to` a day in the past, and one tagged to `branch-B`. None was ever
returned. A `branch-A` chunk *was* returned to a branch-A student and correctly withheld from a
branchless one; an org-wide (`branch_external_id IS NULL`) chunk reached both. Only `academic_year`
failed (AUD-C-09).

**The access-hint probe leaks nothing it shouldn't.** `count_matching_by_audience` clears only the
audience allowlist; `status = approved` and the date window still apply, so the probe cannot reveal
that draft or expired content exists, and it returns counts grouped by audience — never ids, never
text. `build_access_hint`'s priority order is backend-authored and never model-proposed.

**Prompt-injection containment held under real Bedrock.** Five of six adversarial cases passed
(role-claim in the query text, system-override instruction, citation bait, document enumeration, PII
bait): none leaked seeded gated text and none cited outside the public allowlist. The sixth
(`adversarial-false-premise`) failed only its forbidden-string check by repeating the fabricated
time back in its answer — worth a closer read next session, but no content-boundary was crossed.

**Interrupt-approval and tool-call audit rows are written correctly.** Approving an email escalation
and completing a locator turn produced `interrupt_approvals` rows with the right `interrupt_type`,
`decision` and `source_app = "chat"`, and `mcp_tool_calls` rows for `maps.geocode` /
`maps.compute_routes` / `gmail.send_email` with `success` and `duration_ms`. `ToolCallAuditEvent`
carries no PII by construction — tool name, external id, success, exception *type*. The one gap is
AUD-C-15.

**A thread with a pending interrupt correctly rejects new messages.** `_reject_if_paused` returned
409 for both an anonymous caller and a second authenticated caller, so D-021's "a fresh `ainvoke`
silently discards a paused task" trap is genuinely closed. `/respond` also correctly 409s on a
mismatched `interrupt_type` and on "no interrupt is pending".

**Response-shape × render enumeration (the S22.5 class).** All fourteen shapes the API can emit were
enumerated against `ChatScreen`/`App`: grounded answer, no-source refusal, conflict message,
out-of-scope refusal, clarification, access hint, event listing, `.ics` result, rate-limited
escalation, email sent/declined/failed, location declined/missing, and each of the three pending
interrupts. **Twelve render correctly.** The two that do not are AUD-C-04 (a paused turn renders the
previous turn's answer) and AUD-C-10 (an errored turn renders `Thinking…` forever). One latent
gap: `App.tsx` renders a modal only for the three known `interrupt_type` values, and
`busy = pending !== null` — a fourth interrupt type added later would disable the composer with no
modal to resolve it, deadlocking the session. Not reachable today.

**Anonymous access works end to end on live staging.** `POST /chat/sessions` and `/messages` with no
token returned in-scope answers with real citations from the deployed corpus, confirming both that
§5.19.1's anonymous tier is genuinely open and that staging's RAG content is ingested and effective
— which S36's experience with empty learning tables made worth checking rather than assuming.

_(Not covered this session: the LLM-judge dimensions of answer quality — `packages/evals/llm_judge.py`
exists and is unused by this suite; multi-turn conversational context, which `QAState` does not yet
implement (`standalone_query` is always identical to `query`, a known carry-over); and browser-driven
runs, since no browser automation exists in this environment — the frontend findings above are from
code enumeration plus API-level evidence, not from a rendered page.)_

---

## S38 — AUD-X (cross-cutting integrity)

Scope per §2.3's AUD-X paragraph, risk-ordered and deliberately bounded at session start:
(0) settle AUD-C-16 against staging, (1) authn/authz boundaries across every route,
(2) idempotency of every retryable write, (3) the PII floor re-verified against **live staging**.

Crash-consistency (mid-node / mid-interrupt / mid-finalize) and cost ceilings under concurrency
were deferred when the session first ran and are **now covered** — AUD-X-07 and AUD-X-08, both P1,
both reproduced with sequential/consistent control arms. AUD-X-06 was also fixed, because it left
the test baseline intermittently red and so blocked §2.6 criterion 4 regardless of the audit.

### AUD-C-16 (settled) — Staging's corpus is entirely mock hash vectors; its semantic channel has never worked (P3 → **P1**)

S37 left this as the first question for S38's live pass: real Titan vectors or `MockBedrockProvider`
hash vectors? **Mock, all of them.**

- **Method — an exact, free discriminator.** `MockBedrockProvider._deterministic_vector` is a pure
  function of the embedded text, and `_persist_chunks` embeds exactly `draft.chunk_text`, which is
  stored verbatim. So recomputing the mock vector from the stored text and taking the cosine against
  the stored vector answers the question with no Bedrock call at all.
- **Both controls were run before trusting it.** Positive: the local dev corpus scores
  **159/159 at cosine 1.000000**. Negative: a real Titan v2 vector for the same text scores
  **−0.002925** against its mock counterpart — so "not-mock" would have been distinguishable had it
  been true. A discriminator that can only return one answer is not a measurement.
- **Result on staging** (one-off Fargate `ops-task` in the private subnets, the same mechanism the
  deploy uses for Alembic; read-only `SELECT`s; ids and cosines printed, never chunk text):

  ```
  PROBE totals chunks=159 embedded=159 docs=23
  PROBE rag_chunks verdict mock_like=159/159
  PROBE youtube_videos verdict mock_like=0/0   (no rows)
  ```

- **The runtime half, which is what makes it live.** Both deployed services run
  `BEDROCK_PROVIDER=bedrock` with `amazon.titan-embed-text-v2:0`. Every semantic search on staging
  therefore compares a real Titan query vector against hash noise.
- **The effect is measured, not inferred.** Same real Titan query vector, same corpus text, one
  variable — what the *chunk* vectors are (A: the stored mock vectors, B: the same 89 public
  approved chunks embedded with real Titan in memory, never written):

  | query | A — stored mock, top-1 | B — real Titan, top-1 |
  |---|---|---|
  | "What kind of help do you offer families whose kids are struggling in math class?" | `public-student-participation-guide` **+0.065** | `public-organization-overview` **+0.409** |
  | "Do students pay anything to join the tutoring program?" | `public-volunteer-guide` +0.074 | `public-volunteer-guide` +0.254 |
  | "How long has this organization been running, and who does it serve?" | `public-our-team` +0.065 | `public-organization-overview` **+0.190** |

  Arm A's similarities are indistinguishable from chance: random unit vectors in 1024 dimensions sit
  at |cos| ≈ 1/√1024 ≈ 0.031, and the best of 89 draws landing at 0.065–0.074 is exactly that
  distribution's tail. Arm A is not a weak ranking, it is **no ranking**.
- **User-visible, on the deployed system, today.** The seven `paraphrase` fixture cases — written
  specifically to reuse no rare word from the target chunk, so only the semantic channel can find
  them — run anonymously against live staging cite the expected document **1/7**. Of the three that
  actually reached retrieval as `document_qa`, two returned *"I don't have an approved source for
  that yet"* about documents that are approved, effective and ingested. (Two of the other four were
  refused by AUD-C-02's scope gap — independently reconfirmed here — and two routed to
  `branch_locator`, which is correct behavior and returned proper `location_consent` interrupts,
  not blank turns.)
- **Severity: P1, upgraded from P3.** §2.4's P1 is "a launch journey broken". Asking a question in
  your own words rather than the document's is the ordinary case, not an edge case, and on staging
  that path is answered by keyword overlap alone. It also invalidates any retrieval-quality claim
  made *about staging*, including S37's live observations, and §2.6 criterion 3 cannot be evidenced
  on a corpus whose retrieval half is inert. **Counter-argument, recorded:** keyword search still
  answers lexically-close questions (S37 saw real citations live), there are no real users, and the
  fix is mechanical. What moves it off P3 is not the misconfiguration — it is that nothing anywhere
  detects it.
- **Note on framing, corrected against a first reading.** This is not a mock-vs-real *mismatch*
  problem. A mock-embedded corpus has no semantic signal even when queried by the mock, because the
  vectors are hashes of text rather than representations of it. So staging has not "regressed" —
  its semantic channel has never worked, and neither has local dev's. What the real-provider runtime
  changes is only that nothing will ever coincidentally line up again.
- **Fix shape (Phase 0B):** a provenance column on `rag_chunks` (model id + provider) written at
  ingestion, a `make knowledge-reembed` target, a startup or readiness assertion that the configured
  embedding model matches what the corpus was built with, and a re-ingest of staging under
  `BEDROCK_PROVIDER=bedrock`. The assertion is the part that matters — the other three are one-time.

### AUD-X-01 — `POST /sessions/{id}/student` never checks who owns the session; any student can seize another's in-progress exam and lock them out (P1)

- **Severity:** P1. §2.4 puts authorization bypass under P0; this is held at P1 on the same
  reasoning AUD-C-01 was, and the reasoning is weaker here in one respect and stronger in another:
  the attacker still needs a `uuid4` session id, but unlike the chat case the victim **loses
  access to their own data permanently**, so this is a destructive write, not only a read.
- **Reproduction (local, real graph, real Postgres):**

  | step | result |
  |---|---|
  | `student-ext-1` builds a pre-exam session and answers an item | 200, attempt persisted |
  | `student-ext-4` (different branch, no relationship) `POST /sessions/{A's id}/student {"student_id": "student-ext-4"}` | **200** |
  | `student-ext-1` re-reads their own exam overview | **403** — *"Students may only access their own records"* |
  | `student-ext-4` reads the overview | 409 — the claim reset `phase` to `student_selected`, so there is no exam to read |

  A's `assessment_sessions` row stays `in_progress` with `student_external_id = student-ext-1`
  forever: the data is not misattributed, it is **orphaned**, and A has no route back to it.
- **Confirmed on live staging** (`d35dfnjzmgrm01.cloudfront.net`, deployed config, two
  secret-gated `/dev/token` student tokens):

  ```
  A creates + owns session:                200 phase=student_selected
  A selects topic:                         200 phase=blocked        (attendance gate, fail-closed)
  B claims A's session:                    200 phase=student_selected
  A reads own overview AFTER B's claim:    403 "Students may only access their own records"
  A tries to answer in own session AFTER:  403 "Students may only access their own records"
  ```

  The lockout reproduces exactly. The *orphaned in-progress exam* half is local-only evidence:
  staging's synthetic students have no attendance rows, so A's session stopped at `phase=blocked`
  and never built an exam. The authorization defect is identical either way; only the size of what
  the owner loses differs.
- **Root cause, and it is the same shape as AUD-C-01 in the other app.** Seventeen learning
  routes authorize by calling `resolve_target_student(claims, state["student_external_id"], …)`
  — the checkpoint's value, never the client's, which S36 recorded as a negative result and which
  is correct. `select_student` is the eighteenth route, it is **not** one of them, and it is the
  route that *writes* `student_external_id`. It validates the *requested* student against the
  caller's claims (`graph/nodes.py: resolve_student`) and never reads the existing value. **The
  one route that writes the field every other route reads is the one route that does not check
  it** — stated almost verbatim in AUD-C-01 about `post_message`. Two independent apps, same
  structure, found in consecutive audits.
- **The owner can do it to themselves.** The same call replayed by the legitimate owner also
  resets `phase` and 409s their own overview — see AUD-X-03; `busy={false}` is hardcoded at that
  call site too.
- **Fix shape:** in `resolve_student`, refuse to change `student_external_id` once it is set to a
  different value (a rebind is only legitimate for a parent switching children, which routes
  through `await_child_selection` and already carries its own check).

### AUD-X-02 — SPEC §5.1.2's `parental_consent_verified` check does not exist; three consent/account claims are carried in every token and read by nothing (P1)

- **What SPEC says**, §5.1.2, verbatim: *"`learning.intellichoice.org` must not use a
  student-facing notice as a substitute for parental consent for users under 13. It should verify
  `parental_consent_verified=true` from the existing system"*. `account_status` and
  `consent_status` are in the same required claim list.
- **What exists.** `TokenClaims` carries all three. `grep` across both apps finds **zero**
  readers outside the model definition and the dev issuer. Both `get_current_claims` functions
  check signature, expiry and audience, and stop there.
- **Measured, not inferred.** A token with `account_status="suspended"`,
  `consent_status="revoked"`, `parental_consent_verified=False`, `student_age_band="under_13"` —
  same signature, same audience — was run against all 18 learning routes. It behaved **identically
  to a fully-consented active token on every one**: created sessions, selected topics, read the
  dashboard, generated a report, finalized an exam.
- **Why no test catches it.** Three test files construct these claims; all three pass the
  permissive value. No test asserts the restrictive path, because there is no restrictive path.
- **The seam this actually lives in, stated plainly.** S45 owns consent and the roadmap's design
  is *"no-consent → no-token"* — enforcement at issuance rather than at the API. That is a
  defensible placement, but nothing records the decision to move the check out of the consuming
  app that SPEC assigns it to, and the failure mode is specific: if S44 builds the issuer and S45
  builds the ledger, and neither adds a consuming-side assertion, §5.1.2 stays unmet and **no test
  anywhere will notice**, because the claim is already present and already ignored. A fixture that
  always sets the safe value is not coverage.
- **Severity: P1, not P0.** The only issuer today is `FakeTokenIssuer`, which hardcodes the
  permissive defaults, and `/dev/token` is secret-gated on staging — so no token with these values
  can currently be minted by anyone but this audit. It is a child-safety requirement with no
  implementation and no test, on a platform whose primary users are minors, and it must not be
  allowed to fall between S44 and S45.

### AUD-X-03 — `POST /sessions/{id}/topics` is a non-idempotent exam-creating write; a replay silently abandons the first exam (P2)

- **Measured by row counts, not response codes:** replaying `/topics` on a session that already
  built a pre-exam returns **200** and adds **+1 `assessment_sessions`, +10 `assessment_items`**,
  with a **different variant set** (`same_variants=False`). The first exam is left `in_progress`
  and unreachable; any attempts already recorded against it are stranded.
- **The only guard is client-side and single-instance.** `useLearningSession.run()` holds a
  `busyRef` that swallows a second in-flight call — per hook instance. Two tabs, a refresh
  mid-request, a retrying proxy or any non-browser client bypasses it, and the server has no guard
  at all. `TopicSelectScreen` is passed `busy={false}` hardcoded at its `App.tsx` call site, so the
  button is not even visually disabled — **the same hardcoded-`busy` pattern AUD-L-10 found at
  ExamScreen's six call sites**.
  - ⚠️ **This bullet's second half went stale before the fix landed** (noted D-159): AUD-F-27
    wired `session.busy` into every screen including `TopicSelectScreen`, so the hardcoded
    `busy={false}` is gone. Recorded rather than edited away, because it is why the fix is
    server-side only.
- Contributes to the standing `question_variants` accumulation carry-over: every abandoned exam
  is a fresh variant draw.

**✅ Fixed 2026-08-03 (D-159).** `flow.is_topic_selection_replay` — pure, I/O-free, shared by the
route (pre-flight, so a refused replay runs no graph turn) and `graph.nodes.select_topic` (the
invariant). Same topic + still `pre_exam` → the existing exam's items, item for item; different
topic or advanced phase → 409; blocked (nothing built) → fully replayable, which D-152 §2's routine
UNKNOWN attendance and D-154's late-marking recovery both depend on.

**The first draft of this fix was wrong in an instructive way.** The guard went into
`flow.select_topic` — which has **no callers**. `graph/nodes.py:select_topic` reimplements the same
gate-then-build sequence against `LearningState`, and that node is the only path `POST /topics`
takes. The row-count test still measured a second exam being built, which is how the dead copy was
found; it and `TopicSelectionResult` are now deleted (three imports fell unused with them). Same
lesson as AUD-F-37/D-158 from the other direction: **read the path that actually runs before
believing the fix is in it.**

### AUD-X-04 — `POST /students/{id}/report` remains non-idempotent: one click, one paid call, one row (P3)

- Confirmed by row count: two identical calls → **+1 `student_reports` row each**, both 200. There
  is no idempotency key on this route, as AUD-L-02 noted in passing.
- **P3, not higher, and only because AUD-L-02's fix landed.** Before S36 this was the unbounded
  spend path; the `DAILY_REPORT_COST_CEILING_CENTS = 50.0` window now caps the damage at a day's
  ceiling, so what remains is duplicated work and duplicated rows rather than uncontrolled cost.

**✅ Fixed 2026-08-03 (D-159).** `Idempotency-Key` is now **required** on the route, matching
`POST /sessions/{id}/answers`; optional would have left the defect reachable by omission, which is
how it was reachable in the first place. Three layers, and each earns its place:

1. **The replay lookup runs ahead of the cost reservation**, so a replay spends no budget and
   returns the stored row byte-identically (`created_at` included — asserted, so "one row" cannot
   be satisfied by a second report that merely reads the same).
2. **`uq_student_reports_student_audience_key`** is the enforcement, because the lookup is
   read-then-act. Its recognition in `create_if_first` matches the constraint *name*, so a
   `packages/db` test pins that string — inverted once (wrong name → the `IntegrityError` escapes).
3. **A reused key with a different date range is a 409**, not a 200 carrying the stored report: the
   key cannot encode the range, and handing a parent last month's numbers under this month's
   heading is the AUD-L-15/AUD-C-19 failure mode.

**Where the key comes from matters as much as the check.** `submitAnswer` mints a fresh
`crypto.randomUUID()` per call; copying that here would have changed nothing, since two clicks
would send two keys. `StudentDashboardScreen` instead holds one nonce per mount and keys on
`(studentId, rangePreset, nonce)` — stable for the view the parent is looking at, fresh on remount,
so a double click costs one call while deliberate re-generation still writes history.

**Named, not fixed:** two truly concurrent calls under one key both reach Bedrock before either
inserts. The row is deduplicated, the spend is not; AUD-L-02's per-day ceiling and AUD-X-08's
ledger bound it. Closing it properly means claiming the key before the model call, which would put
a report row with no text into a parent's visible history.

**⚠️ The fix opened a regression, closed same-day as D-161:** the replay lookup serves the stored
row regardless of `generated`, and both server fallbacks persist their facts-only row under the
key — so a transient outage *pinned* the degraded report for the lifetime of the view, where
before this fix a second click was a real retry. Client-side repair: the per-mount nonce rotates
on a received `generated: false` (and only then — errors keep the key, because a lost response may
have committed). Three-arm Playwright spec `report-degraded-retry.spec.ts` asserts the key
contract by interception; the degraded arm was watched failing pre-fix.

**The migration is the three-step shape** (add nullable → backfill `legacy-<student_report_id>` →
`SET NOT NULL` → unique constraint), because staging already holds real report rows. Exercised
down-and-up against a dev database with 245 existing rows, not only from empty.

### AUD-X-05 — AUD-L-07 extends to *writes*: a tutor token can answer and finalize another student's exam (P1, extends AUD-L-07)

- AUD-L-07 recorded that `resolve_target_student` returns without a check for tutor and
  branch_manager, and described the impact as reading any student's data and generating reports.
  The route × caller matrix shows the same fall-through covers **every mutating session route**:

  | route | tutor on another student's session |
  |---|---|
  | `POST /sessions/{}/answers` | **ALLOW 200** — an attempt is graded and persisted |
  | `POST /sessions/{}/topics` | ALLOW 200 |
  | `POST /sessions/{}/resume` | ALLOW 200 |
  | `POST /sessions/{}/exam/finalize` | **ALLOW 200** — the exam is scored and closed |
  | `POST /sessions/{}/student` | ALLOW 200 — and `resolve_student` binds the session to *any* id (`target = requested_student_id or claims.sub`, unvalidated for this role) |
  | `GET /sessions/{}/stream` | stream opens |

- **Why this matters beyond the existing finding:** answers submitted by someone other than the
  student are indistinguishable from the student's own in `assessment_attempts`, and they feed
  scoring, mastery and learning-gain. A read-scope gap discloses data; a write-scope gap
  *fabricates* it. The one-line fix AUD-L-07 proposes closes both, which is the argument for
  keeping it a single finding rather than splitting it.

### AUD-X-07 — The checkpoint commits before the domain transaction, so a failure between them leaves the graph ahead of the database and the session permanently stuck (P1)

- **Severity: P1** — §2.4's "a launch journey broken". Both reproduced instances leave the
  student in a state with **no route forward**: every subsequent request 500s, and the exam they
  completed is orphaned. **Counter-argument for P0 ("data corruption"), recorded:** nothing is
  silently *misattributed* — the exam row stays truthfully `in_progress` and the checkpoint is
  merely ahead — and recovery needs a failure event rather than an attacker. What keeps it at P1
  rather than P2 is that the end state is unrecoverable through the API and needs operator DB
  surgery. Held at P1 on the same reasoning as AUD-C-01 and AUD-X-01.

- **The structure, which is the finding.** Two independent stores commit at two different times,
  in a fixed order, with no coordination:

  | # | when | what commits | connection |
  |---|---|---|---|
  | 1 | end of each superstep, inside `graph.ainvoke` | the **checkpoint** | `AsyncPostgresSaver`'s own psycopg pool |
  | 2 | FastAPI dependency teardown, **after the route returns** | the **domain rows** | the SQLAlchemy engine |

  `get_db_session` yields the session and only then calls `await session.commit()`
  ([learning-api dependencies.py:53-55](apps/learning-api/src/learning_api/dependencies.py#L53-L55));
  `main.py` documents that the saver "opens its own psycopg connections, separate from the
  SQLAlchemy engine". So step 1 always precedes step 2, and **anything that fails in between keeps
  the checkpoint and discards the rows** — FastAPI throws the exception in at the `yield`, so
  `session.commit()` is skipped and the session closes with a rollback. `apps/chat-api`'s
  dependency is **identical** ([dependencies.py:86-88](apps/chat-api/src/chat_api/dependencies.py#L86-L88)),
  so the seam exists in both apps.

- **Reproduced twice, at the two seams §2.3 names.** The induced failure is a raise at
  `_publish_snapshot` ([sessions.py:601](apps/learning-api/src/learning_api/routers/sessions.py#L601)) —
  the real statement that sits in that window — against the real graph and real Postgres, with row
  counts read on a second connection.

  **(a) mid-finalize.** A 10-item pre-exam, all answered, then finalize:

  | | checkpoint | database |
  |---|---|---|
  | after the crash | `phase=study`, `study_session_id=f530cf42…` | exam still `in_progress`; **0** `study_sessions` rows with that id; **0** `learning_gain` |

  The student's completed exam is never scored, and the checkpoint's `study_session_id` is a
  dangling reference. **What a reloading client then does, in order:** `POST /resume` → **200**,
  `phase=study`, and it **serves a study question**; the student answers it → **500**; every retry
  → **500**; `GET /exam/overview` → **409** *"session is not in an exam phase (phase=study)"*, so
  there is no way back to the exam either. The session is a dead end that still renders a question.
  (Probe 2 appeared to self-heal only because it called finalize a *second* time explicitly — a
  client that reads `phase=study` never would.)

  **(b) mid-interrupt.** `submit_answer → intervention_choice` is the graph's one multi-superstep
  turn. A wrong study answer writes a `study_attempts` row, then pauses on `interrupt()`:

  | | checkpoint | database |
  |---|---|---|
  | after the crash | `phase=study`, pending task `intervention_choice`, interrupt `intervention_choice` | **0** `study_attempts` rows |

  `POST /respond {"choice":"hint"}` → **500**, `hint_events` **0**, and the pending interrupt
  **never clears** (still `intervention_choice` afterwards). The student is paused on an interrupt
  that cannot be resolved and cannot answer anything else.

- **A negative result that sharpens it: the ordinary answer path does *not* diverge.** A pre-exam
  answer crashed at the same point left `assessment_attempts` at 0, the checkpoint at
  `phase=pre_exam`, and the overview showing every item `unseen` — consistent, because that route's
  entire effect lives in domain tables with nothing durable in the checkpoint to get ahead. A
  same-`Idempotency-Key` replay then produced exactly 1 attempt. **The seam only bites where the
  checkpoint carries a domain-row id**, which is what makes the two reproduced cases the dangerous
  ones rather than a general property of every route.

- **Why the 500s are unhandled: the checkpoint holds row ids and the code `assert`s the rows
  exist.** Both dead ends are bare asserts on a lookup the checkpoint promised —
  [study.py:45](packages/db/src/intellichoice_db/repositories/study.py#L45) `assert attempt is not
  None` (via `state.last_study_attempt_id`) and
  [sessions.py:874](apps/learning-api/src/learning_api/routers/sessions.py#L874) `assert session_row
  is not None`. The pattern is **84 instances** of `assert … is not None` across `learning-api/src`
  and the `packages/db` repositories, **35 in `graph/nodes.py` alone**. They are load-bearing
  invariant checks on cross-store consistency, expressed as a statement Python removes entirely
  under `-O`.

- **Realistic triggers, since the reproduction used injection.** The one that needs no bug at all
  is **a task stop between the two commits** — ECS drains tasks on **every deploy**, and S35 made
  deploys routine, so this window is entered on a schedule. Others: any unhandled exception after
  `ainvoke` in a route that already wrote rows (the MySQL-backed `_pending_interrupt_response` sits
  exactly there for `child_selection` and `email_approval`), a lost database connection at commit
  time, and a worker OOM. **Two candidates were checked and ruled out**, and both are worth
  recording so nobody re-derives them: `LearningGainResponse` makes `normalized_gain` and
  `normalized_gain_status` optional, so AUD-L-08's NULL status does **not** raise here; and
  `SessionSnapshotEvent` is a deliberately all-optional superset, so `_publish_snapshot`'s own
  `model_validate` is not itself a realistic raiser. `_publish_snapshot` is the *location* of the
  window, not the cause.

- **The chat app inherits the same seam with an audit-trail consequence.** `mcp_tool_calls` is
  written on the domain session while the tool result lands in the checkpoint, so the same window
  drops the SPEC §5.1.4 approval/audit row while keeping the effect — the same direction as
  AUD-C-15, reached by a different route. Not separately reproduced this session.

- **Fix shape (Phase 0B), in order of value.** (1) Commit the domain session *before* the
  checkpoint, or bring both under one transaction — LangGraph's saver accepts an external
  connection, which is the only real fix for the ordering. (2) Failing that, make the divergence
  *recoverable* rather than fatal: replace the asserts on checkpointed ids with a reconciliation
  path (missing row → rebuild or roll the phase back) so a stuck session self-heals on the next
  request. (3) A consistency check at session read time comparing `phase` against the rows it
  implies. (2) is the cheap one and would have converted both reproduced dead ends into ordinary
  recoverable turns.

### AUD-X-08 — Every per-day cost ceiling is a read-then-act race: 10 concurrent reports spent 8× the ceiling (P1, weakens AUD-L-02's P0 fix)

- **Severity: P1, with the P0 reading recorded.** §2.4 puts "uncontrolled spend" under P0, and
  there is a real argument for it: the daily ceiling is *the* control bounding this route's spend,
  and the multiplier is the caller's concurrency, which the caller chooses. It is held at P1 on the
  same basis as the other findings here — `/dev/token` is secret-gated on staging, there are no
  real users, and each individual call is still token-capped by the gateway, so what a caller gets
  is a multiple of one report's cost rather than unbounded spend. **This is the top money item for
  Phase 0B**, and unlike AUD-L-02 it was not fixed in-session (§2.4 reserves that for P0s).
- **The shape.** `generate_student_report` reads the spend, then spends:

  ```python
  spend_today = await repo.get_spend_cents_since(student_external_id, now - 24h)   # report.py:206
  if spend_today >= DAILY_REPORT_COST_CEILING_CENTS: ...return the facts-only fallback
  result = await gateway.generate_structured(...)                                  # report.py:242
  ```

  There are **two** windows, not one. Concurrent callers all read the same pre-call value; and
  because the row carrying `cost_cents` is committed by the **dependency teardown after the
  response** (AUD-X-07's ordering), even a *staggered* caller that starts after an earlier call has
  finished its Bedrock request still reads a stale spend.
- **Measured, with the sequential control that makes it meaningful.** Local, real Postgres, real
  graph, `MockBedrockProvider` (the gateway's cost accounting is provider-independent, so the
  arithmetic is real even though the calls are free). The ceiling was monkeypatched down to exactly
  one report's measured cost so that 10 requests can reach it — the race is scale-invariant:

  | arm | result |
  |---|---|
  | one report, to calibrate | `generated=True`, **0.0819¢** |
  | **sequential control** — ceiling = 0.0819¢, second report | `generated=False`, cost **0.0** — *the ceiling works correctly when nothing races* |
  | **10 concurrent**, ceiling = 0.0819¢, zero prior spend | **all 200**, **8 of 10 generated**, total **0.6552¢** = **8.0× the ceiling** |

  The control arm is the point: this is not a broken check, it is a correct check with no
  serialization around it. (8 rather than 10 because two requests happened to read a spend that had
  already committed — the exact multiple is a timing artifact; the direction is not.)
- **A single authenticated caller can drive it**, because AUD-X-04 records that this route has no
  idempotency key: 10 identical concurrent POSTs are 10 accepted paid calls. Via AUD-X-05's
  tutor/branch_manager write fall-through, the same loop can be aimed at any student.
- **Two more ceilings have the identical shape.** Neither was separately measured; both are named
  so the gap is legible rather than inferred:
  - `nodes.py:1126` — the tutor-chat per-day ceiling, read from `tutor_chat_messages` and committed
    at teardown. Same read-then-act, same commit lag.
  - The per-session gateway budget (`_session_budget_cents`, default 50¢). The gateway is
    **stateless with respect to spend** — `session_spend_cents` is a caller-supplied argument
    ([gateway.py:136](packages/adapters/src/intellichoice_adapters/bedrock/gateway.py#L136)), read
    from `state.bedrock_spend_cents` at ~20 call sites — so concurrent turns on one thread each
    read the same checkpointed total and each receive a full budget. Related and already known:
    `run_chat_turn`'s docstring records that chat's own calls are **never persisted back** into
    `bedrock_spend_cents` (D-072), so that ceiling already under-counts by design.
- **Fix shape (Phase 0B):** make the reservation atomic rather than advisory — a single
  `INSERT … SELECT` guarded by the ceiling, or `SELECT … FOR UPDATE` on a per-student spend row, so
  the check and the debit happen in one statement. An idempotency key on the route (AUD-X-04) is a
  partial mitigation for the duplicate-click case but does nothing for distinct concurrent requests.
  Whatever lands must be re-verified **with a concurrent arm**, since the sequential test passes
  today and would keep passing.

### Areas audited with no finding — S38

**The token layer holds on every axis tested.** Every route in both apps (18 learning + 6 chat)
was called with thirteen caller shapes. Anonymous, expired, bad-signature, `alg: none`, and
**wrong-audience tokens in all three directions** (chat→learning, go→learning, learning→chat)
returned **401 on every authenticated route, without exception**. `JwtTokenVerifier` pins
`algorithms=["HS256"]`, so the unsigned-token attack is rejected at the library boundary rather
than by a claim check that could be reordered away.

**Cross-caller isolation holds wherever `resolve_target_student` is actually called.** A different
student and an unlinked parent got **403 on every one of the 18 learning routes**. The failures
above are all *missing calls* to that helper (AUD-X-01) or *fall-through inside* it (AUD-X-05) —
the helper itself is correct for the roles it checks.

**The interrupt-resume path is stricter than the rest of the app, and is the pattern to copy.**
`/respond` against a genuinely pending `child_selection` interrupt denied **every** non-owner —
another parent, a tutor, and even the child the interrupt is about — with 403. It is stricter
because `await_child_selection` compares `ctx.claims.sub` against the **checkpointed**
`parent_external_id` rather than going through the role-based helper. That is exactly the check
AUD-X-01 and AUD-X-05 are missing, already written and working, one file away.

**SSE `?token=` is not a weak spot.** Ownership and audience are both enforced on the query-string
path (other student 403, chat-audience 401, `alg:none` 401, missing token 422), and a tutor's
stream opening is AUD-X-05, not a stream-specific gap. **The token does not reach application
logs**: the access-log middleware records the *route template*
(`/learning/sessions/{learning_session_id}/stream`), so neither the JWT nor the session id is
written — verified by making a real `?token=` request and grepping the log.

**Idempotency holds everywhere it was implemented.** Same-`Idempotency-Key` answer replays produce
**zero** new `assessment_attempts`; double finalize produces zero new completions; duplicate
problem reports dedupe per reporter. AUD-L-10's defect is specific and remains exactly as it was
recorded — a *fresh* key on an already-answered item adds an attempt (+1, reconfirmed here from
S38's side). Two identical chat questions produce two full turns, which is correct behavior, not a
missing dedupe.

**§2.6 criterion 9, logs half: clean, with the positive control that makes that meaningful.**
Fifteen patterns — six exact fixture names, both manager emails, both street addresses, the four
branch coordinates, and shape patterns for email/JWT/`Bearer `/`token=`/PII field names/echoed
query and answer text — over **30 days of both application log groups**: **zero hits**, while the
two positive controls in the same batch returned **32,744** and **2**. *The first version of this
scan reported zero for everything including strings that are demonstrably present*, because
`filter-log-events --max-items` paginates and only the first page's count was read. That is
D-101 §5's failure mode reproduced exactly one session later, caught only because a positive
control was run. Logs Insights `stats count()` over the whole window is the shape that works.

**§2.6 criterion 9, stored-payload half: staging's checkpoints are clean, scanned in full.** All
**1,552 `checkpoint_writes` and 181 `checkpoint_blobs`** rows on staging — the entire tables, not a
sample — deserialized with the checkpointer's own serde and walked as objects: **zero coordinates,
zero names, zero emails, zero JWTs**. The one `street-address` hit is public branch-directory text
inside a RAG `answer`, which is the product working. The same scanner run against local dev as a
positive control found **24 keyed coordinate values across 12 `__resume__` rows**, independently
reproducing AUD-C-03 by a different method than S37 used.

**Metrics carry no identifiers by construction.** Every Prometheus metric uses bounded enum
labels (`result`, `phase`, `support_type`) — no ids, no free text, no unbounded cardinality.

**`/metrics` and `/healthz` are not publicly reachable.** The staging CloudFront distribution
forwards only `/chat/*`, `/dev/token` and `/me` to the ALB; everything else falls through to the
SPA origin. A `curl` of `/metrics` returns **200 with `text/html`** — the SPA's `index.html`, not
the metrics endpoint. Worth stating because the status code alone reads as an exposed endpoint.

**AUD-L-01 reconfirmed on the deployed chat app** (it was recorded against learning): missing and
wrong `X-Staging-Token-Secret` both 404 correctly, while `GET /dev/token` → **405** and
`POST` with `{}` → **422** each disclose that the route exists.

**Crash-consistency and cost ceilings are covered** — see AUD-X-07 and AUD-X-08. Both carry a
control arm rather than only a failure arm, and both controls passed: the ordinary pre-exam answer
path stays *consistent* across the same induced crash (checkpoint and rows both roll back, and a
same-key replay produces exactly one attempt), and the report ceiling *correctly* degrades to the
facts-only template when requests do not overlap. The defects are specific to where the checkpoint
carries a domain-row id, and to concurrency.

_(Limits that remain, stated because they bound what criterion 9 can currently claim: **traces cannot be audited at all — `OTEL_ENABLED` is
`false` on both staging services**, so the "traces" half of criterion 9 is unevidenced rather than
passing; and **AUD-C-03's coordinates are absent from staging only because no locator turn has
ever completed there**, not because anything prevents them — the 22 `__resume__` rows are other
interrupt types. The full route × caller matrix ran against the real local APIs rather than
staging — driving 13 caller shapes × 18 routes live would have created far more residue than the
finding warrants — but **AUD-X-01, the most serious of them, was reproduced end to end on live
staging** and is recorded there.)_

### AUD-X-06 — A hint test asserted a stricter rule than the product's own leak check (P3, fixed in S38)

- **Found by the routine baseline re-run**, on a working tree containing **only documentation
  changes**: `test_hint_ladder_escalates_through_three_levels_without_leaking_answer` failed —
  512 passed, 1 failed.
- **Measured before diagnosing** (D-100's own lesson), twice, with random ordering disabled:
  **7/30** at discovery and **8/40** on re-measurement — **15/70 (21%)** combined. The cause is
  the handler's unseeded `random.Random()` per request, not test order.
- **The failing assertion, and every failure had the same shape** — the answer digit equals the
  hint level, so answer `"1"` fails on round 1, `"2"` on round 2, `"3"` on round 3:

  ```
  AssertionError: assert '3' not in 'hint l3, addressing sign_error: subtract that number ...'
  ```

- **Root cause.** The test asserted `correct_answer_text.lower() not in
  intervention["hint_text"].lower()` — a **plain substring check**. The product's rule,
  `authored_validation.answer_text_leaked`, is a boundary-aware regex that deliberately *does not*
  fire for a digit adjacent to another alphanumeric: it would not flag `hint l3` for the answer
  `"3"`, because the `3` is preceded by `l`. **The test asserted something stricter than the
  product guarantees**, and the mock's own boilerplate is what tripped it.
- **The rate is a property of the bank's answer distribution, not its size.** Of the bank's
  **51,613 variants, 9,215 (17.9%)** have a correct answer of `"1"`, `"2"` or `"3"` — which is the
  measured 15/70 (21%). The earlier draft of this finding guessed "the question bank has grown";
  that hypothesis is **withdrawn**, and it was never needed, because —
- **AUD-L-17 did not regress. This finding originally conflated two different tests.** AUD-L-17
  diagnosed and pinned `test_hint_reflects_the_students_actual_wrong_option`
  (`test_learning_flow.py:1292`), which is **still 0 failures in 20 runs** today. The 60/60 it
  recorded was that test's, not this one's — so there was no contradiction to explain. (A 60/60 run
  at a 17.9% per-run failure rate has probability 0.821^60 ≈ 1×10⁻⁶, which is itself the tell that
  two different tests were being compared.)
- **What AUD-L-17 actually did was *unmask* this flake, and the mechanism is verifiable in one
  line.** Before it, the mock emitted `Level 1`, where the digit is space-delimited — so
  `answer_text_leaked` **fired**, the tutor discarded the personalized hint and substituted the
  canonical ladder text, and the canonical text carries no bare digit, so the substring assertion
  passed. After the change to `Hint L1` the runtime check **stopped** firing, the mock's own hint
  was served for the first time, and the substring assertion started seeing `hint l1`:

  | mock prefix | runtime check (`answer_text_leaked`, answer `"1"`) | plain substring | escalation test |
  |---|---|---|---|
  | `Level 1` (before AUD-L-17) | **leak → canonical served** | leak | passes |
  | `Hint L1` (after AUD-L-17) | no leak → **mock hint served** | leak | **fails 21%** |

- **The transferable part.** AUD-L-17 concluded "the mock's own boilerplate made the mock's own
  hint unusable" and adjusted the boilerplate — which was correct for the test it was fixing, and
  is precisely what exposed a *second*, independent defect one file away. The durable coupling is
  between a **test assertion** and a **mock string**, neither of which is the product; any fix
  applied to the mock only moves which answers collide.
- **Fix applied (in-session, because it blocked the baseline rather than the product):** the
  assertion now calls the two functions `tutor.py:240` itself calls — `leak_phrase_present` and
  `answer_text_leaked` — so the test asserts exactly the guarantee the product makes. The mock was
  **not** touched, on this finding's own reasoning. **0 failures in 40 runs** after (8/40 before),
  and `make lint typecheck test` green **three consecutive times** — the run count §2.6
  criterion 4 asks for.
- **Note on why the S36-continuation guard did not catch it.**
  `test_mock_hint_is_leak_clean.py` asserts the mock's hint against `answer_text_leaked` for every
  reachable answer, and it passes — correctly. It could not have caught this, because the defect
  was in a *different* test's stricter assertion, not in the mock.

---

## S39 — AUD-F (frontend contracts + operations)

**Method.** The browser-driven half of §2.3, which S36 and S37 each left uncovered because no
browser automation existed in this environment. A Playwright harness now lives in
[e2e/](../e2e/) (`make e2e`), chromium-only, one worker, zero retries. Every run attaches a
console/network capture to the page and enforces §2.6 criterion 3's three properties at
teardown over the whole run rather than at any single assertion: zero console errors, zero
5xx, zero blank/stuck states. A test that deliberately drives an error path narrows that check
with an explicit, greppable `audit.allow({...})`; the default is strict.

**The harness carries its own positive control** (`tests/smoke.spec.ts`), for the reason D-101 §5
and D-102 record: a probe that can only return "clean" is not a measurement. It produces a
console error and a failed request on purpose and asserts the fixture saw both.

**Three hypotheses were formed and then disproved by measurement**, which is worth recording
because each would have been a plausible finding written up from code reading alone:
- *"The requested hint is displaced before the student can read it."* Measured: the hint panel
  survives **14.7 s** of no interaction. Not a defect. The journey walk's apparent disappearance
  was the graph having already advanced past that pause.
- *"The SSE stream reconnects ~2×/second."* Suggested by 71 `net::ERR_ABORTED` entries against
  the stream URL in one 38-second run. Measured with the student idle: **0 stream reopens in
  20 s**. The aborts are the session hook's own `EventSource` cleanup on screen swaps — expected
  behavior, and the harness now excludes them rather than reporting a phantom.
- *"The attendance gate is bypassed for an absent student."* The browser reached a stage
  narrative instead of the gate, which looked like a fail-closed violation. Checked directly at
  the API for both fixtures first: the gate fires at `/topics`, not at `/student` — absent →
  `phase: blocked`, present → `pre_exam`. **The gate is correct and the test was asserting at the
  wrong step.** Rule 5 holds.

### AUD-F-01 — Inline-arrow callbacks in effect dependency arrays fire two endpoints per render (P1)

`App.tsx` passes `onFetchOverview={() => void session.fetchExamOverview()}` and
`onRecordTime={(id, ms) => session.recordItemTime(id, ms)}` — new function identities on every
render. `ExamScreen` lists both in effect dependency arrays: the overview poll effect
(`[isExamPhase, phase, onFetchOverview]`) and the view-time autosave effect
(`[currentDisplayOrder, phase, currentOverviewItem?.assessment_item_id, onRecordTime]`). Every
App render therefore tears both effects down and re-runs them — the poll fires an immediate
fetch and installs a fresh interval, and the autosave's *cleanup* reports elapsed time and its
body immediately resets `viewStartRef`.

**Measured, with the student sitting on one question for 15 seconds and touching nothing:**

- **885 `POST /exam/items/{id}/time` requests** (~59/second), values
  `[21, 24, 19, 18, 17, 19, 18, 19, 17, 17, 19, 18, …]`, **max 94 ms**. Each report covers the
  gap between two renders, not time on task.
- **76 `GET /exam/overview` for one 10-item exam** — 7.6 per answer submitted — at a **median
  gap of 30 ms** against the code's own `OVERVIEW_POLL_MS = 20000`, a ~667× amplification.

Both endpoints hit the database (`add_item_time` does a read-modify-write on
`assessment_item_state`). §2.4 puts "cost or latency out of bounds" at P1, and this is on the
hot path of the primary launch journey at 1,000-MAU scale, so P1 is the reading recorded here.
The fix is small — memoize both callbacks, or drop them from the dependency arrays via a ref —
but it must be **re-verified by counting requests**, not by observing that the screen still
works, because the screen has always still worked.

**S41 disposition — fixed, and the re-measurement is the evidence (D-109).** `App.tsx`
destructures `fetchExamOverview`/`recordItemTime` from the hook and passes those memoized
functions straight through. Same probe, same 15-second dwell, current code, freshly started
servers:

| | before | after | control (fix reverted) |
|---|---|---|---|
| `POST /exam/items/{id}/time` | 899 | **1** | 849 |
| `GET /exam/overview` | 903 | **2** | 849 |
| longest single reported dwell | 68 ms | **15,009 ms** | 67 ms |

The control column is the point: `tests/learning/time-telemetry.spec.ts` was promoted from a
`test.fail()` probe to a regression test only after it was watched failing with the fix undone
(D-107 §1). It now asserts the counts as well as the value — a fix that made the reports
accurate while leaving the effect churn in place would still be a database write per render.

**Bearing on AUD-L-14, which needs re-examination rather than a fix as written.** The server
*accumulates* (`state.time_spent_ms += elapsed_ms`), and the browser's 885 reports total
**15,591 ms for a 15,000 ms dwell** — approximately correct. So client telemetry is not
inherently zero, and S36's "140 item-state rows summing to 0 ms" is most consistent with those
journeys having been driven **through the API with no browser in the loop**, which is exactly
how S36 drove them. AUD-L-14's underlying point stands (the report depends on client telemetry
while ignoring the always-populated `assessment_attempts.response_time_ms`), but its headline
evidence should be re-measured with a browser before anything is built on it.

### AUD-F-02 — The client keeps calling exam endpoints after finalize, flooding the console with 409s (P2)

After `POST /exam/finalize` returns 200: **35 requests rejected 409 in a 96 ms burst** — 33
`GET /exam/overview` and 2 `POST /exam/items/{id}/time` — and **zero arriving more than 5 s
later**, with no exam screen mounted at the end of the window. Timestamped precisely to
separate a leaked interval (unbounded) from a remount burst (bounded); it is the latter, driven
by AUD-F-01's per-render effect churn as the app transitions out of the exam phase.

Bounded, self-limiting, and invisible to the student — but each failed fetch is a browser
console error, so a single journey accumulates **35–59** of them. **§2.6 criterion 3 requires
zero console errors on every launch journey, so the criterion cannot be met until this is
fixed**, independently of any user-visible symptom. Reproduced by
`tests/learning/post-finalize-poll.spec.ts`, which is marked `test.fail()` so the suite stays
green while the count keeps being measured on every run; when Phase 0B fixes it the test passes
unexpectedly and fails the run, which is the signal to promote it to a regression test.

**S41 disposition — fixed, and "same root cause as AUD-F-01" turned out to be wrong (D-109).**
The AUD-F-01 fix alone took this from **35 × 409 to 1**, and that last one is a different
defect: the view-time autosave flushes on unmount, and the screen unmounts *because* the exam
was finalized, so no amount of removing effect churn can reach it. `ExamScreen` now raises a
`finalizedRef` that suppresses both the flush and the poll tick — **before awaiting
`onFinalize`, which is the whole of the fix.** `finalizeExam` calls `setSnapshot` inside the
awaited request, so React can flush that render and unmount this screen in a microtask that
lands before the `await` here resumes; setting the ref afterwards left the 409 in place on
every run. That was not deduced, it was instrumented: a temporary `console.warn` in the cleanup
reported `phase=pre_exam isExamPhase=true finalized=false` for the last item, run after run,
until the ref moved ahead of the await.

Now **0 × 409 and 0 console errors**, and the test is promoted, having been confirmed to fail
again with the ref moved back after the await. **A third change was reverted rather than
shipped:** scoping the flush to exam phases looked right and was written up in the code with a
confident explanation, but a control run showed the test passes just as well without it. It was
added on a wrong model of the sequence, no test covers it, so it is not in the diff. Whether
study-phase time is ever attributed to a stale exam item is now a carry-over question, not a
silent fix.

### AUD-F-03 — A refresh mid-exam does not restore the student's position (P2)

Answer two questions, refresh: **"Pre-exam Question 3 of 10" becomes "Pre-exam Question 1 of
10"**. The session, the answers and the read-only locks all survive — only the position is lost,
because `sessionId` is persisted in `sessionStorage` while `currentDisplayOrder` is `ExamScreen`
state that a reload discards.

SPEC Phase 11's own "done when" is that a page refresh restores the exact position, and
`useLearningSession`'s docstring cites it verbatim as the reason the session id is persisted at
all — so this is a documented requirement that no test covered. P2 rather than P1 because the
student can navigate forward with the nav bar and loses no work.

**Fixed in D-173 §1 (2026-08-04).** Derived from the exam overview rather than persisted, applied
once per phase, with the "first unanswered ≠ last viewed" residual named in the code. See the
table row and D-173 for the reasoning; the short version is that the overview endpoint already
existed for this ("lets the exam nav bar restore item statuses after a mid-exam refresh") and a
second copy in `sessionStorage` would have been a source of truth that could disagree with it.

### AUD-F-04 / AUD-F-05 — Stage narratives return after a refresh, and displace live screens (P3, P3)

> **⚠️ Filing these two under one heading is what let AUD-F-05 sit "open" after it was fixed,
> and what shifted every AUD-F-0x reference in the e2e suite by one.** They are separate findings
> with separate mechanisms and, as it turns out, separate fates: F-04 needed code (D-173 §2) and
> F-05 had already been closed by AUD-F-21. Corrected 2026-08-04. The transferable part is
> D-170's, arrived at from the opposite direction: a shared heading is a reason to *read* two
> findings together, never evidence that both still describe a defect — ask of each one
> separately whether it is still true.

`App.tsx` gates `stage_narrative` ahead of every phase branch and tracks dismissal in React
state keyed by the narrative text. Two consequences, both measured:

- **AUD-F-04 — after a reload the narrative returns** (`"Welcome back! Let's see what you
  remember today."`) because the snapshot still carries it and the dismissal did not survive. One
  further click clears it and the exam returns — verified, and the whole of why this is P3.
  **Fixed in D-173 §2**: both gates (`dismissedNarrative` *and* `interactedPhase`, the second
  door the finding did not name) now live in a `sessionStorage` record keyed by learning session
  id.
- **AUD-F-05 — the narrative displaces a screen already in use.** The topic list renders from the
  `/student` response and is interactive for a measured **~26 ms** before the SSE snapshot
  carrying the narrative replaces it; the same swap detaches the Submit-answer and ladder buttons
  mid-click. A human is unlikely to lose a click to a 26 ms window, and the one scripted click
  that landed inside it still reached `POST /topics` — so the real cost is that every automated
  journey needs retry logic, which is how this was found in the first place.
  **Already fixed by AUD-F-21 (status corrected 2026-08-04, D-173 §3, no new code).** AUD-F-21
  made the narrative render *above* the phase screen in a two-slot Fragment rather than returning
  `StageTransitionScreen` as a sibling branch — this finding's own mechanism — and shipped a
  regression test written to this finding's subject (`narrative-displacement.spec.ts` arm 3
  asserts the topic list is visible *beneath* the narrative, and its comment notes it is "the one
  arm of this file that would have caught AUD-F-21 without faking any timing"). What survives is
  a layout shift, not a displacement.

### AUD-F-06 — No scheduled jobs exist, so criterion 6's clock has not started (P2)

`aws events list-rules` and `aws scheduler list-schedules` both return **empty**. All four jobs
run clean when invoked by hand (`chat-purge`: 0 rows older than 90 days; `memory-consolidate`:
160 students; `youtube-sync`: 4 updated; `webcontent-sync`: 5 sections / 50 members / 26
branches / 42 events) — but nothing invokes them.

**Only three of the four are schedulable at all, which changes the Phase 0B work item.**
`make webcontent-sync` **rewrote seven tracked files** under `knowledge-content/` when run here,
and prints "Review the git diff before running `make org-load`/`make knowledge-load`" — it is a
content-authoring step that expects a human to inspect its output, not an unattended job. It also
**broke the test suite** while those edits were in the working tree
(`test_ingestion_creates_all_documents_then_is_idempotent_on_rerun`), which is how it was noticed;
reverting the files restored 513 passed. Scheduling it in ECS would additionally fail outright
against D-088's `readonlyRootFilesystem = true`. §2.5's "EventBridge schedules for the four manual
jobs" should therefore be re-scoped to **three** (`chat-purge`, `memory-consolidate`,
`youtube-sync`), with `webcontent-sync` left manual and that decision recorded.

**Fixed in S40, and building it changed the answer twice.** `terraform/modules/scheduled-jobs`
creates EventBridge **Scheduler** schedules (not a rule + cron: explicit timezone, per-target retry
policy, per-job enable gate) targeting the existing ops task with a command override, plus an
EventBridge rule on any non-zero-exit ops-task run routed to the alerts topic.

**Re-scoped again: three schedulable jobs became *two* enabled ones.** This finding counted three
from a *local* run, and running them against the deployed environment is what showed the
difference. `memory-consolidate` and `youtube-sync` read `MEMORY_*`/`YOUTUBE_*`-prefixed settings
that the ops task never set, and both default to **`bedrock_provider = "mock"`**. A mocked
scheduled job does not fail - **it succeeds and writes fabricated data into the real database on a
weekly cadence**, which is strictly worse than an outage, and AUD-C-16 is precisely what that looks
like discovered months later. `memory-consolidate` is now wired explicitly - including pointing
`MEMORY_BEDROCK_CONSOLIDATION_MODEL_ID` at the model IAM actually grants, since its own default is
Sonnet 5 which this task role cannot invoke, so the unwired job would have been *either* mocked or
denied. **`youtube-sync` is DISABLED**: `youtube_provider` defaults to `"fake"` and no real key
exists (D-002's posture, still true), so an unattended run would refresh the catalog from a fake
source every week.

**The failure notification was itself dead on arrival, and only a test caught it.** The rule fired
correctly - `Invocations = 1` - and `FailedInvocations = 1` while SNS delivered **0**: the topic
policy did not permit `events.amazonaws.com` to publish. **CloudWatch *alarms* publish to that same
topic fine on the default policy alone** (4 delivered during S39's induction), which is exactly why
this was worth measuring rather than reasoning about - the working service gave false confidence
about a different one. Fixed with an explicit topic policy that reproduces the default statement
verbatim (dropping it would revoke the account's own Subscribe rights and orphan the email
subscription) plus an `events.amazonaws.com` publish grant scoped by `SourceAccount`. Re-verified:
the next two deliberate failures both delivered, 0 failed. **The notification built to stop a
scheduled job failing unnoticed would itself have failed unnoticed** - AUD-F-12's shape reproduced
inside its own remedy, one session later.

The consequence is a schedule fact, not just a defect: §2.6 criterion 6 requires the jobs to have
run **unattended for ≥ 1 week**, so **the earliest the gate can pass is one week after the
EventBridge schedules land in Phase 0B**. That should be sequenced early in S40–S41 rather than
late, or it becomes the critical path to S42 on its own. It also means the 90-day `chat-purge`
retention promise currently depends entirely on a human remembering to run `make`.

### AUD-F-07 — The memory-consolidation job spends 94% of its budget on load-test fixtures (P2)

One `make memory-consolidate` run: **160 students, 577 facts added, 145.97 cents**. Of the 159
distinct students with `semantic_memory` rows, **150 are `loadtest-student-N`** — disposable
fixtures S34's load test created and never removed.

**Premise corrected in S40: staging has *zero* `loadtest-` rows** - its `semantic_memory` table is
empty entirely, and `learning_events`/`stage_transitions`/`assessment_sessions` contain no
loadtest-prefixed ids at all (checked directly against staging Postgres via the ops task). The 150
fixtures are **local-only**, which follows from D-095: S34's load test ran against docker-compose
because that session had no live AWS access. So the ordering constraint below - clean the fixtures
*before* creating the schedule - **was not actually load-bearing**, and no scheduled run was ever
going to spend Bedrock money on synthetic students. Cleaning the local dev database is now
optional hygiene (it does make `make memory-consolidate` locally report 160 students and 145.97
cents, which is noise that could mask a real regression). Recorded because the reasoning was sound
and the premise was still wrong: **a measurement taken locally is not a measurement of staging**,
the same correction D-103 §3 made about browser-vs-API evidence.

Locally the provider is `MockBedrockProvider`, so that figure is what the cost-accounting layer
would charge rather than a real charge; the same job against staging's real Bedrock spends real
money, and would do so on **every** scheduled run once AUD-F-06 is addressed. Ordering matters:
clean the fixtures (or scope the job to real students) **before** creating the schedule, not
after. Same family as AUD-L-02 and AUD-X-08 — a paid path with no bound on how much work it
decides to do.

### AUD-F-08 — Two of four deployables have no CI job (P3)

`ci.yml` has `lint-typecheck-test` (Python) and `learning-web` (lint + typecheck + build).
**`chat-web` has no job**, already known and on the Phase 0B list, and the new `e2e/` harness has
none either. Against criterion 4's "CI builds and tests every deployable", two of four are
uncovered. Recorded rather than fixed here because §2.5 already owns chat-web CI; the e2e harness
should join the same job when it lands.

### AUD-F-09 — The deploy workflow would have crash-looped the new sidecar (P2, fixed in S39)

`deploy-staging.yml` patched the image tag with `for c in td['containerDefinitions']` — every
container, not just the app's. Correct while each task had exactly one container, and silently
fatal the moment Terraform added the `aws-otel-collector` sidecar: the loop would have rewritten
`aws-otel-collector:v0.43.3` to `aws-otel-collector:gha-<sha>`, an image that does not exist,
and every subsequent deploy would have failed to start and rolled back via the circuit breaker.

Found by reading the deploy path *before* applying the sidecar rather than by watching a deploy
fail. Fixed in the same session because it is a defect in the change being made, not a
pre-existing product defect: the patch now selects the app container by name and asserts exactly
one match, so a future container-name change fails loudly instead of mis-tagging.

### Negative results, S39

All of the following were exercised **in a real browser** and behaved correctly.

- **Every chat response shape renders.** All **18** payload shapes the API can emit — S37's
  fourteen, with the email and location outcomes split into their sub-variants — rendered
  correctly, including citations, escalation banner, access hint, `.ics` download button,
  suggestion chips, and a visible modal for each of the three interrupt types. **S37's
  code-reading conclusion is confirmed by rendering**, which is what its ⏸ was waiting for.
- **The fixtures are not fiction.** A drift control runs one *real*, un-stubbed turn and asserts
  the live `/messages` field set equals the fixtures' — so a backend change that outgrew these
  shapes fails the suite instead of letting it audit a payload the API no longer sends.
- **AUD-C-04, AUD-C-10 and AUD-C-11 reproduced visually**, not just at the API: the paused turn
  renders the previous turn's answer *and* citation above an unrelated approval modal; an errored
  turn keeps a `Thinking…` bubble indefinitely while the error text renders separately below; and
  the no-source refusal renders a citation chip beside the sentence denying a source exists.
- **The composer locks and unlocks correctly** around a pending interrupt — which is what makes
  S37's "a fourth interrupt type would deadlock the session" a genuine latent gap rather than a
  live one.
- **Attendance fails closed in the browser for both cases.** Absent (`student-ext-2`) and
  **unknown-attendance** (`student-ext-3`, no row at all) students both reach the gate and never
  reach an exam screen; the branch-manager path shows the email draft with both Send and Decline
  before anything is sent (SPEC §5.1.4), and declining leaves the gate closed.
- **The parent journeys work.** A two-child parent is offered exactly both children and the
  selection sticks; a **single-child parent is auto-selected** without being asked, so S11's
  auto-select gap does not reproduce here.
- **Chat answers render for every audience** — guest and signed-in student, parent, tutor and
  branch_manager — plus out-of-scope refusal, welcome-card suggestion chips, new-chat reset, real
  login-screen sign-in, and transcript restoration across a refresh.
- **The branch locator asks consent before collecting anything**, renders the notice text,
  disables the composer while pending, honors "Don't use my location", and returns a rendered
  answer when a ZIP is shared.
- **No SSE reconnect storm**: 0 stream reopens in 20 s of idle.
- **X-Ray held 0 traces over 6 hours** before any change — a clean baseline for the trace work,
  recorded so that traces appearing after the sidecar deploys means something.

### AUD-F-10 — Private-subnet tasks cannot reach public.ecr.aws, so the sidecar could not be pulled (P2)

The VPC has interface endpoints for `ecr.dkr`, `ecr.api`, `secretsmanager`, `logs` and
`bedrock-runtime`, an S3 gateway endpoint for image layers, and **no NAT gateway** — deliberate,
per D-084's cost posture. Private ECR works through those endpoints; `public.ecr.aws` is a
separate registry with **no interface endpoint at all**, so it is simply unroutable from a task.

Nothing predicted this. It appeared the moment the sidecar deployed:

```
CannotPullContainerError: pull image manifest has been retried 7 time(s): failed to resolve ref
public.ecr.aws/aws-observability/aws-otel-collector:v0.43.3: ... dial tcp 75.2.101.78:443: i/o timeout
```

`essential: false` on the sidecar did **not** help, and the reason is worth recording: a
non-essential container that *exits* leaves the task running, but one that cannot be **pulled**
fails the whole task before it starts. Non-essential protects against a crashing collector, not
against an unreachable image.

**Handled, and the state is precise.** Both services were rolled back to the pre-sidecar revision
and re-verified through the public edge — frontends 200, learning `/readyz` **200** (which proves
real Postgres *and* MySQL connectivity), chat `/me` 401, `/dev/token` **404** with no credential,
so S35's security gate is intact. An `aws-otel-collector` repository now exists in this account's
private ECR, `scripts/mirror-otel-collector.sh` pins the version and pushes **linux/arm64** (to
match `runtime_platform`, since an amd64 image on an ARM64 task fails with an exec-format error
that looks nothing like a platform mismatch), and Terraform points the sidecar at the mirror.
**The push did not finish before the AWS session expired**, so the mirror is empty.

**The one thing that must be done first next session.** Task-definition revision 18 is the latest
and still references the public image, and `deploy-staging.yml` resolves
`--task-definition intellichoice-staging-<svc>` to the *latest* revision before patching it — so
**the next CI deploy inherits the unreachable sidecar and fails** (safely: the circuit breaker
rolls it back, as it just did). Either run the mirror script, or set `enable_otel_tracing = false`
and re-apply, before the next push to `main`.

**Closed in the S39 continuation.** The mirror was pushed (`sha256:ba3c3f06…`, 39 MB,
`linux/arm64` confirmed against `runtime_platform`), Terraform re-applied, and both services
deployed onto the sidecar revision cleanly — `COMPLETED`, both `otel-collector` containers
RUNNING, both target groups healthy, the hazard above de-armed because the latest revision now
names the private mirror. **One addition to the script:** the anonymous pull failed with
`toomanyrequests: Rate exceeded`. `public.ecr.aws` rate-limits unauthenticated pulls, and
`aws ecr-public get-login-password | docker login public.ecr.aws` clears it — worth knowing before
concluding the image is gone.

### AUD-F-11 — Terraform's image pin had gone stale behind deployed reality, so `apply` reverted a security fix (P2, fixed in the S39 continuation)

`terraform.tfvars` pinned both services at `gha-6cc4a27430bd`. Both services were *running*
`gha-d1899a483d06`. The gap matters because of which commit that is:

| tag | commit | pushed to ECR | what it is |
|---|---|---|---|
| `gha-6cc4a27430bd` | 6cc4a27 | 2026-07-24 10:34 | the asyncpg SSL fix |
| `gha-d1899a483d06` | d1899a4 | 2026-07-24 **16:31** | **"`/dev/token` signed with the public dev constant, not the real secret"** |

So every `terraform apply` registered a task-definition revision that **silently reverted a
security fix**, and an operator who applied and then pointed the service at the new revision —
the natural reading of "apply, then deploy what I just applied" — would have deployed the
regression. CI never noticed because `deploy-staging.yml` patches the image tag on top of
whatever Terraform registered, so the stale pin is invisible on the path that is normally used.

**Why nothing could have caught it.** `terraform plan` is clean: the tag exists in ECR and pulls
fine. `terraform validate` is clean. The tfvars comment even asserted the pin was "latest on
main", true when written and false six hours later. The only thing that reveals it is diffing the
*registered* revision against the *running* one, which is what found it here — done because
D-103 §5's lesson was to read the deploy path before applying, and the same discipline applied one
step further.

**Fixed** by bumping the pin to `gha-d1899a483d06` with a comment stating the failure mode, and
the sidecar revision was then verified to differ from the running revision in exactly one
dimension (OTel on, sidecar added) before deploying. **Third occurrence of this project's
recurring shape:** config-level intent and deployed reality disagreeing with nothing tying them
together — D-096 (P0, `/dev/token` open for two days) and AUD-F-09 (the per-container tag rewrite)
are the first two.

### AUD-F-12 — The collector accepted every span and discarded every one, and nothing detected it (P2, fixed in the S39 continuation)

With the sidecar finally running, no trace reached X-Ray. The app was exporting correctly and the
collector was receiving correctly; the **export leg** failed, every time:

```
Exporting failed. Rejecting data. {"kind": "exporter", "data_type": "traces", "name": "awsxray",
 "error": "Post \"https://xray.us-east-1.amazonaws.com/TraceSegments\": context deadline exceeded",
 "rejected_items": 64}
```

**AUD-F-10's root cause, one layer further in.** No NAT gateway, and no interface endpoint for
`xray` — so in this VPC, every AWS API the tasks call needs its own endpoint, and X-Ray had been
overlooked exactly as public ECR was. The lesson generalises past both: **`terraform plan` cannot
see reachability**, and each of these appeared only at runtime.

**The part that makes it a finding rather than a config oversight is that nothing detected it.**
The sidecar is `essential: false` and starts perfectly healthy. The app's own export succeeds — it
hands spans to a local collector that accepts them. Both services stayed green, both target
groups healthy, no alarm watches collector export failures, and the only evidence was a WARN
buried in a sidecar log stream nobody reads. **Criterion 9 would have been reported "clean" from
an empty trace store** — which is precisely why `scripts/scan_xray_pii.py` treats zero traces
scanned as an explicit FAIL rather than a pass. That guard, not the endpoint, is the durable fix.

**Fixed** with a single-AZ `xray` interface endpoint (`var.xray_endpoint_enabled`, wired to
`enable_otel_tracing` so it is not paid for when tracing is off), matching the cost posture of the
existing five (~$7.30/mo; a NAT to carry the same traffic would be ~$32). Traces went from the
recorded baseline of **0 over 6 hours** to **650** on the next traffic run. The failures logged
*after* the endpoint went live were the batch queue draining spans buffered during the outage —
identical `rejected_items: 64` each time — not new failures, which is worth stating because they
read exactly like an unfixed problem for several minutes.

### AUD-F-13 — A bearer JWT is recorded in `http.url` on every SSE connection (P1, fixed in the S39 continuation)

The very first PII scan of real traces found a **455-character JWT** in a span attribute:

```
$.http.request.url   http://d35dfnjzmgrm01.cloudfront.net/learning/sessions/
                     65bb3d96-.../stream?token=<JWT>
```

**Mechanism.** The SSE stream authenticates via a query parameter because `EventSource` cannot
set an `Authorization` header, and `FastAPIInstrumentor` sets `http.url` to the **full** request
URL, query string included. Reproduced locally in three lines: `http.route` is templated and
`http.target` is the bare path — **`http.url` alone carries the credential.**

**The same request is sanitized in one store and not the other**, which is the transferable part.
Access log and trace segment for the identical request (`trace_id 3a10417997b2a36996a5fb2c75194901`,
19:44:47 UTC, 401):

```
log:   {"event": "http_request", "path": "/learning/sessions/{learning_session_id}/stream", "status_code": 401}
trace: http.request.url = ".../stream?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

The app's own access logger templates the path and drops the query string — deliberately. That is
why **S38's log scan was clean and this trace scan was not**, and why a PII floor has to be
re-established per store rather than inherited: instrumentation added later does not honour the
sanitisation the application wrote for itself.

**Impact, bounded honestly.** Token TTL is 1 hour, so a captured token is usable for at most an
hour after issuance; reading it requires AWS access to this account; and the one token actually
captured was **already expired when recorded** (hence the 401). X-Ray has no delete API, so it
ages out with the 30-day retention. Held at **P1 rather than P0** on that basis — but it becomes a
live-credential capture the moment authenticated traffic runs with tracing on, which the load run
and any `make e2e` against staging both do.

**Fixed in-session**, on the D-103 §5 rule: enabling tracing on staging is this session's own
change, and this is a defect in that change rather than a pre-existing product defect §2.4 would
defer. Redaction happens in a `RedactingSpanExporter` at the **export boundary**, not in a
`server_request_hook`. The hook does work — measured, the instrumentation sets `http.url` before
calling it, so an override wins — but that is an ordering guarantee no library documents, and
`tracing.py` already records two upstream ordering footguns that silently dropped spans. Export is
the one point every span from every instrumentation must cross. **The regression test drives the
real instrumentation** (a FastAPI app, a real SSE-shaped route, `TestClient`) rather than the
regex, because the defect was about which attribute the instrumentation populates, not about the
pattern — and it was confirmed to fail with redaction disabled before being trusted. A second test
asserts ordinary attributes survive, since a redactor that rewrote everything would also pass the
first one.

**Re-verified live on staging after the CI deploy (`bccc3ac`, task-definition revision 21)**, which
matters because the local test proves the code and not the deployment. Three SSE requests carrying a
deliberately fake JWT — a 401 is irrelevant, since the URL is recorded either way, which is what
makes this testable **without holding a real credential**:

```
$.http.request.url = .../learning/sessions/00000000-0000-4000-8000-000000000001/stream?token=REDACTED
leaked_jwt: False | redacted: True   (×3)
```

The path and session id survive, so the span stays diagnostically useful. Found live, fixed,
deployed through the normal pipeline, and re-verified live by the same scanner that found it.
**Both services confirmed**, which matters because chat's stream takes the same optional `?token=`
(SPEC §5.19.1) and the fix lives in shared `packages/observability` rather than in either app:

```
chat-api:     .../chat/sessions/88cd4977-.../stream?token=REDACTED   leaked=False redacted=True (×2)
learning-api: .../learning/sessions/00000000-.../stream?token=REDACTED  leaked=False redacted=True (×3)
```

**Still to do before the gate:** a re-scan against *authenticated* traffic — see the coverage limit
below.

### Criterion 9, traces half: clean, with both a positive control and a coverage control

**1,925 traces / 9,614 segments / 749,155 strings** scanned clean over a 2-hour window, and the
apparatus matters more than the number:

- **Positive control, every run: 20/20 patterns fired** against a synthetic segment. Without it,
  "clean" is unfalsifiable — the failure mode S38 hit and D-101 §5 recorded.
- **Coverage control.** The one request that carried precise coordinates in its body (a guest
  locator consent flow, `latitude: 39.781712, longitude: -89.650143`) was proven to be *in the
  scanned set* — session `fa31a009-…`, with a `langgraph.branch_locator_consent` subsegment — and
  **no coordinate appeared anywhere in it.** Request bodies are not captured into spans. Without
  this control, a clean result could equally mean the interesting request was never scanned.
- **17 hits in the first run were all false positives**, and the fix is recorded because the shape
  recurs: `39.85` as a *substring* matches the epoch `start_time` on every segment
  (`1785093039.8546414`). Now boundary-aware and control-tested both ways — epochs do not match,
  `39.850012` does. Same mistake AUD-X-06 records in a test assertion one session earlier.
- **One narrow allowlist, printed rather than silent:** `sql.sanitized_query` legitimately contains
  the column names `manager_email, address, latitude, longitude`. That is schema, not data, and its
  presence alongside no parameter values is evidence the stripping works. A coordinate *value* in a
  sanitized query would still be reported.

**Coverage limit, stated plainly.** Only guest and unauthenticated traffic could be driven — the
per-app `STAGING_TOKEN_SECRET_*` values were not available to this session, and reading them out
of Secrets Manager is not something an audit should do. Authenticated journeys are where names and
emails would actually enter a span, so **the trace scan is real but narrow**; it must be re-run
against authenticated traffic before the gate. AUD-F-13 was found in unauthenticated traffic only
because a stale browser token happened to be retrying.

### AUD-F-15 — `chat-purge` had never run against the deployed database, so the 90-day retention promise was never kept (P1, fixed in S40)

Found by the **first ever scheduled run** of the job, which is the only thing that could have found
it:

```
ConnectionRefusedError: [Errno 111] Connect call failed ('127.0.0.1', 5432)
```

**Mechanism.** The CLI called `create_engine(get_settings().database_url)`.
`learning_api.config.Settings` sets `env_prefix = "LEARNING_"`, so it looks for
`LEARNING_DB_HOST`/`LEARNING_DB_PORT`/… — while the **ops task** supplies D-092's *unprefixed*
`DB_HOST`/`DB_PORT`/`DB_NAME` plus credentials from Secrets Manager, which is what
`create_engine()`'s bare fallback resolves. Finding none of its prefixed variables, the settings
object kept `database_url`'s hardcoded default: `postgresql+asyncpg://…@localhost:5432/…`.

**Why three prior audits and a CLI-level test all missed it.** On a developer's machine, and in CI,
**localhost genuinely is the database**. `make chat-purge` worked. `test_tutor_chat_purge_cli.py`
worked — it exercises the real cutoff arithmetic against a real Postgres, which is worth having and
is orthogonal to this. Every signal available without a deployment said the job was fine. The
consequence is not a crash but an unkept promise: SPEC's 90-day tutor-chat retention **had never
once executed against real data**, and would not have until someone ran it by hand inside the VPC.

**Fix:** `create_engine()`, bare, matching `consolidate_cli` and `sync_cli`. Local behaviour is
unchanged (no components set → `DATABASE_URL` → the same localhost default).

**Verified on the real path after deploying, not just locally** — the fix is in app code, so only a
deployed run proves it. A one-shot Scheduler probe was fired against the rebuilt image:

```
startedBy: chronos-schedule/probe-chat-purge-af    (i.e. EventBridge Scheduler, not run-task)
taskDefinition: intellichoice-staging-ops-task:17  (the image containing the fix)
exitCode: 0
log: "purged 0 tutor_chat_messages row(s) older than 90 days"
```

`0` is the correct answer here — staging holds no tutor-chat rows past the cutoff — and it is
distinguishable from the failure it replaced, because the broken form could not reach a database at
all. **The same probe technique is what found the defect and what confirmed the fix**, and it cost
about two minutes each time; waiting for 18:10 UTC would have deferred both by a day.

**Third instance of one shape, so the fix is a guard rather than a patch.** `create_engine`'s own
docstring already records the S32/D-084 instance (`curriculum-load` against real RDS, same
`ConnectionRefusedError`). `packages/db/tests/test_standalone_clis_use_the_env_fallback.py` now
asserts every standalone CLI calls `create_engine()` with no argument, **with a negative arm**
asserting the two FastAPI apps still pass theirs explicitly — because a blanket "never pass an
argument" rule would be wrong for them, and a guard that over-applies gets deleted by the next
person who trips over it. Deliberately a source-level check: the behaviour to guard is "does not
read the app's prefixed settings", and the only runtime condition that reveals it is having no
database at localhost — which is exactly what a developer's machine cannot reproduce.

### AUD-F-14 — Five concurrent chat turns take 30 seconds each, and the autoscaling policy cannot see it (P1)

**Measured on live staging**, 45 guest RAG turns against real Bedrock, all **200** — no errors, no
timeouts. The service queues rather than failing, which is the right failure mode, and then:

| condition | response time |
|---|---|
| unloaded, single turn | **1.62–1.88 s** |
| 5 concurrent turns | p50 **26.92 s**, p95 **32.14 s**, max **33.41 s** |

ALB-observed p95 per minute: **3.56 → 31.97 → 30.96 → 30.98 s** against the alarm's 3.0 s
threshold — roughly **10× out of bounds at a concurrency of five**, which for a launch aimed at
~1,000 MAU is not a stress test.

**The part that is a defect rather than a capacity fact: nothing can react to it.** Application
Auto Scaling is configured (min 1, max 3) with a single **`ECSServiceAverageCPUUtilization`
target-tracking policy at 70%**. The workload is I/O-bound — it is waiting on Bedrock, not
computing — so during the window where p95 sat at 31 s, CPU **peaked at 15.19%** against an idle
baseline of ~1.3%:

```
15:43  CPU max  1.44%   p95  3.56s
15:44  CPU max 15.19%   p95 31.97s     <- worst CPU of the whole run, still 55 points below target
15:45  CPU max 12.56%   p95 30.96s
15:46  CPU max  9.11%   p95 30.98s
```

`desiredCount` never left **1**. So the scaling policy will not fire at any latency this workload
can produce, and **§2.6 criterion 7's "live load meeting the S34-calibrated thresholds with ≥2
tasks" is unreachable as configured** — not because scaling is absent, but because it is wired to
the one signal that stays flat. The fix is a different signal (`ALBRequestCountPerTarget`
target-tracking, or a step policy on the p95 latency alarm that already exists), or a higher static
`desired_count`; the choice belongs in Phase 0B alongside the item the roadmap already carries.

**This also sharpens D-095's diagnosis rather than contradicting it.** S34 concluded "the real
bottleneck is that `desired_count=1` with one uvicorn worker means all concurrent request handling
serializes on one Python process… the real fix for the P95 gap is capacity, not code," and added
this autoscaling. Correct on the cause. What could not be seen from a docker-compose run against
`MockBedrockProvider` — S34 had no live AWS session (D-095) — is that **the capacity fix it added
cannot be triggered by the bottleneck it diagnosed.** S34 measured 2.77 s p95 at 150 concurrent
sessions with a mock; real Bedrock puts ~2 s of I/O wait into every turn, and five of those
serialized is 30 s at a CPU cost of nothing.

### Criterion 5 — deliberate bad-image deploy, auto-rolled back, with downtime measured

A revision was registered with an unpullable tag on the **essential** container (`gha-deadbeefdead0`),
so the task fails before any bad code serves a request — the breaker is what is under test.

```
15:28:11  task 1 started -> CannotPullContainerError, pull retried 7 time(s), not found
15:30:21  task 2 started -> same
15:32:34  task 3 started -> same
15:39:09  task 4 started -> same
15:42:06  deployment failed: tasks failed to start
15:42:06  rolling back to deployment ecs-svc/5798213581200726447
```

`failedTasks` reached **3**, the threshold for a single-task service; the bad deployment ended
`FAILED`/`DRAINING` with 0 running, and revision 21 returned as `PRIMARY`. **13 m 55 s** from bad
deploy to rollback — worth knowing, because it is the floor on how long a bad deploy is stuck
before ECS gives up.

**Zero downtime, measured rather than assumed: 200 edge probes across the whole window
(20:27:56 → 20:44:56), every one a 401 from the application, zero 5xx and zero connection
failures.** `minimum_healthy_percent = 100` kept the old task serving the entire time.

**Two tooling mistakes made while measuring this, both recorded because they are the recurring
shape of this project's near-misses.** (1) The poller first targeted the CloudFront **root**, which
is the S3-hosted SPA and returns 200 with the API completely dead — the availability number would
have been meaningless. It was changed to `/learning/*`, one of the three behaviours CloudFront
forwards to the ALB, where a 401 proves the application answered. (2) The script's summary line
still compared against literal `200` after that change, so it reported `non-200=200` — every probe
"failing" when every probe was the expected 401. The raw log settled it. **A check that cannot
fail, and a check that cannot pass, are the same bug.**

**Cleanup:** revision 22 was deregistered. Leaving a poisoned revision as the family's *latest* is
precisely AUD-F-10's trap, since `update-service` against a bare family name resolves to latest.

### Criterion 8 — one alarm induced genuinely end to end, three on the delivery leg only

**`chat-api-p95-latency`: fully induced, detection and delivery.** Real 30-second latency drove it
`OK → ALARM` at 15:48:54 on its own evaluation, citing the actual datapoints:

```
Threshold Crossed: 3 datapoints [30.955 (20:45), 31.966 (20:44), 3.558 (20:43)]
were greater than the threshold (3.0).
```

and the topic action executed. **Delivery is proven by SNS's own metrics, not inferred from the
alarm**: `NumberOfMessagesPublished` 1, **`NumberOfNotificationsDelivered` 1**,
`NumberOfNotificationsFailed` 0, against a three-hour baseline of zero. Across all four inductions:
**4 delivered, 0 failed**, to the one confirmed email subscription on
`intellichoice-staging-alerts`.

**Human receipt confirmed by the maintainer, 2026-07-26: all four emails arrived.** Recorded
explicitly because it is the half of criterion 8 that no AWS API can evidence — `Delivered` means
SNS handed the message to SES, not that it survived spam filtering into a monitored inbox. **So the
"reaching a monitored inbox" half of criterion 8 is now met for all four alarms**; what remains
partial is the *detection* half for the three that could only be driven with `set-alarm-state`.

**The other three used `set-alarm-state`, and that is a real limit, not a formality.** No
unauthenticated path exists to induce them: every learning route depends on `get_current_claims`,
and chat has no reachable 5xx (a malformed session id and a nonexistent one both return **200** —
any string is a valid LangGraph thread id for a guest, which is AUD-C-01's shape again). So for
`learning-api-5xx-rate`, `learning-api-p95-latency` and `chat-api-5xx-rate`, what is proven is that
**each alarm's own action wiring reaches a delivering subscriber** — worth having, since a
mis-wired action on one alarm would otherwise be invisible — but **not** that the metric and
threshold detect the condition they exist for. Those three need `STAGING_TOKEN_SECRET_*` and stay
**partial**.

**Two operational facts learned here, both of which will bite whoever repeats this.**
**(1) An alarm fires several minutes after the breach ends.** ALB metrics publish with ~1.5–2 min
lag (a period's `SampleCount` was watched growing 9 → 20 after the minute closed), so the p95 alarm
transitioned at 15:48:54 for a window that closed at 15:46. An interim conclusion that a short
burst *cannot* fire it was wrong, and the correction is the useful part: the lag **delays** firing,
it does not prevent it — so do not extend a load run just because the alarm has not tripped yet.
**(2) `set-alarm-state` is transient and the next real evaluation overrides it.** The p95 alarm was
manually cleared to OK, then legitimately returned to ALARM minutes later on the tail of the load
data. **This matters beyond tidiness: `deploy-staging.yml`'s canary-bake step rolls a deploy back
if any of these four alarms is in ALARM**, so an induction left lit — or cleared too early and
re-firing — breaks the next deploy. Staging was left with all four settled `OK` naturally.

## S43 — the latency carry-overs, diagnosed (2026-07-29)

D-113 left two observations with no IDs and an explicit instruction to diagnose before filing: a
consistent ~26 s gap between the `embedding` and `rag_answer` log lines with **no `rerank` line at
all**, and nine of 114 load turns returning 200 in 30–84 ms with zero Bedrock calls. They are
**one defect with three separable faults**, filed here as AUD-X-09/10/11 and all three fixed in the
same session.

**The measurement that settled it was one X-Ray trace**, not a hypothesis. `7ee8e72c…`, a 24.6 s
staging turn against the `9467c78` deploy:

| span | duration |
|---|---|
| `langgraph.scope_guard` (incl. its Bedrock call) | 1.59 s |
| `bedrock.create_embedding` | 0.14 s |
| `hybrid_search` — 3 SQL queries | **38 ms** |
| `bedrock.generate_structured` (rerank) | **20.93 s**, and no log line |
| `langgraph.synthesize_answer` | 1.83 s |

That killed the leading rival hypothesis outright — Postgres/pgvector was never slow, it answered in
38 ms — and located 85% of the turn inside a single call that never logged, i.e. one that failed.

### AUD-X-09 — The rerank output cap truncates every real rerank, and the failure is invisible (P1, fixed in S43)

`retrieve()` asked for 30 candidate scores keyed by `chunk_id` under a fixed
`max_output_tokens=1024`. A `chunk_id` is a 36-character UUID; echoing 30 of them back costs most of
that budget on its own. Measured against real Bedrock with the production call shape (Haiku 4.5,
`converse` + forced tool call, the real 30-chunk corpus payload):

| candidates | maxTokens | stopReason | output tokens | elapsed | validates |
|---|---|---|---|---|---|
| 30, `chunk_id` UUIDs | **1024 (production)** | **`max_tokens`** | 1024 | 11.6 s | **no — ValidationError** |
| 30, `chunk_id` UUIDs | 2048 | `tool_use` | 1361 | 15.7 s | yes, 30/30 |
| 30, `chunk_id` UUIDs | 4096 | `tool_use` | 1464 | 14.8 s | yes, but **28/30** |
| 30, **`candidate_index`** | 2048 | `tool_use` | 613 | **3.2 s** | yes, 30/30 |

**Mechanism, end to end.** `converse` still returns a `toolUse` block when it runs out of output
budget mid-emission; its `input` is a truncated fragment that happens to be valid JSON of the wrong
shape, and **only `stopReason` distinguishes the two** — which nothing read. So: fragment → Pydantic
fails → the gateway spends a **full repair call** under the same ceiling → truncates identically →
`StructuredOutputError` → `retrieval.py` swallows it into the RRF-order fallback. Two ~11 s calls
account for the 20.93 s span.

**Three consequences, in order of how much they matter.**
1. **Retrieval quality**: the fallback returns `candidates[:top_k]` *unfiltered*, so the §5.21.7
   `score > 0` cut — the thing that makes reranking a filter and not just a sort (D-052) — had not
   run on staging since the corpus became real (D-112). This is almost certainly D-112's carry-over
   (ii), the "Who is on the leadership team?" 1-in-3 no-source flake: with no filter, the margin
   between a real chunk and the closest-available noise row is whatever the hybrid search happened
   to return.
2. **Cost**: ~10,957 input + 1,024 output tokens **twice** per grounded turn ≈ **3.2 cents burned
   per turn** for a discarded result — more than the answer call itself (0.42 c). A cost bug by
   CLAUDE.md's own rule 7, running unnoticed for a week.
3. **Latency**: ~21 s of the 24.6 s turn, which is what made criterion 7 unmeetable.

**Fix.** Score by `candidate_index` (the model never handles an identifier at all; the caller maps
positions back deterministically) and derive the cap from the candidate count instead of fixing it.
**Verified through the real `retrieve()` path against real Bedrock: 3.84 s, the rerank succeeds, and
4 of 30 candidates survive the filter** — the filter demonstrably doing work again.

**Why nothing caught it, which is the more useful half.** `MockBedrockProvider` echoes whatever key
the request used and never truncates, so the mock-backed suite could not see it. The opt-in
real-Bedrock eval (`test_qa_coverage_eval_real_bedrock.py`) *did* run against real Bedrock — and
still passed, because a degraded rerank still produces plausible grounded answers. The suite stayed
green at 565 tests through the entire outage. `packages/knowledge/tests/test_retrieval.py` now pins
the three things that would have caught it: the output-token budget against the measured need, the
index round-trip, and the fact that a degraded rerank logs.

### AUD-X-10 — A schema-validation failure trips the shared circuit breaker, failing every task closed (P2, fixed in S43)

This is D-113's "nine turns of 114 returned 200 in 30–84 ms with zero Bedrock calls", which D-113
attributed to new tasks entering the target group. **That attribution was wrong.** The nine turns
land at 04:23:30 (×2), 04:23:59 (×2), 04:24:26–27 (×5) — **~30 s apart, which is
`circuit_cooldown_s`**, not a scaling event. X-Ray names the cause without inference:

```
intellichoice_shared.bedrock.CircuitOpenError: "Bedrock circuit breaker is open"
  gateway.py:90 _circuit_check  →  langgraph.refuse        (span: 1 ms)
```

**Mechanism.** Each AUD-X-09 failure called `_record_failure()`. Sequentially that is harmless — the
next turn's successful `scope_and_intent` resets the counter — but under concurrency five reranks
fail before any success interleaves, the counter reaches the threshold of 5, and the breaker opens
for 30 s **for every task**. `scope_guard` then fails closed to `out_of_scope` → `refuse`, so the
student gets a polite refusal in 30 ms with no Bedrock call and no log line. Fail-closed behaved
exactly as designed; it was fed a false signal.

**Fix.** Only provider-health failures (timeout, `ProviderCallError`) trip the breaker. A response
that arrives promptly and fails our schema is evidence that Bedrock is *healthy* and our request is
wrong — the opposite of what the breaker exists to detect. A deliberate control test asserts
provider outages still open it, so the narrowing cannot quietly remove the protection.

### AUD-X-11 — The gateway logs successes only, so a call failing 100% of the time is invisible (P2, fixed in S43)

`gateway.py` had exactly two `logger` calls, both after a successful call. Every failure exit —
timeout after retries, `ProviderCallError`, invalid-after-repair, truncation, circuit open, budget
exceeded — returned or raised in silence, and `retrieval.py`'s fallback logged nothing either.

**This is why AUD-X-09 survived a week.** The only visible symptom was a gap between two *unrelated*
log lines, which reads as "something is slow" rather than "this call is failing on every request".
D-113 correctly measured the gap and correctly declined to guess at it; there was nothing in the
logs to guess *from*.

**Fix.** `bedrock_call_failed` at WARNING on every failure exit, carrying `reason` (one of
`circuit_open`, `budget_exceeded`, `provider_unavailable`, `schema_invalid`, `output_truncated`),
`duration_ms`, `attempts` and `consecutive_failures`; `duration_ms` added to both success lines so a
slow call is attributable from one line instead of a timestamp diff; and
`retrieval_rerank_degraded` at the fallback itself. Truncation additionally short-circuits the
repair retry — a repair under the same ceiling truncates identically, so it only ever doubled the
cost and latency of a certain failure.

### AUD-X-12 — `rag_answer`'s fixed cap turns ~1 grounded turn in 30 into a false "no approved source" refusal (P1, fixed in S43)

**Found by AUD-X-11's own fix, minutes after it reached staging.** The first load run against
the new instrumentation produced two `bedrock_call_failed` lines, both `rag_answer`:

```
rag_answer  output_truncated  dur=9076ms   attempts=1  max_out=1536
  "model hit max_output_tokens=1536 before completing the RagAnswerResponse response"
rag_answer  schema_invalid    dur=13191ms  attempts=1  max_out=1536
```

**The distribution says it was never marginal.** Over 70 real grounded turns at `top_k=8`,
`rag_answer` output tokens measured **p50 662, p95 1490, max 1530 — against a cap of 1536**,
with 8 of 70 within 10% of the ceiling. The cap was set where real answers actually end.

**Why this is a correctness finding and not a performance one.** `qa.answer_question` catches
`BedrockGatewayError` and returns `NO_SOURCE_MESSAGE` — *"I don't have an approved source for
that yet"* — which is the correct fail-closed behaviour for an ungrounded question and the
*wrong* answer for a truncated response, and from inside that function **the two are
indistinguishable**. So the product told students there was no approved source for questions
that had one, at roughly one turn in thirty. It is a strong candidate for D-112's unexplained
"Who is on the leadership team?" 1-in-3 no-source flake, which was filed as
rerank/confidence-threshold territory.

**A second, quieter path to the same refusal.** `LlmCitation.chunk_id` required the model to
echo a 36-character UUID per citation. `_verify_citations` looks the citation up in
`chunks_by_id` and **drops anything it cannot match** — correctly, since an unmatched citation
is unverifiable — so a single garbled character in a UUID also produced a refusal, with no
diagnostic anywhere. Index-keying removes the failure mode rather than mitigating it.

**Fix.** `max_output_tokens_for(n) = 768 + 192n` (2304 at `top_k=8`, ~50% above the measured
maximum), `context_index` in place of `chunk_id` on both `RagContextChunk` and `LlmCitation`,
and `rag_answer_unavailable` at WARNING where the fallback happens.

**Unlike AUD-X-09, this shape *was* covered by tests** — `test_qa_service.py` stopped
typechecking the moment the schema changed, and its citation-verification tests are what make
the reshape safe. The gap was never "nobody tested citations"; it was that nothing tested the
*token budget*, because a budget is only wrong against real model output.

**Two more instances of this shape are deliberately not chased**, and are recorded as
carry-over rather than fixed blind: `learning_api.services.report` and
`intellichoice_memory.consolidation` both use fixed caps over inputs whose size grows with a
student's history. There is no measurement for either yet — and thanks to AUD-X-11, both would
now log `output_truncated` the first time they hit it, which is the honest place to start.

**Follow-up, same session: AUD-X-12's first fix regressed the low-passage end.** The derived
cap shipped as `768 + 192n`, measured at `top_k=8` and reasoned by analogy with the reranker's
per-candidate response. An answer's length is not per-passage, so single-passage turns got a
**960-token ceiling, below the flat 1536 being replaced**, and the next clean load run
truncated 3 of 74 turns, all `context_chunk_count=1`. Corrected to `2048 + 96n` (a fixed prose
floor plus a small per-citation allowance) with a test asserting **every** passage count from
1 to 30 clears the old flat cap — watched failing against the cap then live on staging. See
D-115 §10; the transferable rule is that a derived value replacing a constant must not be
smaller than that constant anywhere in its domain.

### AUD-X-13 — The chat p95-latency alarm fires on healthy traffic, and the canary bake rolls back deploys when it does (P2, filed in S43; ✅ fixed and live-verified in the S43 continuation, D-116 — heading status corrected 2026-08-04, D-174)

Surfaced by D-115's re-baseline rather than by a failure. `intellichoice-staging-chat-api-p95-latency`
alarms on `TargetResponseTime` **p95 > 3 s for 3×60 s**, and notifies
`intellichoice-staging-alerts`. That threshold is the same mock-calibrated 3 s discussed in the
gate's criterion 7 — and a *healthy* grounded chat turn now measures **p50 ~10 s / p95 ~16 s**
against the real corpus, because it is four sequential model calls. So the alarm's steady state
during normal use is ALARM.

**Three consequences, in increasing order of cost.** It is alarm fatigue on a monitored inbox,
which trains the recipient to ignore it. It is criterion 8's evidence alarm, so what that
criterion currently evidences is an alarm that cannot distinguish an incident from a
conversation. And **`deploy-staging.yml`'s canary bake rolls both services back if any of the
four alarms is in ALARM** (D-095's sequencing fact (i)) — so a deploy attempted while anyone is
using chat would auto-roll-back a perfectly good release, and the rollback would look like a
failed deploy rather than a mis-set threshold.

**Mitigating detail:** `treat_missing_data = notBreaching`, so with no traffic the alarm returns
to OK on its own; the exposure is "a deploy that overlaps real usage", not a permanently red
staging.

**Not fixed here, because the number is the same decision as criterion 7's** and should be set
once, from the same measured budget, rather than twice by two people guessing. Recommendation:
move this alarm to the same **20 s** proposed for criterion 7's live-staging threshold, keeping
the separate scale-out alarm at 3 s where a low trigger is *correct* (D-113 §2 chose it
deliberately: scaling should react long before a human should). That split — a sensitive scaling
signal and an insensitive paging signal on the same metric — is the point, and it is why the two
alarms were separated in the first place.

**Fixed and live-verified in the S43 continuation (D-116).** The threshold is now per-service:
`latency_p95_alarm_thresholds` in `terraform/modules/observability`, chat-api at 20 s,
learning-api left at the module default of 3 s (nothing has re-measured it and its requests are
not model calls). The scale-out alarm in `modules/ecs-service` is untouched at 3 s, deliberately.
Applied 2026-07-29 15:27 CDT: **0 add, 2 change, 0 destroy** (chat-api threshold + both
descriptions).

**The before/after is unusually clean, and the "before" was not something the finding had —
it was reasoned from the threshold, not observed.** The alarm's own history shows it flapping on
real traffic that morning, three times in 100 minutes with nothing wrong:

| | |
|---|---|
| 10:57 → ALARM, 11:05 → OK | 11:51 → ALARM, 12:05 → OK |
| 12:25 → ALARM, 12:36 → OK | (all pre-apply, threshold 3 s) |

After the apply, a 70-turn load run at concurrency 5 produced **four consecutive minutes of ALB
p95 at 14.59 / 15.16 / 16.58 / 17.84 s** — every one of them above the old 3 s threshold, and the
alarm needs only three — and **the alarm never left OK** (last state change 12:36, nearly three
hours earlier). So healthy conversation no longer pages, and a deploy overlapping that load would
no longer auto-roll-back.

### AUD-X-14 — `memory_consolidation`'s output cap is flat over a response that is one item per existing fact (P2, found and fixed in S43-continuation, D-116)

D-115's carry-over (ii), confirmed by measurement rather than by analogy. `consolidation.py`
passed a fixed `max_output_tokens=1200`, but `MemoryUpdateResponse`'s two largest lists —
`facts_to_update` and `facts_to_expire` — are one item per fact the model was shown, and
`list_facts_for_student` is unbounded. This is the same shape as the reranker (AUD-X-09), which
sat truncating against real Bedrock for a week, and explicitly *not* the shape of a RAG answer,
whose length follows the question (the D-115 §10 distinction).

Measured against the serialized schema, at ~94 tokens per reconfirmed fact and ~10 per expiry:

| live facts | 1 | 5 | 10 | 20 | 40 |
|---|---|---|---|---|---|
| response tokens | 261 | 1249 | 1733 | 2712 | 4659 |

So the flat 1200 was under the real need from roughly **five live facts onward**. Fixed with
`MemoryUpdateResponse.max_output_tokens_for(n) = 1280 + 128n`.

**Two things worth keeping from how this went.** The base is 1280 rather than the 896 the
measurement alone justified, because 896 yields 1024 at one fact — *below* the 1200 it replaced.
That is D-115 §10's regression exactly, and **the new test caught it in this session before it
shipped**, which is the first time that rule has paid for itself. And the fix does not scale
forever: past **21** live facts the derived budget exceeds the gateway's own 4000-token hard
ceiling, so the *payload* would have to be bounded — a behaviour change (which facts get
dropped?) that needs its own decision. Not made here; `consolidation.py` logs
`memory_consolidation_payload_oversized` with the count so the decision arrives with a
distribution attached instead of a guess.

### AUD-X-15 — The parent report's output cap was below what its own prompt asks for (P2, found and fixed in S43-continuation, D-116)

Looked at as part of the same carry-over, and the carry-over's premise was wrong here: a report's
length is a function of the *writing task*, not of how much history went in, so a flat cap is the
right shape. The measurement found a different defect — the flat cap was simply too small.
`report.py` asked for 500 output tokens while its own system prompt asks for "two short
paragraphs" plus a `reasoning` field nothing tells the model to leave empty:

| words/paragraph | 40 | 60 | 80 | 100 | 120 | 150 |
|---|---|---|---|---|---|---|
| response tokens | 305 | 448 | **591** | 733 | 876 | 1091 |

Truncation therefore begins around **70 words per paragraph**, and D-115 measured this same model
emitting ~375 words for a chat answer. **The consequence is not a short report**: the gateway
raises, and `report.py` falls back to deterministic text, so a parent silently receives the
un-personalized version and nothing says why. Raised to 1024.

**The coupling was the useful part.** `REPORT_RESERVATION_ESTIMATE_CENTS` is derived from this
cap, and `test_cost_reservation_estimates.py` — written for AUD-X-08 — failed immediately with
"a report can cost up to 2.1360 cents but only 1.5 is reserved", which is the guard doing exactly
its job on a change it was not written for. Reservation raised to 2.25; the 50-cent daily ceiling
is unchanged and still permits ~70 reports/student/day at the deployed model's rate.

**Neither AUD-X-14 nor AUD-X-15 has been observed failing in production**, because both were
found by measuring the schema rather than by an incident — which is the posture D-115 §5 asked
for after the reranker spent a week dead without a single log line. Both will now log
`output_truncated` if they are hit (AUD-X-11's logging).

### AUD-F-21 — A late stage narrative unmounts the screen the student is already using (P1, found in the S43 continuation, D-116; ✅ fixed 2026-07-29, D-117 — heading status corrected 2026-08-04, D-174)

**Both of criterion 3's two remaining staging failures are this one defect**, and it is not what
either was filed as. The staging suite reproduced exactly its previous shape — **47 passed /
2 failed / 4 skipped**, a third consecutive identical run — and the two failures are
`time-telemetry.spec.ts` and `journey-student.spec.ts`.

**First, what it is not.** The standing hypothesis was a stale served bundle, because the dwell
failure carries AUD-F-01's signature while AUD-F-01's fix is in `main`. That is now disproved by
measurement, and the disproof is unusually strong: rebuilding `apps/learning-web` locally at HEAD
with the deploy's own `VITE_LEARNING_API_URL=""` emits `index-be8gjEfS.js` — the **same
content-hashed filename** CloudFront serves — and the served file is **byte-identical**
(SHA-256 `63eca681…7dd1055`). The APIs are `gha-12508257ac10` on both services. Staging is running
exactly what `main` builds.

**And AUD-F-01's fix demonstrably works on staging.** Its two counting assertions both pass:
**1** time report during the 15-second dwell (was 899) and **0** overview fetches in the window
(was 903). What fails is the *value* — a single flush of **2116 ms** against a 15,000 ms dwell —
which is why keeping both halves of that assertion mattered (D-103 §2).

**The mechanism, from the request timeline.** `App.tsx:199` renders `StageTransitionScreen`
**instead of** `ExamScreen` — a sibling branch, so a narrative arriving mid-phase *unmounts* the
exam screen rather than overlaying it, firing the view-time cleanup:

| t | event |
|---|---|
| 1259 ms | `GET /exam/overview` returns → `assessment_item_id` defined → view-time effect runs, `viewStartRef = ~1315 ms` |
| 3370 ms | SSE `/stream` finally connects (locally: near-instant) |
| 3431 ms | first snapshot lands carrying `stage_narrative` → `ExamScreen` unmounts → **flush of 2116 ms** = 3431 − 1315 ✓ |
| +13 s | the narrative holds the screen; no further dwell is ever measured |

The same branch explains the other failure exactly: after `POST /exam/finalize`, the outro
narrative replaces `ExamScreen`, and `StageTransitionScreen` has no `.phase-chip`, so the
journey's 60-second wait for the next phase resolves `null` and times out. `narrative-refresh`
(a `test.fail()` expected failure, so it does not appear in the count) corroborates from the other
side, noting **"narratives dismissed before the exam: 0"** — the narrative had not arrived yet
when the test looked for it.

**Why it is staging-only:** the narrative is an LLM call. `MockBedrockProvider` returns in ~26 ms,
so locally the narrative is in the first snapshot before `ExamScreen` ever renders. On real Bedrock
it lands seconds *after* the student is already working. This is the same "the mock cannot see this
defect class" lesson as AUD-C-02 and AUD-F-19, on a third surface.

**Real-user impact, not just harness impact — which is why P1 and not P2:**
1. `time_spent_minutes` for the first item is truncated to however long the narrative took to
   arrive. This is **upstream of AUD-L-14** (S36's `time_spent_minutes: 0.0` next to
   `attempts_count: 26`) and feeds wrong numbers into parent reports.
2. The screen is yanked away mid-question. `ExamScreen` remounts fresh afterwards, so
   `useState(0)` re-initialises and the student is returned to **Question 1** with `cachedBatch`
   and `answeredSelections` gone — which is precisely what the refresh probe recorded
   ("before refresh: Question 3 of 10 / after refresh: Question 1 of 10").

**Not fixed here, deliberately.** The fix is a product decision, not a mechanical one: *should a
narrative that arrives after the student has started working interpose at all?* The likely right
shape is to render it as a dismissible overlay above the phase screen rather than as a sibling
branch that replaces it, and to suppress a stage-intro narrative once interaction has begun — but
that is visible behaviour on the primary journey and deserves its own decision and its own
before/after, the same posture D-115 §11 took with answer brevity. **Criterion 3 is blocked on
this one fix**, and it is now a single well-located change rather than two vague observations.

**✅ Fixed 2026-07-29 (D-117), on the shape above, with the product call taken.** The narrative
renders in the same `.stack` shape `AssistancePanel` already used, above the phase screen instead
of in place of it, and a narrative arriving after the student has interacted *in the current phase*
is dropped rather than interposed. Interaction is tracked as the phase name (`interactedPhase`)
rather than a boolean, so it self-clears at every phase boundary — `nodes.py` writes `phase` and
`stage_narrative` in the *same* state update, so a boolean plus a reset effect would race the
narrative it exists to gate, and the pre/post-exam outros would have been dropped by accident.

**Verified against the mock, which previously could not see this class at all.**
`tests/learning/narrative-displacement.spec.ts` holds back the SSE connect (`route.continue()`
after a delay) so `pre_intro` fires *after* the exam screen is up, reproducing real Bedrock's
timing on `MockBedrockProvider`. Three arms — the mid-exam arrival, the post-interaction drop, and
the co-existence contract in the other ordering — each asserted non-vacuously (the narrative's
arrival is asserted before anything about it is). **All three were watched failing against the
pre-fix `App.tsx`**, with the messages they were written for: exam screen unmounted, narrative
interposed after answering, topic list absent beneath the narrative. Local suite 54 passed /
2 skipped with the fix, no regression in the other 47 specs; the dwell now reports the full
15,000 ms where the pre-fix run reported a truncated flush.

**Staging re-verification is still outstanding** — the fix is not on staging at the time of
writing, so criterion 3's two clean runs have not been taken.

### AUD-F-22 — A parent cannot reach their child's progress dashboard without finishing a whole cycle (P2, found in the S43 continuation, D-117; ✅ fixed 2026-08-04, D-176)

Found by de-conditionalizing a `test.skip()`, which is the only reason it is written down: the
skip's own message was *"no dashboard entry point from the current screen"* — an accurate
description of a defect, recorded as a reason not to look at it, on every run from S39 through S43.

**The mechanism is two facts that only bite together.** `View progress dashboard` is rendered by
exactly two screens:

- `StartScreen`, and only `{studentId && …}` — for a parent, `App.tsx`'s `dashboardStudentId` is
  `session.studentId`, which is `null` until a child is resolved, and a child is only resolved *by
  starting a session*. So the button is never on the start screen a parent actually sees.
- `ResultsScreen`, at the end of a completed pre → study → post cycle.

And backing out does not help: `useLearningSession.endSession()` clears `STUDENT_ID_KEY` and calls
`setStudentId(null)`, so returning to the start screen returns to the state with no button.

**Net effect:** a parent's only route to their child's progress dashboard — the surface SPEC §5.13's
parent-facing reporting lives on — is to sit through an entire learning session as if they were the
student. Measured: `dashboard button reachable mid-session: false`, after resolving a child.

**Severity P2, not P1.** Nothing is wrong, lost, or exposed; a feature that exists is unreachable
by its intended user on the natural path. It is also the practical consequence of the long-standing
S11 carry-over (parent auto-select does not set `student_external_id` client-side) rather than a
new regression.

**Not fixed here.** The fix is a UX decision about where a persistent entry point belongs (app
header? a dashboard link on the phase screens? resolving the parent's child before the session
starts, which is the S11 item itself) — visible behaviour on the parent journey, and this session
already spent its one product call on AUD-F-21. The probe is now `test.fail()` rather than a
conditional skip, on AUD-F-04/AUD-F-05's pattern: it keeps measuring, and it fails the run the day
the gap closes, which is the signal to promote it to a regression test.

**Closed 2026-08-04 (D-176), per the user's UX call: the child resolves at login.** One linked
child resolves silently; several show the *existing* `ChildSelectionScreen` once, before the start
screen — no new UI, exactly as D-175 §5 recorded. Mechanics: new parent-only
`GET /learning/parents/me/children` (id from the verified token, live MySQL lookup per D-020,
every other role 403s), the resolved child is **login-scoped** (`endSession` no longer clears it —
that clearing is what made "backing out does not help" — logout does, via `forgetStudent`), and
session start passes the child explicitly so the in-session interrupt is the server-side fallback
and the resume re-check, with the link still verified server-side either way. Also closes the S11
carry-over. **The probe was promoted by rewriting, not by flipping:** its journey assumed a
mid-session button, which no faithful reading of the recorded decision produces; the promoted
regression test asserts the stronger property — login → pick child → dashboard → report with
**zero** learning sessions. Known deliberate limitation: switching children means signing out and
back in (a persistent switcher is new UI, which the decision excluded).

### AUD-F-23 — A conditional skip made an untested journey look tested for four sessions (P3, found and fixed in the S43 continuation, D-117)

`journey-chat.spec.ts`'s *"the welcome card's suggested prompt works as a one-click turn"* skipped
on every run from S39 to S43 with `no suggestion chips rendered for a guest`, and the reason was in
the test, not the product: `chips.count()` was taken **immediately after `page.goto`**, while
`App.tsx` fetches `/chat/meta` in an effect. The count read an empty DOM and the test skipped
itself, every time.

The data was there all along — `chat_suggestions` holds **7 active `public` rows**, and
`suggestions_for_role` returns the first four to a guest (`role_access.resolve_role_context` maps an
anonymous caller to `public`). Fixed by waiting for the chip rather than counting immediately, and
by making its absence a **failure** instead of a skip. The test now runs and passes, so the
one-click-turn path has been exercised for the first time.

**Why this is worth an ID rather than a quiet fix.** It is the same class as AUD-F-16 and AUD-F-17
— the harness reporting on something it had not measured — and it is the third instance. A skip
whose condition is never false is indistinguishable, in a run summary, from a test that is passing;
`2 skipped` looked like a known allowance rather than two journeys nobody had ever driven. The
matching pattern to watch for: a skip message that *describes a defect* is a finding, not a
condition.

### AUD-F-24 — A conditional wrapper remounts the screen below it, so AUD-F-21's first fix truncated the dwell anyway (P1, found and fixed in the S43 continuation, D-118)

**AUD-F-21's fix was deployed to staging and the failure it was supposed to close did not close.**
`time-telemetry.spec.ts` still reported a truncated dwell — **1578 ms against a 15,000 ms dwell**,
where the pre-fix number was 2116 ms. Same defect, different number.

**The mechanism, and it is a React reconciliation rule rather than anything about narratives.**
The first fix rendered the narrative *above* the phase screen, in a wrapper:

```tsx
if (!showNarrative) return phaseContent;
return <div className="stack">{narrative}{phaseContent}</div>;   // WRONG
```

React reconciles children by position. Without a narrative, `ExamScreen` is `main`'s child; with
one, it is `main > div.stack`'s child. That is a **different position in the tree**, so React
unmounts and remounts it — which is precisely what AUD-F-21 was: the view-time cleanup fires early
and `useState(0)` re-initialises. **A conditional wrapper is a remount.** Moving the narrative from
a sibling *branch* to a conditional *parent* changed which line caused the unmount, not whether one
happened.

**Fixed with a Fragment carrying two fixed slots**, always returned, so slot 1 holds the phase
content at the same index whether or not a narrative is showing:

```tsx
return <>{showNarrative ? <StageTransitionScreen … /> : null}{phaseContent}</>;
```

A Fragment rather than an always-present `div` for a second reason found while fixing it:
`.stack` carries `max-width: 480px`, so the first fix had also been quietly **narrowing the exam
screen for the duration of every narrative**. A Fragment adds no DOM node, so the no-narrative
render is identical to what shipped before any of this. The 16 px gap the wrapper used to provide
moved to `.app-main`, which already centres a flex column and has one child on every other screen.

**Why the local suite passed the broken fix — a blind spot in the regression test, not bad luck.**
`narrative-displacement.spec.ts` arm 1 compared the question position across the narrative's
arrival, but it did so **while sitting on Question 1**. A remount resets to Question 1, so the
assertion compared 1 to 1 and passed straight through the defect. The arm now clicks the question
navigator to move off Question 1 first, and asserts it succeeded — and it was verified to fail
against **both** the original sibling-branch code *and* the conditional-wrapper fix, with the
message it exists for ("the exam screen remounted, so useState(0) re-initialised…"). Two failure
modes, one test, both watched.

**The lesson worth more than the fix:** a test that asserts state is preserved has to first put
that state somewhere a reset would be visible. Asserting a default value is unchanged proves
nothing, and it is invisible in a green run.

**And keeping the screen mounted exposed a latent 409, which the fix has to carry too.** With the
remount gone, `post-finalize-poll.spec.ts` began reporting **exactly one 409 at +2004 ms** — a
`POST .../exam/items/<pre-exam item>/time` against a finalized exam. Mechanism: `overview` is the
*exam's* item list and `App` keeps holding it after the phase moves to study, so
`currentOverviewItem` kept resolving a pre-exam item; meanwhile the phase-change effect had just
cleared `finalizedRef`, so the next dependency change flushed for an item whose exam was closed. The
unmount used to hide it by destroying the component before a second commit could fire. Fixed by
gating the lookup on `isExamPhase`, which is what the data means anyway — view time is recorded
against `assessment_item_id`, and only pre/post-exam items have one. Watched failing without the
gate (`1 requests the server rejected with 409`) and passing with it.

**Still present, deliberately: the same class one branch over.** `renderPhase` wraps the exam view
in `.stack` *conditionally* when an intervention arrives (`snapshot.intervention &&
!interventionDismissed`), so a hint arriving mid-question remounts `ExamScreen` for exactly the same
reason. That is pre-existing, it is the AUD-F-03/hint-displacement family, and unlike the narrative
case the `.stack` styling there is load-bearing for the panel's own layout — so it needs a layout
decision rather than a mechanical change. Not touched here; recorded so the next person does not
have to rediscover the mechanism.

### AUD-F-25 — chat's suggestion chips have never been seeded on staging, and the seeder cannot run there (P2, found in the S43 continuation, D-118; ✅ fixed 2026-07-29, D-119 §3 — heading status corrected 2026-08-04, D-174)

Uncovered by AUD-F-23's fix: making the skipped chips test *fail* on absence turned a silent skip
into a real result, and the real result is that staging has no suggestions at all.

```
GET https://<chat cf domain>/chat/meta
{"welcome_text":"Founded in 1993 …","suggested_prompts":[]}
```

The welcome text is there (it is RAG-derived); `suggested_prompts` is empty. SPEC §18-C3's welcome
card therefore renders with no chips for every caller on staging, and the one-click-turn path is
dead.

**Two causes stacked.** First, `deploy-staging.yml` re-seeds MySQL fixtures (AUD-F-20's fix) and
re-embeds the RAG corpus (AUD-C-16's fix) but **never runs `chat_api.services.suggestions_seed_cli`**
— the `make chat-suggestions-load` equivalent. Second, and the reason this is not a one-line
workflow addition: **it cannot be run from the ops task at all.** Probed directly —

```
python -c "import chat_api.services.suggestions_seed"
→ ModuleNotFoundError: No module named 'chat_api'   (exit 1)
```

The ops task reuses the learning-api image on the stated grounds that it "already has every
workspace package installed". Its *builder* stage does `COPY apps/chat-api/`, so `uv sync` installs
chat-api — but the *runtime* stage copies only `apps/learning-api`, leaving a **dangling editable
install**: the venv metadata says `chat_api` is installed and the source is not there.

**Three fix shapes, and it is a packaging decision rather than a mechanical one:**
1. Copy `apps/chat-api/` into the learning-api image's runtime stage (one line) — smallest, and
   arguably just repairs the image's own stated intent, but couples the two apps' images and grows
   the learning-api image for the sake of an ops path.
2. A second ops-task definition on the chat-api image (Terraform) — clean separation, more moving
   parts, and a second task definition to keep in step.
3. Move the seed catalogue and seeder into a shared package — best long-term shape, largest change,
   touches an app boundary.

**Not fixed here**, and criterion 3 is deliberately left failing on it rather than the chips test
being scoped back to `local`: a launch-journey feature is genuinely broken on staging, and a gate
criterion that goes green while that is true is the exact failure mode AUD-F-23 was about.

### AUD-F-26 — The initial SSE snapshot serves state captured before a seconds-long Bedrock call, pushing the client backwards (P1, found and fixed in the S43 continuation, D-118)

**This is the actual cause of both criterion-3 learning failures.** AUD-F-21 and AUD-F-24 were real
defects and their fixes stand, but neither was what `time-telemetry` and `journey-student` were
failing on — a distinction only the third measurement made, and one worth stating plainly rather
than leaving the record implying a solved problem.

**The evidence is one request timeline, read from `journeys.jsonl`'s own millisecond stamps:**

| t | event |
|---|---|
| 434 ms | `POST /learning/sessions` → the client has a session id and opens `EventSource` |
| 994 ms | `POST /topics` → **phase becomes `pre_exam`**, exam screen renders |
| 1085 ms | `GET /exam/overview` → `assessment_item_id` defined, view-time effect arms (`viewStart ≈ 1183`) |
| 2736 ms | the `/stream` response finally arrives — carrying **`phase: student_selected`** |
| 2836 ms | `POST .../time` with `elapsed_ms` **1653** = 2836 − 1183 |

And the page at failure, from the same artifact: the narrative panel rendering correctly above —
AUD-F-21's fix working — and **"Choose a topic"** underneath it. The student was sent back to topic
selection.

**The mechanism.** `_initial_snapshot` reads the checkpoint, then calls `_maybe_fire_pre_intro`,
then builds its response **from the state it read before that call**:

```python
snapshot = await graph.aget_state(...)     # phase == "student_selected"
state = snapshot.values
...
if narrative_text is None:
    narrative_text, … = await _maybe_fire_pre_intro(…)   # real Bedrock, ~2.3s measured
return SessionSnapshotEvent(phase=state.get("phase", "created"), …)   # STALE
```

The browser opens `EventSource` the moment it has a session id, so it routinely starts a topic — and
therefore the pre-exam — while the connect is still inside that call. The stale snapshot then
overwrites newer client state.

**Why every previously observed symptom follows from this one bug:**
- The exam screen is replaced by `TopicSelectScreen` (phase went backwards), so its view-time
  cleanup fires and flushes a **truncated dwell** — 2116 ms, then 1578 ms, then 1653 ms across three
  runs, all of them just "however long since the overview landed". The number moved when unrelated
  latencies moved, which is why it looked like progress twice and was not.
- No further `GET /exam/overview` in the window (the poll effect returns early outside an exam
  phase), and **no question navigator**, which is why `time-telemetry`'s trailing
  `if (nav.count() > 1)` click never fired and only one time report was ever recorded.
- `journey-student` answers all 10 items, finalizes, and then waits 60 s for `study|post-exam` —
  and a stale snapshot can put it back on a screen with no matching phase chip.

**Staging-only for the fourth time in this family** (after AUD-C-02, AUD-F-19, AUD-F-21):
`MockBedrockProvider` returns in ~26 ms, so locally the window is too small to lose a race in.

**Fixed** by re-reading the checkpoint after the narrative call and rebuilding everything derived
from state — including `pending`, since an interrupt can be raised or resolved inside the same
window, and including a re-authorization when `student_external_id` resolved during it (SPEC
§5.30.2 wants the check against the state actually served). A narrative found in the refreshed
checkpoint wins over the `pre_intro` fallback, preserving S26's existing precedence.

**Regression test** fakes the seam rather than racing a real model call, because the defect is an
*ordering* one and its test should be deterministic: `aget_state` returns `student_selected` first
and `pre_exam` afterwards — exactly what the real checkpoint does when the client advances mid-call
— and the test asserts both that the second read happened and that the served phase is the later
one. Watched failing against the pre-fix code (`assert ['student_selected'] == [… 'pre_exam']`).

**Correction to the AUD-F-21 record.** AUD-F-21's diagnosis attributed the truncated dwell to the
narrative unmounting the exam screen. The narrative *did* replace the screen and that was worth
fixing, but the flush the tests measured came from the phase going backwards. Two fixes were shipped
on a diagnosis that fit the symptom and was not the cause — the honest reading is that the timeline
in `journeys.jsonl` contained the answer from the first staging run onward, and it was not read
until the third.

### AUD-F-27 — The client silently drops any mutation attempted while another is in flight, and tells the student it succeeded (P1, found in the S43 continuation, D-120; ✅ fixed 2026-07-29, D-120 — heading status corrected 2026-08-04, D-174; not fixed)

**Criterion 3's last two failures are this, and it is silent data loss on the primary journey.**

`useLearningSession`'s `run()` wrapper gates every mutation on a single flag:

```ts
const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | null> => {
  if (busyRef.current) return null;   // no request, no error, no retry
  ...
```

`submitAnswer`, `finalizeExam`, `skipExamItem`, `chooseTopic` — all of them. A second call while
the first is in flight returns `null` and **does nothing at all**. Nothing surfaces: `setError` is
not called, and `ExamScreen`'s `handleSubmit` has already advanced `currentDisplayOrder` and set
`Answer submitted for question N` before any of this is known.

**Measured on staging, from one run's own artifacts:**

| spec | answers the test submitted | `POST /answers` actually sent | `POST /exam/finalize` sent |
|---|---|---|---|
| `journey-student` | 10 | **2** | **0** |
| `hint-displacement` | 10 | **1** | **0** |

The page snapshot is unambiguous: the question navigator shows questions **1 and 9** as
"answered, locked" and the rest "not yet answered", the status line reads *"Answer submitted for
question 10"*, and the finalize modal is open with *"8 questions still need an answer"* — its
Submit button `[active]`, i.e. clicked. `handleFinalizeConfirm` ran, `onFinalize` returned falsy
because `run()` dropped it, so `setModalOpen(false)` never fired and the modal stayed for the full
30 s. **Zero console errors, zero failed requests, zero 4xx/5xx** — from the browser's point of view
nothing went wrong.

**Real-user impact, which is why P1 rather than a harness complaint:**
1. **A submitted answer can be lost with positive confirmation shown.** The student sees the
   advance and the status message; the answer never reaches the server and the item stays
   unanswered, so it is marked incorrect at finalize. That corrupts the pre-exam score, and
   therefore `learning_gain`, and therefore the parent report.
2. **"Submit exam" immediately after answering the last question is a normal human action
   sequence**, and on staging a `POST /answers` takes ~200-400 ms — so the finalize lands inside
   the window, is dropped, and the modal simply does nothing when confirmed. The student is stuck
   on a dialog whose button appears dead.

**The intended design exists and was never wired up.** `ExamScreen` already accepts a `busy` prop
and `App.tsx` passes **`busy={false}`** at every call site, while the hook keeps its flag in a
`useRef` — non-reactive by construction, so it cannot drive the UI. Whatever the original intent,
the guard currently protects the hook's internal state at the cost of the student's work.

**Why it never showed before this session:** `MockBedrockProvider` and a local Postgres answer in
~1 ms, so the in-flight window is too small for the next click to land inside it. This is the
**fifth** finding in the "only staging can see it" family (AUD-C-02, AUD-F-19, AUD-F-21, AUD-F-26,
AUD-F-27) and the third that is a *race* the mock is too fast to lose.

**✅ Fixed 2026-07-29 (D-120, user decision): wire the prop that already existed, and stop being
silent.** `busy` is now state as well as a ref — the ref for `run()`'s synchronous guard (state is a
render behind, so two clicks in one tick would both pass it), the state for the UI — wired to all six
`App.tsx` call sites, and a refused call sets a real error instead of returning `null` quietly.
`ExamScreen` needed no change at all: it already disabled every control on `busy` and switched its
label to "Submitting…".

**Deliberately not a queue.** An answer arriving after a finalize has nowhere valid to land (AUD-F-02's
409), so serialize-and-refuse is the honest behaviour; the fix is to make the second click impossible,
not to replay it. `recordItemTime` stays outside the guard — fire-and-forget telemetry, and gating it
would re-open AUD-F-01.

**Regression test** (`mutation-serialization.spec.ts`) holds the answer POST open for 1200 ms with
`route.continue()` after a timer, reproducing staging's latency on the mock, and asserts a **count**:
three answers submitted, three `POST /answers` sent. Watched failing with the wiring reverted —
**2 of 3 reached the server** — which is the defect in miniature.

**And it caught a harness bug the fix would otherwise have introduced.** The new "Submitting…" label
made `answerCurrentQuestion`'s exact-name locator miss, and that function returning false means "no
answerable question", which `answerWholeExam` treats as *the end of the exam* — so it would have
answered fewer items than it reported, on staging, silently. The fixture now waits out an in-flight
submission first.

### AUD-F-28 — learning-api cannot serve criterion 7's 150 concurrent sessions: one task, 100% CPU, and the ALB kills it (P1, found in the S43 continuation, D-121; **fixed 2026-07-30, D-122** — the failure mode is gone and capacity is 3× higher; the p95 leg at 150 is now a *documented capacity gap* with a price on it, see the resolution at the end)

**Criterion 7's learning-app leg fails at the criterion's own parameters**, measured for the first
time. §2.6 criterion 7 asks for "P95 ≤ 3 s at 150 concurrent, error rate < 1% … with ≥ 2 tasks and
autoscaling active". At **VUS=150** (`make load-staging-learning`, 150 complete iterations, nothing
interrupted):

| leg | required | measured |
|---|---|---|
| p95 | ≤ 3 s | **36.01 s** |
| error rate | < 1% | **13.16%** (208 / 1580 checks) |
| tasks | ≥ 2, autoscaling active | **stayed at desiredCount 1** |

Per step, which locates it: `select_topic` p95 **48.08 s**, `answer` p95 **29.41 s**,
`select_student` p95 **18.12 s** — and even `dev_token` p95 **7.42 s** and `create_session` p95
**6.99 s**, calls that do almost nothing. Everything slowed together, which is the signature of one
saturated process rather than one slow query.

**The infrastructure side, from CloudWatch over the same window:**
- ALB `TargetResponseTime` p95 by minute: 1.35 → **18.81 → 45.92 → 20.95 → 18.55** s
- `HTTPCode_Target_5XX_Count`: **71**; `TargetConnectionErrorCount`: **137**; `HTTPCode_ELB_5XX`: 0
- ECS `CPUUtilization`: **average 99.88%** at the peak minute (67% / 83% / 64% either side)
- ECS event: **`(port 8001) is unhealthy`** → the task was stopped and replaced *during* the run

So the single task hit 100% CPU, latency went to ~46 s, the ALB health check failed, and ECS killed
the task mid-flight — which is where the connection errors and most of the 5xx came from. A real
cohort of 150 students starting exams at once (a branch's session start, exactly the SPEC §6.23
scenario) would see this.

**A hypothesis worth recording as *disproved*, because it was the obvious one.** learning-api is the
service D-113 deliberately left on **CPU-based** target tracking while moving chat-api to ALB p95
latency, on the grounds that "no measurement says to move it" — so the expected story was AUD-F-14's:
CPU tracking blind to a latency-bound saturation. **It is not that.** CPU was pinned at 100%, so the
tracking metric saw the load perfectly well. What did not happen is a *reaction*: the burst lasted
~3.5 minutes, which is comparable to CPU target tracking's own evaluation window plus metric-publish
lag plus cooldown, so no capacity arrived before the run ended. The distinction matters for the fix —
this is a **sizing and reaction-time** problem, not a wrong-signal problem.

**Not fixed here.** The options are a capacity decision (`min_capacity` > 1 and/or a larger task),
a faster scale-out signal for learning-api (the ALB p95 policy chat-api already has, which reacts in
2 minutes), or accepting a documented lower concurrency target for the pilot — and picking among them
needs the pilot's real expected concurrency, which is a product input rather than a code change.
**Criterion 7's chat leg remains met** (p95 16.68 s < 20 s, 0 errors, 3 tasks — D-116); it is the
learning leg that is open.

**Also measured, and passing, at the concurrency the chat leg used:** at **VUS=5** the same scenario
returns p95 **1.4 s**, **0.00%** errors, 70/70 checks, `select_topic` p95 1.5 s, `answer` p95 1.22 s.
So the flow itself is not slow — the failure is purely a capacity-under-concurrency one, and the two
numbers together bound where it breaks.

---

#### Resolution (2026-07-30, D-122)

**The curve, measured before anything was changed.** Four runs on the unchanged single
256-CPU-unit task, plus D-121's VUS=5:

| VUS | p95 | errors | throughput | ECS CPU (max) |
|---|---|---|---|---|
| 5 | 1.4 s | 0.00% | — | — |
| 10 | 4.36 s | 0.00% | 5.8 req/s | 100% |
| 25 | 9.98 s | 0.00% | 5.6 req/s | 100% |
| 50 | 16.48 s | 9.14% | 6.4 req/s | 100% |
| 100 | 31.48 s | 0.00% | 5.8 req/s | 100% |
| 150 (×2) | 34.98 / 34.91 s | 12.06% / 4.37% | 5.9 req/s | 100% |

**Throughput is flat at ~5.8 req/s from 10 concurrent upward and latency grows exactly linearly**
— Little's law (concurrency = throughput × latency) holds to within 4% at every point. That is a
saturated server with a fixed service rate, which makes the sizing arithmetic honest rather than a
guess: capacity buys latency proportionally, and the p95 ≤ 3 s promise held only to **~8 concurrent
sessions**.

**Applied** (terraform, learning-api only): task `256/512` → **`512/1024`**; `min_capacity` 1 → **2**;
CPU target-tracking replaced by the **ALB p95 step-scaling** policy chat-api has had since D-113; the
app container given an **explicit 384-unit share** (it read `"cpu": 0` beside a sidecar declaring 128
— see `pin_app_container_cpu`); and `unhealthy_threshold` 3 → 5 (**AUD-F-29**, below).

**Measured after, on the 2-task floor:**

| VUS | p95 | errors | note |
|---|---|---|---|
| 10 | 1.02 s | 0.00% | |
| 15 | 1.36 s | 0.00% | |
| 20 | 2.15 s | 0.00% | |
| **25** | **2.45 s / 2.51 s** | 0.00% | measured twice, warm — **the supported concurrency** |
| 30 | 5.71 s | 0.00% | |
| 40 | 12.41 s | 0.00% | |
| 150 | 17.73 s | **0.04%** | 2 → 3 tasks, scale-out inside ~1 minute |

Throughput went 5.8 → ~17.5 req/s, a **3.0×** gain against 3.0× the CPU units (2 tasks × 384 vs
1 × 256) — which also retires the worry that the sidecar's share had been starving the app.

**What the criterion looks like now, at its own 150 concurrent:** error rate **0.04%** (was 12.06%)
✅, **≥ 2 tasks with autoscaling active** ✅ (2 → 3, reacting in about a minute), **zero** target 5xx,
**zero** connection errors, and **no task killed** — where the pre-fix run at the same concurrency
produced 64 5xx/min twice, 127 connection errors, and a task replaced mid-run. **The p95 leg does not
pass: 17.73 s against ≤ 3 s.**

**That gap now has a price rather than a mystery.** At the measured ~25 concurrent per $36/month,
150 at p95 ≤ 3 s needs roughly **6× today's capacity (~12 tasks, ~$216/month)**. The decision
(D-122 §4, user call) is to **document 25 as the pilot target** — ~37 once autoscaling reaches its
3-task ceiling — keep the spend, and carry 150 as a post-pilot obligation. The cheaper lever, if one
is wanted before spending: `select_topic` is the dominant cost (a LangGraph invoke with checkpoint
writes; 1.6 s even at 25 concurrent, and the p95 driver in every single run above).

**A measurement-method note that cost one wrong number.** The *first* run after the task roll read
p95 6.13 s at VUS=25; warm re-runs of the identical scenario read 2.45 s and 2.51 s. The first run
after a deployment is a cold-start measurement, not a capacity measurement — discard it or take it
twice.

### AUD-F-29 — a CPU-saturated learning-api task fails its own readiness check and gets killed, turning a latency problem into an availability one (P2, found 2026-07-30, D-122; fixed same session)

`/readyz` is the ALB's health check and it opens a pooled connection to Postgres *and* MySQL with a
3 s timeout (`intellichoice_shared.db_ready.ping_engine`). A task pinned at 100% CPU cannot schedule
that handler inside the ALB's 5 s check timeout, so it answers **503 while still serving real
requests with 200s**. Three consecutive misses (15 s apart) and ECS replaces the task.

**The measurement that separates this from AUD-F-28**, both on the same unchanged single task:

- **VUS=50** — task killed, `(port 8001) is unhealthy … Health checks failed with these codes: [503]`,
  replaced mid-run → **64 TargetConnectionErrors, 9.14% of the run failed**.
- **VUS=100** — *slower* (p95 31.48 s vs 16.48 s), never killed → **0.00% errors**.

The heavier run was the healthier one. The errors do not come from the saturation; they come from the
**reaction to** the saturation, which is why this is its own finding. With `min_capacity` now 2, a
false kill is worse than it was: it removes half the capacity in the middle of the burst that caused
it.

**Fixed** by raising `unhealthy_threshold` 3 → **5** (~45 s → ~75 s) for learning-api only, via the
new `health_check_unhealthy_threshold` module variable; the default stays 3 for every other service.
**The trade is explicit:** a genuine database outage now takes 75 s rather than 45 s to pull the task
out of service. That is deliberate, because this readiness check cannot currently tell "the database
is gone" from "I am busy" — the *right* fix is to make it able to (distinguish a pool-checkout
timeout from a connection failure, or give the check its own connection), and that is left as a
carry-over rather than done under a capacity change.

**Post-fix evidence:** the 150-concurrent run after the change produced zero connection errors, zero
5xx, and no replacement, at a concurrency 3× higher than the one that killed a task before.

## Criterion 9's authenticated half (2026-07-30, D-129)

Two findings, both from the same 25-VU authenticated load run that produced the criterion-9
evidence. Neither is a correctness defect; both are things a measurement was quietly wrong about.

### AUD-F-30 — 97% of every trace this project has ever scanned is a health check, and X-Ray's free tier stopped covering it (P3, found 2026-07-30, D-129; ✅ fixed 2026-07-31, D-132, on the third attempt)

Measured, not estimated: **2,394 traces in the hour before the load run, and every one of them was
`GET /readyz`** — 5 tasks × ~478 checks each. The 350 authenticated requests the load run generated
were 13% of the corpus the criterion-9 scan then walked; on an idle window it is 100% health checks.

Two consequences, in increasing order of importance:

1. **The cost assumption in the code is now false.**
   [terraform/environments/staging/variables.tf:78-81](../terraform/environments/staging/variables.tf#L78-L81)
   defaults `enable_otel_tracing` to true and justifies it with "X-Ray's free tier covers 100k
   traces/month". At the measured rate that is **~57k traces/day, ~1.7M/month — about 17× the free
   tier**, or ~$8/month at $5 per million recorded. July's bill is genuinely $0 (85,892 traces
   stored, under the tier) but only because tracing has been on for four days *and* the task count
   doubled on 2026-07-30 (learning-api `min_capacity` 1 → 2, chat-api sitting at 3). **The comment
   was true when written and is now an assumption that silently stopped holding** — the same shape as
   D-072's retention assumption (see §5.15 in [TRACEABILITY.md](TRACEABILITY.md)), at a much lower
   stake.
2. **It dilutes the one criterion that depends on the trace corpus.** A scan reporting "2,747 traces
   CLEAN" sounds like broad coverage and is mostly the same three-span health check repeated. This is
   exactly why D-104 §3's coverage control exists and why this session ran one: the claim that
   matters is not the total, it is that the **350 authenticated traces were in the scanned set**.

**✅ FIXED (2026-07-31, D-132) — on the third attempt, and the first two were measured wrong in
opposite ways. The "~97%" in the fix direction below was not merely imprecise; the first attempt got
the sign wrong.**

| attempt | change | idle traces / 10 min |
|---|---|---|
| baseline | — | **320**, 100% `GET /readyz` |
| 1 | `excluded_urls` on `FastAPIInstrumentor` | **1,095** ⬆ **3.4× worse**, 100% no-URL orphans |
| 2 | + `suppress_instrumentation` inside `ping_engine` | **160**, still all orphans |
| 3 | + suppression around each `/readyz` **handler body** | **0** ✅ |

**And zero is only meaningful with the coverage control**, because "no traces at all" is exactly how
AUD-F-12 certified an empty store as PII-clean. Immediately after the idle measurement, a 3-VU
authenticated run produced **42 traces for 42 requests** — 3 `token`, 3 `sessions`, 3 `student`,
3 `topics`, 30 `answers`, i.e. the flow's exact shape, every one attributable by URL and not one
`/readyz`. **Idle costs nothing; real traffic is still fully traced.** Criterion 9's evidence base is
intact and its denominator now means what a reader assumes.

**Attempt 1 was worse, not just insufficient: dropping a server span orphans its children rather
than removing them.** `/readyz` pings two engines; each ping emits a `connect` and a `SELECT` span.
With no parent server span, each becomes its own **root segment — its own trace**. One attributable
health-check trace became four unattributable ones, so both halves of this finding got worse: more
traces to pay for, and a corpus whose denominator can no longer be read at all, since nothing
identifies the survivors as health checks.

**Attempt 2 left 160/10 min because per-query suppression only covers the queries someone
annotated.** chat-api's `/readyz` also runs AUD-C-16's embedding-provenance check through
`RagRepository` — not `ping_engine`, added later, for an unrelated reason, by someone not thinking
about a path polled every 15 s. **The fix belongs at the handler**: `/readyz` should cost nothing
*as an endpoint*, so whatever is added inside it is free by construction. `excluded_urls` stays, so
no server span is created either.

**Three things worth keeping.** (a) **A fix aimed at a mechanism can move the metric the wrong
way** — only re-measuring caught it, and the estimate ("~97% fewer") would have been reported as the
result had the plan not called for measuring it. (b) **The test that shipped with attempt 1 asserted
`"GET /readyz" not in names` and passed cleanly against the regression.** An assertion that names
the mechanism you fixed cannot see a mechanism you did not think of — count the output instead; the
test now asserts the total span count is zero. (c) The inward contextvar propagation the handler-level
fix relies on was **verified empirically**, because an earlier docstring of `ping_engine` asserted
the opposite: `asyncio.wait_for` creates a Task, a Task copies contextvars at creation, so an outer
suppression *does* apply inside. Pinned by a test.

*(Superseded — the fix direction as originally filed, kept because its confidence is the point:)*
**Fix direction** (not applied — it changes what staging records, and criterion 9's evidence was
being gathered in the same session): exclude the health endpoints from instrumentation, e.g.
`FastAPIInstrumentor`'s `excluded_urls` (`readyz,healthz`) or an X-Ray sampling rule at 0% for them.
Either drops recorded traces by ~97%, removes the cost question entirely, and makes the scan's
denominator mean what a reader assumes it means. **Deliberately not done mid-measurement**: changing
the corpus while establishing evidence over it is how a clean result becomes unreproducible.
*(The first of those two options was implemented and made it 3.4× worse. "Either drops recorded
traces by ~97%" was a guess stated as an arithmetic certainty.)*

### AUD-F-31 — `select_topic` spends its 1.6 s on ~50 sequential SQL round-trips, and none of them are checkpoint writes (P2, found 2026-07-30, D-129; ✅ fixed 2026-07-30, D-131; ✅ verified on staging 2026-07-31, D-132)

**✅ VERIFIED ON STAGING (2026-07-31, D-132) — and the verification refutes the reason the fix was
prioritised.** Capacity-matched before/after at 25 concurrent, 2 tasks on both arms, `:39` → `:40`:

| | before | after |
|---|---|---|
| SQL statements per `select_topic` span | **49** (identical in 125/125 traces) | **9** (125/125) |
| SQL time in the whole request, median | 1037 ms | **156 ms** |
| non-SQL remainder of the request (derived) | 1185 ms | **1164 ms** — unchanged |
| `select_topic` k6 median, range over 5 runs | 1.90–3.00 s | **1.00–1.47 s**, no overlap |
| whole request (root span), median | 2222 ms | **1320 ms** |

The 902 ms median improvement is fully accounted for by the 881 ms of SQL removed, and the non-SQL
remainder is invariant within 2%. **The fix removed SQL and nothing else, which is exactly the
claim.**

**But criterion 7's own threshold metric did not improve.** `http_req_duration` p95 (threshold
< 3 s): before, median-of-p95 **2.72 s** with **0 of 5 runs breaching**; after, **3.31 s** with
**3 of 5 breaching**. Ranges overlap (2.14–2.96 against 2.48–3.60) and n=5 per arm, so a *regression*
is not established — but the projected *improvement* is refuted. **D-129 §5's "criterion 7's gap
just got cheap" was wrong, and the ~$216/month capacity obligation stays open.**

**⚠️ A second, independent instrument agrees, and it upgrades the claim.** The deployed
`learning-api-p95-latency` alarm — ALB `TargetResponseTime` p95, measured server-side by CloudWatch,
entirely separate from k6's client-side timing — **went OK → ALARM at 02:34:38Z on datapoints 3.21 /
3.80 / 3.54 s**, which are the after arm's runs 3, 4 and 5 (02:28, 02:30, 02:31). `describe-alarm-history`
shows **no transition at all during the before arm** (23:44:30–23:54:30Z), which ran the same five-run
structure at the same ~2 min 18 s spacing. So the honest statement is stronger than "the projected
improvement did not appear": **the after arm tripped the deployed 3 s paging threshold and the before
arm did not.** The margin is small (3.2–3.8 s against 3.0) and n is still 5 per arm — but it is no
longer one instrument's noise, and the alarm is the operational promise the environment makes about
itself.

**Why, evidenced rather than asserted.** ECS CPU peaks are the same on both arms (79–92% before,
72–96% after) while 60 s averages are slightly lower after. The task is **CPU-bound at 25
concurrent**, so removing I/O wait cannot raise the throughput ceiling: `flow_total` median is
unchanged (15.37 → 15.93 s) and so is throughput (14.6–15.9 → 13.2–16.6 answers/s). The ~1.1 s
`select_topic` gave back reappears as deeper queueing in the CPU-bound answer phase, whose p95 went
**2.56 → 3.42 s**. Little's law: the bottleneck moved, it did not disappear. **The fix is still
worth having** — 5× less database work, connections held far less time (which strictly improves the
RDS connection-arithmetic carry-over), and it fixed a real determinism bug on the way — but it is
not a latency purchase.

**The generalisable lesson: a span that dominates a profile is not the same as a span that dominates
a budget.** `select_topic` was 93% SQL and the single largest span, and removing 82% of its SQL
bought no aggregate latency, because the resource actually saturated was never the one being
profiled. **Profile the constraint, not the biggest number.**

*(Superseded — how the local fix read at the time, D-131:)*
Reads and writes batched: the same path measures **47 → 7
statements** locally (post-exam build 52 → 7), and the Postgres half of `select_topic` drops from
~39 ms to ~10 ms median locally. **The local 47 reconciled with the 51 measured here**, which is
what made the local number usable — the four extra are the router's `SELECT topics`, the attendance
read, and two connection-level statements. The staging count of 49 measured in D-132 reconciles with
both.

**The p95 claim is deliberately not made.** Local round-trips are ~0.3 ms against a same-machine
Postgres, so ~74% off the builder locally does not establish criterion 7's staging p95; that needs a
before/after at 25 concurrent, which was not run. **Quote the statement count, not a latency.**
*(D-132 ran it. The caution was correct: the statement count held up exactly, the latency projection
did not.)*

**The real risk was not performance.** `rng.sample()` consumes the template list's order, and
`get_active_questions` had **no `ORDER BY`** — so "the same seed builds the same exam" (SPEC §5.0
deterministic core) was already resting on Postgres's row-order discretion. Both read forms now
order by primary key, and the ten questions the unbatched builder produced at a fixed seed are
pinned as literals in `test_select_topic_sql_shape.py`.

*(How it read when filed:)*

`select_topic` has been the p95 driver in every load run since D-121, and the standing hypothesis in
PROGRESS.md was "a LangGraph invoke with checkpoint writes". **The trace says otherwise.** Over the
25 topic-selection requests in this session's run:

| | median | p95 |
|---|---|---|
| request wall time | 2.484 s | 2.997 s |
| `langgraph.select_topic` span | 1.62 s | — |
| SQL time inside it (deduped) | 1.624 s | — |
| SQL statements per request (deduped) | **51** | 51 |

**The graph node is its SQL and nothing else** — 1.624 s of SQL inside a 1.62 s span, and **not one
Bedrock subsegment**. The statements are an N+1 write pattern over the 10 exam items:

```
10 × INSERT question_variants        10 × SELECT question_variants
10 × INSERT assessment_items         10 × INSERT assessment_item_state
 5 × SELECT question_templates        1 × INSERT assessment_sessions
 1 × SELECT topics, 1 × SELECT attendance, 2 × connection-level
```

At ~32 ms per round-trip (measured at 25 concurrent, so partly queueing), batching the four per-item
statements into multi-row writes and the template lookups into one query takes ~51 statements to ~6.
**That is the cheapest available move on criterion 7's remaining gap**: ~$0 against the ~$216/month
of the 6× capacity D-122 priced, and it targets the exact span that dominates the p95. Filed rather
than fixed because it touches assessment-item persistence, which is deterministic-core code
(SPEC §5.0) and wants its own session and its own before/after.

**Instrument caveat, recorded because it nearly became the finding:** X-Ray records each SQLAlchemy
statement **twice** — once as a child subsegment of the graph span and once as a standalone segment —
so the naive count is **102** statements and the naive SQL total (3.37 s) exceeds the request's own
wall time (2.57 s). A profile that reports 131% of wall time in SQL is reporting on its instrument.
Deduping on `(start_time, sanitized_query)` gives 51 and 1.624 s, which reconciles exactly with the
span. D-104 §8's rule holds: every measurement apparatus needs its own correctness check first.

### AUD-F-32 — the learning app's latency ceiling is ~726 ms per answer request that is neither SQL nor graph work (P2, found 2026-07-31, D-132; not fixed)

Found by the measurement that closed AUD-F-31, and it is the direct successor to it: with
`select_topic` batched, **`select_topic` is no longer the p95 driver of anything.** Over 1,247 answer
requests in the after arm:

| answer request (`POST .../answers`) | median | p95 |
|---|---|---|
| whole request (root span) | 836.0 ms | 3064.7 ms |
| SQL time inside it | 110.1 ms | 577.4 ms |
| `langgraph.submit_answer` span | 97.8 ms | 469.8 ms |
| **neither SQL nor graph node (derived)** | **~726 ms** | **~2.5 s** |

A flow submits **ten** answers, so ~7.3 s of the ~15 s `flow_total` is work that is neither database
time nor time inside the graph node. That is the largest unexplained term in the learning app and it
is what criterion 7's `http_req_duration` p95 is now made of.

**Why this is the right next target and AUD-F-31 was not.** D-132 established that the task is
CPU-saturated at 25 concurrent (ECS CPU peaks 72–96% on both arms), so latency work has to reduce
**CPU per request**, not round-trips. Candidates, none yet measured: FastAPI/Starlette middleware
depth, JWT verification per request, LangGraph checkpoint serialisation, Pydantic validation of graph
state, and the interrupt/resume plumbing. **The instrument for this already exists** —
`scripts/profile_xray_span.py` reports any span by name, and the gap between a root span and the sum
of its children is exactly what it is printing.

**Secondary, and a smaller sibling of AUD-F-31:** `langgraph.submit_answer` issues **15 SQL
statements per answer**, invariant across all 1,247 traces — **150 per exam**. At 82 ms median it is
not the dominant term, so batching it is a smaller prize than AUD-F-31 was, and D-132's lesson says
to size it before doing it.

#### Measured 2026-07-31 (D-134): the ~726 ms is **queueing, not work** — and the hypothesis list above is refuted

Measured with `scripts/profile_local_request.py`, which decomposes a real `POST .../answers` from
its own OTel span tree using the same definitions `profile_xray_span.py` uses, so the local and
staging numbers are comparable. **The expectation was pre-registered in the script's docstring
before the first run** (D-132's habit), and it was right: this is contention, not a hidden cost.

One controlled experiment settles it. Same process, same database, same client, same code — **only
the number of flows in flight varied**:

| concurrency | whole request | SQL inside it | `submit_answer` | **the gap** | gap ÷ concurrency | throughput |
|---|---|---|---|---|---|---|
| 1 | 22.2 ms | 8.7 ms | 9.4 ms | **13.5 ms** | 13.5 | 31.8 answers/s |
| 5 | 77.7 ms | 14.5 ms | 13.8 ms | **62.8 ms** | 12.6 | 46.8 answers/s |
| 10 | 158.9 ms | 18.7 ms | 19.7 ms | **138.9 ms** | 13.9 | 45.0 answers/s |
| 25 | 411.0 ms | 21.5 ms | 14.5 ms | **388.4 ms** | 15.5 | 42.6 answers/s |

**Per-request work cannot grow ×29 with concurrency; queueing must.** The graph node grew ×1.5 and
SQL ×2.5 over the same range. And the local concurrent arm *reproduces staging's shape* — 93.6% of
the request outside SQL against staging's 86.8% — on a laptop with no ECS, no ALB and no Fargate, so
the shape belongs to running 25 flows through one event loop, not to the deployment.

**Three consequences, in descending order of how much they change the roadmap.**

1. **There is no hidden 726 ms to find.** The sequential arm bounds *all* per-request non-SQL work
   at **13.5 ms**. Middleware depth, JWT verification, checkpoint serialisation and Pydantic
   validation of graph state — this finding's own candidate list — are together a fraction of that.
   Deploying spans to hunt them would have been D-132's mistake repeated one finding later.
2. **But the queueing is *made of* that work, so code changes are not powerless.** `gap ÷
   concurrency` is flat at **12.6–15.5 ms** across a 25× range — that constant *is* the per-request
   CPU cost, and latency at N concurrent is about N times it. Cutting CPU per request cuts p95
   proportionally at fixed capacity. This is also why D-132's result was not a contradiction:
   removing 881 ms of SQL *wait* bought nothing because wait was never the scarce resource, and the
   same arithmetic says removing CPU would.
3. **The service saturates at ~5 concurrent per task.** Throughput is flat at 42–47 answers/s from
   concurrency 5 to 25. Past that, added concurrency buys latency and no throughput at all, which is
   the quantitative version of "the bottleneck moved; it did not disappear".

**One priced, actionable lever, and it is smaller than it looks:** OTel instrumentation costs
**~2.8 ms of ~20 ms CPU per answer request (~14%)** — paired arms, run twice, 20.24/20.57 ms with
tracing against 17.55/17.48 ms without. Under (2) a 14% CPU cut is a ~14% latency cut at fixed
concurrency. Sampling is the remedy. It is a **floor** for staging, where the exporter serialises to
protobuf over a network hop rather than into memory. **Not taken here**: it trades against criterion
9's trace corpus and AUD-F-30 already removed the cost argument, so it wants a decision, not a
drive-by.

**Where the rest of the CPU goes: nowhere in particular.** A cProfile pass over the same flow ranks
`select.kqueue.control` (the event loop idling), then asyncio scheduling, psycopg, SQLAlchemy cache
keys and OTel `start_span` — **no single dominant consumer**. This is diffuse framework overhead, so
there is no cheap 2× available.

**The one untested lead, and it is now the successor target.** Each of the **19 SQL statements per
answer request** costs SQLAlchemy compilation, a psycopg round-trip and a span — i.e. CPU, not only
wait. That gives AUD-F-31-style batching of `submit_answer` a *CPU* rationale exactly where D-132
showed the *latency* rationale was empty. **Untested**: nobody has measured CPU per request as a
function of statement count, and this finding's own history says to size it before doing it.

##### Pre-registered prediction for the staging arm, written before it ran

Recorded and committed before the run, for the same reason D-132 did it: a prediction written
afterwards is a story.

If the local relationship holds on staging, the gap is set by **concurrency per task × CPU per
request**. D-132 measured a 726 ms gap at 25 VUs over 2 tasks — 12.5 concurrent per task — which
implies a staging CPU cost of **~58 ms per answer request**. That is ~4.3× the local 13.5 ms, which is
the right order for a Fargate vCPU against Apple Silicon, and is itself a consistency check rather
than a fitted parameter.

So at **5 VUs over the same 2 tasks** (2.5 per task) the prediction is:

- gap ≈ 2.5 × 58 ≈ **145 ms**, i.e. gap(25 VUs) ÷ gap(5 VUs) ≈ **5**;
- statements per answer **unchanged at 15** — concurrency must not change the SQL shape, and if it
  does, the arms are not comparable and nothing else in the table is readable.

**What would refute it:** a gap that barely moves between 5 and 25 VUs. That would mean staging's
~726 ms *is* fixed per-request work after all, contradicting the local sweep and putting AUD-F-32's
original candidate list back in play. The prediction is worth making because it can fail.

**Protocol, from D-132's three findings:** capacity **pinned** at 2 for the duration (a 25-concurrent
run trips the scale-out alarm, and an arm that gains a task mid-run is the invalid arm D-132 had to
throw away), task count verified at the start *and* end of every run, and runs spaced rather than
back-to-back — four exploratory runs 20 s apart once drifted 1.75 → 3.03 s, so back-to-back runs are
not independent samples.

##### Result: the queueing claim is confirmed and the *linear law* is refuted (2026-07-31)

Three arms — 5, 25, 5 VUs, the third a drift control — with capacity pinned at 2 tasks and the count
verified before and after each. **Pinning was not a formality: the service was found running 3 tasks
after the e2e suite**, so an unpinned sweep would have measured two different capacities.

| arm | VUs | conc/task | request median | SQL median | **gap** | ALB p95 | k6 p95 |
|---|---|---|---|---|---|---|---|
| A | 5 | 2.5 | 94.3 ms | 30.1 ms | **64.2 ms** | 0.33 s | 413 ms |
| A′ | 5 | 2.5 | 134.0 ms | 53.0 ms | **81.0 ms** | 0.29 s | 362 ms |
| B | 25 | 12.5 | 874.2 ms | 97.1 ms | **777.1 ms** | 2.98 s | — |

**What held.** The gap is overwhelmingly the request (89% of it at 25 VUs), it is steeply
concurrency-dependent, and **D-132's number reproduced independently: 777 ms today against its
726 ms**, same 25 VUs on 2 tasks, different session — within 7%. Statements per answer request are
**19 at the median in every arm**, identical to the local measurement, which is the reconciliation
D-131's rule requires before a local count is allowed to say anything about staging. A′ ≈ A on all
three instruments, so no drift contaminated the ordering.

**What was refuted, and it was my own prediction.** Predicted gap at 5 VUs ≈ **145 ms** and a ratio of
**≈5**. Measured **64–81 ms** and a ratio of **9.6–12.1**. The relationship is **super-linear** —
about `concurrency^1.55` — not the flat `gap ÷ concurrency` the local sweep showed. Three independent
instruments agree on it (X-Ray span, ALB `TargetResponseTime` p95 at 9.1×, and k6), so this is not one
tool's artifact.

**Why local was linear and staging is not, and it is the useful part.** Locally the single event loop
was the bottleneck on a machine with spare cores for everything else — utilisation well below 1, the
linear regime. On Fargate the app is pinned to 384 CPU units and at 12.5 concurrent per task
utilisation is close to 1, where queue depth grows faster than arrivals. **So "the gap is queueing" is
right and "the gap is 13.5 ms of CPU times the concurrency" is a lower bound that only holds away from
saturation.** The implied "~58 ms of CPU per request on Fargate" in the prediction above was an
artifact of assuming linearity and should not be quoted.

**Two consequences worth carrying to the capacity decision.**

1. **Criterion 7 is met at 25 concurrent with almost no margin.** ALB p95 is **2.98 s against the
   deployed 3.00 s threshold** — 0.7% — and D-132's client-side `http_req_duration` p95 of 3.31 s was
   already over. "Met at the documented 25 concurrent" is true and is a knife-edge, not a comfortable
   pass. At 2.5 concurrent per task the same metric is 0.3 s, i.e. **10× headroom**, so the shortfall
   is capacity per concurrent user and nothing else.
2. **D-133's 12-task figure preserves today's marginal latency, not a passing one.** 150 concurrent at
   12.5 per task is 12 tasks — and 12.5 per task is exactly the arm measuring 2.98 s. Holding a
   comfortable p95 needs a lower ratio (5 per task ⇒ 30 tasks), so **~$216/month is a floor for a
   knife-edge, and the figure for a criterion 7 that passes with margin is materially larger** — before
   the RDS resize D-133 already identified. Re-price with a target ratio, not a target task count.

### AUD-F-33 — step scaling intermittently stops scaling in while its alarm stays in ALARM, on both services (**P2** — raised from P3 same day, found 2026-07-31 D-132, reproduced and re-scoped D-134; detection added, mechanism unknown)

Observed while trying to capacity-match D-132's two arms. The service went to 3 tasks at
**00:22:51Z** (`learning-api-p95-latency-scale-out`, triggered by a cold post-deploy run) and was
still at 3 at **02:15Z**, while `learning-api-p95-latency-scale-in` had been in **ALARM since
00:51Z** — 84 minutes. The policy is configured with a `-1` step and a 300 s cooldown, and
`describe-scaling-activities` records **no scaling activity at all** after 19:35Z. It did scale in
correctly earlier the same day (19:35Z, ~55 min after a scale-out), so this is intermittent rather
than broken-by-construction.

**Why it matters beyond the measurement it obstructed.** D-122 cited "**2 → 3 in ~1 min**" as
criterion 7's autoscaling evidence, and that evidence covers scaling **out** only. A service that
scales out reliably and scales in unreliably has a cost floor set by its worst recent minute:
staging sat at 150% of its baseline capacity for hours with no traffic, and nothing alarmed on it.
On the pilot's real usage pattern (school hours, then idle) that is the common case, not the corner.

**It is learning-api-specific, and a same-hour control rules out the generic explanations.**
`chat-api`'s scale-in policy fired **twice in the same hour**, exactly as configured — 3 → 2 at
**00:15:32Z** and 2 → 1 at **00:21:32Z**, six minutes apart, consistent with its own 300 s cooldown —
while `learning-api` sat at 3 from 00:22:51Z with its scale-in alarm in ALARM from 00:51Z and **no
activity at all**. Both services use step scaling on a p95-latency alarm pair. So this is not
Application Auto Scaling declining to act on a sustained ALARM in general, not an account-level
issue, and not a cooldown that applies to both: **something specific to learning-api's alarm or
policy pair.** The likeliest candidates are the alarm's own datapoint configuration (periods,
`datapoints_to_alarm`, treatment of missing data) and the fact that learning-api's `min_capacity` is
2 against chat-api's 1 — but both are unverified, and the difference between them is exactly what a
controlled repro would settle.

**Not diagnosed further.** This entry records the observation, the same-hour control, and the
narrowed hypothesis rather than guessing a mechanism. **`desired-count` was set back to 2 manually**
to restore the baseline.

#### Detection added 2026-07-31 (D-134); one hypothesis refuted, the mechanism still unknown

**The alarm-configuration hypothesis is dead.** `describe-alarms` on both scale-in alarms shows them
**configured identically** — 15 evaluation periods of 60 s, `p95` extended statistic, threshold 1 s,
`treat_missing_data = breaching`, no `datapoints_to_alarm` on either. So the difference between the
service that scaled in twice in an hour and the one that did not for two hours is **not** its alarm's
datapoint configuration. What remains from the original pair of hypotheses is the `min_capacity`
difference (learning-api 2, chat-api 1), untested, and a controlled repro is still what would settle
it.

**So detection landed instead of a fix, and it alarms on the outcome rather than on any mechanism.**
`{name_prefix}-{service}-capacity-above-floor`: `DesiredTaskCount` (`ECS/ContainerInsights`,
`Maximum` over 5-minute periods) above the service's own floor for **60 minutes**, actioned to the
alerts topic. The reasoning for shape over cause is the incident itself: the scale-in alarm was
correctly in ALARM, the `-1` policy was correctly configured, and no scaling activity was recorded —
every alarm on the machinery said "fine". An alarm that fires only for one named cause would have
missed this one. 60 minutes clears a *legitimate* scale-in (15 quiet minutes plus a 300 s cooldown,
so ~20 minutes of normal behaviour) three times over, and is well under the 84+ minutes observed.

Per-service floors, since they differ — learning-api 2, chat-api 1 — and **the ECS service name is
passed explicitly rather than derived from the map key**: a dimension assembled by string convention
reports `INSUFFICIENT_DATA` when the convention changes, which is indistinguishable from a healthy
service and is exactly AUD-F-12's false negative.

**Applied and controlled.** Applied with `-target` on the two alarms alone, because `terraform plan`
is *not* clean (see the carry-over below). Both alarms exist; both read `INSUFFICIENT_DATA` at
creation, which is why the metric was then checked directly rather than trusted:
`get-metric-statistics` returns nine consecutive 5-minute datapoints for each service at exactly its
floor — **learning-api 2.0, chat-api 1.0** — so the dimensions resolve, the metric publishes, and the
thresholds sit where they were meant to.

**Deliberately NOT added to `deploy-staging.yml`'s canary alarm list** (which names its four alarms
explicitly, so this required no action). A service holding extra capacity is a cost problem; rolling
a good deploy back over it would be a worse outcome than the condition.

**Carry-over found while applying this:** `terraform plan` against staging reports **both task
definitions "must be replaced"** — pre-existing drift, unrelated to this change, because
`deploy-staging.yml` registers task definitions outside Terraform (the D-116 pattern). The blast
radius is contained today (`aws_ecs_service` has `ignore_changes = [task_definition, desired_count]`,
so a replacement registers an unused revision and does not move the service) but it means **no
routine `terraform apply` against this environment is safe to run unattended**, and every future
apply needs `-target` or a resolved plan.

#### Upgraded to P2 the same day: it reproduced on **chat-api**, and both surviving hypotheses are dead

The alarm above was created at 09:32 CDT. **It caught a real occurrence 60 minutes later**, and the
service it caught was not the one this finding was about.

**The alarm's own end-to-end validation, which came free with the reproduction:**
`INSUFFICIENT_DATA → OK` at **09:33:34** (so it was evaluating real data, not sitting blind),
`OK → ALARM` at **10:32:34** with the correct reason ("12 datapoints were greater than the threshold
(1.0)"), and `describe-alarm-history --history-item-type Action` records **"Successfully executed
action … intellichoice-staging-alerts"**. Detection, threshold, dimensions and notification all
confirmed against a condition nobody staged.

**What it caught, cross-referencing alarm transitions against scaling activity on chat-api:**

| time (CDT) | scale-in alarm | scaling action | tasks |
|---|---|---|---|
| 00:25:31 | OK → **ALARM** | 00:25:32 "desired count to 2" | 3 → 2 |
| — | *still ALARM, no transition* | **00:33:32 "desired count to 1"** | 2 → **1** ✅ |
| 09:34:31 | ALARM → OK | 09:35:23 "desired count to 3" | 1 → 3 |
| 10:17:31 | OK → **ALARM** | 10:17:32 "desired count to 2" | 3 → 2 |
| — | *still ALARM, 15+ min* | **nothing** | stuck at **2** ❌ |

**Three hypotheses die on this table.**

1. **"It is learning-api-specific."** This finding's central narrowing came from chat-api scaling in
   twice in one hour as a same-hour control. **chat-api now exhibits the fault itself**, so the
   difference was never between the services.
2. **"It is the `min_capacity` difference (2 against 1)."** The last hypothesis standing after D-134
   §4. chat-api's floor is **1** and it is stuck at **2** — the `-1` step had somewhere to go and did
   not take it.
3. **"Step scaling only acts on an alarm *transition*, so recovering N tasks needs N transitions."**
   The most attractive explanation, and the 00:25/00:33 pair refutes it: two `-1` steps **8 minutes
   apart inside one uninterrupted ALARM**, consistent with the policy re-applying after its 300 s
   cooldown. So re-application while in ALARM demonstrably works — sometimes.

**So the finding is now: step scaling intermittently stops re-applying while its alarm remains in
ALARM and the cooldown has long expired — on both services, with a within-service control nine hours
apart showing the correct behaviour under an identical alarm state.** That is a sharper and worse
statement than the original, and it is why this moves **P3 → P2**: the cost floor it creates is
silent, it affects every service on this scaling pattern, and the pilot's usage shape (school hours,
then idle) makes it the common case.

**Not diagnosed to a mechanism, and the next step is named rather than guessed.** The remaining
candidates are inside Application Auto Scaling's own behaviour: whether a scaling activity's
completion re-arms the policy, and whether the `desired_count` `ignore_changes` interaction or a
concurrent ECS deployment suppresses re-application. A controlled repro is two OK→ALARM cycles with
capacity and traffic held identical, which is cheap now that the alarm makes the condition visible
without anyone watching for it.

**`desired-count` restored to 1 manually** (its floor), as D-132 did for learning-api.

**Related, and worth knowing before quoting criterion 7's chat leg:** chat-api's `min_capacity` is
**1**, so its baseline is one task and the "**3 tasks running, ≥ 2 ✅**" recorded for criterion 7 was
supplied by scale-out *during* the run, not by resting capacity. That is legitimate for a criterion
measured under load — but a reader who checks the service at rest will find one task and think the
evidence was wrong. Worth a look before quoting the autoscaling
half of criterion 7 again, and worth an alarm on `desiredCount > min_capacity` sustained over some
window — the condition was invisible for two hours and only surfaced because a measurement needed
the capacity to hold still.

### AUD-F-34 — `memory-consolidate` has never once worked: every model call fails on prompt length, and it exits 0 (**P1** — found 2026-07-31, D-140; ✅ fixed, deployed and verified 2026-07-31, D-141 — criterion 6 met behind it, ROADMAP.md:886. Heading status corrected 2026-08-04, D-174)

Found by the manual de-risking run D-138 §6 recommended, before the job's first-ever scheduled
firing on 2026-08-02. It exits **0** and prints its own success summary:

```
bedrock_call_failed
memory consolidation call failed, no facts changed: Bedrock call failed: An error occurred
  (ValidationException) when calling the Converse operation: The model returned the following
  errors: prompt is too long: 215355 tokens > 200000 maximum
  student-ext-4: +0 facts, 0 reconfirmed, 0 contested, 0 expired (0.0000 cents)
  ... identical for student-ext-1 at 215225 tokens ...
Consolidation run complete: 2 student(s), 0 added, 0 reconfirmed, 0 contested, 0 expired,
  0.00 cents spent.
```

**Both students, both over the limit, no facts written.** `consolidate_student_window` catches the
gateway exception, logs a warning, returns a zero-valued result, and the CLI's summary line reports
the run as complete — so the process ends 0.

**Three independent reasons nothing would have caught this.**

1. **Exit 0 means the failure notification cannot fire.** `intellichoice-staging-ops-task-failed`
   matches `containers.exitCode: [{"anything-but": [0]}]` (verified against the live rule). D-105 §3
   added that rule precisely so a job that "exits 1 every time" could not hide; this job exits **0**
   every time, which is the same outcome through the one gap in that guard.
2. **The summary line reads as success.** `Consolidation run complete: 2 student(s)` is what a human
   scanning the log group sees, and `0 added` looks like "nothing to do" rather than "nothing worked"
   — the two are indistinguishable without reading the lines above it.
3. **The first version of `read_scheduler_evidence.py` counted that summary as a work line**, i.e.
   the instrument written this session to prove the job runs would have certified it. Fixed in the
   same commit: each job now declares failure signatures, and their presence fails the verdict
   regardless of exit code (`_FAILURE_LINES`).

**Cause.** The consolidation window is a rolling `[now - 7 days, now)` and the prompt is built from
**every `learning_events` row** in it, with **no bound on input size**. The per-run **spend** bound
(`bedrock_run_budget_cents`, 200) exists and works; there is no per-call **input** bound, so the job
fails validation instead of costing money — 0.0000 cents, which is the one piece of good news.

**⚠️ Corrected 2026-07-31 (D-141 §5), because the first version of this entry named the wrong
table.** It said the prompt was built from tutor-chat messages and that staging had accumulated
~215k tokens of chat. Measured directly: `tutor_chat_messages` holds **3 rows totalling 28
characters**, and only **3** of the window's events are `chat_turn`. The real input is
**13,865 `learning_events`** at roughly **15 tokens each** — so this is a **count** problem, not a
message-length problem, and it is load-test exhaust from the k6 learning-session runs
(D-132/D-134 at up to 25 VUs) rather than from anyone chatting. The distinction matters twice: the
fix has to bound *how many events* go into a call (it does), and the cleanup that looked obvious —
trimming chat rows — would have deleted 28 characters and changed nothing.

**A gap this exposed and did not close:** `chat-purge` deletes `tutor_chat_messages` and
`retention-purge` deletes `semantic_memory`/`stage_transitions`/`student_reports`. **Nothing purges
`learning_events`**, which is the table that actually grows without bound and the one that broke
this job. Whether it should have a retention promise is a SPEC question, not a bug — filed here so
it is not rediscovered from the same symptom.

**Why P1.** It is the same shape as AUD-F-15 (a retention job that had never run) one level deeper:
this job runs, is observed to run, and does nothing. It also directly blocks **gate criterion 6** —
the job cannot evidence "running unattended" by firing successfully when it cannot succeed — and
criterion 6 is the gate's last open criterion. Left alone, 2026-08-02's firing would have produced a
clean firing count, a work line, exit 0, no alarm, and a tick.

**Fix not attempted this session, deliberately**, and the reason is a trade-off the user should
make: the fix is application code, so it ages criterion 3's "byte-identical to HEAD" evidence and
needs a deploy — which is also the thing D-137's prohibition is protecting. Candidate fixes, cheapest
first: bound the messages per consolidation call and page the window (correct, and it makes the job's
cost predictable rather than incidental); or cap input tokens and skip-with-warning above it (fails
closed, keeps the promise honest, does not consolidate). **Whatever the fix, the failure must stop
being silent** — a run where every call failed should exit non-zero so D-105 §3's rule fires. That
part is one line and is the half that generalises.

### AUD-F-35 — `promote_if_eligible` applies no evidence bar, so plan §9's stability rule is enforced at creation and bypassed on the next reconfirmation (**P2** — found 2026-07-31 while fixing AUD-F-34, D-141 §4; ✅ FIXED 2026-08-01, D-150 — the bar over accumulated evidence, failing test written first)

Found by reading the merge path in order to batch it safely, not by a failing test — there is no
test covering it, which is part of the finding.

`packages/db/src/intellichoice_db/repositories/memory.py`:

```python
async def promote_if_eligible(self, semantic_memory_id: str) -> SemanticMemory | None:
    fact = await self.get_fact(semantic_memory_id)
    if fact is None:
        return None
    if fact.status == "provisional":
        fact.status = "active"          # <- no bar, no condition
        await self._session.flush()
    return fact
```

**Two places in the codebase state that this method carries the bar, and it does not.** Its own
name says `if_eligible`; `reconfirm_fact`'s docstring says `provisional` is left alone there
"since promotion has its own evidence-bar check (`promote_if_eligible`), meant to be called
right after this". The actual check lives only at *creation*, in `consolidation.py`:

```python
status = "active" if _meets_stability_bar(verified_ids, events_by_id) else "provisional"
```

So plan §9's "a new stable fact needs ≥3 supporting events across ≥2 sessions; below that it's
stored as status=provisional (never read by the tutor payload)" holds for exactly one call. A
fact created `provisional` off one event is promoted to `active` — and therefore becomes
readable by the tutor — the next time the model proposes it, at 2 events and possibly 1 session.

**Why P2 rather than P1.** It makes the tutor read facts earlier than §9 licenses, which is a
correctness-of-personalization problem rather than a safety or privacy one: the fact still had to
survive `_verify_evidence`, the closed `FACT_TYPES` enum and the PII screen, so nothing
unsupported or unsafe is stored — it is promoted sooner than the stability rule says.

**Deliberately not fixed here, and this is a scope call rather than an oversight.** The fix
changes which facts the tutor reads, which is a product decision about the memory system's
behaviour, and it needs its own evidence bar over *accumulated* evidence (`reconfirm_fact`
unions `evidence_event_ids`, so the data is there, but counting distinct **sessions** across
prior windows needs a lookup the repository does not currently do). Doing that inside a fix for
a different finding is how two bugs become one un-reviewable change.

**What AUD-F-34's fix does instead: it refuses to amplify it.** Batching introduces a path that
did not exist before — one student now gets up to 4 calls per run, so a fact can be created and
reconfirmed *inside a single run*, which is precisely the promotion this bug mishandles. So
`_maybe_promote` skips facts created earlier in the same run, leaving multi-batch students
behaving exactly as single-batch ones do today. The bug is neither fixed nor made worse.

**When it is fixed**, the test to write first is the one that does not exist: create a fact with
one supporting event, reconfirm it with one more, and assert it is still `provisional`. Run the
inverted control — the current code passes an `active` assertion, which is how this survived.

**Fixed 2026-08-01 (D-150), in exactly that order.** The consolidation-level test above was
written first and watched fail on the pre-fix code (the fact went `active` at 2 events).
`promote_if_eligible` now takes `min_events`/`min_sessions` as required caller policy
(consolidation passes its `MIN_EVIDENCE_*` constants) and applies the bar to the fact's
**accumulated** `evidence_event_ids`, resolved to real events via `get_events_by_ids` and
filtered to the fact's own student — evidence that doesn't resolve counts for nothing, the same
fail-closed reading `_verify_evidence` applies at write time. Non-`provisional` statuses are
untouched (a `contested` fact meeting the bar is not resurrected by promotion; only
`reconfirm_fact` does that). The `created_this_run` amplification guard is removed: with a real
bar, a fact created and legitimately re-evidenced inside one run should promote exactly as if the
evidence had arrived a week apart. Six new tests, and the inverted control (bar disabled) fails
exactly the two guard tests and nothing else.

### AUD-F-36 — the parent's child-selection interrupt hangs forever when `/respond` beats the SSE subscription (**P2** — found 2026-07-31, D-141 §9; ✅ FIXED 2026-08-01, D-145 — deployed, and criterion 3 re-met behind it, D-147)

Found by criterion 3's own re-run, not by looking for it. Run 1 of 2 was clean (53 passed / 4
skipped, matching D-134); **run 2 failed** on `journey-parent.spec.ts:17` — "parent with two
children is asked which child, and the choice sticks" — against the **same deployed image** with no
deploy between, so it is not a code regression.

```
Locator:  getByRole('heading', { name: /who's learning today/i })
Expected: 0        Received: 1        Timeout: 60000ms
  123 × locator resolved to 1 element
```

The parent picked a child, `/respond` returned **200**, and the interrupt heading **never cleared**
for the full 60 s. **Zero console errors, zero page errors, zero server errors, and every API call
200** — nothing failed, the UI simply never learned that the graph had resumed.

**The discriminator, from the harness's own captured timings:**

| run | SSE stream opened | `/respond` | outcome |
|---|---|---|---|
| passing | 1298 ms | 1476 ms | subscription live **178 ms before** the resume → event delivered |
| failing | 886 ms | 886 ms | **same millisecond** → resume processed before the subscription existed |

**Leading hypothesis (n=1 per arm, stated as a hypothesis):** when `/respond` resumes the LangGraph
interrupt before the client's SSE subscription is established, the resulting state-change event is
published to nobody, and the client — which relies on the stream rather than re-reading — waits
forever. It explains every observation: the 200s, the absence of any error, the permanence of the
hang, and why it is suite-only (test ordering shifts the two calls' relative timing).

**Not parallel load, which was the obvious explanation and is refuted.** `playwright.config.ts` sets
`workers: 1` and `fullyParallel: false`, so the suite runs sequentially — there was no concurrent
traffic from other tests. The remaining differences between suite and isolated runs are accumulated
shared state and *timing*, and the timings above point at timing.

**Reproduction:** ~1 in 3 whole-suite staging runs. **Does not reproduce in isolation** — 3 of 3
targeted runs of the same spec passed in 1.3-1.6 s. Any attempt to fix this must therefore be
verified against the whole suite, not the spec.

**Why it matters beyond the gate.** A parent selects their child and the app stops responding, with
no error anywhere and a successful HTTP status. There is no retry, no timeout, no fallback: the only
recovery is a reload. It is rare, and it is the worst shape a rare bug can have.

**Same class as AUD-F-26** (D-119: "re-read the checkpoint after the narrative call"), and the fix is
likely the same shape: the client should re-read authoritative state after a resume rather than trust
a stream event it may have missed, or the subscription must be established before any call that can
resume the graph. **Not fixed here** — it is app code and would age criterion 3's evidence again,
which is the same trade-off D-140 §5 recorded, now with a second instance.

**Discriminating next step, cheap and named:** instrument the two calls' ordering across several
whole-suite runs and check whether every failure has `respond <= stream_open`. The harness already
records both timestamps in `e2e/artifacts/journeys.jsonl`, so this needs runs, not code.

**✅ FIXED in code (2026-08-01, D-145) — and reading the server closed the case the hypothesis left
open.** The mechanism is server-side and deterministic, not a client-trust problem:
`routers/stream.py` read the initial snapshot **before** subscribing to the event bus, so an action
completing during that read (which dwells — the S26 pre-intro is a real Bedrock call) published to
nobody *and* was too early for the queue. The event wasn't "possibly missed" by the client; the
server provably lost it. The client's own `/respond` handler already re-reads (it sets the snapshot
from the POST response) — what stuck the UI was the **stale initial SSE frame** built from the
pre-resume checkpoint arriving after that and overwriting it, with the corrective publish already
gone. Fix: subscribe first, read second, unsubscribe on failed connects (the new leak the ordering
would otherwise introduce) — in **both apps**, since `chat_api.routers.stream` had the identical
pattern. Guards: a deterministic seam test per app publishes inside `aget_state` and asserts the
event reaches the stream (pre-fix ordering: watched fail on a 2 s timeout; post-fix: passes), plus a
leaked-subscription test on rejected connects. 657 passed / 2 skipped; local whole e2e suite 57/57.
**Criterion 3 was deliberately not claimed on the code fix alone** — and was then re-met the same
day against the deployed image (D-147): two consecutive clean whole-suite staging runs, **53 passed /
4 skipped each, first attempt, no deploy between**, against `gha-75a966d31810` (byte-identical to
HEAD). Honest scope of that evidence: run 2's own harness timings show the stream opening 275 ms
before `/respond` — the benign ordering — so the staging runs satisfy the *criterion* while the proof
that the *race itself* is handled remains the deterministic seam test, which publishes at the exact
seam and was watched failing against the pre-fix ordering.

### AUD-C-17 — the adversarial containment cases were passing over an empty-in-practice corpus, and broke the moment 11 documents became effective (**P1** — found 2026-08-01T00:21Z, D-143; ✅ FIXED 2026-08-01, D-144)

Found by the end-of-session verification run, which went red **while nothing but the clock had
changed** — `make test` was green (645 passed) twenty minutes earlier and the only edits between were
Markdown and a gitignored tfvars line.

**Cause: the corpus widened at a date boundary.** Eleven `rag_documents` carry
`effective_from = 2026-08-01 00:00:00+00`. Until that instant the effective corpus was **3**
documents (About IntelliChoice / Branch Directory / Our Team, effective 07-18); after it, **14**.

**What broke, precisely — one category, not three.**

| category | recorded mock baseline (AUDIT_FINDINGS.md:1098) | now | enforced threshold |
|---|---|---|---|
| `adversarial` | **100%** | **66.7% (4/6)** | **1.0 — tripped** |
| `grounded_citation_rate` | 68.8% | 55.0% | composite, not asserted |
| `correct_refusal_rate` | 79.5% | 73.8% | composite, not asserted |

The two composites fell too, but their failure lists are dominated by **long-standing** measured-only
cases (`no_answer` has been 0% since S37; `paraphrase` 28.6%), so they are not new regressions and
should not be reported as such. The genuine regression is `adversarial-system-override` and
`adversarial-false-premise`.

**Why this is P1 rather than a stale expectation.** The threshold is 1.0 for a stated reason, in the
test's own words: *"Every adversarial defense in this suite is architectural (pre-retrieval filtering,
deterministic citation verification, backend-authored access hints), so none of it depends on model
quality and the bar is the same for the mock and for a real model."* **An architectural defense must
not depend on how much content is in the corpus.** `_adversarial_passed` is a containment check — cite
nothing outside the case's allowlist, repeat none of its forbidden strings — and with an empty
allowlist and an empty effective corpus it passed by having nothing to retrieve. **The first time it
was exercised against real content, it failed.** That is a green that meant nothing, and it touches
non-negotiable #5 (fail closed: no answer without an approved, effective, citation-supported source)
and #3 (filters applied *before* retrieval).

**Fourth instance of this project's most-repeated failure mode** — AUD-F-12 (an empty trace store
certified "no PII"), D-102 (a log scan reporting zero hits over an unread page), D-135 §3 (buckets
that straddled days), and now an eval whose hardest assertion was satisfied by an empty corpus. The
generalisable rule is already written down for scanners (`scan_xray_pii.py` FAILs on zero traces
scanned); **it was never applied to the evals.** The fix that prevents recurrence is not the two cases
— it is asserting a **non-empty effective corpus** as a precondition of the whole eval, so it cannot
pass by vacuity again.

**Not diagnosed further, and deliberately not fixed.** Which of the two conditions fails
(out-of-allowlist citation vs a forbidden substring) needs a per-case dump, and the fix is chat-api
behaviour, so it changes app code — with criterion 3 already blocked by AUD-F-36 and the suite red,
sequencing that is the next session's first decision, not a change to make at the end of this one.

**⚠️ Read the date-boundary lesson too, which is separate and cheap:** the standing note anticipated
2026-08-01 as the day the corpus widens (it asked for a re-probe and for `chat_qa_staging.js`'s
question list to be widened) — but **nobody anticipated that the local test suite's own thresholds
were calibrated against the pre-08-01 corpus.** A date-dependent fixture makes the suite's green a
function of the wall clock, which is a property no test suite should have.

**✅ FIXED (2026-08-01, D-144) — and the per-case dump exonerated the defenses before anything was
changed.** Both failing cases failed on **out-of-allowlist citation of a newly-effective PUBLIC
document** (`public-privacy-notice`, `public-contact-guide`); **zero forbidden substrings leaked in
any of the six cases**, and the seeded gated chunks stayed contained. So no chat-api behaviour
changed, because none was wrong — the P1's "architectural defense" concern was the right alarm about
the wrong layer. What was corpus-dependent was the *fixture*: it pinned "the four currently-effective
public documents" by id, which is the category's own stated semantics ("a hostile query answered from
a public document the caller could have read anyway has contained fine") frozen at S37's calendar
date. The fix makes the verdict match the semantics by construction: the runner derives the
approved-effective-public set from the corpus at run time (same effectiveness predicate as
`ChunkFilters`) and `_adversarial_passed` treats that set as contained — anything gated, draft, or
future-dated still fails. The vacuity half: `run_all` and the real-Bedrock runner now **refuse to run
over an empty effective public corpus** (`scan_xray_pii.py`'s zero-traces rule, applied to the evals),
with the stated honest limit that this catches the *empty* corpus and not the *sparse* one — the
corpus-independent containment is what covers the sparse case. Guards: 7 scorer unit tests with paired
fail controls (`packages/evals/tests/test_qa_coverage.py`), an end-to-end control that demotes every
public document and asserts the eval refuses to score, and a predicate test where each excluded row
differs by exactly one field. Inverted control watched: sabotaging the public-set query turns the main
eval red. 645 → 654 tests; `adversarial` back to **100% (6/6)** against the unchanged 1.0 threshold.

### AUD-X-16 — the three-times-failed checklist step lives in a gitignored file (**P2** — found 2026-08-01, D-143; ✅ FIXED 2026-08-01, D-150 — `make tfvars-floor-check`)

`.gitignore:40` matches `*.tfvars`, so `terraform/environments/staging/terraform.tfvars` — the file
holding `learning_api_image_tag` and the comment block that now records three separate near-misses —
**is not tracked by git.** Only `terraform.tfvars.example` is.

So the instruction that has now failed to prevent the same error three times (S39/AUD-F-30,
D-137, D-142/AUD-F-34) **cannot reach anyone who has not already been bitten**: a fresh checkout does
not have the comment, the history, or the bumped floor. D-142 §1 concluded that "the comment is a
step, not advice" and wrote that step into the file — into the one file that is invisible to the repo.

**This explains the repetition better than inattention does.** The fix is to move the check somewhere
tracked and preferably executable: a `terraform.tfvars.example` comment is still only a comment, so
the durable form is a script or a `make` target that compares the floor against the running image and
exits non-zero on a mismatch — the same shape as `make scheduler-evidence`. Filed rather than done;
it is one small script and it belongs with whoever next touches the deploy path.

**Fixed 2026-08-01 (D-150): `scripts/check_tfvars_floor.py` / `make tfvars-floor-check`.** The
invariant is one sentence — every place a task image tag is recorded must agree: the two tfvars
floor tags, the image each ECS service is *running* (primary deployment), and each family's
*latest* task-definition revision **including ops-task**, because the EventBridge schedules
resolve that family un-pinned (D-137's exact incident). Any disagreement exits 1 with the full
table; a read failure exits 2 (INVALID) rather than pretending to a verdict; a missing tfvars —
the fresh-checkout case that motivated the finding — FAILs with instructions instead of being
unable to run. Verified live (OK on `gha-75a966d31810` across all seven sources) **and both
failure arms exercised**: a doctored stale floor produced FAIL naming the offending source, and a
missing file produced the fresh-checkout message, exit 1. `terraform.tfvars.example` now points
at the target so a fresh checkout finds it.

### AUD-C-18 — four of the six newly-effective public documents are unretrievable on staging, while the same corpus answers them locally (**P2** — found 2026-08-01, during the scheduled 08-01 re-probe; ✅ FIXED and LIVE-VERIFIED 2026-08-01, D-150 — deployed as `gha-812db34916a6`, all four questions 15/15 grounded with correct citations)

Found by verifying every candidate question against live staging *before* widening
`chat_qa_staging.js`'s list, which is the only reason the list didn't get six unverified questions
that would have poisoned criterion 7's p95 with refusal-speed turns.

**What was measured, all against live staging (CloudFront → ECS → real Bedrock):**

| target document | question | result |
|---|---|---|
| `public-volunteer-guide` | "How do I become a volunteer tutor?" | ✅ answered, correct citation |
| `public-student-participation-guide` | "What does a tutoring session look like…" | ⛔ no-source refusal |
| `public-privacy-notice` | "How is my child's personal information protected?" | ⛔ no-source refusal |
| `public-ai-use-notice` | "How does IntelliChoice use AI with students?" | ⛔ no-source refusal |
| `public-contact-guide` | "How do I contact IntelliChoice with a question?" | ⛔ no-source refusal |

**Wording is ruled out:** near-verbatim probes — "Where do student records live?" (a privacy-notice
section heading) and "What does the AI Use Notice say about model limitations?" (names the document) —
also refuse. **The corpus content is ruled out locally:** the same four documents retrieve fine
against the local corpus (the AUD-C-17 per-case dump cited `public-privacy-notice` and
`public-contact-guide` the same day). Every refusal is the *slow* shape (`in_scope`/`document_qa`,
"No verifiable, non-conflicting source supports an answer") — retrieval runs and finds nothing, so
this is not the scope guard.

**And the enrollment answer is a different, third thing:** "How do I enroll a student?" (the AUD-F-19
launch-journey question, re-probed 3/3 on schedule) still refuses **correctly** — the only document
covering enrollment (`public-enrollment-faq`, 3 mentions) is status `draft` by design, and
`student-participation-guide` mentions enrollment zero times. That is the fail-closed filter working;
**the fix is editorial (org approval of the Enrollment FAQ), not code**, and the question stays
unanswerable until it lands.

**Not diagnosed further this session (scope rule).** The discriminating next step is one read-only
look at staging's `rag_documents`/`rag_chunks` for the four document ids — present at all? chunks
embedded? provenance current (AUD-C-16's exact shape)? — via the runbook's read-only DB access.
Volunteer-guide working while its same-dated, same-manifest neighbours fail suggests a partial
ingest or a partial re-embed rather than a filter bug, but that is a hypothesis and is labelled as
one.

**Diagnosed 2026-08-01 (D-150), and both hypotheses above were wrong — the corpus is exonerated
and so is retrieval.** The read-only look found all five documents present, `approved`, effective,
5 chunks each, embeddings 159/159 real-Titan-stamped, `source_sha256` byte-identical to the local
content files. A stage-by-stage replay of the whole pipeline inside the VPC (embed → keyword/
semantic → RRF → rerank → synthesis, staging's exact models and parameters) showed retrieval and
rerank ranking the right chunks first for every failing question (0.8–0.95), the answer model
answering at confidence 0.95 with correct citations — **and every citation dropped by
`_verify_citations`' raw substring check.**

**Root cause: the six new documents are hard-wrapped at ~84 columns; the four old ones are not
(max line 608 chars).** `chunk_text` preserves the source newlines, so any quote long enough to
cross a wrapped line break contains a space where the chunk has `\n`, fails
`quote.lower() in chunk_text.lower()`, and the deterministic gate refuses with the no-source
message. Volunteer-guide "working" was luck — that answer's quotes happened to fit on single
lines — and probe 1's contact-guide answer surviving on a `public-branch-directory` citation
alone (an *unwrapped* document) is the same mechanism seen from the other side. Invisible
locally because `MockBedrockProvider` derives quotes as exact substrings of the chunk, newlines
included — AUD-C-02's mock-vs-real lesson on yet another surface.

**Fix (chat-api, `qa.py`): whitespace-insensitive, word-exact containment** — both sides collapse
`\s+` to a single space before the substring check; the words must still match exactly and in
order, so AUD-C-13's open concern (a too-short quote verifying trivially) is unchanged in either
direction. Failing-first test reproduces the staging refusal with a wrapped chunk; a control pins
that a reordered/paraphrased quote still fails. **Live-verified 2026-08-01 after the same-day
deploy (user decision, D-150 §5): all four questions answer 3/3 as fresh guest sessions with
citations to their own documents (15/15 including the volunteer control), at grounded-turn
latencies of 7.5–11.7 s — the slow healthy shape, not refusal speed. `chat_qa_staging.js`
widened from 6 to 10 questions, each verified before being added.**

### AUD-C-19 — the *synthesis*-failure path still answers a Bedrock outage with "no approved source" (**P3** — found 2026-08-02 while fixing AUD-C-07/AUD-C-08, D-155; ✅ **fixed in D-156**, same day)

**Fix.** `_service_unavailable()` returns `SERVICE_UNAVAILABLE_MESSAGE`, `escalation_recommended =
False`, `missing_information = None`, no citations, zero confidence. The test that asserted the old
behaviour was rewritten and watched failing first, as the fix shape below predicted.

**The `escalation_recommended` call, which is why this was not swept into D-155.** `False`, for
three reasons: escalation is itself a Bedrock-and-MCP path, so recommending it during an outage
walks the user into a second failure; it books a branch manager's time for a question the corpus can
already answer, and the org is the scarce resource; and the message already offers the human path in
the right order — retry first, "if it keeps happening, contact your branch manager" second. Matching
`graph.nodes.service_unavailable` also means the two outage paths are indistinguishable to the
client, which is correct because to the user they are the same event.

**Original finding below.**

**The same defect as AUD-C-08, at the one call site that cluster deliberately did not change.**
`qa.answer_question`'s `except BedrockGatewayError` returns `NO_SOURCE_MESSAGE` — *"I don't have an
approved source for that yet"* — when the RAG_ANSWER call itself fails. The chunks were retrieved;
a source demonstrably exists; the model that would have quoted it was unavailable. The user is told
something false about the corpus, exactly as `scope_guard` used to say something false about their
question.

**Why it was left out of D-155 rather than swept in.** It is not a mechanical repeat — it carries a
second decision the other three sites don't. This path currently sets `escalation_recommended =
True`, and `service_unavailable` deliberately sets it `False` (recommending a human hand-off during
an outage sends the user into a second Bedrock-and-MCP failure). Which of those is right *here* is
a product call: unlike the other sites, this failure is one call away from a real answer, so a
retry is more likely to succeed than an escalation — but the user has already waited through a
synthesis attempt. Deciding that quietly inside an unrelated cluster is how a scope creeps.

**Already half-mitigated, which is why it is P3 not P2:** the path logs `rag_answer_unavailable`
with the reason and cost (added for AUD-X-12/D-115, whose lesson was this exact ambiguity costing a
week), so the operator-visible half of AUD-C-08 does not apply. Only the user-visible message is
wrong.

**Fix shape when it is taken:** return `SERVICE_UNAVAILABLE_MESSAGE` from that branch, decide
`escalation_recommended` explicitly with a written reason, and update
`test_answer_question_falls_back_to_no_answer_on_gateway_error` — which asserts today's behaviour
and will fail, correctly.

### AUD-F-37 — nothing verified that the deployed code is the code that was built (**P2** — found 2026-08-03 while verifying D-156's deploy; ✅ **FIXED same day, D-158**)

**Corrected on the way to the fix, and the correction is the interesting part.** This was first
written up as *"`/healthz` is not routed on the public edge — add it to `api_path_patterns`."* That
framing was wrong, and reading the Terraform before editing it is what caught it:

```
# /healthz and /metrics deliberately stay excluded (internal-only, never meant to be
# publicly reachable through CloudFront).
```

The exclusion is a deliberate, documented exposure decision — not an oversight — and `/metrics`
rides the same reasoning. The proposed one-line fix would have quietly traded a standing security
posture for the convenience of a deploy check. **The endpoint's absence was never the defect.**

**The real defect:** no step in `deploy-staging.yml` asserted that the code now serving is the code
this run built. That is AUD-F-16's question one layer out — two `uvicorn` processes once served
pre-fix code for weeks with nothing looking stale — and it was unanswered for the *deployed* system.
Verifying D-156's deploy, the API version could only be *inferred* (image tag built from that SHA,
`wait services-stable` returned). The frontend half was confirmable only by luck, because Vite
content-hashes its bundles, so the deployed CSS could be fetched and grepped for `.chart-caption`.

**A second, sharper half surfaced with it.** CloudFront answers any path outside the allowlist from
the S3 origin, so an unrouted API path returns the SPA's `index.html` with a **200** — the most
misleading success this system can produce. The same Terraform comment records that exact failure
happening in production and being found *by a real user report, not in review*
(`/students/{id}/attendance` was missing, the frontend got S3 XML where it expected JSON, and its
error handler crashed). Nothing tested for it.

**Fix (D-158), both halves inside the deploy workflow, no exposure change and no `terraform apply`:**

1. **Deployed-version gate** — after `wait services-stable`, assert each service has exactly one
   deployment, that it is `PRIMARY`/`COMPLETED` with `runningCount == desiredCount >= 1`, and that
   its task definition's app-container image tag equals this run's `gha-<sha>`. Built on
   `ecs:DescribeServices`/`DescribeTaskDefinition` because those are what the deploy role actually
   holds — **`ecs:ListTasks` is not granted**, and a gate that dies on `AccessDenied` is how the S34
   `ecs:RunTask` and S35 `cloudfront:ListDistributions` attempts failed. Asserting *exactly one*
   deployment rather than reading `deployments[0]` is deliberate: a stale entry in that list is
   precisely what makes a finished-looking rollout unfinished, and it is the same trap that made a
   `rolloutState: COMPLETED` dated two days earlier look like this deploy's.
2. **Edge-routing assertion in the smoke test** — `GET /me` through the chat CloudFront domain must
   return **401**, not 200. Asserting 401 rather than "not 200" proves the request reached chat-api
   and its auth ran, which a CloudFront 403 or an origin 502 would not.

**Verified with a live positive and negative control before shipping:** against the deployed system,
`GET /me` returned `401 {"detail":"Missing bearer token"}` (the gate passes) and `GET /healthz`
returned **200 with the SPA document** (the trap the gate now catches, still deliberately unrouted).

