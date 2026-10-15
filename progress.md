# Syncra — Progress Log

Live record of what has been built. Agents add an entry here after every task (format in [`agent.md`](agent.md)).

## Current status

- **Current phase:** Phase 0 — Foundation
- **Next task:** 0.3 — Configuration (then 0.2, 0.4, 0.5, 0.6)
- **Completed tasks:** 0.1

## Log

### Task 0.1 — Project skeleton  ✅ done
**Date:** 2026-10-15

**Built**
- Python project at the **repo root** (not in `backend/`): `pyproject.toml`, `Makefile`, `.gitignore`, `README.md`.
- FastAPI app with `GET /health` → `{"status": "ok"}` and a test for it.
- Package layout `syncra/{api,learning,chat,models,db,jobs,config}` plus `config/` (yaml), `scripts/`, `tests/`.

**Key files**
- `pyproject.toml` — deps (`fastapi`, `uvicorn`), dev deps (`pytest`, `httpx`, `ruff`), ruff + pytest config
- `Makefile` — `make install` / `make run` / `make test` / `make lint` / `make fmt`
- `syncra/api/main.py` — FastAPI app
- `tests/test_health.py` — health test

**Decisions**
- **Python 3.12** via `python3.12 -m venv .venv` + pip (no uv/poetry). Override with `make install PYTHON=python3.11`.
- **Layout:** `syncra/api` (web API), `syncra/learning` (learning pipeline), `syncra/chat` (chatbot pipeline), `syncra/models` (model gateway), `syncra/db` (database), `syncra/jobs` (background jobs), `syncra/config` (settings code), `config/` (yaml + prompts), `scripts/`, `tests/`.
- **Linter + formatter:** ruff. **Tests:** pytest (`tests/` is a package, tests import `syncra` directly from the editable install).
- The old `backend/` scaffold (125 empty files) could not be deleted by the agent (permission denied). It is dead; delete it with `git rm -r backend frontend/hello.txt`. `ruff` excludes it.

**How to run / test**
- `make install && make test && make lint`; `make run` then `curl localhost:8000/health`.

**Known issues / TODO**
- Starlette's TestClient warns that `httpx` is deprecated in favour of `httpx2`; harmless, revisit when `httpx2` is stable.
