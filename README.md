# Syncra

Team-memory chatbot: learns from GitHub, Jira and Slack, answers questions with cited sources. Every model runs locally.

Docs: [`description.md`](description.md) (what it is) · [`phases.md`](phases.md) (task list) · [`progress.md`](progress.md) (what's done) · [`agent.md`](agent.md) (how agents work on it).

Layout: `backend/` (Python API + pipelines) · `frontend/` (web app, Phase 9).

## Local development (no Docker)

Requires Python 3.12, PostgreSQL 16+ with the pgvector extension (Homebrew: `brew install postgresql@18 pgvector`), and [Ollama](https://ollama.com) running natively.

```bash
cd backend
make install             # creates backend/.venv and installs the backend + dev tools
cp .env.example .env     # set DATABASE_URL to your Postgres (USER = your macOS user)
make db-init             # creates the syncra database and enables pgvector
make migrate             # creates the tables (alembic upgrade head)
make pull-models         # ollama pull qwen3:4b + qwen3:8b
make download-models     # downloads every Hugging Face model from config/models.yaml
```

Browse the database in DBeaver: host `localhost`, port `5434`, database `syncra`, user = your macOS user name, no password (Homebrew default).

## Run

```bash
cd backend
make run          # API on http://127.0.0.1:8000  (GET /health -> {"status": "ok"})
make worker       # background job runner (every SYNC_INTERVAL_MINUTES)
make lint         # ruff check + format check
```

## Connect a source

Put the credentials in `backend/.env` (`GITHUB_TOKEN`, `JIRA_BASE_URL` + `JIRA_EMAIL` + `JIRA_API_TOKEN`, `SLACK_BOT_TOKEN` + `SLACK_WORKSPACE_URL`) and insert one row per repo / project / channel into the `sources` table (a UI comes in Phase 9):

```sql
insert into sources (kind, name, external_id) values
  ('github', 'acme/payments', 'acme/payments'),   -- owner/repo
  ('jira',   'PAY',           'PAY'),             -- project key
  ('slack',  '#eng-payments', 'C0123456789');     -- channel id
```

`make worker` then pulls new items every `SYNC_INTERVAL_MINUTES`, scrubs personal data and secrets, and stores them with status `new`.

## Production (Docker)

`backend/Dockerfile` and `backend/docker-compose.yml` run the whole stack on a Linux host: Postgres + pgvector, Ollama, the API and the worker. They are not used for local development.

```bash
cd backend
cp .env.example .env     # set POSTGRES_PASSWORD (and HF_TOKEN if you use gated models)
docker compose up -d --build
docker compose exec ollama ollama pull qwen3:4b && docker compose exec ollama ollama pull qwen3:8b
docker compose run --rm api python scripts/download_hf_models.py
```

The API listens on `API_PORT` (default 8000). The compose Postgres is reachable from the host only on `127.0.0.1:POSTGRES_PORT`. For an NVIDIA GPU, build with `--build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu124` and uncomment the GPU reservation on the `ollama` service.
