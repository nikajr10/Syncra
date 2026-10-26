"""Find evidence (Phase 6): the pieces of the knowledge store that answer a question.

Every search takes the asking user's access tags (`permissions.user_tags`) and filters inside
its SQL query (`permissions.visible`), so hidden items are never fetched, ranked or counted.

- `vector_search` (6.2): the question's embedding against the chunks' HNSW index.
- `keyword_search` (6.3): PostgreSQL full-text search on the chunks' GIN index; exact ids
  (`PAY-1234`), function names (`charge_card`) and error codes (`E4012`) must all match.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import Text, cast, func, select, text
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.orm import Session

from app.chat.permissions import visible
from app.config.settings import get_settings
from app.db.schema import Chunk, Item
from app.models import gateway

# ids, function names, error codes: a word with a digit, an underscore or an inner capital
IDENTIFIER = re.compile(r"\b\w[\w-]*?(?:\d|_|[a-z][A-Z])[\w-]*")


@dataclass(frozen=True)
class Evidence:
    """One piece of evidence: a chunk of an item, or a decision read from one."""

    kind: Literal["chunk", "decision"]
    id: int  # chunks.id or decisions.id
    text: str
    item_id: int
    title: str | None
    link: str | None
    author: str | None
    created_at: datetime | None
    score: float  # the search's own score until reranked, then the reranker's
    label: str = ""  # E1…E8 once reranked

    @property
    def key(self) -> tuple[str, int]:
        return self.kind, self.id


def _chunk(chunk: Chunk, item: Item, score: float) -> Evidence:
    return Evidence(
        "chunk", chunk.id, chunk.text, item.id, item.title, item.link, item.author,
        item.created_at, float(score),
    )  # fmt: skip


def _limit(limit: int | None) -> int:
    return limit or get_settings().search_candidates


def vector_search(
    session: Session, tags: list[str], question: str, limit: int | None = None
) -> list[Evidence]:
    """The chunks closest in meaning to `question` (cosine similarity, 1 = same direction)."""
    vector = gateway.embed("embedder", [question], prompt_name="query")[0]
    # pgvector 0.8: keep scanning the HNSW graph until enough rows pass the permission filter
    session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    distance = Chunk.vector.cosine_distance(vector)
    rows = session.execute(
        select(Chunk, Item, distance)
        .join(Item, Item.id == Chunk.item_id)
        .where(visible(tags), Chunk.vector.is_not(None))
        .order_by(distance)
        .limit(_limit(limit))
    ).all()
    return [_chunk(chunk, item, 1 - d) for chunk, item, d in rows]


def keyword_search(
    session: Session, tags: list[str], question: str, limit: int | None = None
) -> list[Evidence]:
    """Chunks sharing words with `question`, best `ts_rank` first.

    A question naming identifiers (`PAY-1234`, `charge_card`, `E4012`) only matches chunks that
    contain all of them; any other question matches chunks with any of its words.
    """
    ids = IDENTIFIER.findall(question)
    if ids:
        query = func.plainto_tsquery("english", " ".join(ids))  # every word must match
    else:  # any word may match: plainto's "&" becomes "|"
        anded = cast(func.plainto_tsquery("english", question), Text)
        query = cast(func.replace(anded, "&", "|"), TSQUERY)
    rank = func.ts_rank(Chunk.tsv, query)
    rows = session.execute(
        select(Chunk, Item, rank)
        .join(Item, Item.id == Chunk.item_id)
        .where(visible(tags), Chunk.tsv.op("@@")(query))
        .order_by(rank.desc(), Chunk.id)
        .limit(_limit(limit))
    ).all()
    return [_chunk(chunk, item, r) for chunk, item, r in rows]
