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
make train-triage        # trains the noise filter on config/triage.yaml (~30 s; again after editing it)
```

Browse the database in DBeaver: host `localhost`, port `5434`, database `syncra`, user = your macOS user name, no password (Homebrew default).

## Run

```bash
cd backend
make run          # API on http://127.0.0.1:8000  (GET /health -> {"status": "ok"})
make worker       # learning pipeline: sync + learn every SYNC_INTERVAL_MINUTES (needs Ollama)
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

`make worker` then, every `SYNC_INTERVAL_MINUTES`, pulls new items, scrubs personal data and secrets, drops noise and learns from the rest: chunks with vectors and a keyword index, entities, decisions and the links between them. It needs Ollama running and `make train-triage` done once. Each item's `status` ends up `processed` or `noise`; `failed` ones (e.g. Ollama was down) are retried on the next run.

## Production (Docker)

`backend/Dockerfile` and `backend/docker-compose.yml` run the whole stack on a Linux host: Postgres + pgvector, Ollama, the API and the worker. They are not used for local development.

```bash
cd backend
cp .env.example .env     # set POSTGRES_PASSWORD (and HF_TOKEN if you use gated models)
docker compose up -d --build
docker compose exec ollama ollama pull qwen3:4b && docker compose exec ollama ollama pull qwen3:8b
docker compose run --rm api python scripts/download_hf_models.py
docker compose run --rm api python scripts/train_triage.py
```

The API listens on `127.0.0.1:API_PORT` (default 8000) only: put a TLS reverse proxy (Caddy / nginx) in front of it, and don't make it public before login exists (Phase 9). API docs (`/docs`) are off in production. The compose Postgres is reachable from the host only on `127.0.0.1:POSTGRES_PORT`. For an NVIDIA GPU, build with `--build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu124` and uncomment the GPU reservation on the `ollama` service.

## Security

- Secrets live only in `backend/.env` (git-ignored). **If a real token or password is ever committed, rotate it at the provider immediately.** Deleting the line doesn't help, because it stays in git history.
- Never reuse the old local-dev database password `syncra` that appears in early commits.
- Audit checklist: [`security.md`](security.md) · latest results and open items: [`security-audit.md`](security-audit.md).
