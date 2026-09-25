# 2026-09-25 (third entry) — D-476 landed and deployed (`gha-63f9d59f0ddc`, D-478); CI flake recurred and was re-diagnosed (D-477)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-477, D-478.

User: "let's do it" (land + deploy, the D-475 sequence). `land/d476-cache-billing` → PR #475.
One required check red: the real-uvicorn SSE harness test, `KeyError: 'phase'` — D-451's n=1
signature, now n=2. Read the test instead of the old note: `finalize` there is the
`POST /exam/finalize` **HTTP body**, not a frame, so the endpoint returned a 409/422/503 after
an unchecked setup POST; the CI log carries no server line because the uvicorn thread logs into
pytest's closed capture stream. Rerun green; merged by rebase as `63f9d59`. Recorded as D-477
with the corrected signature and queued (`SSE-HARNESS-FINALIZE-FLAKE`, last row) — the fix is
diagnosability (status asserts with bodies; a capture-proof log sink), never a frame-wait.

Deploy run 36198370659, 22:47 → 23:07 UTC, all gates green, rollback skipped. Post-deploy:
learning `:157` 2/2, chat `:155` 1/1, ops `:149`, all tasks on `gha-63f9d59f0ddc`, `/me` 401,
SPAs 200, 0/0/0 failure signatures. Docs reconciled in a follow-up PR (this entry rides it).
Handoff: queue row 1 is `OBSERVABILITY-TRACE-GAPS`; next rotation 2026-10-02 (UD-14 open).
