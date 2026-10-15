"""Shared test setup.

Tests must never touch the dev database, so DATABASE_URL is forced to the test database
(TEST_DATABASE_URL from the environment or backend/.env) before any `app` module reads settings.
"""

import getpass
import os

from dotenv import dotenv_values

from app.config.settings import BACKEND_DIR

_env = {**dotenv_values(BACKEND_DIR / ".env"), **os.environ}
os.environ["DATABASE_URL"] = _env.get("TEST_DATABASE_URL") or (
    f"postgresql+psycopg://{getpass.getuser()}@localhost:5434/syncra_test"
)
