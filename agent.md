# Syncra — Agent Guide

You are a coding agent (e.g. Claude Code) joining the **Syncra** project. This file tells you how to pick up work, what is already done, and how to hand off to the next agent.

---

## 1. Read these first, in this order

| File | Why |
|---|---|
| `agent.md` | This file — how to work |
| `progress.md` | **What is already done**, what's next, open problems |
| `description.md` | **What Syncra is** — architecture, pipelines, models, rules |
| `phases.md` | **The task list** — every task with Build / Done when / Depends on |

Never start coding before reading `progress.md`. Earlier agents may have made choices (frameworks, folder layout, naming) you must follow.

---

## 2. Project in one paragraph

Syncra is a team-memory chatbot. A **learning pipeline** (offline, every 15 min) pulls GitHub, Jira and Slack data, hides private data (Presidio), drops noise (SetFit), chunks text, finds entities (GLiNER), reads decisions (Qwen3 via Ollama), embeds chunks (Qwen3-Embedding, 1024-dim), links entities (SBERT) and stores everything in **PostgreSQL + pgvector**. A **chatbot pipeline** (online) remembers the last 10 turns, rewrites follow-ups (Qwen3 4B), blocks prompt attacks (Prompt Guard 2), routes intent (SetFit), runs hybrid search (vector + keyword + graph, permission-filtered), reranks to the best 8 (cross-encoder), writes a streamed cited answer (Qwen3 8B), checks claims (DeBERTa NLI) and returns answer · sources · confidence · follow-ups. Everything runs **locally**.

---

## 3. Current state of the repo

- Planning docs are written: `description.md`, `phases.md`, `agent.md`, `progress.md`.
- **The Python project lives in `backend/`** (decided in Task 0.1): package `backend/app/`, yaml in `backend/config/`, `backend/tests/`, `backend/scripts/`, `backend/pyproject.toml`, `backend/Makefile`. Commands (from `backend/`): `make install`, `make run`, `make test`, `make lint`.
- `frontend/` is reserved for the web app (Phase 9); it only holds a placeholder today.
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

---

## 7. When you get stuck

- Missing dependency, unclear requirement, or a choice that changes the architecture → **stop and ask the user**.
- Can't finish → log the task as ⚠️ or ❌ in `progress.md` with exactly what is missing, so the next agent can continue.
- Found a problem in an earlier task → note it under **Known issues** and tell the user; fix it only if it's small and blocks your task.
