# Syncra

Team-memory chatbot: learns from GitHub, Jira and Slack, answers questions with cited sources. Every model runs locally.

Docs: [`description.md`](description.md) (what it is) · [`flow.md`](flow.md) (how it works, end to end) · [`decision.md`](decision.md) (why it's built this way) · [`phases.md`](phases.md) (task list) · [`progress.md`](progress.md) (what's done) · [`timing.md`](timing.md) (how fast it answers) · [`agent.md`](agent.md) (how agents work on it).

Layout: `backend/` (Python API + pipelines) · `frontend/` (the web app: React, Vite and Arc UI components).

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
make train-intent-router # trains the chat's intent router on config/intent_router.yaml (~25 s; same)
```

Browse the database in DBeaver: host `localhost`, port `5434`, database `syncra`, user = your macOS user name, no password (Homebrew default).

## Run

```bash
cd backend
make run          # API on http://127.0.0.1:8000  (GET /health -> {"status": "ok"})
                  # API documentation (Swagger UI): http://127.0.0.1:8000/docs, or ReDoc at /redoc
make worker       # learning pipeline: sync + learn every SYNC_INTERVAL_MINUTES (needs Ollama)
make lint         # ruff check + format check
```

## Web app

Requires Node.js 20 or newer (`brew install node`). In a second terminal, with `make run` going:

```bash
cd frontend
npm install       # once, and again when package.json changes
npm run dev       # http://localhost:5173
```

Log in with a user from `make add-user`. Everyone gets their chats (streamed answers, numbered citations that preview their source, confidence, follow-ups) and an Approvals page for action cards. Admins also get Sources, People and Activity in the sidebar. ⌘K searches chats and pages.

The app calls the API under `/api`, and Vite passes those calls to `http://127.0.0.1:8000`, so the API needs no CORS setting. `npm run build` writes the production files to `frontend/dist`; `npm run preview` serves them with the same pass-through.

## Users and login

Every API endpoint except `/health` needs a login. An admin creates each user and links their GitHub, Jira and Slack accounts. Only admins can link accounts, because from Phase 6 those accounts decide what a user may search.

```bash
cd backend
make add-user         # asks for a username, a display name, a password and whether it's an admin
make link-account     # asks for the username, the tool (github, jira or slack) and the account id
```

Admins can also link accounts through the API (`POST /admin/users/{username}/accounts`, see `/docs`). The account id is the GitHub login, the Jira accountId, or the Slack member id (`U0123…`, from the person's Slack profile → ⋮ → Copy member ID). The next learning run merges a user's accounts into one person.

`POST /auth/login` with `{"username": "…", "password": "…"}` returns a token. Send it as `Authorization: Bearer <token>` until it expires (`TOKEN_TTL_HOURS`, 12 by default); `POST /auth/logout` ends it and `GET /me` shows who is logged in. In `/docs`, click **Authorize** and paste the token.

## Connect a source

Put the credentials in `backend/.env` (`GITHUB_TOKEN`, `JIRA_BASE_URL` + `JIRA_EMAIL` + `JIRA_API_TOKEN`, `SLACK_BOT_TOKEN` + `SLACK_WORKSPACE_URL`). Then, logged in as an admin in `/docs`, add one source per repo / project / channel with `POST /admin/sources`:

```json
{"kind": "github", "external_id": "acme/payments"}
{"kind": "jira",   "external_id": "PAY"}
{"kind": "slack",  "external_id": "C0123456789", "name": "#eng-payments"}
```

`GET /admin/sources` shows which tools have credentials, and each source's last sync, last error, item count and member count. `POST /admin/sources/{id}/sync` syncs one right away; `PATCH /admin/sources/{id}` with `{"enabled": false}` pauses it.

Syncra only shows a user what their linked accounts can see in the tool itself, so each sync also reads who can see the source. The GitHub token needs push access to private repos (to list collaborators), the Slack bot needs `channels:read` / `groups:read`, and the Jira user must be allowed to see project permissions.

`make worker` then, every `SYNC_INTERVAL_MINUTES`, pulls new items, scrubs personal data and secrets, drops noise and learns from the rest: chunks with vectors and a keyword index, entities, decisions and the links between them. It needs Ollama running and `make train-triage` done once. Each item's `status` ends up `processed` or `noise`; `failed` ones (e.g. Ollama was down) are retried on the next run.

## Chat

The web app is the easy way to chat. Through the API directly: logged in, start a chat with `POST /chat/sessions`, then send messages to `POST /chat/sessions/{id}/messages`. The reply's `path` says what happened: small talk gets an instant reply; a question gets an answer citing its `sources` as `[E1]`…, with a `confidence` (high, medium or low) and suggested `follow_ups`; a request like "open a Jira ticket to …" gets an approval card (`action`). `…/messages/stream` sends the same reply as Server-Sent Events, word by word. Approve or reject a card with `POST /actions/{id}/approve` or `…/reject`; nothing is created before that.

The chat needs Ollama running, `make train-intent-router` done once, and `HF_TOKEN` in `backend/.env` for the prompt guard (Meta's Llama Prompt Guard 2 is gated: accept its licence on Hugging Face, then `make download-models`).

## Demo

`make demo` loads Acme Pay, a fictional payments company (`backend/demo/company.yaml`): six people, two private GitHub repos and a public one, two Jira projects and three Slack channels, with PRs, reviews, tickets and threads about real-looking decisions. It asks for one password for all demo users (or reads `DEMO_PASSWORD`), creates them with their linked accounts, and runs one learning run over the data (about 3 minutes; needs Ollama and both classifiers trained). Running it again changes nothing unless the file changed.

Log in as `alice` (payments team) or `dave` (auth team) and ask, for example, "Why do orders go through a queue before payments?", "Who reviewed the idempotency keys PR?", "What does PAY-131 say?" or "Why did we choose Keycloak over Auth0?" (dave can answer that one; alice can't see it).

The demo's sources never call the real GitHub, Jira or Slack. Load it into its own database if you don't want it next to real data, e.g. `DATABASE_URL=postgresql+psycopg://<you>@localhost:5434/syncra_demo make db-init migrate demo`. It's for local demos, not production.

`make eval` then asks the 66 questions of `backend/demo/eval.yaml` as their users and prints a score report (right source found, leaks, citations, unsupported claims, "I don't know", time per stage); `python scripts/evaluate.py --search-only` checks retrieval alone in seconds.

## Production (Docker)

`backend/Dockerfile` and `backend/docker-compose.yml` run the whole stack on a Linux host: Postgres + pgvector, Ollama, the API and the worker. They are not used for local development.

```bash
cd backend
cp .env.example .env     # set POSTGRES_PASSWORD (and HF_TOKEN if you use gated models)
docker compose up -d --build
docker compose exec ollama ollama pull qwen3:4b && docker compose exec ollama ollama pull qwen3:8b
docker compose run --rm api python scripts/download_hf_models.py
docker compose run --rm api python scripts/train.py triage
docker compose run --rm api python scripts/train.py intent_router
```

The web app isn't in the compose file yet: build it (`npm run build`), serve `frontend/dist` from the reverse proxy, and send `/api/…` to the API with the `/api` prefix removed.

The API listens on `127.0.0.1:API_PORT` (default 8000) only: put a TLS reverse proxy (Caddy / nginx) in front of it, and don't make it public before rate limits are in place. API docs (`/docs`) are off in production. The compose Postgres is reachable from the host only on `127.0.0.1:POSTGRES_PORT`. For an NVIDIA GPU, build with `--build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu124` and uncomment the GPU reservation on the `ollama` service.

## Security

- Secrets live only in `backend/.env` (git-ignored). **If a real token or password is ever committed, rotate it at the provider immediately.** Deleting the line doesn't help, because it stays in git history.
- Never reuse the old local-dev database password `syncra` that appears in early commits.
- Audit checklist: [`security.md`](security.md) · latest results and open items: [`security-audit.md`](security-audit.md).
