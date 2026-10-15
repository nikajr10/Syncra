"""Fakes and helpers shared by tests. No network, no real services."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.schema import Chunk, Decision, Edge, Entity, Item
from app.learning.connectors.base import RawItem


def item(n: int, text: str = "", **overrides: object) -> RawItem:
    base = dict(
        external_id=str(n),
        type="message",
        text=text or f"message {n}",
        author="slack:U1",
        created_at=datetime(2026, 10, 1, 0, 0, n, tzinfo=UTC),
        link=f"https://example.test/{n}",
        access_tags=("slack:channel:C1",),
    )
    return RawItem(**{**base, **overrides})


class FakeConnector:
    """Items with numeric external ids; the cursor is the highest id handed out so far."""

    def __init__(self, items: list[RawItem]) -> None:
        self.items = items
        self.calls: list[str | None] = []

    def fetch_new(self, since_cursor: str | None) -> tuple[list[RawItem], str | None]:
        self.calls.append(since_cursor)
        start = int(since_cursor) if since_cursor else 0
        new = [i for i in self.items if int(i.external_id) > start]
        return new, (new[-1].external_id if new else since_cursor)


class Feed:
    """A source whose items arrive in order: each fetch returns what it hasn't handed out yet."""

    def __init__(self, *items: RawItem) -> None:
        self.items = list(items)

    def fetch_new(self, since_cursor: str | None) -> tuple[list[RawItem], str | None]:
        start = int(since_cursor or 0)
        return self.items[start:], str(len(self.items))


def graph_links(session: Session) -> list[tuple[str, str, str]]:
    """Every knowledge-graph link as (from, relation, to) with readable names, duplicates kept."""
    session.expire_all()  # other sessions may have written
    items = {i.id: i.external_id for i in session.scalars(select(Item))}
    name = {("entity", e.id): e.name for e in session.scalars(select(Entity))}
    name |= {("item", i): external for i, external in items.items()}
    name |= {
        ("chunk", c.id): f"chunk of {items[c.item_id]}" for c in session.scalars(select(Chunk))
    }
    name |= {
        ("decision", d.id): f"decision on {items[d.item_id]}"
        for d in session.scalars(select(Decision))
    }
    return sorted(
        (name[e.src_type, e.src_id], e.relation, name[e.dst_type, e.dst_id])
        for e in session.scalars(select(Edge))
    )
