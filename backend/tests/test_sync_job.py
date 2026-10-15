"""Task 1.6: running the job twice stores only new items; a failing connector is logged, skipped."""

import logging

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.engine import new_session
from app.db.schema import Item, Source, SyncCursor
from app.learning.connectors import build_connector
from app.learning.sync import sync_all_sources
from tests.fakes import FakeConnector, item


class Broken:
    def fetch_new(self, since_cursor: str | None) -> tuple:
        raise ConnectionError("jira is down")


def test_sync_all_sources_skips_failures_and_is_idempotent(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    good = Source(kind="slack", name="#eng", external_id="C1")
    bad = Source(kind="jira", name="PAY", external_id="PAY")
    off = Source(kind="github", name="acme/old", external_id="acme/old", enabled=False)
    db_session.add_all([good, bad, off])
    db_session.commit()

    connectors = {"C1": FakeConnector([item(1), item(2)]), "PAY": Broken()}

    def build(source: Source):  # noqa: ANN202
        return connectors[source.external_id]

    with caplog.at_level(logging.ERROR, logger="syncra.learning"):
        results = sync_all_sources(new_session, build)

    assert results["#eng"] == 2
    assert results["PAY"].startswith("ConnectionError: jira is down")
    assert "acme/old" not in results  # disabled sources are not synced
    assert "sync failed for jira PAY" in caplog.text

    db_session.expire_all()
    assert db_session.get(Source, bad.id).last_error.startswith("ConnectionError")
    assert db_session.get(Source, good.id).last_error is None
    assert db_session.get(SyncCursor, good.id).cursor == "2"
    assert {i.status for i in db_session.scalars(select(Item))} == {"new"}  # Phase 2 queue

    # Second run: nothing new for the good source, the bad one still fails without side effects.
    results = sync_all_sources(new_session, build)
    assert results["#eng"] == 0
    assert db_session.scalars(select(Item)).all().__len__() == 2
    assert connectors["C1"].calls == [None, "2"]


def test_registry_builds_a_connector_per_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "t")
    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        assert type(build_connector(Source(kind="github", external_id="o/r"))).__name__ == (
            "GitHubConnector"
        )
        assert type(build_connector(Source(kind="slack", external_id="C1"))).__name__ == (
            "SlackConnector"
        )
        with pytest.raises(ValueError):
            build_connector(Source(kind="email", external_id="x"))
    finally:
        get_settings.cache_clear()
