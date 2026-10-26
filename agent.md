# Syncra — Agent Guide

You are a coding agent (e.g. Claude Code) joining the **Syncra** project. This file tells you how to pick up work, what is already done, and how to hand off to the next agent.

---

## 1. Read these first, in this order

1. `agent.md`: this file, how to work.
2. `progress.md`: **what is already done**, what's next and the open problems.
3. `description.md`: **what Syncra is**, its architecture, pipelines, models and rules.
4. `phases.md`: **the task list**, every task with Build / Done when / Depends on.

Never start coding before reading `progress.md`. Earlier agents may have made choices (frameworks, folder layout, naming) you must follow.

For background written for humans: `flow.md` follows the data through the system end to end, and `decision.md` explains each choice made so far and what else was possible.

---

## 2. Project in one paragraph

Syncra is a team-memory chatbot. A **learning pipeline** (offline, every 15 min) pulls GitHub, Jira and Slack data, hides private data (Presidio), drops noise (SetFit), chunks text, finds entities (GLiNER), reads decisions (Qwen3 via Ollama), embeds chunks (Qwen3-Embedding, 1024-dim), links entities (SBERT) and stores everything in **PostgreSQL + pgvector**. A **chatbot pipeline** (online) remembers the last 10 turns, rewrites follow-ups (Qwen3 4B), blocks prompt attacks (Prompt Guard 2), routes intent (SetFit), runs hybrid search (vector + keyword + graph, permission-filtered), reranks to the best 8 (cross-encoder), writes a streamed cited answer (Qwen3 8B), checks claims (DeBERTa NLI) and returns answer · sources · confidence · follow-ups. Everything runs **locally**.

---

## 3. Current state of the repo

- Planning docs are written: `description.md`, `phases.md`, `agent.md`, `progress.md`.
- **The Python project lives in `backend/`** (decided in Task 0.1): package `backend/app/`, yaml in `backend/config/`, `backend/tests/`, `backend/scripts/`, `backend/pyproject.toml`, `backend/Makefile`. Commands (from `backend/`): `make install`, `make run`, `make test`, `make lint`.
- **The learning pipeline is complete (Phases 1–4):** `make worker` runs `app/learning/pipeline.py: learn()` every `SYNC_INTERVAL_MINUTES` (sync → scrub → triage → chunk → entities → decisions → embed → link → store).
- **The chat is complete (Phases 5–8):** `app/chat/pipeline.py` runs memory → guard → intent → rewrite → search (`app/chat/search.py`, permission-filtered by `app/chat/permissions.py`) → answer (`answer.py`) → check + confidence (`check.py`), or plans an action (`actions.py`). Endpoints: `app/api/chat.py` (JSON and Server-Sent Events), `app/api/actions.py`, admin endpoints in `app/api/admin.py` (sources, account links, `/admin/status`).
- **Phase 10:** `make demo` loads the fictional company in `backend/demo/company.yaml` (demo sources use `DemoConnector`, never a real API); `make eval` scores the chat on `backend/demo/eval.yaml`; `timing.md` is the speed report; `app/monitor.py` records events for admins. Change a prompt by adding a new version file and pointing `config/models.yaml` at it; re-run `make eval` after any change to search, prompts or the checker.
- **Open:** Task 5.4's real Prompt Guard run waits for `HF_TOKEN` in `backend/.env` (the chat can't answer without it); 9.1–9.3 (web app) are not built because the user asked to keep `frontend/` as it is; 10.4's 3-second target is only partly met (see `timing.md`).
- `frontend/` is reserved for the web app (Phase 9); it holds a prototype (`index.html`, `app.js`, `styles.css`).
- **Local dev runs without Docker** (user decision): your own PostgreSQL + pgvector (dev machine: Homebrew PostgreSQL 18 on port 5434, `make db-init`) and native Ollama. `backend/Dockerfile` + `backend/docker-compose.yml` are **production-only**; never `docker compose up` locally.
- The old empty scaffold that used to live in `backend/` was deleted in Task 0.1.

> Keep this section up to date when something big changes (e.g. layout decided, stack chosen).

---

## 4. How to do a task

1. **Find your task.** Use the task ID you were given. If none was given, take the **Next task** from `progress.md`.
2. **Check dependencies.** Every task in its **Depends on** line must be marked done in `progress.md`. If not, stop and report it — don't build the missing task yourself unless asked.
3. **Read the code that exists.** Follow patterns, names and libraries earlier tasks chose (see **Decisions** in the `progress.md` log).
4. **Build only that task.** Follow its **Build** list. No extra features, no work on later tasks.
5. **Test.** Write tests for the task and run the **whole** test suite. Everything must pass.
6. **Check "Done when".** Every item must be true. If one can't be met, say so in the log — don't hide it.
7. **Update the docs:**
   - Add a log entry to `progress.md` (format below) and update its **Current status**.
   - Tick the task in the **Progress checklist** at the bottom of `phases.md`.
   - Update `README.md` if setup or run commands changed.
   - Update `flow.md` if the task changes how data moves through the system, and add each real choice between alternatives to `decision.md`.
   - Update section 3 of this file if the repo state changed in a big way.
8. **Commit** with message `Task <ID>: <title>`.

---

## 5. Progress log entry format

Add new entries **at the top** of the **Log** section in `progress.md`:

```markdown
### Task <ID> — <title>  ✅ done | ⚠️ partly done | ❌ blocked
**Date:** YYYY-MM-DD

**Built**
- What was added, in plain words.

**Key files**
- `path/to/file` — what it is

**Decisions**
- Choices later agents must follow (library picked, naming, folder layout, config keys).

**How to run / test**
- Commands.

**Known issues / TODO**
- Anything not finished, workarounds, things the next task must know.
```

Then update **Current status** (current phase, next task, completed task list).

---

## 6. Rules (always)

- **Follow `description.md`.** Don't swap a tool or model for another without asking the user.
- **Local only.** LLMs on **Ollama**, small models from **Hugging Face**. No hosted LLM APIs.
- **One database.** PostgreSQL + pgvector for everything. No extra vector DB, search engine or graph DB.
- **Config, not constants.** Model names, labels, 15 min, 10 turns, top 8, 1024 dims live in config.
- **All model calls go through the model gateway** (built in Task 0.5).
- **Privacy first.** Data is scrubbed before it is stored. Searches filter by user permissions **inside** the query.
- **Answers must cite evidence** (`[E1]…[E8]`). Actions need user approval.
- **Tests use fakes.** Mock GitHub, Jira, Slack and Ollama in tests. Never commit real tokens or `.env`.
- **Keep it simple.** Smallest working solution for the task; no speculative abstractions.
- **No tables in the docs.** The user finds markdown tables hard to read: write short paragraphs (2–3 lines each) or simple lists instead.

---

## 7. When you get stuck

- Missing dependency, unclear requirement, or a choice that changes the architecture → **stop and ask the user**.
- Can't finish → log the task as ⚠️ or ❌ in `progress.md` with exactly what is missing, so the next agent can continue.
- Found a problem in an earlier task → note it under **Known issues** and tell the user; fix it only if it's small and blocks your task.
