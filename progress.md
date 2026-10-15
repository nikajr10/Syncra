# Syncra — Progress Log

Live record of what has been built. Agents add an entry here after every task (format in [`agent.md`](agent.md)).

## Current status

- **Current phase:** Phase 0 — Foundation
- **Next task:** 0.4 — Database schema and migrations (then 0.5, 0.6)
- **Completed tasks:** 0.1, 0.2, 0.3

## Log

### Task 0.2 — Local services with Docker  ✅ done
**Date:** 2026-10-15

**Built**
- `backend/docker-compose.yml`: **PostgreSQL 17 + pgvector** (`pgvector/pgvector:pg17`) on host port **5436**, healthcheck, named volume; **Ollama** service behind the `ollama` compose profile.
- `backend/scripts/init_db.sql`: enables `vector` in `syncra` and creates `syncra_test` (with `vector`) on first start.
- `backend/scripts/pull_ollama_models.py` (`make pull-models`): pulls every `runtime: ollama` model in `config/models.yaml` (qwen3:4b, qwen3:8b). Both are pulled on the dev machine.
- `backend/.env.example` lists every setting. `backend/.env` is a copy (gitignored).
- Test drives the pull script with a fake `ollama` binary on PATH.

**Key files**
- `backend/docker-compose.yml`, `backend/scripts/init_db.sql`, `backend/scripts/pull_ollama_models.py`, `backend/.env.example`, `backend/tests/test_pull_ollama_models.py`

**Decisions**
- Compose project name is pinned to `syncra` (`name: syncra`). The default (folder name `backend`) collided with another project on the dev machine.
- Host port **5436**: ports 5432–5435 are taken by other Postgres servers on the dev machine. Change `POSTGRES_PORT` + URLs in `.env` if needed.
- **Ollama runs natively on macOS** (Docker has no GPU there); the compose `ollama` service is for Linux: `docker compose --profile ollama up -d`. The app only needs `OLLAMA_BASE_URL`.
- DB credentials for local dev / DBeaver: host `localhost`, port `5436`, db `syncra`, user `syncra`, password `syncra`. Tests use db `syncra_test` on the same server.

**How to run / test**
- `cd backend && cp .env.example .env && docker compose up -d && make pull-models && make test`

**Known issues / TODO**
- `docker compose up` on macOS starts only Postgres (Ollama is native); on Linux use the profile to start both.

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
- Tests never touch the dev DB: `conftest.py` sets `DATABASE_URL` to `TEST_DATABASE_URL` (default `postgresql+psycopg://syncra:syncra@localhost:5436/syncra_test`).

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
