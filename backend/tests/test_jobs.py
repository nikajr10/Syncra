"""Task 0.6: the worker runs the dummy job on the configured interval and logs it."""

import logging
import threading
from datetime import timedelta

import pytest

from app.config.settings import get_settings
from app.jobs import scheduler as jobs


def test_dummy_job_interval_comes_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    job = jobs.build_scheduler().get_job("heartbeat")
    assert job.trigger.interval == timedelta(minutes=get_settings().sync_interval_minutes)

    monkeypatch.setenv("SYNC_INTERVAL_MINUTES", "3")
    get_settings.cache_clear()
    try:
        assert jobs.build_scheduler().get_job("heartbeat").trigger.interval == timedelta(minutes=3)
    finally:
        get_settings.cache_clear()


def test_worker_runs_dummy_job_on_start_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    fired = threading.Event()
    scheduler = jobs.build_scheduler()
    scheduler.add_listener(lambda event: fired.set(), mask=4096)  # EVENT_JOB_EXECUTED

    worker = threading.Thread(target=scheduler.start, daemon=True)
    with caplog.at_level(logging.INFO, logger="syncra.jobs"):
        worker.start()
        assert fired.wait(timeout=10), "heartbeat job did not run"
        scheduler.shutdown(wait=False)
        worker.join(timeout=5)

    assert "heartbeat: worker alive" in caplog.text
