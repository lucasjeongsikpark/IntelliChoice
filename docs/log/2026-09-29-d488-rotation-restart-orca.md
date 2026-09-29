# 2026-09-29 — UD-14 and UD-15 answered; restart-on-rotation built, applied and proven live (D-488)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-488.

"proceed" on an empty queue → asked the user the two nearest decisions: UD-14 (rotation) and
UD-15 (memory ceiling). Answers: automate restart-on-rotation; cap the consolidation payload to
the 11 most recent facts. UD-14 first (rotation due 2026-10-02).

Coordinator pre-verified the AWS-side assumption from CloudTrail (both 2026-09-24 rotations
emitted `RotationSucceeded` as a service event with the ARN in `SecretId`). Sixth Orca task
(`run_97e72c1a271b`, Opus 5.5 high, receipt matched): the executor returned two conflicts
correctly — the archive provider missing from the lock (Revision 1) and the targeted plan
pulling in three drifted task definitions through `service_name` (Revision 2: constructed
names; drift reported, not absorbed). Coordinator: validate/fmt clean, targeted plan 8/0/0,
handler ruff + 3 tests, lint/typecheck green; targeted apply 8 added; on-demand Postgres
rotation at 20:33:00Z → Lambda at +105 s, both rollouts complete in 195 s, tasks replaced,
0 `InvalidPasswordError`. Worker released.

Handoff: UD-14 closed (D-488); `ARCH-34-REVISION-DRIFT` re-observed in Terraform state and
recorded in §8 (next untargeted apply must reconcile first). UD-15's Frozen Spec
(`tasks/memory-ceiling-bound.md`) is written and dispatches after this lands. Repository
changes (module, wiring, lock, docs) uncommitted at this entry.
