# Incident Response Runbook

S33 Security Hardening (SPEC §6.22 "incident-response drills"). This is the practical
runbook a solo maintainer actually follows during a real incident - not a compliance
document. A live tabletop drill (walking this runbook against a simulated scenario with
no real system impact) is a human-process activity for you to run when convenient; this
document is what you'd follow either way. Written using two real events from this
project's own history as worked examples, not hypotheticals - see D-084 and D-085 for
the full detail behind each.

## Before anything else: what makes IntelliChoice's incidents different

- **Minors are the primary users.** Any incident touching real student/parent data
  warrants a higher bar for care and speed than a typical B2B SaaS incident, even at
  small scale.
- **The PII boundary is the single most important fact to check first.** CLAUDE.md's
  non-negotiable #1: no PII in Postgres, logs, traces, or LLM payloads - MongoDB
  originally, now MySQL (`go.intellichoice.org`'s real database, D-082/D-083) is the
  only store holding names/emails/roles/relationships. This means: a Postgres-only
  incident (e.g. a leaked `RagDocument`, a bug exposing `learning_events` rows) is
  serious but does **not** by itself expose PII - only `*_external_id` references. A
  MySQL-adjacent incident (leaked MySQL credentials, a bug in `MySQLProfileAdapter`,
  unauthorized MySQL access) is the one that can actually expose names/emails/
  relationships. Triage severity accordingly - don't default to "assume the worst"
  without checking which store was actually involved, and don't under-react to a MySQL-
  adjacent incident just because it "sounds like just a config bug."
- **Real credentials now exist** (since S32, D-084) - AWS, RDS, GitHub OIDC, Bedrock. Before
  S32 there was nothing real to leak; that's no longer true.
- **No real CAPTCHA, WAF, or 24/7 monitoring exist yet** (D-002 posture, S33's own
  WAF-deferred carry-over) - you are the entire detection and response capacity. Lean on
  what *does* exist: the AWS Budget alarm (cost anomalies), CloudWatch Logs +
  Container Insights, ECR scan-on-push, the new `security-scan.yml` CI gate (D-089),
  and the Bedrock gateway's own circuit breaker/session budget cap.

## Severity (keep it simple - two tiers, not five)

- **Stop-and-fix now**: anything touching real credentials, real student/parent data
  (MySQL-adjacent), or an actively open unauthenticated path to either. Drop what you're
  doing.
- **Fix this session, don't drop everything**: a real but currently-unexploited gap
  (no live access path exists yet), a cost anomaly within the Budget alarm's ceiling, a
  known-and-accepted risk resurfacing (check DECISIONS.md first - it may already be a
  documented, intentional trade-off, not a new incident; see D-085's `/dev/token`
  finding below for exactly this situation).

## General procedure

1. **Detect.** Where would you actually notice? AWS Budget alarm email, CloudWatch Logs
   (`aws logs tail /ecs/intellichoice-staging-<service> --follow`), GitHub's own
   Dependabot/security-scan.yml alerts (D-089), a user report, or - as happened twice
   in this project's real history - noticing something wrong while doing unrelated work.
2. **Contain.** Stop the bleeding before investigating root cause. For a live credential
   leak: rotate it *first*, ask questions later (see the leaked-credential playbook).
   For an open auth surface: close it (redeploy with the fix, or in a true emergency,
   scale the ECS service to 0 - `aws ecs update-service --desired-count 0` - stops all
   traffic instantly at the cost of downtime).
3. **Eradicate.** Fix the actual source, not just the symptom. Confirm the fix with a
   real test, not just code review (this project's own convention throughout - every
   D-xxx entry above describes verifying the fix, not just writing it).
4. **Recover.** Redeploy, confirm the fixed behavior live, watch logs for a few minutes.
5. **Post-mortem.** Write it up as a DECISIONS.md entry (this project's established
   format - what happened, why, the fix, how it was verified) and a PROGRESS.md
   carry-over if anything's still open. This is not optional busywork - it's the only
   institutional memory a solo project has.

## Playbook: leaked credential

**Real worked example (D-084, S32, 2026-07-22):** `seed_mysql.py`'s own
`print(f"Seeded fixture data into {mysql_url}")` printed the real RDS MySQL master
password (a live Secrets Manager credential) into CloudWatch Logs - and that log output
then also appeared in the session transcript. Found and fixed live, not after the fact.

**Second real worked example (D-310, C1, 2026-08-13) - three ways it differed from the
first, each worth knowing before the next one:**

Running `pgrep -fl` to check whether an `e2e-staging` process was alive echoed that
process's environment, printing both `/dev/token` shared secrets into the session
transcript. Then:

- **The exposure could not be deleted.** Step 2 below assumes a CloudWatch stream you can
  drop. Here the vectors were a **process table** (unscrubbable, gone when the process
  exits) and a **session transcript** (already sent to an API). When the exposure cannot
  be deleted, rotation is the only containment - which makes step 1 more important, not
  less.
- **The vector was documented as safe.** `make e2e-staging` passed the secrets as
  environment assignments and the Makefile asserted they "never [reach] argv, `ps`, or a
  shell history". Measured: **4 process-table lines carried an expanded secret**, because
  npm's `exec` path and Playwright's workers re-expose the inherited environment in their
  process titles. The comment is why nobody checked for ten sessions. **A safety claim in a
  comment is a hypothesis; measure it once.**
- **Rotation was declined, deliberately.** The user's decision, on bounded exposure:
  staging only, production is a separate frozen system, Postgres holds no PII by design,
  and the residual risk is Bedrock spend that the gateway caps. Recorded as a departure
  from step 1's default with its reason, not as an oversight. **The fix went to the source
  instead** - `e2e/config.ts` fetches the secrets itself, so nothing downstream inherits
  them (0 exposed process lines after, verified while token minting still works).

Steps, in this order (rotate before investigating - a live credential is actively
exploitable for as long as it's valid):

1. **Rotate the credential immediately.**
   - RDS master passwords: since D-092 (S33), both RDS instances use
     `manage_master_user_password = true` - AWS auto-rotates every 7 days on its own,
     but you don't have to wait: `aws secretsmanager rotate-secret --secret-id
     <master_user_secret_arn>` forces it immediately. (Before D-092, this was
     `terraform apply -replace=module.rds_mysql.random_password.master` - that
     resource no longer exists; don't reach for the old command.)
   - JWT signing secrets (D-085): `terraform apply
     -replace=random_password.jwt_signing_secret_learning` (or `_chat`) generates a new
     one; requires a redeploy to actually take effect (ECS tasks read it at container
     start, not live).
     **⚠️ `-replace` does not mean "only this resource" - it applies the whole plan.**
     Scope it, every time, or you apply whatever else has drifted while under incident
     time pressure:
     `terraform apply -target=random_password.jwt_signing_secret_learning -replace=random_password.jwt_signing_secret_learning`
     The specific thing that bites here (D-137): a plan against staging routinely wants to
     replace **both `aws_ecs_task_definition`s**, because `deploy-staging.yml` registers
     revisions outside Terraform. Replacing them does not disturb the running service -
     `lifecycle.ignore_changes = [task_definition]` holds - but it makes *Terraform's*
     revision each family's **latest**, and CI's next deploy resolves the family name to
     the latest and inherits its shape. So a bare apply silently changes what the next
     deploy is built from, and if `learning_api_image_tag` in `terraform.tfvars` is stale
     it stages a rollback of whatever fix landed after it. **Check that tag against the
     running image before any apply here** (`aws ecs describe-services` → the revision's
     image), and note that `-target`ing the ecs-service *module* is not narrow enough:
     the task definition lives inside it.
   - Any other secret: rotate at the source (AWS console/CLI), then redeploy anything
     that reads it.
2. **Delete the exposure**, not just the credential: the specific CloudWatch log
   stream/group containing the leaked value
   (`aws logs delete-log-stream` or filter+redact if the stream has other needed data).
   If it appeared in a chat transcript, terminal scrollback, or anywhere else outside
   AWS, treat those as compromised too.
3. **Fix the source.** Find every place that could print/log a raw secret and stop it -
   `sqlalchemy.engine.make_url(...).render_as_string(hide_password=True)` is the
   pattern this codebase already uses (`seed_mysql.py`). Grep for other `print`/`log`
   calls near anything secret-shaped before considering this done.
4. **Check for actual misuse during the exposure window** - CloudTrail
   (`aws cloudtrail lookup-events`) for the credential's ARN/principal, RDS/Secrets
   Manager access logs if enabled. At this project's real scale (D-084's `~1,000 MAU`
   posture), this is usually fast to check and worth doing even when misuse seems
   unlikely.
5. **Re-verify clean** - confirm the fixed code path no longer prints/logs the secret,
   on a real run, not just by reading the diff.
6. **Write the DECISIONS.md entry.** Root cause, exact remediation steps taken in order,
   re-verification. D-084's own entry is the template.

## Playbook: authentication/authorization bypass discovered

**Real worked example (D-085, S33, 2026-07-23):** `/dev/token` (a dev-only stand-in for
`go.intellichoice.org`'s real auth, meant to 404 outside `environment=="dev"`) was
reachable on the real staging ALB, because `terraform.tfvars` had deliberately set
`app_environment = "dev"` mid-S32 for legitimate real-browser testing - a real,
documented, user-approved trade-off, not an unknown bug. **The first step matters as
much as the fix**: check DECISIONS.md before treating this as a fresh incident. If it's
already a documented, intentional, temporary trade-off (as this one was), the response
is "revert per the trade-off's own stated condition," not "emergency incident response."
If it's genuinely new, treat it as stop-and-fix-now.

1. **Check DECISIONS.md/PROGRESS.md first** - `grep -i` the relevant surface/endpoint
   name. A surprising amount of "found a bug" turns out to be "found a documented,
   deliberate trade-off whose revert condition just arrived" (exactly what happened
   here). This changes the response from emergency to routine.
2. **Assess real exploitability**: is this reachable *right now* on the real deployed
   URL, or only in a code path that isn't live yet? Check the actual live
   `terraform.tfvars`/deployed environment variables, not just the code.
3. **Close the surface** - prefer the most surgical fix (D-085's pattern: an
   independent, defense-in-depth second gate, not just flipping the one flag that
   caused the original exposure - a second guard makes the exact same mistake harder to
   repeat).
4. **Redeploy** and confirm the surface is actually closed against the live URL (a
   direct `curl`/browser check against the real ALB/CloudFront URL, not just a passing
   test suite).
5. **Write the DECISIONS.md entry**, same as the credential playbook.

## Playbook: suspected unauthorized data access

1. Identify which store: Postgres-only (see the PII-boundary note above - serious, but
   not a PII exposure by itself) vs. MySQL-adjacent (is a PII exposure).
2. For a MySQL-adjacent incident: this is the one that would need real user
   notification if confirmed. At this project's pre-launch stage, "real users" mostly
   means the fixture/test identities in `mysql_fixtures.py`, not real students/parents -
   confirm which is actually the case before assuming a notification obligation exists.
   Real launch changes this calculus entirely (see the Phase 0 legal/policy track in
   ROADMAP.md - Privacy Notice, retention policy, etc. - `counsel review is a launch
   gate`, not something to improvise here).
3. Contain: revoke/rotate whatever credential or access path allowed it (see the
   credential playbook).
4. Check `interrupt_approvals`/`mcp_tool_calls` audit tables (already built, S14+) for
   anything unexpected in the relevant time window - this is real, already-persisted
   audit data, not something you'd need to reconstruct from logs.
5. **To answer "did PII actually reach a store?", both scanners take a window and fail
   loudly rather than reporting clean when they cannot see** (D-129):
   `make scan-traces HOURS=<n>` and
   `make scan-logs START=<iso> END=<iso>` - same patterns, same matcher, needles sourced
   from `mysql_fixtures.py` so they cannot drift from the fixtures. Two cautions for an
   incident: an out-of-retention window **fails** rather than answering "nothing there"
   (logs are 30-day, X-Ray shorter), and a clean result over an idle window is close to
   meaningless because ~97% of traces are health checks (AUD-F-30) - scan the window that
   contains the *suspect* traffic and check the authenticated request count in it.

## Playbook: cost anomaly (Bedrock or otherwise)

CLAUDE.md's own rule: cost bugs are real bugs. What's already built to catch this:

- The AWS Budget alarm (`terraform/modules/observability`) - the first real signal,
  emails when spend crosses the configured threshold.
- `ResilientBedrockGateway`'s per-session `session_budget_cents` cap and circuit breaker
  (`bedrock_circuit_failure_threshold`/`bedrock_circuit_cooldown_s`) - already limits
  any *single* session's runaway spend; a cost anomaly is more likely many sessions
  each behaving normally, or the new S33 global rate limiter (D-087) not being enough
  against a determined abuser (it's a stopgap, not a WAF - see that decision's own
  caveat).

Steps: check the Budget alarm's linked Cost Explorer view for which service actually
spiked, check CloudWatch Logs for `bedrock_call` entries clustering unusually (real
volume, or a retry storm from a single failing session), consider temporarily lowering
`bedrock_session_budget_cents` or scaling `desired_count` to 0 if spend is actively
runaway and the source isn't yet clear.

## Playbook: service outage / database failure

Out of this runbook's depth on purpose - S34 (Load Testing and Production Readiness,
SPEC §6.23) is where failure drills (DB failover, Bedrock throttling, MCP outage) and
rollback triggers get built and exercised for real. This runbook's job is detection and
first response, not a full DR procedure: check ECS service health
(`aws ecs describe-services`), RDS status (`aws rds describe-db-instances`), and the
`/healthz` endpoints on both apps first: they'll usually tell you which layer failed.

## After the incident

Every real incident in this project's history became a DECISIONS.md entry (D-084's
credential leak, D-085's auth-bypass finding) - keep doing that. It's the only
institutional memory a solo project has, and future-you (or a future session) will need
it exactly the way this runbook needed D-084/D-085 to write real, grounded playbooks
instead of generic ones.
