.PHONY: up down dev dev-observability test lint typecheck dev-learning dev-chat dev-learning-web dev-chat-web seed curriculum-load question-gen-run question-gen-authored question-gen-preflight question-review question-review-rejected question-export knowledge-load knowledge-reembed youtube-sync webcontent-sync org-load chat-suggestions-load chat-purge memory-consolidate db-upgrade db-downgrade db-revision security-scan-staging e2e e2e-install e2e-staging e2e-typecheck load-staging-chat load-staging-learning scan-traces scan-logs scheduler-evidence tfvars-floor-check

up:
	docker compose up -d

down:
	docker compose down

# Runs db + both backends + both frontends from one terminal (scripts/dev-up.sh);
# Ctrl+C stops the four app processes.
dev:
	./scripts/dev-up.sh

# Same, plus the otel-collector/jaeger/prometheus/grafana stack with tracing enabled.
dev-observability:
	./scripts/dev-up.sh --observability

seed:
	uv run python -m intellichoice_adapters.seed.seed_mysql

curriculum-load:
	uv run python -m intellichoice_curriculum.loader

# Extra CLI arguments go through QUESTION_GEN_ARGS rather than by editing these targets
# (D-194), e.g. to author three candidates for one skill at two tiers in a fresh id range:
#
#   make question-gen-authored QUESTION_GEN_ARGS="\
#     --topic-id linear_equations --skill-id linear_both_sides \
#     --difficulty 3 --difficulty 4 --candidates-per-slot 3 \
#     --seed-offset 40000 --run-budget-cents 100"
QUESTION_GEN_ARGS ?=

# D-224: this used to be the unqualified "run the generator" target *and* to default to
# --mode shape, whose output `_servable()` filters out of every serving read (D-210) - so
# the obvious target was the one that could only waste money. It now runs the authored
# mode, which is what every servable item in the bank came through; `question-gen-authored`
# below is kept as the explicit name.
question-gen-run:
	uv run python -m intellichoice_curriculum.pipeline_cli $(QUESTION_GEN_ARGS)

question-gen-authored:
	uv run python -m intellichoice_curriculum.pipeline_cli --mode authored $(QUESTION_GEN_ARGS)

# Free: says which models a run would use, which slots and template ids it would claim,
# and its spend ceiling - calling nothing and writing nothing. Run before every paid batch;
# a paid run now refuses to start if it fails. Add --dry-run to list every planned slot.
question-gen-preflight:
	uv run python -m intellichoice_curriculum.pipeline_cli --mode authored --preflight \
		$(QUESTION_GEN_ARGS)

question-review:
	uv run python -m intellichoice_curriculum.review_cli

# D-195: read-only. Prints rejected candidates with the content that was rejected, which
# before D-195 was discarded - a pilot that rejects every candidate otherwise leaves
# nothing to review. Has no approve path and builds no gateway, so it cannot spend.
# Narrow with QUESTION_REVIEW_ARGS='--planned-id authored-linear_equations-d4-400400'.
QUESTION_REVIEW_ARGS ?=
question-review-rejected:
	uv run python -m intellichoice_curriculum.review_cli --rejected $(QUESTION_REVIEW_ARGS)

# D-190: the last step of the authoring workflow. Until this runs and its diff is
# committed, approval exists only as a row in whatever database was reviewed against, and
# no other environment has the content.
question-export:
	uv run python -m intellichoice_curriculum.export_cli

knowledge-load:
	uv run python -m intellichoice_knowledge.ingest_cli

# AUD-C-16: re-embeds every rag_chunks row whose embedding provenance doesn't match the
# configured provider/model (NULL provenance counts as a mismatch). Idempotent - a
# current corpus is a no-op. chat-api /readyz fails closed until this has run.
knowledge-reembed:
	uv run python -m intellichoice_knowledge.reembed_cli

youtube-sync:
	uv run python -m intellichoice_youtube.sync_cli

webcontent-sync:
	uv run python -m intellichoice_webcontent.sync_cli

org-load:
	uv run python -m intellichoice_webcontent.org_load_cli

chat-suggestions-load:
	uv run python -m chat_api.services.suggestions_seed_cli

chat-purge:
	uv run python -m learning_api.services.tutor_chat_purge_cli

retention-purge:
	uv run python -m learning_api.services.retention_purge_cli

memory-consolidate:
	uv run python -m intellichoice_memory.consolidate_cli

db-upgrade:
	cd packages/db && uv run alembic upgrade head

db-downgrade:
	cd packages/db && uv run alembic downgrade -1

db-revision:
	cd packages/db && uv run alembic revision --autogenerate -m "$(m)"

test:
	uv run pytest

lint:
	uv run ruff check .

typecheck:
	uv run pyright

dev-learning:
	uv run uvicorn learning_api.main:app --reload --port 8001

dev-chat:
	uv run uvicorn chat_api.main:app --reload --port 8002

dev-learning-web:
	cd apps/learning-web && npm install && npm run dev

dev-chat-web:
	cd apps/chat-web && npm install && npm run dev

# S39 (AUD-F): browser-driven journey audit. Playwright starts both APIs and both vite
# dev servers itself, so the only prerequisite is `make up` (Postgres + MySQL) plus a
# migrated/seeded database. Console and network capture from every run lands in
# e2e/artifacts/ (gitignored) - journeys.jsonl is the greppable record.
e2e-install:
	cd e2e && npm install && npx playwright install chromium

e2e:
	cd e2e && npx playwright test

# Same suite against the real staging CloudFront distributions. `/dev/token` is
# secret-gated there (D-097), so the harness mints tokens out of band and seeds
# localStorage. The target fetches both secrets itself - see the comment above the recipe.
#
# S42: the two URLs are set here, and that is the fix, not a convenience. `E2E_TARGET=
# staging` alone does NOT retarget the browser - `config.ts` defaults LEARNING_WEB/
# CHAT_WEB to localhost regardless of target, and only `LEARNING_WEB_URL`/`CHAT_WEB_URL`
# move them. So this target used to run the whole staging suite against localhost:5173,
# where nothing was listening: 2 passed, everything else failed on ERR_CONNECTION_REFUSED.
# It had never been run, which is why criterion 3's staging half stayed open.
# Domains match deploy-staging.yml's LEARNING_CF_DOMAIN/CHAT_CF_DOMAIN.
STAGING_LEARNING_WEB_URL ?= https://d35dfnjzmgrm01.cloudfront.net
STAGING_CHAT_WEB_URL ?= https://d222glidpp4azv.cloudfront.net

# Fetches both `/dev/token` secrets (D-097) the way load-staging-learning does, for the
# reason D-132 recorded: without them e2e/config.ts defaulted each to "", mintToken sent
# no header, and all seventeen authenticated journeys failed together on a 404 that looks
# like an application fault. Same length sanity check as the load target; the values are
# passed as environment assignments rather than arguments, so they land in the child's envp
# and never in argv, `ps`, or a shell history, and the recipe is `@`-prefixed so make does
# not echo the fetch. config.ts now also refuses to start a staging run with either empty.
# E2E_ARGS forwards a spec path or `--repeat-each`, e.g.
#   make e2e-staging E2E_ARGS="tests/learning/narrative-refresh.spec.ts"
e2e-staging:
	@LEARNING_SECRET="$$(aws $${AWS_PROFILE:+--profile $$AWS_PROFILE} secretsmanager get-secret-value \
	    --secret-id intellichoice-staging/learning-api/staging-token-shared-secret \
	    --query SecretString --output text)" && \
	  CHAT_SECRET="$$(aws $${AWS_PROFILE:+--profile $$AWS_PROFILE} secretsmanager get-secret-value \
	    --secret-id intellichoice-staging/chat-api/staging-token-shared-secret \
	    --query SecretString --output text)" && \
	  if [ $${#LEARNING_SECRET} -lt 10 ] || [ $${#CHAT_SECRET} -lt 10 ]; then \
	    echo "FATAL: a token secret came back too short to be real - refusing to run"; exit 1; \
	  fi && \
	  cd e2e && E2E_TARGET=staging \
	    LEARNING_WEB_URL=$(STAGING_LEARNING_WEB_URL) \
	    CHAT_WEB_URL=$(STAGING_CHAT_WEB_URL) \
	    STAGING_TOKEN_SECRET_LEARNING="$$LEARNING_SECRET" \
	    STAGING_TOKEN_SECRET_CHAT="$$CHAT_SECRET" \
	    npx playwright test $(E2E_ARGS)

e2e-typecheck:
	cd e2e && npx tsc --noEmit

# S43 / criterion 7's live-staging leg. Distinct from load-tests/k6/chat_qa.js, which
# measures the local mock-backed server and keeps its p(95)<1000 - see the scenario's own
# header for why the two thresholds are different numbers on purpose (D-115 §11). Guest
# turns, so no secrets are needed and none can leak into a log. Same CloudFront domain as
# e2e-staging.
load-staging-chat:
	docker run --rm -i \
	  -e BASE_URL=$(STAGING_CHAT_WEB_URL) \
	  -e VUS=$${VUS:-5} -e ITERATIONS=$${ITERATIONS:-14} \
	  grafana/k6 run - < load-tests/k6/chat_qa_staging.js

# S43 continuation / criterion 7's learning-app leg. Unlike the chat leg this one is
# authenticated, so it needs the staging `/dev/token` secret (D-097) - fetched here rather
# than stored anywhere, and passed to the container as a bare `-e NAME` pass-through so the
# value never appears in the docker command line (and so never in `ps` or a shell history).
# The API shares the SPA's CloudFront domain on staging (D-084 same-origin), so BASE_URL is
# the same host e2e-staging uses.
load-staging-learning:
	@STAGING_TOKEN_SECRET_LEARNING="$$(aws $${AWS_PROFILE:+--profile $$AWS_PROFILE} secretsmanager get-secret-value \
	    --secret-id intellichoice-staging/learning-api/staging-token-shared-secret \
	    --query SecretString --output text)" && \
	  if [ $${#STAGING_TOKEN_SECRET_LEARNING} -lt 10 ]; then \
	    echo "FATAL: the token secret came back too short to be real - refusing to run"; exit 1; \
	  fi && \
	  export STAGING_TOKEN_SECRET_LEARNING && \
	  docker run --rm -i \
	    -e BASE_URL=$(STAGING_LEARNING_WEB_URL) \
	    -e STAGING_TOKEN_SECRET_LEARNING \
	    -e VUS=$${VUS:-5} \
	    grafana/k6 run - < load-tests/k6/learning_sessions_staging.js

# S39 continuation (D-104): §2.6 criterion 9's trace half. Runs a positive control over
# all 20 patterns before it will report anything, and FAILS on zero traces scanned - an
# empty trace store certified "no PII" for the first hour of this session's tracing
# (AUD-F-12), which is the false negative this target exists to make impossible.
# boto3 cannot read the CLI's `aws login` cache without botocore[crt], hence the export.
scan-traces:
	eval "$$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
	  uv run python -u scripts/scan_xray_pii.py --hours $${HOURS:-6}

# Criterion 9's *log* half, which until now rested on S38's one-off CLI pipeline over guest
# traffic only. Same patterns and same matcher as scan-traces, on purpose - D-104 §4's rule is
# that a PII floor is per-store and is not inherited, and a second hand-rolled detector would
# need its own proof. Takes a window rather than only a lookback, so a scan can be pinned to
# the authenticated load run that produced the interesting traffic:
#   make scan-logs START=2026-07-30T21:38:00Z END=2026-07-30T21:40:00Z
scan-logs:
	eval "$$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
	  uv run python -u scripts/scan_logs_pii.py --minutes $${MINUTES:-60} \
	    $${START:+--start $$START} $${END:+--end $$END}

# Criterion 6's read, per job (D-114 §3). Read-only. Exists because the hand reading has been
# wrong twice in opposite directions and both errors were in the instrument: D-135 §3 read
# daily buckets offset from midnight and saw a broken clock that was not broken, then recorded
# per-job counts as if AWS/Scheduler had a per-schedule dimension - it does not, so the weekly
# job's count was an inference that happened to be false. This target computes the expected
# firings from each schedule's own expression and creation time, attributes the group-level
# metric by 5-minute bucket (refusing to attribute at all if two enabled schedules could
# share one), and confirms execution independently from the ops-task log group behind a
# positive control. Exit code follows the weakest job, so 08-02-style reads have an answer.
scheduler-evidence:
	eval "$$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
	  uv run python -u scripts/read_scheduler_evidence.py --days $${DAYS:-21}

# AUD-F-33's read (D-182). Read-only. Joins each scale-in alarm's `OK -> ALARM` transition to
# the Auto Scaling outcome that followed, which is where the mechanism was recorded all along:
# `treat_missing_data = "breaching"` on a metric that publishes nothing at zero traffic puts
# the alarm into ALARM with no metric VALUE, and a step-scaling policy cannot select a step
# without one - so the invocation is refused and no scaling activity is created, which is why
# `describe-scaling-activities` looked empty. Measured deterministic at 46/46 on first run,
# and the split moves with the rolling window while the separation does not. Exits 1 while
# any refusal is present, so the same command that demonstrates the defect verifies the
# `FILL(m1, 0)` fix. Exits 2 on an empty window, because "no refusals" from an instrument that
# saw nothing is the AUD-F-12 false negative.
scaling-evidence:
	eval "$$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
	  uv run python -u scripts/read_scaling_evidence.py --days $${DAYS:-8}

# AUD-X-16: the tfvars image-tag floor check, executable and tracked (the comment form
# of this step lives in a gitignored file and failed to prevent the same near-miss three
# times - see scripts/check_tfvars_floor.py's docstring). Run before EVERY
# `terraform apply` in terraform/environments/staging; exits non-zero on any
# floor/running/latest disagreement.
tfvars-floor-check:
	eval "$$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
	  uv run python -u scripts/check_tfvars_floor.py

# Criterion 7 / AUD-F-31's before-after instrument. D-129 §5's hand-rolled profile of the
# same span first reported 102 statements and 131% of wall time in SQL, because X-Ray records
# each SQLAlchemy statement twice (a child subsegment *and* a standalone segment). The
# correction lives in the script rather than in a shell pipeline so that both arms of a
# comparison are measured identically - see its docstring. Pin it to the load run whose
# traffic you care about, and keep --url-contains: ~97% of staging's traces are /readyz
# (AUD-F-30), so an unfiltered denominator flatters a profile that never saw the request.
#   make profile-span START=2026-07-30T23:38:00Z END=2026-07-30T23:42:00Z
profile-span:
	eval "$$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
	  uv run python -u scripts/profile_xray_span.py \
	    --span $${SPAN:-langgraph.select_topic} \
	    --url-contains $${URL_CONTAINS:-topics} \
	    $${START:+--start $$START} $${END:+--end $$END} \
	    $${MINUTES:+--minutes $$MINUTES} $${LABEL:+--label "$$LABEL"}

# S33 (D-089/D-094): authorized OWASP ZAP baseline scan against the real staging
# CloudFront URLs - you own this AWS account/app, so this is authorized self-testing,
# not something requiring a paid third-party pentest engagement (that's still a real,
# separate launch-gate item - see PROGRESS.md's S33 carry-over). Needs a live AWS
# session (`terraform output` reads real state) - not runnable this session, blocked on
# AWS SSO reauth; ready to run as soon as that's restored. Reports land in
# zap-reports/ (gitignored) - review before treating any finding as real; a baseline
# scan is noisy (informational-level findings especially) by design.
security-scan-staging:
	mkdir -p zap-reports
	$(eval LEARNING_URL := $(shell cd terraform/environments/staging && terraform output -raw cloudfront_learning_domain))
	$(eval CHAT_URL := $(shell cd terraform/environments/staging && terraform output -raw cloudfront_chat_domain))
	docker run --rm -v $(PWD)/zap-reports:/zap/wrk/:rw -t ghcr.io/zaproxy/zaproxy:stable \
		zap-baseline.py -t https://$(LEARNING_URL) -r learning-web-zap-report.html || true
	docker run --rm -v $(PWD)/zap-reports:/zap/wrk/:rw -t ghcr.io/zaproxy/zaproxy:stable \
		zap-baseline.py -t https://$(CHAT_URL) -r chat-web-zap-report.html || true
	@echo "Reports: zap-reports/learning-web-zap-report.html, zap-reports/chat-web-zap-report.html"
