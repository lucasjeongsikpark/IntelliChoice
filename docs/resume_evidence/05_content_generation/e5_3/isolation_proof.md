# E5.3 isolation proof — the dev database is not touched

The generation run, every scoring pass and the funnel harness all ran against a **separate
Postgres database** in the same local docker-compose instance, selected by `DATABASE_URL`
for every command. The dev database (`intellichoice`) is read here only to record its row
counts before and after.

## Setup (exact commands, reproducible)

```bash
docker compose exec -T postgres psql -U intellichoice -d postgres \
  -c "DROP DATABASE IF EXISTS intellichoice_e53;" \
  -c "CREATE DATABASE intellichoice_e53 OWNER intellichoice;"
docker compose exec -T postgres psql -U intellichoice -d intellichoice_e53 \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"

export DATABASE_URL="postgresql+asyncpg://intellichoice:intellichoice@localhost:5432/intellichoice_e53"
(cd packages/db && uv run alembic upgrade head)     # replayed from empty
uv run python -m intellichoice_curriculum.loader     # taxonomy + the committed bank
```

`alembic upgrade head` replayed the full migration chain from an empty database. The loader
reported `33 topics, 112 skills, 958 templates created (0 updated, 0 unchanged, 0 retired),
958 sample variants` — the committed bank, loaded so the pipeline's dedup stage sees the
same corpus a real run would.

## Dev-database row counts, before and after

```sql
SELECT (SELECT count(*) FROM question_templates)      AS question_templates,
       (SELECT count(*) FROM question_validation_runs) AS question_validation_runs;
```

| when | `question_templates` | `question_validation_runs` |
|---|---|---|
| before — 2026-08-29 23:33 UTC, before the run | **1077** | **1827** |
| after — 2026-08-30 02:02 UTC, after the run and every scoring pass | **1077** | **1827** |

**Unchanged, both columns.** Everything the run wrote went to `intellichoice_e53`, which
holds 174 `pending` + 30 `rejected` validation runs and 174 new `question_templates` rows
on top of the 958 loaded from the committed bank.

## What was never run

- No `review_cli` (no approval path was opened).
- No `export_cli` (nothing was written to `curriculum/`; `git status curriculum/` is empty).
- No staging or production database was contacted; `DATABASE_URL` pointed at
  `localhost:5432/intellichoice_e53` for every command of this experiment.

Per **D-342**, nothing this run produced is approved, exported, committed to `curriculum/`,
or counted toward any coverage target. The 174 machine-accepted rows are measurement
subjects that live only in a disposable database; "machine-accepted" means *cleared the
automated pipeline*, never *approved by a person*.

## Cleanup

The benchmark database is disposable and can be dropped at any time:

```bash
docker compose exec -T postgres psql -U intellichoice -d postgres \
  -c "DROP DATABASE IF EXISTS intellichoice_e53;"
```

It is deliberately left in place for now so the artifacts in this directory can be
re-derived from their source rows without paying for the run again. Nothing depends on it.

