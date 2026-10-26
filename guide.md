# Syncra – Setup Guide

A step-by-step guide to get Syncra running on your own computer, from nothing to a working API.
Written for macOS. Linux and Windows notes are at the end.

Locally we **do not use Docker**. Postgres, Ollama and Python all run directly on your machine.
Docker (`backend/Dockerfile`, `backend/docker-compose.yml`) is only for production.

---

## 0. What you will install

- **Homebrew**: the macOS package manager. It installs everything else.
- **Git**: to clone the code.
- **Python 3.12**: the backend is written in Python.
- **PostgreSQL 18 + pgvector**: the database. pgvector lets it store AI embeddings.
- **Ollama**: runs the local LLMs (Qwen3).
- **Node.js**: runs the web app you chat in.
- **DBeaver**: a window into the database, to look at the tables (optional but handy).

---

## 1. Install the tools

Install Homebrew first if you don't have it (https://brew.sh), then:

```bash
brew install git python@3.12 postgresql@18 pgvector node
brew install --cask ollama dbeaver-community
```

Check they work:

```bash
python3.12 --version     # Python 3.12.x
psql --version           # psql (PostgreSQL) 18.x
ollama --version
```

> If `psql` is "command not found", add Postgres to your PATH:
> `echo 'export PATH="$(brew --prefix postgresql@18)/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc`

---

## 2. Get the code

```bash
git clone https://github.com/nikajr10/Syncra.git
cd Syncra/backend
```

From here on, **every command runs inside `Syncra/backend`** unless said otherwise.

---

## 3. Start PostgreSQL

```bash
brew services start postgresql@18
```

This runs Postgres in the background and starts it again on every reboot.
(Stop it with `brew services stop postgresql@18`.)

Homebrew creates a Postgres superuser with **your macOS user name** and **no password**.
Find your user name with:

```bash
whoami
```

### Which port?

- Postgres default port is **5432**. If you've never installed Postgres before, use **5432**.
- The original dev machine uses **5434** because 5432 was already taken. You don't have to.

Check which port your Postgres is on:

```bash
psql -d postgres -c "show port;"
```

If you *want* a different port, edit `$(brew --prefix)/var/postgresql@18/postgresql.conf`,
set `port = 5434` (remove the `#` in front), then `brew services restart postgresql@18`.

Remember the port — you need it in step 5 and in DBeaver.

---

## 4. Create the virtual environment (venv)

### What is a venv?

A **virtual environment** is a private folder (`backend/.venv`) holding its own Python and its own
installed packages. Syncra's packages (FastAPI, SQLAlchemy, spaCy, …) go there instead of into your
system Python, so projects never fight over versions. `.venv` is in `.gitignore` — every person
creates their own; never commit it.

### Easy way (recommended)

```bash
make install
```

That does three things:

```bash
python3.12 -m venv .venv                  # 1. create the venv folder
.venv/bin/pip install --upgrade pip       # 2. update pip inside it
.venv/bin/pip install -e ".[dev]"         # 3. install Syncra and its packages
```

It takes a few minutes the first time (torch and spaCy are big).

### Using the venv

All `make` commands already use `.venv/bin/...` directly, so **you don't need to activate it** to use make.

If you want to type `python`, `alembic`, etc. yourself, activate it:

```bash
source .venv/bin/activate      # your prompt now starts with (.venv)
python --version               # -> 3.12.x, from the venv
deactivate                     # leave the venv
```

If the venv ever gets broken: `rm -rf .venv && make install`.

> In VS Code: `Cmd+Shift+P` → "Python: Select Interpreter" → pick `backend/.venv/bin/python`.

---

## 5. Configure `.env`

```bash
cp .env.example .env
```

Open `backend/.env` and fix the `DATABASE_URL` line. Replace `USER` with your `whoami` output and
the port with yours from step 3. Example for user `alice` on port 5432:

```env
DATABASE_URL=postgresql+psycopg://alice@localhost:5432/syncra
```

Leave everything else as it is. The API tokens (GitHub, Jira, Slack, Hugging Face) will be shared with you
separately. The `POSTGRES_*` lines are for Docker/production only, so ignore them locally.
`.env` is in `.gitignore`: **never commit it**, and never paste tokens into chats, issues or docs.

---

## 6. Create the databases and tables

```bash
make db-init     # creates the syncra database and enables the pgvector extension
make migrate     # creates all tables (runs alembic upgrade head)
```

Expected output of `make db-init`:

```
created database syncra
syncra: ready (pgvector 0.8.x)
```

You never need to create databases or tables by hand — these two commands do it.
Run `make migrate` again any time someone adds a new migration (after a `git pull`).

---

## 7. Look inside the database with DBeaver

1. Open **DBeaver**.
2. Click the **plug icon with a +** (top-left), or menu **Database → New Database Connection**.
3. Choose **PostgreSQL** → **Next**.
4. Fill the **Main** tab:

   - **Connect by**: Host
   - **Host**: `localhost`
   - **Port**: your port from step 3 (`5432` or `5434`)
   - **Database**: `syncra`
   - **Authentication**: Database Native
   - **Username**: your `whoami` name
   - **Password**: *leave it empty*

5. Click **Test Connection…**. The first time, DBeaver asks to **download the PostgreSQL driver** → click **Download**.
   You should see "Connected".
6. Click **Finish**.

Now in the left panel open: `localhost` → `Databases` → `syncra` → `Schemas` → `public` → `Tables`.
You should see tables like `users`, `sources`, `items`, `chunks`, `entities`, `edges`, `decisions`,
`chat_sessions`, `chat_messages`, `actions`, `sync_cursors` and `alembic_version`.

- Double-click a table → **Data** tab to see rows.
- **SQL Editor → New SQL script** (or `Ctrl+]`) to run queries.
- If tables don't show up after `make migrate`, right-click the connection → **Refresh** (F5).

> Tables are created by `make migrate`, **not** by DBeaver. Don't create or change tables by hand in DBeaver —
> schema changes go through Alembic migrations in `backend/migrations/versions/`.

---

## 8. Download the AI models

Start Ollama (open the **Ollama** app once, or run `ollama serve` in a separate terminal), then:

```bash
make pull-models        # Ollama LLMs: qwen3:4b and qwen3:8b   (~8 GB)
make download-models    # Hugging Face models from config/models.yaml (embeddings, reranker, …)
make train-triage       # trains the noise filter (~30 s), prints "Held-out accuracy: 9x.x%"
make train-intent-router  # trains the chat's intent router (~25 s), prints its accuracy too
```

- Models are listed in `backend/config/models.yaml`. Change models there, not in code.
- `meta-llama/Llama-Prompt-Guard-2-86M` is **gated**: it needs a Hugging Face token. Accept Meta's licence on
  its Hugging Face page, create a token (Settings → Access Tokens, "read"), put it in `backend/.env` as
  `HF_TOKEN=…` and run `make download-models` again. Until then it's skipped (the script says so), the rest
  still download, and **chat messages fail at the prompt guard**.
- Downloads are big and slow — do this on good Wi-Fi. You only do it once.
- `make train-triage` and `make train-intent-router` save their classifiers in `backend/models/`
  (not in git). Run each again whenever its examples (`backend/config/triage.yaml`,
  `backend/config/intent_router.yaml`) change after a `git pull`.

---

## 9. Run it

```bash
make run        # API on http://127.0.0.1:8000
```

Check it works — open http://127.0.0.1:8000/health (should show `{"status":"ok"}`)
or http://127.0.0.1:8000/docs for the interactive API page. Stop with `Ctrl+C`.

Everything else in the API needs a login. Create one for yourself (in a second terminal, inside `backend/`):

```bash
make add-user      # asks for a username, a display name, a password (8+ characters) and "Admin?" (say y)
```

In http://127.0.0.1:8000/docs, open `POST /auth/login`, click **Try it out**, send your username and
password, and copy the `token` from the answer. Click **Authorize** at the top of the page and paste it.
Now `GET /me` shows who you are. A token works for 12 hours; then log in again.

**Open the web app.** In another terminal:

```bash
cd frontend
npm install     # first time only
npm run dev     # then open http://localhost:5173
```

Log in with the user you just made and ask a question. Answers stream in word by word; the small numbers
are citations (point at one to see its source, click to open it). "Open a Jira ticket to …" shows an
approval card: nothing happens until you press **Approve and create**. As an admin you also get
**Sources** (add and sync repos, projects, channels), **People** (link accounts) and **Activity**.

**Chat through the API instead.** In `/docs`, `POST /chat/sessions` starts a chat (copy its `id`), then
`POST /chat/sessions/{id}/messages` with `{"message": "who built the payment service?"}` answers with cited
`sources`, a `confidence` and `follow_ups`. "Open a Jira ticket to …" returns an approval card instead;
approve it with `POST /actions/{id}/approve`. The first question after `make run` can take a few extra
seconds while the models finish loading.

**No data yet?** Load the demo company (step 11) to try the chat right away.

To sync and learn from GitHub/Jira/Slack in the background, run `make worker` in a second terminal (also inside `backend/`).
It needs Ollama running and the noise filter trained (`make train-triage`, step 8).
It needs the source credentials (step 10).

---

## 10. Connect a data source (optional)

1. Get the source credentials from the project owner and add them to `backend/.env`.
2. Logged in as an admin in http://127.0.0.1:8000/docs, add one source per repo / project / channel with
   `POST /admin/sources`, e.g. `{"kind": "github", "external_id": "acme/payments"}`,
   `{"kind": "jira", "external_id": "PAY"}` or `{"kind": "slack", "external_id": "C0123456789", "name": "#eng"}`.
   `GET /admin/sources` shows each one's last sync and error; `POST /admin/sources/{id}/sync` syncs one now.
   The tokens need to see who can read each source: push access to private GitHub repos, the Slack scopes
   `channels:read` / `groups:read`, and permission to see Jira project permissions.
3. `make worker` — new items show up in the `items` table (personal data and secrets are scrubbed first), then the
   worker learns from them: `chunks`, `entities`, `decisions` and `edges` fill up, and each item's `status` becomes
   `processed` or `noise`.
4. Link each person's accounts to their Syncra user with `make link-account`. It asks for the username, the tool
   (`github`, `jira` or `slack`) and the account id: the GitHub login, the Jira accountId, or the Slack member id
   (`U0123…`, from their Slack profile → ⋮ → Copy member ID). Admins can also use
   `POST /admin/users/{username}/accounts` in `/docs`. Only admins can link accounts, because they decide what each
   user may search: a user sees only what their linked accounts can see in the tool itself.
5. `GET /admin/status` shows failed syncs, model errors and slow answers.

---

## 11. Try the demo company (optional)

Want to try the chat without real accounts? Load Acme Pay, a made-up payments company:

```bash
make demo          # asks for one password for all demo users; takes about 3 minutes
```

It needs Ollama running and both classifiers trained (step 8). Then log in as `alice` or `dave` with that
password and ask "Why do orders go through a queue before payments?" or "Who reviewed the idempotency keys PR?".
alice is on the payments team and dave on the auth team, so each sees only their team's private data.

To keep the demo apart from real data, load it into its own database:
`DATABASE_URL=postgresql+psycopg://YOU@localhost:5434/syncra_demo make db-init migrate demo`
(and start the API with the same `DATABASE_URL`).

---

## Daily routine (after first setup)

```bash
cd Syncra
git pull
cd backend
make install        # only if pyproject.toml changed (new packages)
make migrate        # only if new migrations came in (safe to run anyway)
make train-triage   # only if config/triage.yaml changed
make train-intent-router   # only if config/intent_router.yaml changed
make run
make worker         # in a second terminal, if you have sources connected
cd ../frontend && npm install && npm run dev   # in a third terminal: the web app
```

Postgres (`brew services`) and Ollama keep running in the background.

---

## Troubleshooting

**`python3.12: command not found`**: install it with `brew install python@3.12`.

**`connection refused` or `could not connect to server`**: Postgres isn't running. Start it with `brew services start postgresql@18`, and check that the port in `.env` matches what `show port;` says.

**`role "USER" does not exist`**: you forgot to replace `USER` in `.env` with your `whoami` name.

**`extension "vector" is not available`**: run `brew install pgvector`, then `brew services restart postgresql@18`, then `make db-init` again.

**`database "syncra" does not exist`**: run `make db-init`.

**`relation "..." does not exist`**: run `make migrate`.

**`No such file .venv/bin/...`**: run `make install` first.

**The web app says "The answer stopped before it finished"**: the API failed while answering. Look at the
`make run` terminal. Usually `HF_TOKEN` isn't set yet (the prompt guard can't load) or Ollama isn't running.

**Signing in to the web app says "The server had a problem"**: usually the API isn't running. Start
`make run` in `backend/`; the web app expects it on port 8000.

**Ollama errors, or connection refused on port 11434**: start the Ollama app, or run `ollama serve`.

**Port 8000 already in use**: find what's using it with `lsof -i :8000`, or run the API on another port with `.venv/bin/uvicorn app.main:app --reload --port 8001`.

**`No trained triage classifier in …`**: run `make train-triage`.

**`No trained intent_router classifier in …`**: run `make train-intent-router`.

**Every chat message fails with an error about `Llama-Prompt-Guard-2`**: the prompt guard can't load. Add
`HF_TOKEN` to `backend/.env` (step 8) and run `make download-models`.

**Answers say "Sorry, I can't write an answer right now"**: Ollama isn't reachable. Start it, and check
`ollama list` shows `qwen3:8b` and `qwen3:4b` (`make pull-models`).

**Answers always say "I don't know"**: nothing you can see matches. Check that sources synced
(`GET /admin/sources`), that the worker has learned from them, and that an admin linked your accounts
(`GET /me`): without linked accounts you only see public items.

**A source shows `last_error`**: usually a token without the right access. The error text says which call
failed; fix the token in `.env` and `POST /admin/sources/{id}/sync`.

**Answers are slow**: see `timing.md`. Keep Ollama running; the first question after a restart loads models.

**Packages behaving strangely**: rebuild the venv with `rm -rf .venv && make install`.

---

## Linux / Windows

- **Linux**: install `python3.12`, `postgresql` + `postgresql-XX-pgvector` from your distro, and Ollama from ollama.com.
  The default Postgres user is `postgres` (with a password), so your URL looks like
  `postgresql+psycopg://postgres:PASSWORD@localhost:5432/syncra`. Everything else is the same.
- **Windows**: easiest is **WSL2** (Ubuntu) and follow the Linux notes. Native Windows has no `make`;
  run the commands from the `Makefile` by hand and use `.venv\Scripts\python` instead of `.venv/bin/python`.

---

More docs: [`README.md`](README.md) · [`description.md`](description.md) (what Syncra is) ·
[`flow.md`](flow.md) (how it works, end to end) · [`decision.md`](decision.md) (why it's built this way) ·
[`phases.md`](phases.md) (task list) · [`progress.md`](progress.md) (what's done) · [`agent.md`](agent.md).
