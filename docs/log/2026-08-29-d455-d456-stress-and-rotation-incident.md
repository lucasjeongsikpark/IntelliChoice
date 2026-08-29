# 2026-08-29 — the user-ordered stress test: a live incident found and mitigated, and the ceilings measured (D-455, D-456)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgments:
> D-455 (the incident), D-456 (the measurement).

## The incident (D-455)

The first 25-VU run failed 33.57% of requests on a system every monitor called healthy.
Triage: VUS=1 clean (the discriminator), app access logs showed real 500s, plain-text
tracebacks named `InvalidPasswordError`, and `describe-secret` showed **both RDS managed
master secrets rotated after the D-448 tasks started** (Postgres 08-28T06:15Z). ECS resolves
the secrets once at task start; pooled connections survive rotation; new ones don't. A month
of frequent deploys had masked the defect. Mitigated live: forced redeploys of both services;
5 VUs went from 10% errors to 0.00% with all answers. Durable posture → **UD-14**; the next
rotation (≈ 09-04) re-breaks staging without a restart — now §8's first bullet and an
INCIDENT_RESPONSE playbook entry. Second defect found inside the first: the 500s emit **no
JSON ERROR line** → queued as `SILENT-500S`.

## The measurement (D-456)

Learning: **error-free through 100 concurrent** (warm p95 3.03 s @25 vs D-129's 2.75 s;
8.8–10.7 s @50–100, autoscaled to 3 tasks) — load becomes queueing, never failures. Chat:
error-free at 5 guests (p95 12.0 s); at 10 the shared anonymous rate-limit bucket 429s by
design (all 90 failures; zero 5xx) — WORK-44 #2's accepted limiter, not capacity.
Spend: cents (the learning path makes no model calls; chat's 210 turns moved the cost counter
~1¢ on the observed task). The user's stress order is recorded on UD-2 as conduct-answering
the stress-spend slice only.

## Method notes

Three near-findings died on evidence before filing: the ALB-metrics propagation lag (read
"0 target 5xx" too early and briefly exonerated the app), plus the earlier timezone-bucket
and dimensionless-query snares. The honest sources were the app access logs and the raw
tracebacks.
