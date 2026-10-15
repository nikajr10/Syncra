# Syncra — Progress Log

Live record of what has been built. Agents add an entry here after every task (format in [`agent.md`](agent.md)).

## Current status

- **Current phase:** Phase 1 — Collect and clean
- **Next task:** 1.1 — Connector interface
- **Completed tasks:** 0.1, 0.2, 0.3, 0.4, 0.5, 0.6 (Phase 0 complete)

## Log

### Task 0.6 — Background job runner  ✅ done
**Date:** 2026-10-15

**Built**
- `app/jobs/scheduler.py`: APScheduler `BlockingScheduler`; `build_scheduler()` registers the dummy `heartbeat` job on an interval of `SYNC_INTERVAL_MINUTES` (runs once at startup, then every interval; `max_instances=1`, `coalesce=True` so runs never overlap). `make worker` starts it.
- Tests: the interval comes from config (and changes with the env), and a started worker fires the job and logs `heartbeat: worker alive`.

**Key files**
- `backend/app/jobs/scheduler.py`, `backend/tests/test_jobs.py`, `Makefile` target `worker`

**Decisions**
- **APScheduler 3 in-process, no Celery / broker.** One database is the rule; the `items.status` column is the work queue. Jobs are plain functions registered in `build_scheduler()`; Task 1.6 adds `sync_all_sources` there.
- The worker is a separate process from the API (`make worker` vs `make run`).

**How to run / test**
- `make worker` (Ctrl-C to stop) · `make test`

**Known issues / TODO**
- Single worker process, no persisted job state. Fine while jobs are idempotent and re-run on the interval.

### Task 0.5 — Model gateway  ✅ done
**Date:** 2026-10-15

**Built**
- `app/models/gateway.py`: `OllamaClient` (`generate`, `generate_json`, `stream`; JSON mode via Ollama `format`; timeout + retries from settings; Qwen3 thinking off by default), `ollama()` cached client, `device()` (cuda > mps > cpu, or `DEVICE` setting), cached `load_sentence_transformer(role)` / `load_cross_encoder(role)`, helpers `embed(role, texts)` (normalised) and `rerank(role, query, candidates)`.
- Every call logs `model=<name> took=<ms> prompt_tokens=… tokens=…` (Ollama) or `items=…` (HF) on logger `syncra.models`.
- `app/models/download.py` + `scripts/download_hf_models.py` (`make download-models`): downloads every `runtime: huggingface` model once; gated models are skipped with a warning unless `HF_TOKEN` is set.
- Tests: mocked Ollama (`httpx.MockTransport`) for generate / JSON / retry / stream; real tiny HF model (`all-MiniLM-L6-v2`, cached) loaded once and embedding; download logic with a fake downloader.

**Key files**
- `backend/app/models/gateway.py`, `backend/app/models/download.py`, `backend/scripts/download_hf_models.py`, `backend/tests/test_gateway.py`

**Decisions**
- Call models by **role**: `ollama().generate("answer_writer", prompt)`, `embed("embedder", texts)`, `rerank("reranker", q, docs)`. Never import `sentence_transformers` or call Ollama outside `app/models/`.
- Ollama requests set `think: false` (Qwen3) unless `think=True` is passed; JSON mode = `json_mode=True` or a JSON-schema dict.
- `stream()` retries only before the first token; `generate()` retries `retries` times (default 2) on HTTP / bad-JSON errors, then raises `OllamaError`.
- New loaders for other model types (GLiNER, SetFit, transformers pipelines) go in `gateway.py` as `@lru_cache` functions taking a role.
- `DEVICE=auto` picks the GPU (`mps` on Apple Silicon); set `DEVICE=cpu` if a model misbehaves on MPS.
- `httpx` is a runtime dependency now (Ollama client; connectors will reuse it).

**How to run / test**
- `make download-models` · `make test` (the HF test takes ~5 s after the first run)

**Known issues / TODO**
- `meta-llama/Llama-Prompt-Guard-2-86M` is gated: accept the licence on Hugging Face and set `HF_TOKEN` before Task 5.4.
- First `make test` after install is slow (~1 min) while torch / the model warm up.

### Task 0.4 — Database schema and migrations  ✅ done
**Date:** 2026-10-15

**Built**
- SQLAlchemy 2 ORM (`app/db/schema.py`) + Alembic migration `0001_initial_schema` creating: `users`, `user_source_identities`, `sources`, `sync_cursors`, `items`, `chunks` (`vector(1024)` + generated `tsv`), `entities`, `entity_aliases`, `edges`, `decisions`, `chat_sessions`, `chat_messages`, `actions`.
- Indexes: **HNSW** (`vector_cosine_ops`, m=16, ef_construction=64) on `chunks.vector`, **GIN** on `chunks.tsv` and `items.access_tags`, plus lookup indexes on status / edges / aliases.
- `app/db/engine.py`: `get_engine()` (cached), `new_session()`, `get_db()` FastAPI dependency.
- Test: downgrade → upgrade → insert and read one row in every table → cosine + full-text queries → downgrade (nothing left but `alembic_version`).
- Dev database migrated (`make migrate`).

**Key files**
- `backend/app/db/schema.py` — ORM models + allowed-value tuples (`ITEM_TYPES`, `ITEM_STATUSES`, `ENTITY_TYPES`, …)
- `backend/app/db/engine.py` — engine/session helpers
- `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/versions/0001_initial_schema.py`
- `backend/tests/test_db_schema.py`

**Decisions**
- Migrations live in `backend/migrations/` (not `alembic/`, which shadows the `alembic` package). Write them **by hand** with explicit column types on FK columns; the vector dim comes from `get_settings().embedding_dim`.
- `items.access_tags text[]` is the permission model: tags like `github:repo:org/x`, `jira:project:PAY`, `slack:channel:C123`, `public`. Task 6.1 filters with `access_tags && user_tags` inside the query.
- `items.status` (`new` → `processed` | `noise` | `failed`) is the Phase 2 work queue; no broker needed.
- `chunks.tsv` is a stored generated column (`to_tsvector('english', text)`), so the keyword index needs no app code.
- `edges` is polymorphic: `(src_type, src_id) -relation-> (dst_type, dst_id)` over node types `entity | item | chunk | decision` with optional `item_id` evidence; unique on the 5-tuple so re-runs don't duplicate.
- Authors / identities are strings like `github:alice`, `slack:U123`, `jira:<accountId>`; `user_source_identities` links them to Syncra users.
- Sessions: sync SQLAlchemy (`psycopg` 3), `expire_on_commit=False`.
- Tests that need the DB use the module-scoped `migrated` fixture + a per-test `session` that rolls back.

**How to run / test**
- `make migrate` (dev DB) · `make test` (uses `syncra_test`, leaves it empty)

**Known issues / TODO**
- SQLAlchemy 2.1 got installed (pin is `>=2.0`); no problems so far.

### Task 0.2 — Local services with Docker  ✅ done
**Date:** 2026-10-15

**Built**
- **Production** Docker setup (user decision: **no Docker for local development**): `backend/Dockerfile` (multi-stage, non-root, CPU torch by default, healthcheck) and `backend/docker-compose.yml` with `postgres` (`pgvector/pgvector:pg17`), `ollama` (`0.35.0`), `api` (runs migrations, then uvicorn) and `worker`. Named volumes for Postgres data, Ollama models and the Hugging Face cache.
- Local development uses the developer's **own PostgreSQL + pgvector** (dev machine: Homebrew PostgreSQL 18 on port **5434**) and **native Ollama**. `make db-init` (`scripts/init_local_db.py`) creates the `syncra` and `syncra_test` databases and enables `vector`.
- `backend/scripts/pull_ollama_models.py` (`make pull-models`): pulls every `runtime: ollama` model in `config/models.yaml` (qwen3:4b, qwen3:8b; both pulled on the dev machine). Test drives it with a fake `ollama` binary on PATH.
- `backend/.env.example` lists every setting; `backend/.env` is the local copy (gitignored).

**Key files**
- `backend/Dockerfile`, `backend/.dockerignore`, `backend/docker-compose.yml`, `backend/scripts/init_db.sql` (compose first start: enables `vector`), `backend/scripts/init_local_db.py`, `backend/scripts/pull_ollama_models.py`, `backend/.env.example`, `backend/tests/test_pull_ollama_models.py`

**Decisions**
- **Do not start Docker locally.** Dev = local Postgres + native Ollama; Docker = production only. The compose Postgres was verified once (Postgres 17 + pgvector 0.8.7 came up with the extension enabled) and torn down; the image build has not been run.
- Compose project name is pinned (`name: syncra`); the default (folder name `backend`) collided with another project's containers on the dev machine.
- In containers the API / worker get `DATABASE_URL` and `OLLAMA_BASE_URL` pointing at the `postgres` / `ollama` services (set in compose), `DEVICE=cpu`, `HF_HOME=/models`.
- DBeaver (local dev): host `localhost`, port `5434`, db `syncra`, user = macOS user, no password. Tests use `syncra_test` on the same server (`TEST_DATABASE_URL` in `.env`).

**How to run / test**
- Local: `make db-init && make migrate && make pull-models && make download-models && make test`
- Production: README section "Production (Docker)".

**Known issues / TODO**
- `docker compose build` has not been exercised (no local Docker by decision); the first production deploy must build and smoke-test the image.
- Ollama image tag `0.35.0` is assumed to exist on Docker Hub (matches the local version); bump if it does not.

### Task 0.3 — Configuration  ✅ done
**Date:** 2026-10-15

**Built**
- `Settings` (pydantic-settings) loads `backend/.env` + environment; `get_settings()` raises `ConfigError` naming every missing/invalid field.
- `config/models.yaml` lists every model from `description.md` §8 by **role**; `get_models_config()["answer_writer"]` returns a `ModelSpec(runtime, name, revision, gated)`.
- API lifespan calls both loaders, so bad config fails at startup with a clear message.
- Tests: env override changes values, missing `DATABASE_URL` fails clearly, every role present, bad yaml rejected.

**Key files**
- `backend/app/config/settings.py` — `Settings`, `ModelSpec`, `ModelsConfig`, `get_settings()`, `get_models_config()`, `ConfigError`
- `backend/config/models.yaml` — model roles
- `backend/tests/conftest.py` — forces `DATABASE_URL` to the test DB for every test run
- `backend/tests/test_settings.py`

**Decisions**
- Key numbers are settings: `SYNC_INTERVAL_MINUTES=15`, `CHAT_MEMORY_TURNS=10`, `TOP_K_EVIDENCE=8`, `EMBEDDING_DIM=1024`. Read them via `get_settings()`, never hard-code.
- Models are addressed by role name (`entity_finder`, `decision_reader`, `embedder`, `entity_linker`, `triage_base`, `presidio_nlp`, `question_rewriter`, `prompt_guard`, `intent_router_base`, `reranker`, `answer_writer`, `claim_checker`). Change models in yaml, not code.
- Ollama entries use the full tag as `name` (`qwen3:8b`); Hugging Face entries use the repo id, optional `revision`, `gated: true` when a token is needed.
- Env vars beat `.env`; empty env values are ignored. Only `DATABASE_URL` is required.
- Tests never touch the dev DB: `conftest.py` sets `DATABASE_URL` to `TEST_DATABASE_URL` (from the environment or `backend/.env`; fallback `postgresql+psycopg://<mac user>@localhost:5434/syncra_test`).

**How to run / test**
- `cd backend && make test`

**Known issues / TODO**
- none

### Task 0.1 — Project skeleton  ✅ done
**Date:** 2026-10-15

**Built**
- Python project in **`backend/`**: `pyproject.toml`, `Makefile`; `.gitignore` and `README.md` at the repo root.
- FastAPI app with `GET /health` → `{"status": "ok"}` and a test for it.
- Package layout `backend/app/{api,learning,chat,models,db,jobs,config}` plus `backend/config/` (yaml), `backend/scripts/`, `backend/tests/`.
- The old empty scaffold (125 zero-byte files) in `backend/` was deleted.

**Key files**
- `backend/pyproject.toml` — deps (`fastapi`, `uvicorn`), dev deps (`pytest`, `httpx`, `ruff`), ruff + pytest config
- `backend/Makefile` — `make install` / `make run` / `make test` / `make lint` / `make fmt`
- `backend/app/api/main.py` — FastAPI app
- `backend/tests/test_health.py` — health test

**Decisions**
- **Python 3.12** via `python3.12 -m venv .venv` + pip (no uv/poetry). Override with `make install PYTHON=python3.11`.
- **Layout:** `app/api` (web API), `app/learning` (learning pipeline), `app/chat` (chatbot pipeline), `app/models` (model gateway), `app/db` (database), `app/jobs` (background jobs), `app/config` (settings code), `config/` (yaml + prompts), `scripts/`, `tests/` — all under `backend/`. `frontend/` is for the web app (Phase 9).
- Package is named `app` (as in the FastAPI docs layout); imports look like `from app.api.main import app`.
- **Linter + formatter:** ruff. **Tests:** pytest (`tests/` is a package, tests import `app` from the editable install).

**How to run / test**
- `cd backend && make install && make test && make lint`; `make run` then `curl localhost:8000/health`.

**Known issues / TODO**
- Starlette's TestClient warns that `httpx` is deprecated in favour of `httpx2`; harmless, revisit when `httpx2` is stable.
