"""Shared test setup.

Tests must never touch the dev database, so DATABASE_URL is forced to the test database
before any `syncra` module reads settings. Override with TEST_DATABASE_URL.
"""

import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://syncra:syncra@localhost:5436/syncra_test"
)
