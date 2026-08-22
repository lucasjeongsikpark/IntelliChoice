# 2026-08-22 (night) — the narrow-coverage batch resolved (sixth Orca coordinator/executor run)

Historical narration only — non-authoritative (DQ-1). Current state: `docs/PROJECT_STATE.md`;
durable evidence: the tests and fixes named below and git history. No new judgment was made, so
no DECISIONS entry exists for this session.

**Queue-gate note.** This continue arrived Friday 21:47 UTC — queue row 1 (RD-01's Sunday
confirmation) stays time-blocked until 2026-08-24 18:30 UTC, so the cursor took row 2:
`BATCH-LOW-NARROW-COVERAGE` + `REQ-44-REASON-SWEEP` (three code members; `DRIFT-85` is the
register's own standing exception, BLOCKED on S43, untouched).

**What was done.** Sixth Orca run. Frozen Spec `tasks/narrow-coverage-three-gaps.md`
(run `run_19898c1ed656`, task `task_521cf659aab0`, dispatch `ctx_16044dd344bd`; agent `claude` /
model `opus` / effort `high`, receipt requested == effective). Zero correction rounds. The
coordinator's spec pre-identified two subtleties the register did not carry: the redactor's
`if cleaned == attributes` early return defeats a naive events fix, and blind
`REASON_MESSAGES` exhaustiveness collides with reasons that legitimately have no default copy.

**What the executor delivered (three commits, landed by PR #372 as
`fb74f38`/`fd6927d`/`67cd708`).**

- **DRIFT-82 (rule 1):** span **events** are now redacted at export — names, attribute values,
  recorded-exception messages — on both exporter branches, with the change-detection fast path
  widened to cover events; three tests recorded failing pre-fix.
- **DRIFT-68 (rule 5):** the approved/effective predicate landed inside `get_chunks_by_ids`
  (required `as_of`; reuses `_apply_filters`), so the synthesis-time check cannot drift from
  the pre-retrieval one; `synthesize_answer` passes `now` (same UTC clock basis as
  `role_access.py`'s filter construction), `hybrid_search` passes `filters.as_of`. Both flip
  dimensions were pinned by tests that wrongly synthesized pre-fix; total loss fails closed
  into `NO_APPROVED_SOURCE` + `[]` citations (AUD-C-11), asserted end to end.
- **REQ-44/DRIFT-74:** the reason-code sweep is total by **discovery** over every chat-api
  module's copy constants (9 of 10 labels; `ANSWER` the sole evidence-forced exemption,
  self-removing), with a maintained exclusion list whose stale entries fail, and a **three-way**
  enum pin (dict / node-local / no-copy partition the ten — the register's exhaustiveness
  option was wrong in two ways, recorded on the entry). No existing copy violated the widened
  sweep, so the evidence is the recorded old-vs-new vacuity contrast.

**Evidence.** Eight executor mutation controls (A–H) each killed exactly the intended test;
coordinator independently re-ran the four touched test modules (61 passed), performed two of its
own kills (events pass-through → 3 failed; synthesis `as_of=None` → only the window test failed,
proving the two predicates are independently pinned), lint, typecheck. Full gate: 1778 passed /
2 skipped / 1 xfailed. All 12 CI checks green on PR #372.

**Reconciliation applied.** PROJECT_STATE: both rows deleted (counts 23→21, 13→12, 10→9), queue
row 2 deleted and renumbered (18 rows), snapshot header to `67cd708` (gap 21). Register: dated
resolution annotations on both entries — including the rejected-with-cause record for the
exhaustiveness option and the chat-api-only scope note. ARCHITECTURE: untouched (the span
redactor's boundary is not described there; enforcement widened within an existing boundary,
no architecture change). SPEC/DECISIONS/TRACEABILITY: untouched. Frozen Spec deleted.

**Unresolved handoff items.** (1) All three fixes are deploy-gated (UD-1, LB-05). (2) The
reason-sweep guard covers chat-api only; learning-app copy has no equivalent — a candidate
register row if the user wants it. (3) F-09's primary text lives in `docs/archive/`; the
executor correctly quoted the register's rendering instead. (4) Queue row 1 remains RD-01's
Sunday 2026-08-24 confirmation.

**Commits/SHA.** Worktree `1eb0d60`/`ad2178c`/`650a90f` on
`lucasjeongsikpark/narrow-coverage-gaps`; landed as `fb74f38`/`fd6927d`/`67cd708` by PR #372.
