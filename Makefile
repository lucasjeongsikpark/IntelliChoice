.PHONY: up down dev dev-observability test lint typecheck dev-learning dev-chat dev-learning-web dev-chat-web seed curriculum-load question-gen-run question-gen-authored question-review knowledge-load youtube-sync webcontent-sync org-load chat-suggestions-load chat-purge memory-consolidate db-upgrade db-downgrade db-revision security-scan-staging

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

question-gen-run:
	uv run python -m intellichoice_curriculum.pipeline_cli

question-gen-authored:
	uv run python -m intellichoice_curriculum.pipeline_cli --mode authored

question-review:
	uv run python -m intellichoice_curriculum.review_cli

knowledge-load:
	uv run python -m intellichoice_knowledge.ingest_cli

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
