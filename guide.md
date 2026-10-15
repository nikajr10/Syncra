# Syncra – Setup Guide

A step-by-step guide to get Syncra running on your own computer, from nothing to a working API.
Written for macOS. Linux and Windows notes are at the end.

Locally we **do not use Docker**. Postgres, Ollama and Python all run directly on your machine.
Docker (`backend/Dockerfile`, `backend/docker-compose.yml`) is only for production.

---

## 0. What you will install

| Tool | Why |
|---|---|
| Homebrew | macOS package manager, installs everything else |
| Git | to clone the code |
| Python 3.12 | the backend is Python |
| PostgreSQL 18 + pgvector | the database (pgvector stores AI embeddings) |
| Ollama | runs the local LLMs (Qwen3) |
| DBeaver | a GUI to look inside the database (optional but handy) |

---

## 1. Install the tools

Install Homebrew first if you don't have it (https://brew.sh), then:

```bash
brew install git python@3.12 postgresql@18 pgvector
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

   | Field | Value |
   |---|---|
   | Connect by | Host |
   | Host | `localhost` |
   | Port | your port from step 3 (`5432` or `5434`) |
   | Database | `syncra` |
   | Authentication | Database Native |
   | Username | your `whoami` name |
   | Password | *leave empty* |

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
```

- Models are listed in `backend/config/models.yaml`. Change models there, not in code.
- `meta-llama/Llama-Prompt-Guard-2-86M` is **gated**: it needs a Hugging Face token, which you'll get later.
  Until then it's skipped (the script says so); the rest still download.
- Downloads are big and slow — do this on good Wi-Fi. You only do it once.

---

## 9. Run it

```bash
make run        # API on http://127.0.0.1:8000
```

Check it works — open http://127.0.0.1:8000/health (should show `{"status":"ok"}`)
or http://127.0.0.1:8000/docs for the interactive API page. Stop with `Ctrl+C`.

To sync GitHub/Jira/Slack in the background, run `make worker` in a second terminal (also inside `backend/`).
It needs the source credentials (step 10).

---

## 10. Connect a data source (optional)

1. Get the source credentials from the project owner and add them to `backend/.env`.
2. Add one row per repo / project / channel to the `sources` table (DBeaver SQL editor works):

   ```sql
   insert into sources (kind, name, external_id) values
     ('github', 'acme/payments', 'acme/payments'),   -- owner/repo
     ('jira',   'PAY',           'PAY'),             -- project key
     ('slack',  '#eng-payments', 'C0123456789');     -- channel id
   ```
3. `make worker` — new items show up in the `items` table (personal data and secrets are scrubbed first).

---

## Daily routine (after first setup)

```bash
cd Syncra
git pull
cd backend
make install        # only if pyproject.toml changed (new packages)
make migrate        # only if new migrations came in (safe to run anyway)
make run
```

Postgres (`brew services`) and Ollama keep running in the background.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `python3.12: command not found` | `brew install python@3.12` |
| `connection refused` / `could not connect to server` | Postgres isn't running: `brew services start postgresql@18`. Check the port in `.env` matches `show port;` |
| `role "USER" does not exist` | You forgot to replace `USER` in `.env` with your `whoami` name |
| `extension "vector" is not available` | `brew install pgvector`, then `brew services restart postgresql@18` and `make db-init` again |
| `database "syncra" does not exist` | Run `make db-init` |
| `relation "..." does not exist` | Run `make migrate` |
| `No such file .venv/bin/...` | Run `make install` first |
| Ollama errors / connection refused on 11434 | Start the Ollama app or `ollama serve` |
| Port 8000 already in use | `lsof -i :8000` to find it, or run `.venv/bin/uvicorn app.api.main:app --reload --port 8001` |
| Everything weird with packages | `rm -rf .venv && make install` |

---

## Linux / Windows

- **Linux**: install `python3.12`, `postgresql` + `postgresql-XX-pgvector` from your distro, and Ollama from ollama.com.
  The default Postgres user is `postgres` (with a password), so your URL looks like
  `postgresql+psycopg://postgres:PASSWORD@localhost:5432/syncra`. Everything else is the same.
- **Windows**: easiest is **WSL2** (Ubuntu) and follow the Linux notes. Native Windows has no `make`;
  run the commands from the `Makefile` by hand and use `.venv\Scripts\python` instead of `.venv/bin/python`.

---

More docs: [`README.md`](README.md) · [`description.md`](description.md) (what Syncra is) ·
[`phases.md`](phases.md) (task list) · [`progress.md`](progress.md) (what's done) · [`agent.md`](agent.md).
