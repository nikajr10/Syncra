"""Shared test setup.

Tests must never touch the dev database, so DATABASE_URL is forced to the test database
(TEST_DATABASE_URL from the environment or backend/.env) before any `app` module reads settings.
"""

import getpass
import os
from collections.abc import Iterator

import pytest
from dotenv import dotenv_values

from app.config.settings import BACKEND_DIR

_env = {**dotenv_values(BACKEND_DIR / ".env"), **os.environ}
os.environ["DATABASE_URL"] = _env.get("TEST_DATABASE_URL") or (
    f"postgresql+psycopg://{getpass.getuser()}@localhost:5434/syncra_test"
)


@pytest.fixture(scope="session")
def migrated_db() -> Iterator[None]:
    """Empty, fully migrated test database for the whole session; dropped again at the end."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
    command.downgrade(cfg, "base")


@pytest.fixture
def db_session(migrated_db: None) -> Iterator["Session"]:  # noqa: F821
    """A session on the test database. Every table is truncated after the test."""
    from sqlalchemy import text

    from app.db.engine import get_engine, new_session
    from app.db.schema import Base

    with new_session() as session:
        yield session
        session.rollback()
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with get_engine().begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
