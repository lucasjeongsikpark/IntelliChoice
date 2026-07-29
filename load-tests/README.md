# Load testing and failure drills (S34, SPEC §6.23)

Most of this runs against the **local docker-compose stack**, not the real
`intellichoice-staging` AWS environment - the staging SSO session was expired for all of
S33 and stayed expired into S34, which is why it was built that way. Real load/failure
testing against staging was a carry-over in the same posture S33 left the ZAP baseline
scan and backup-restore test in.

**Exception, added S43:** `k6/chat_qa_staging.js` runs against the deployed stack and is
criterion 7's live-staging leg. Read its header before comparing its numbers to
`chat_qa.js`'s - the two thresholds (20s vs 1s) measure genuinely different things, and
conflating them is the mistake D-115 §11 had to undo.

## What SPEC §6.23 asks for vs. what this project actually has

SPEC §5.33/§6.23 were written against the EKS/Aurora/HPA/SQS architecture the spec
describes. D-004/D-082/D-084 diverged from that for a solo-maintainer ~1,000-MAU target:
this is **ECS Fargate**, not EKS (no HPA - `desired_count` is a fixed `1` in staging, no
autoscaling resource exists at all), RDS **single-AZ** in staging (`multi_az=false` - no
live Multi-AZ failover target to test), **MySQL not MongoDB** (D-082/D-083), and **no SQS
queue or separate MCP-gateway service** anywhere in the codebase (Gmail/Calendar/Maps/
YouTube tool calls are in-process adapter functions inside the two apps, not a queued
microservice). Two of §6.23's bullets are translated rather than built literally:

- "MongoDB timeout" -> tested as a MySQL connection-loss drill instead (see
  `drills/db_connection_loss.sh` - Postgres-focused, but the same drill exercises the
  `MySQLProfileAdapter` path too, since `/readyz` pings both).
- "Queue backlog" -> not applicable; there is no queue in this architecture. Not built.

## What's here

| File | SPEC §6.23 target | What it tests |
|---|---|---|
| `loadtest_fixtures.py` | ">1,000 students" (local proxy) | Seeds/cleans up N disposable `loadtest-student-N` MySQL rows so k6 VUs are distinct students, not one student under concurrent contention |
| `k6/learning_sessions.js` | ">100 concurrent learning sessions" | Real pre-exam flow (dev-token -> create -> select student -> select topic -> answer every item) per VU |
| `k6/chat_qa.js` | "concurrent Bedrock requests" (local proxy) | Concurrent chat-api Q&A turns; local dev server uses `MockBedrockProvider` by default - proves the async request path holds up under concurrency, not real Bedrock throughput |
| `k6/chat_qa_staging.js` | §2.6 criterion 7, live-staging leg | The same turn against the **deployed** stack through CloudFront: real ALB, real Bedrock, real corpus. Guest turns, no secrets. `make load-staging-chat` |
| `sse_load.py` | ">100 SSE connections" | Holds N concurrent `GET .../stream` connections open (k6 has no native SSE support, hence a separate script) |
| `drills/db_connection_loss.sh` | "Database failover" (translated - see above) | Stops/restarts the local Postgres container mid-load, confirms clean failure + automatic recovery |

Bedrock throttling and external-tool-outage drills are plain pytest tests, not scripts
here - see `packages/adapters/tests/test_bedrock_gateway.py` (concurrency case) and the
relevant fake-provider test for the tool-outage case; both are deterministic and need no
live infrastructure.

## Running

Local prerequisites: `make up` (Postgres + MySQL), `make db-upgrade`, `make seed`,
`make curriculum-load`, then `make dev-learning` / `make dev-chat` running natively
(matches the real deployment - single uvicorn process, no `--reload` for load testing).

```bash
# 1. Seed distinct load-test students (MySQL)
uv run python load-tests/loadtest_fixtures.py --count 150

# 2. k6 scenarios (grafana/k6 Docker image - no local k6 install needed).
#    host.docker.internal reaches the host's native uvicorn process from inside the
#    k6 container (works out of the box on Docker Desktop for Mac; on Linux add
#    --add-host=host.docker.internal:host-gateway).
docker run --rm -i -e BASE_URL=http://host.docker.internal:8001 -e VUS=150 -e DURATION=2m \
  grafana/k6 run - < load-tests/k6/learning_sessions.js

docker run --rm -i -e BASE_URL=http://host.docker.internal:8002 -e VUS=150 -e DURATION=2m \
  grafana/k6 run - < load-tests/k6/chat_qa.js

# 3. SSE connections
uv run python load-tests/sse_load.py --count 150 --hold-seconds 30

# 4. DB connection-loss drill (separate terminal, app already running)
./load-tests/drills/db_connection_loss.sh

# 5. Clean up the synthetic students afterward
uv run python load-tests/loadtest_fixtures.py --cleanup
```

Against live staging (no local stack, no fixtures, no secrets - guest turns):

```bash
make load-staging-chat                    # 5 VUs x 14 iterations = 70 grounded turns
VUS=5 ITERATIONS=20 make load-staging-chat
```

## Real findings from S34 (see DECISIONS.md for the full writeup)

- `/healthz` never checked database connectivity - the ALB target group health-checked
  it, so a real DB outage would have kept the ALB routing user traffic to a task that
  could only 500. Fixed with a new `/readyz` (checks Postgres + MySQL, `/healthz` stays
  liveness-only) and staging's target-group health check now points at `/readyz`.
- See DECISIONS.md for whatever the k6/SSE/drill runs themselves turned up.
