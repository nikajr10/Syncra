"""Task 0.6 / 1.6: the worker runs the sync job on the configured interval and logs it."""

import logging
import threading
from datetime import timedelta

import pytest

from app.config.settings import get_settings
from app.jobs import scheduler as jobs


def test_sync_job_interval_comes_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    job = jobs.build_scheduler().get_job("sync_sources")
    assert job.trigger.interval == timedelta(minutes=get_settings().sync_interval_minutes)

    monkeypatch.setenv("SYNC_INTERVAL_MINUTES", "3")
    get_settings.cache_clear()
    try:
        job = jobs.build_scheduler().get_job("sync_sources")
        assert job.trigger.interval == timedelta(minutes=3)
    finally:
        get_settings.cache_clear()


def test_worker_runs_sync_job_on_start_and_logs(
    migrated_db: None, caplog: pytest.LogCaptureFixture
) -> None:
    fired = threading.Event()
    scheduler = jobs.build_scheduler()
    scheduler.add_listener(lambda event: fired.set(), mask=4096)  # EVENT_JOB_EXECUTED

    worker = threading.Thread(target=scheduler.start, daemon=True)
    with caplog.at_level(logging.INFO, logger="syncra"):
        worker.start()
        assert fired.wait(timeout=30), "sync job did not run"
        scheduler.shutdown(wait=False)
        worker.join(timeout=5)

    assert "sync_sources: 0 sources done" in caplog.text  # empty test DB: nothing to sync
