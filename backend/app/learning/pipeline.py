"""Learning pipeline (Task 4.4): sync → scrub → triage → chunk → entities → decisions → embed →
link → store. The worker runs `learn()` every SYNC_INTERVAL_MINUTES.

The unit of work is a conversation: a PR, issue, Slack thread or message (or a commit) with its
replies. When any of its items is new, the whole conversation is learned again in one
transaction, and what it said before is replaced, so nothing is stored twice. Model calls take a
conversation's chunks in one batch. A conversation that fails (e.g. Ollama is down) is rolled back
and its items are marked "failed"; the others carry on, and failed items are retried next run.
Items that turned into noise lose what was learned from them.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app import monitor
from app.db.engine import new_session
from app.db.schema import Chunk, Decision, Edge, Item
from app.learning import triage
from app.learning.chunk import chunk_item
from app.learning.decisions import read_decision
from app.learning.embed import embed_chunks
from app.learning.entities import find_entities
from app.learning.graph import write_graph
from app.learning.index import save_chunks
from app.learning.link import link_identities
from app.learning.sync import sync_all_sources

log = logging.getLogger("syncra.learning.pipeline")


def learn() -> dict[str, int]:
    """One learning run: sync every source, then learn from everything new. Returns counts."""
    synced = sync_all_sources()
    with new_session() as session:
        # ponytail: triage loads every new item at once; page it if a first sync brings 100k+
        new = set(session.scalars(select(Item.id).where(Item.status == "new")))
        useful = triage.triage_new_items(session)
        noise = new - {item.id for item in useful}
        _forget(session, noise)
        failed = session.scalars(select(Item).where(Item.status == "failed")).all()
        roots = list(dict.fromkeys(_root_id(session, item) for item in [*useful, *failed]))
        session.commit()

    counts = {"sources": len(synced), "noise": len(noise), "learned": 0, "failed": 0}
    for root_id in roots:  # ponytail: failed items retry every run; count attempts if one sticks
        with new_session() as session:
            conversation = _conversation(session, root_id)
            ids = [item.id for item in conversation]
            try:
                _learn(session, conversation)
                session.commit()
                counts["learned"] += 1
            except Exception:  # one bad conversation must not stop the others
                session.rollback()
                log.exception("learning failed for items %s; retrying next run", ids)
                session.execute(
                    update(Item)
                    .where(Item.id.in_(ids), Item.status != "processed")
                    .values(status="failed")
                )
                session.commit()
                counts["failed"] += 1
                monitor.record("learn_failed", f"Learning failed for items {ids}", items=ids)

    with new_session() as session:
        link_identities(session)  # identities may have been linked since the last run
        session.commit()
    log.info("learn: %s", counts)
    return counts


def _learn(session: Session, conversation: Sequence[Item]) -> None:
    """Chunk, find entities, read the decision, embed; then store chunks and the graph."""
    chunks = [chunk for item in conversation for chunk in chunk_item(item)]
    found = find_entities([chunk.text for chunk in chunks])
    decision = read_decision(conversation, [e for entities in found for e in entities])
    vectors = embed_chunks(chunks)
    rows = save_chunks(session, [item.id for item in conversation], chunks, vectors)
    write_graph(session, conversation, rows, found, decision)
    for item in conversation:
        item.status = "processed"


def _root_id(session: Session, item: Item) -> int:
    """The conversation `item` belongs to: the PR / issue / ticket it replies to, or itself."""
    if not item.parent_external_id:
        return item.id
    root = session.scalar(
        select(Item.id).where(
            Item.source_id == item.source_id,
            Item.external_id == item.parent_external_id,
            Item.status != "noise",
        )
    )
    return root or item.id  # its parent wasn't synced, or is noise: on its own


def _conversation(session: Session, root_id: int) -> list[Item]:
    """The root, then its replies that aren't noise, oldest first (the Task 3.3 contract)."""
    root = session.get(Item, root_id)
    if root.parent_external_id:  # a reply on its own
        return [root]
    replies = session.scalars(
        select(Item)
        .where(
            Item.source_id == root.source_id,
            Item.parent_external_id == root.external_id,
            Item.status != "noise",
        )
        .order_by(Item.created_at.asc().nulls_last(), Item.id)
    ).all()
    return [root, *replies]


def _forget(session: Session, item_ids: set[int]) -> None:
    """Drop what was learned from these items (e.g. a message edited down to "+1")."""
    for model in (Chunk, Edge, Decision):
        session.execute(delete(model).where(model.item_id.in_(item_ids)))
