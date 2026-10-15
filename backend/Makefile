.PHONY: install run test lint fmt

PYTHON ?= python3.12

install:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -q --upgrade pip
	.venv/bin/pip install -q -e ".[dev]"

run:
	.venv/bin/uvicorn app.api.main:app --reload

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check . && .venv/bin/ruff format --check .

fmt:
	.venv/bin/ruff format . && .venv/bin/ruff check --fix .
