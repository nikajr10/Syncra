"""Fakes shared by tests. No network, no real services."""

from __future__ import annotations

from datetime import UTC, datetime

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
