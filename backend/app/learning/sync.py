"""Save connector output and move the source's cursor, in one transaction (Task 1.1)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.engine import new_session
from app.db.schema import Item, Source, SyncCursor
from app.learning.connectors import build_connector
from app.learning.connectors.base import Connector, RawItem

log = logging.getLogger("syncra.learning")

BATCH = 500
_UPDATABLE = (
    "type",
    "title",
    "text",
    "author",
    "link",
    "parent_external_id",
    "created_at",
    "updated_at",
    "access_tags",
    "content_hash",
)


def save_items(
    session: Session, source: Source, items: Iterable[RawItem], next_cursor: str | None
) -> int:
    """Upsert `items` for `source` and set its cursor, then commit once.

    Returns the number of rows inserted or changed. Items whose content hash is unchanged are
    skipped; changed ones go back to status "new" so later stages process them again.
    Exact duplicates inside one batch collapse to the last one.
    """
    by_id = {item.external_id: item for item in items}
    rows = [
        {
            "source_id": source.id,
            "external_id": item.external_id,
            "type": item.type,
            "title": item.title,
            "text": item.text,
            "author": item.author,
            "link": item.link,
            "parent_external_id": item.parent_external_id,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "access_tags": list(item.access_tags),
            "content_hash": item.content_hash(),
        }
        for item in by_id.values()
    ]
    changed = 0
    for start in range(0, len(rows), BATCH):
        stmt = insert(Item).values(rows[start : start + BATCH])
        set_ = {col: getattr(stmt.excluded, col) for col in _UPDATABLE}
        set_["status"] = "new"
        set_["ingested_at"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=["source_id", "external_id"],
            set_=set_,
            where=Item.content_hash.is_distinct_from(stmt.excluded.content_hash),
        ).returning(Item.id)
        changed += len(session.execute(stmt).all())

    cursor = session.get(SyncCursor, source.id) or SyncCursor(source_id=source.id)
    cursor.cursor = next_cursor
    session.add(cursor)
    source.last_synced_at = datetime.now(UTC)
    source.last_error = None
    session.commit()
    return changed


def sync_source(
    session: Session,
    source: Source,
    connector: Connector,
    scrub: Callable[[RawItem], RawItem] | None = None,
) -> int:
    """fetch_new(cursor) -> scrub every item -> save items + new cursor, in one transaction.

    `scrub` defaults to the Presidio scrubber (Task 1.5); nothing is stored unscrubbed.
    Returns rows inserted or changed.
    """
    if scrub is None:
        from app.learning.scrub import get_scrubber  # heavy import kept lazy

        scrub = get_scrubber().scrub_item
    cursor = session.get(SyncCursor, source.id)
    items, next_cursor = connector.fetch_new(cursor.cursor if cursor else None)
    items = [scrub(item) for item in items]
    source.members = sorted(set(connector.members()))  # saved with the items, in one commit
    changed = save_items(session, source, items, next_cursor)
    log.info(
        "sync %s %s: fetched=%d changed=%d cursor=%s",
        source.kind,
        source.name,
        len(items),
        changed,
        next_cursor,
    )
    return changed


def sync_all_sources(
    session_factory: Callable[[], Session] = new_session,
    build: Callable[[Source], Connector] = build_connector,
) -> dict[str, int | str]:
    """The scheduled job (Task 1.6): every enabled source -> connector -> scrub -> save.

    Each source runs in its own session. A failing source is logged, recorded in
    `sources.last_error` and skipped; the others still run. Saved items have status "new",
    which is the queue for Phase 2. Returns {source name: rows changed | error message}.
    """
    with session_factory() as session:
        source_ids = session.scalars(
            select(Source.id).where(Source.enabled.is_(True)).order_by(Source.id)
        ).all()

    results: dict[str, int | str] = {}
    for source_id in source_ids:
        with session_factory() as session:
            source = session.get(Source, source_id)
            if source is None:
                continue
            try:
                results[source.name] = sync_source(session, source, build(source))
            except Exception as exc:  # one bad source must not stop the others
                session.rollback()
                log.exception("sync failed for %s %s", source.kind, source.name)
                source.last_error = f"{type(exc).__name__}: {exc}"[:2000]
                session.commit()
                results[source.name] = source.last_error
    log.info("sync run finished: %d sources, %s", len(results), results)
    return results
