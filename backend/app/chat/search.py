"""Find evidence (Phase 6): the pieces of the knowledge store that answer a question.

Every search takes the asking user's access tags (`permissions.user_tags`) and filters inside
its SQL query (`permissions.visible`), so hidden items are never fetched, ranked or counted.

- `vector_search` (6.2): the question's embedding against the chunks' HNSW index.
- `keyword_search` (6.3): PostgreSQL full-text search on the chunks' GIN index; exact ids
  (`PAY-1234`), function names (`charge_card`) and error codes (`E4012`) must all match.
- `graph_search` (6.4): entities named in the question, then the knowledge graph 1–2 links out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import Text, and_, cast, func, or_, select, text
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.orm import Session

from app.chat.permissions import visible
from app.config.settings import get_settings
from app.db.schema import Chunk, Decision, Edge, EntityAlias, Item
from app.learning.link import key, keys_in
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


def named_entities(session: Session, question: str) -> set[int]:
    """The entities whose name (any alias) appears in `question`, compared by `link.key`, the
    same normalisation the learning pipeline merged names with (`payments-svc` = `PaymentService`).
    """
    # ponytail: every name alias is loaded per question; store alias keys in the table if
    # entities reach the tens of thousands (same ceiling as link._name_aliases).
    wanted = keys_in(question)
    aliases = session.execute(
        select(EntityAlias.alias, EntityAlias.entity_id).where(EntityAlias.source_kind.is_(None))
    )
    return {entity_id for alias, entity_id in aliases if key(alias) in wanted}


def graph_search(
    session: Session, tags: list[str], question: str, limit: int | None = None
) -> list[Evidence]:
    """Evidence 1–2 links away from the entities the question names.

    One link: chunks that mention them, items they authored or reviewed, decisions they made or
    that are about them. Two links: the replies, reviews and decisions of those items. One-link
    evidence scores 1, two-link evidence 0.5; the reranker orders them later.
    """
    entities = named_entities(session, question)
    if not entities:
        return []
    from_entity = and_(Edge.src_type == "entity", Edge.src_id.in_(entities))
    mentions = select(Edge.src_id).where(
        Edge.relation == "mentions", Edge.dst_type == "entity", Edge.dst_id.in_(entities)
    )
    near_items = {  # items one link away: those with a mentioning chunk, authored or reviewed
        *session.scalars(select(Chunk.item_id).where(Chunk.id.in_(mentions))),
        *session.scalars(select(Edge.dst_id).where(from_entity, Edge.dst_type == "item")),
        *session.scalars(select(Edge.item_id).where(from_entity, Edge.dst_type == "item")),
    }
    near_decisions = select(Edge.dst_id).where(from_entity, Edge.relation == "decided")
    about = select(Edge.src_id).where(
        Edge.src_type == "decision", Edge.relation == "about", Edge.dst_type == "entity",
        Edge.dst_id.in_(entities),
    )  # fmt: skip
    parents = select(Item.source_id, Item.external_id).where(Item.id.in_(near_items))
    far_items = set(
        session.scalars(
            select(Item.id).where(
                or_(
                    Item.id.in_(select(Edge.item_id).where(  # reviews and authorship evidence
                        Edge.dst_type == "item", Edge.dst_id.in_(near_items))),
                    Item.parent_external_id.is_not(None)
                    & func.row(Item.source_id, Item.parent_external_id).in_(parents),  # replies
                )
            )
        )
    ) - near_items  # fmt: skip

    found = [
        *_decisions(session, tags, Decision.id.in_(near_decisions.union(about)), 1.0),
        *_chunks(session, tags, or_(Chunk.id.in_(mentions), Chunk.item_id.in_(near_items)), 1.0),
        *_decisions(session, tags, Decision.item_id.in_(near_items), 0.5),
        *_chunks(session, tags, Chunk.item_id.in_(far_items), 0.5),
    ]
    unique = {e.key: e for e in reversed(found)}  # first (best) score wins
    return sorted(unique.values(), key=lambda e: -e.score)[: _limit(limit)]


def _chunks(session: Session, tags: list[str], where: object, score: float) -> list[Evidence]:
    rows = session.execute(
        select(Chunk, Item).join(Item, Item.id == Chunk.item_id).where(visible(tags), where)
        .order_by(Chunk.item_id, Chunk.position).limit(_limit(None))
    ).all()  # fmt: skip
    return [_chunk(chunk, item, score) for chunk, item in rows]


def _decisions(session: Session, tags: list[str], where: object, score: float) -> list[Evidence]:
    rows = session.execute(
        select(Decision, Item).join(Item, Item.id == Decision.item_id).where(visible(tags), where)
        .order_by(Decision.id).limit(_limit(None))
    ).all()  # fmt: skip
    return [
        Evidence(
            "decision",
            d.id,
            decision_text(d),
            item.id,
            item.title,
            d.link or item.link,
            item.author,
            d.decided_at or item.created_at,
            score,
        )  # fmt: skip
        for d, item in rows
    ]


def decision_text(d: Decision) -> str:
    lines = [f"Decision: {d.decision}"]
    if d.reason:
        lines.append(f"Reason: {d.reason}")
    if d.people:
        lines.append(f"Decided by: {', '.join(d.people)}")
    return "\n".join(lines)
