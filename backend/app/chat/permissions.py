"""Permission filter (Task 6.1): limit any search to the items the asking user may see.

A user may see an item when the item is tagged `public`, or when one of the user's linked
accounts (`user_source_identities`) is a member of the source whose tag the item carries
(`sources.members`, refreshed by every sync). `visible(tags)` is a WHERE condition on `items`,
so the filter runs inside the search query: hidden items are never fetched, ranked or counted.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from app.db.schema import Item, Source, UserSourceIdentity

PUBLIC = "public"


def user_tags(session: Session, user_id: int) -> list[str]:
    """The access tags `user_id` holds: `public`, plus the tag of every source they belong to."""
    accounts = [
        f"{kind}:{external_id}"
        for kind, external_id in session.execute(
            select(UserSourceIdentity.source_kind, UserSourceIdentity.external_id).where(
                UserSourceIdentity.user_id == user_id
            )
        )
    ]
    sources = session.scalars(select(Source).where(Source.members.overlap(accounts))).all()
    return sorted({PUBLIC, *(source.access_tag for source in sources)})


def visible(tags: list[str]) -> ColumnElement[bool]:
    """WHERE condition: the item carries at least one of `tags` (GIN-indexed array overlap)."""
    return Item.access_tags.overlap(tags)
