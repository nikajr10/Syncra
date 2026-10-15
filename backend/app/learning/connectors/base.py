"""Connector interface and the one item format every source produces (Task 1.1)."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, field_validator

from app.db.schema import ItemType


class RawItem(BaseModel):
    """One thing pulled from a source (before privacy scrubbing). Stored in `items`."""

    model_config = ConfigDict(frozen=True)

    external_id: str  # unique within its source: "#42", "comment:9", "<sha>", "<slack ts>"
    type: ItemType
    text: str
    title: str | None = None
    author: str | None = None  # "github:alice", "jira:<accountId>", "slack:U0123"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    link: str | None = None
    parent_external_id: str | None = None  # the PR / issue / thread this belongs to
    # who may see it: "public", "github:repo:org/x", "jira:project:PAY", "slack:channel:C1"
    access_tags: tuple[str, ...]

    @field_validator("access_tags")
    @classmethod
    def _must_say_who_can_see_it(cls, tags: tuple[str, ...]) -> tuple[str, ...]:
        if not tags:
            raise ValueError("access_tags must name who can see the item (fail closed)")
        return tags

    def content_hash(self) -> str:
        parts = (self.type, self.title or "", self.text, self.author or "", self.link or "")
        return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


class Connector(Protocol):
    def fetch_new(self, since_cursor: str | None) -> tuple[list[RawItem], str | None]:
        """Return (new or changed items since the cursor, next cursor).

        Re-running with the returned cursor must fetch nothing new. Return the same cursor
        back when there is nothing new.
        """
