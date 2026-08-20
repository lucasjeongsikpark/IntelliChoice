> **ARCHIVED 2026-08-20.** Point-in-time audit evidence (reconciliation, 2026-08-19/20) — **do not treat as current state.**
> **Current state:** `docs/PROJECT_STATE.md`
> **Reason:** resolved remediation record — D-310's rotation **executed 2026-08-20T03:20:57Z** (`:66`; the step-7d instruction's "2026-08-18" is this file's *CloudTrail access-review* window at `:45`, not the apply); never an active exposure; the `ps`-visibility residual is unmeasured, not cleared. **Superseded by:** the 166-entry register at `docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md`.

# REMEDIATION_D310_ROTATION.md — rotation of the D-310-exposed staging token secrets

**Date:** 2026-08-20 (all times UTC). **Authorized by:** user approval of the remediation plan,
with six additional safeguards, after the Phase 3B-1 finding RD-02. **Executed by:** the audit
session, AWS profile `jeongsik-staging-admin`, us-east-1. **No secret value was ever printed,
logged, passed as a command argument, or written to any artifact** — including this one.

## 1. What was remediated

The two `/dev/token` staging shared secrets, exposed on 2026-08-13 (D-310,
`docs/DECISIONS.md:22172-22228`: a `pgrep -fl` liveness check echoed the process environment
into a session transcript already sent to an LLM API, and four process-table lines carried the
expanded values for the whole `make e2e-staging` run):

| Secret name | ARN suffix | Terraform address |
|---|---|---|
| `intellichoice-staging/learning-api/staging-token-shared-secret` | `…-vo3lst` | `random_password.staging_token_shared_secret_learning` + `aws_secretsmanager_secret_version.staging_token_shared_secret_learning` |
| `intellichoice-staging/chat-api/staging-token-shared-secret` | `…-oT74Ug` | `random_password.staging_token_shared_secret_chat` + `aws_secretsmanager_secret_version.staging_token_shared_secret_chat` |

Explicitly untouched: the adjacent `jwt_signing_secret_*` resources, the AWS-managed `rds!…`
secrets, `LANGSMITH_API_KEY`, and every other credential. D-310's own record scopes the
exposure to the two secrets above.

## 2. Pre-remediation state (preserved)

- The canonical pre-remediation snapshot is `DEPLOYED_INFRA_DRIFT_REGISTER.md` RD-02
  (observed 2026-08-20T00:07Z) and `DEPLOYED_INFRA_STATE_EVIDENCE.md` SEC-26 — left unmodified
  except RD-02's dated resolution addendum.
- Re-verified immediately before remediation (2026-08-20T02:24Z, `describe-secret`, metadata
  only): both secrets held exactly one version (the original terraform-created one, `AWSCURRENT`),
  `CreatedDate` = `LastChangedDate` = 2026-07-24T21:06:19Z, `LastRotatedDate: None`,
  `LastAccessedDate` 2026-08-18 (learning) / 2026-08-17 (chat). Consumers: ECS-injected env vars
  `LEARNING_STAGING_TOKEN_SHARED_SECRET` (learning-api) / `CHAT_STAGING_TOKEN_SHARED_SECRET`
  (chat-api), floating on `AWSCURRENT`, read at process start.

## 3. Step 0 — CloudTrail access review (gate: PASSED)

`lookup-events` on both secrets:

- **GetSecretValue since 2026-08-13:** 8 events, all accounted for — 5 by
  `jeongsik-staging-admin` via Terraform 1.15.8 during the known 2026-08-18T20:19–20:21Z apply,
  and 3 by the Amazon Fargate Agent from private IPs (10.0.x.x) at task startup on
  2026-08-18/19 (the expected ECS injection path). **No unexpected principal, IP, or user agent.**
- **PutSecretValue since creation:** exactly 2 events, both 2026-07-24T21:06:19Z by Terraform —
  the creation writes, matching `LastChangedDate` exactly. **UpdateSecret / DeleteSecret /
  RestoreSecret: zero.**

Conclusion: the AWS-side read history shows only known consumers during the exposure window.
(What a transcript-side reader might have done off-AWS is unknowable; that risk is what the
rotation closes.)

## 4. Rotation (targeted Terraform apply)

- Plan: `terraform plan -replace=random_password.staging_token_shared_secret_learning
  -replace=random_password.staging_token_shared_secret_chat
  -target=aws_secretsmanager_secret_version.staging_token_shared_secret_learning
  -target=aws_secretsmanager_secret_version.staging_token_shared_secret_chat -out=rotate-d310.tfplan`
  → `Plan: 4 to add, 0 to change, 4 to destroy.`
- **Safety gate (user safeguard): PASSED** — machine-readable review of `terraform show -json`
  (addresses and actions only, no values) showed exactly the four intended resources, all
  `delete/create`, nothing else.
- Apply completed 2026-08-20T03:20:57Z. Post-apply metadata: both secrets show
  `LastChangedDate` 2026-08-20T03:20:57Z with a single new terraform version on `AWSCURRENT`.
  **The old exposed versions were destroyed, not deprecated** — no staged copy of the exposed
  values remains in Secrets Manager. Rollback, if ever needed, is a fresh rotation, never a
  restore of the exposed value.
- The plan file `rotate-d310.tfplan` was treated as sensitive throughout (gitignored by the
  repo's existing `*.tfplan` rule, never committed, never shown) and **deleted after completion**
  (deletion verified).

## 5. Service restart and drain (gate: PASSED)

- `aws ecs update-service --force-new-deployment` on both services at 2026-08-20T03:21Z;
  `aws ecs wait services-stable` returned at 03:24Z.
- Drain verified: each service has exactly one deployment (`PRIMARY` / `COMPLETED`), running
  counts 2/2 (learning) and 1/1 (chat), and **every running task started 03:22Z — after the
  03:20:57Z rotation**. No pre-rotation task survived.

## 6. Behavioral verification (gate: PASSED)

In-process probe (boto3 fetch into memory → HTTPS `POST /dev/token` with the
`X-Staging-Token-Secret` header, via CloudFront since the ALB accepts only CloudFront-originated
traffic; the value never appeared in argv, logs, or output — the exact D-310 vector this
procedure was designed not to recreate). Per the user's safeguard, the old exposed value was
**not** retrieved or replayed; the negative probes used a wrong literal and a missing header:

| App | new secret | wrong literal | no header |
|---|---|---|---|
| learning (`d35dfnjzmgrm01.cloudfront.net`) | **200** | 404 | 404 |
| chat (`d222glidpp4azv.cloudfront.net`) | **200** | 404 | 404 |

Fail-closed behavior (404 indistinguishable from an absent route) confirmed intact post-rotation.

## 7. Post-rotation drift check (gate: PASSED)

Full read-only `terraform plan -detailed-exitcode` after the targeted apply:
**exit 0 — "No changes. Your infrastructure matches the configuration."** The targeted apply
neither caused nor hid residual drift.

## 8. Consumers after rotation

- **ECS services:** restarted, verified above.
- **Operator workflows** (`e2e/config.ts`, `make load-staging-learning`,
  `scripts/measure_hint_delivery.py`): fetch the value by id per run — self-healing, no action.
- **CI:** holds no copy by design (`deploy-staging.yml:532-537` runs only negative probes) —
  rotation-immune, no action.
- **Browser `localStorage`** (`intellichoice.staging_token_secret` on any machine where a
  human pasted it): the old copy is now a **dead credential** (fails with 404). Anyone using the
  dev-login screen's staging-secret field must re-paste the current value (fetch by id).
  This is the one manual follow-up.

## 9. Residual notes

- D-310's decline stands as the historical record; this remediation supersedes it operationally
  (RD-02 addendum dated 2026-08-20). The `main.tf:355-360` S44 plan (delete these secrets
  entirely when real auth lands) is unchanged.
- The transcript that captured the old values still exists wherever transcripts are retained;
  the values it contains are now worthless.
- Not remediated here (out of scope, unchanged): the D-310-adjacent hygiene items noted in
  Phase 3A/3B-1 — `make load-staging-learning`'s docker env pass-through was never re-measured
  for `ps` visibility, and `e2e/README.md:16-17` still documents the pre-D-310 export shape.
