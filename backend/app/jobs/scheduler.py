"""Background job runner: APScheduler in-process, no broker. Run with `make worker`.

Jobs are plain functions registered in `build_scheduler()`. The interval comes from settings
(`SYNC_INTERVAL_MINUTES`). Each job runs once at startup, then on its interval; overlapping
runs are never started (`max_instances=1`, `coalesce=True`).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from app.config.settings import get_settings

log = logging.getLogger("syncra.jobs")


def learn() -> None:
    """Task 4.4: sync every source, then run the learning pipeline over what is new."""
    from app.learning.pipeline import learn as run_pipeline  # heavy imports kept lazy

    run_pipeline()  # logs "learn: {counts}"


def build_scheduler() -> BlockingScheduler:
    minutes = get_settings().sync_interval_minutes
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        learn,
        "interval",
        minutes=minutes,
        id="learn",
        next_run_time=datetime.now(UTC),
        max_instances=1,
        coalesce=True,
    )
    return scheduler


def main() -> None:
    from app.monitor import setup_logging

    settings = get_settings()
    setup_logging()
    log.info("worker starting; learning every %s min", settings.sync_interval_minutes)
    try:
        build_scheduler().start()
    except (KeyboardInterrupt, SystemExit):
        log.info("worker stopped")


if __name__ == "__main__":
    main()
