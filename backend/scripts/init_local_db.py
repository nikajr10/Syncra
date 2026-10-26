"""Create the local database named in DATABASE_URL and enable pgvector.

Usage (from backend/):  make db-init        (needs a running PostgreSQL with pgvector installed)
"""

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import get_settings


def ensure_database(url_str: str) -> None:
    url = make_url(url_str)
    dsn = url.set(drivername="postgresql").render_as_string(hide_password=False)
    admin_dsn = url.set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        exists = conn.execute(
            "select 1 from pg_database where datname = %s", (url.database,)
        ).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(url.database)))
            print(f"created database {url.database}")
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        version = conn.execute(
            "select extversion from pg_extension where extname = 'vector'"
        ).fetchone()
    print(f"{url.database}: ready (pgvector {version[0] if version else '?'})")


if __name__ == "__main__":
    ensure_database(get_settings().database_url)
