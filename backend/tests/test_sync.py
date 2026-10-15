"""Task 1.1: a fake connector's items are saved, the cursor moves, re-running fetches nothing."""

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.engine import new_session
from app.db.schema import Item, Source, SyncCursor
from app.learning.connectors.base import RawItem
from app.learning.sync import save_items, sync_source
from tests.fakes import FakeConnector, item


@pytest.fixture
def source(db_session: Session) -> Source:
    src = Source(kind="slack", name="#eng", external_id="C1")
    db_session.add(src)
    db_session.commit()
    return src


def _items(session: Session) -> dict[str, Item]:
    return {i.external_id: i for i in session.scalars(select(Item))}


def test_items_saved_cursor_moves_and_rerun_fetches_nothing(
    db_session: Session, source: Source
) -> None:
    connector = FakeConnector([item(1), item(2), item(3)])

    assert sync_source(db_session, source, connector) == 3
    assert db_session.get(SyncCursor, source.id).cursor == "3"
    assert set(_items(db_session)) == {"1", "2", "3"}
    assert source.last_synced_at is not None

    assert sync_source(db_session, source, connector) == 0
    assert connector.calls == [None, "3"]
    assert db_session.get(SyncCursor, source.id).cursor == "3"
    assert len(_items(db_session)) == 3

    connector.items.append(item(4))
    assert sync_source(db_session, source, connector) == 1
    assert db_session.get(SyncCursor, source.id).cursor == "4"


def test_changed_items_update_and_reset_status_unchanged_are_skipped(
    db_session: Session, source: Source
) -> None:
    save_items(db_session, source, [item(1, "old text"), item(2)], "2")
    stored = _items(db_session)["1"]
    stored.status = "processed"
    db_session.commit()
    first_ingest = stored.ingested_at

    changed = save_items(db_session, source, [item(1, "new text"), item(2)], "2")
    assert changed == 1
    db_session.expire_all()
    stored = _items(db_session)["1"]
    assert stored.text == "new text" and stored.status == "new"
    assert stored.ingested_at > first_ingest
    assert _items(db_session)["2"].status == "new"


def test_duplicates_in_one_batch_collapse(db_session: Session, source: Source) -> None:
    assert save_items(db_session, source, [item(1, "a"), item(1, "b")], "1") == 1
    assert _items(db_session)["1"].text == "b"


def test_items_and_cursor_are_one_transaction(
    db_session: Session, source: Source, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail() -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(db_session, "commit", fail)
    with pytest.raises(RuntimeError):
        save_items(db_session, source, [item(1)], "1")
    db_session.rollback()

    with new_session() as fresh:
        assert fresh.scalars(select(Item)).all() == []
        assert fresh.get(SyncCursor, source.id) is None


def test_item_must_say_who_can_see_it() -> None:
    with pytest.raises(ValidationError):
        RawItem(external_id="1", type="message", text="x", access_tags=())
    with pytest.raises(ValidationError):
        RawItem(external_id="1", type="tweet", text="x", access_tags=("public",))
