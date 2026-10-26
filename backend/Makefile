.PHONY: install run worker lint fmt pull-models download-models train-triage db-init migrate \
	train-intent-router add-user link-account demo eval

PYTHON ?= python3.12

install:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -q --upgrade pip
	.venv/bin/pip install -q -e ".[dev]"

run:
	.venv/bin/uvicorn app.api.main:app --reload

worker:
	.venv/bin/python -m app.jobs.scheduler

lint:
	.venv/bin/ruff check . && .venv/bin/ruff format --check .

fmt:
	.venv/bin/ruff format . && .venv/bin/ruff check --fix .

pull-models:
	.venv/bin/python scripts/pull_ollama_models.py

download-models:
	.venv/bin/python scripts/download_hf_models.py

train-triage:
	.venv/bin/python scripts/train.py triage

train-intent-router:
	.venv/bin/python scripts/train.py intent_router

db-init:
	.venv/bin/python scripts/init_local_db.py

migrate:
	.venv/bin/alembic upgrade head

add-user:
	.venv/bin/python scripts/users.py add

link-account:
	.venv/bin/python scripts/users.py link

demo:
	.venv/bin/python scripts/demo.py

eval:
	.venv/bin/python scripts/evaluate.py
