"""Monitoring (Task 10.5): logging setup, and events an admin sees in GET /admin/status.

`record(kind, message, **details)` saves an event in its own session, so it survives the
caller's rollback, and never raises: monitoring must not break what it watches. Kinds:
`sync_failed`, `learn_failed`, `model_error`, `slow_answer`.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete

from app.core.config import get_settings
from app.db.models import Event
from app.db.session import new_session

log = logging.getLogger("syncra.monitor")
STANDARD = set(vars(logging.makeLogRecord({})))  # attributes every log record has


class JsonFormatter(logging.Formatter):
    """One JSON object per line: time, level, logger, message, extra fields, exception."""

    def format(self, record: logging.LogRecord) -> str:
        line = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **{k: v for k, v in vars(record).items() if k not in STANDARD},
        }
        if record.exc_info:
            line["exception"] = self.formatException(record.exc_info)
        return json.dumps(line, default=str)


def setup_logging() -> None:
    """Syncra's loggers at LOG_LEVEL, as text or JSON (LOG_FORMAT), for the API and the worker."""
    settings = get_settings()
    handler = logging.StreamHandler()
    if settings.log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    syncra = logging.getLogger("syncra")
    syncra.handlers[:] = [handler]
    syncra.setLevel(settings.log_level)
    syncra.propagate = False


def record(kind: str, message: str, **details: Any) -> None:
    try:
        with new_session() as session:
            session.add(Event(kind=kind, message=message[:2000], details=details))
            keep = datetime.now(UTC) - timedelta(days=get_settings().events_keep_days)
            session.execute(delete(Event).where(Event.created_at < keep))
            session.commit()
    except Exception:
        log.exception("could not record event %s: %s", kind, message)


class Timer:
    """Seconds per stage: `lap("search")` records the time since the previous lap."""

    def __init__(self) -> None:
        self.started = self.last = time.perf_counter()
        self.stages: dict[str, float] = {}

    def lap(self, stage: str) -> None:
        now = time.perf_counter()
        self.stages[stage] = round(now - self.last, 3)
        self.last = now

    def total(self) -> float:
        return round(time.perf_counter() - self.started, 3)
