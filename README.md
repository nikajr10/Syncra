# Syncra

Team-memory chatbot: learns from GitHub, Jira and Slack, answers questions with cited sources. Every model runs locally.

Docs: [`description.md`](description.md) (what it is) · [`phases.md`](phases.md) (task list) · [`progress.md`](progress.md) (what's done) · [`agent.md`](agent.md) (how agents work on it).

## Setup

Requires Python 3.11+ (3.12 recommended), Docker, and [Ollama](https://ollama.com) installed natively (on macOS Ollama in Docker has no GPU).

```bash
make install      # creates .venv and installs the backend + dev tools
```

## Run

```bash
make run          # API on http://127.0.0.1:8000  (GET /health -> {"status": "ok"})
make test         # run the test suite
make lint         # ruff check + format check
```
