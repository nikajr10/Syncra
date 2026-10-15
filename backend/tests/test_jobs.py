"""Tasks 0.6 / 1.6 / 4.4: the worker runs the learning job on its interval and logs it."""

import logging
import threading
from datetime import timedelta

import pytest

from app.config.settings import get_settings
from app.jobs import scheduler as jobs


def test_learning_job_interval_comes_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    job = jobs.build_scheduler().get_job("learn")
    assert job.trigger.interval == timedelta(minutes=get_settings().sync_interval_minutes)

    monkeypatch.setenv("SYNC_INTERVAL_MINUTES", "3")
    get_settings.cache_clear()
    try:
        job = jobs.build_scheduler().get_job("learn")
        assert job.trigger.interval == timedelta(minutes=3)
    finally:
        get_settings.cache_clear()


def test_worker_runs_the_learning_job_on_start_and_logs(
    migrated_db: None, caplog: pytest.LogCaptureFixture
) -> None:
    fired = threading.Event()
    scheduler = jobs.build_scheduler()
    scheduler.add_listener(lambda event: fired.set(), mask=4096)  # EVENT_JOB_EXECUTED

    worker = threading.Thread(target=scheduler.start, daemon=True)
    with caplog.at_level(logging.INFO, logger="syncra"):
        worker.start()
        assert fired.wait(timeout=30), "learning job did not run"
        scheduler.shutdown(wait=False)
        worker.join(timeout=5)

    # empty test DB: nothing to sync or learn
    assert "learn: {'sources': 0, 'noise': 0, 'learned': 0, 'failed': 0}" in caplog.text
