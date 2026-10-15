# Syncra

Team-memory chatbot: learns from GitHub, Jira and Slack, answers questions with cited sources. Every model runs locally.

Docs: [`description.md`](description.md) (what it is) · [`phases.md`](phases.md) (task list) · [`progress.md`](progress.md) (what's done) · [`agent.md`](agent.md) (how agents work on it).

Layout: `backend/` (Python API + pipelines) · `frontend/` (web app, Phase 9).

## Setup

Requires Python 3.11+ (3.12 recommended), Docker, and [Ollama](https://ollama.com) installed natively (on macOS Ollama in Docker has no GPU).

```bash
cd backend
make install      # creates backend/.venv and installs the backend + dev tools
```

## Local services

```bash
cd backend
cp .env.example .env     # all settings live here; defaults work for local dev
docker compose up -d     # PostgreSQL 17 + pgvector on localhost:5436 (db/user/password: syncra)
make migrate             # create / upgrade the database tables (alembic upgrade head)
make pull-models         # ollama pull qwen3:4b + qwen3:8b into your native Ollama
make download-models     # download every Hugging Face model from config/models.yaml
```

Open the database in DBeaver (or any client): host `localhost`, port `5436`, database `syncra`, user `syncra`, password `syncra`. Tests use the `syncra_test` database on the same server.

Ollama runs natively (macOS Docker has no GPU). On Linux you can run it in Docker instead: `docker compose --profile ollama up -d`.

## Run

```bash
cd backend
make run          # API on http://127.0.0.1:8000  (GET /health -> {"status": "ok"})
make worker       # background job runner (every SYNC_INTERVAL_MINUTES)
make test         # run the test suite (needs the compose Postgres running)
make lint         # ruff check + format check
```
