"""Knowledge graph writer (Task 4.2): the people, entities and decision one conversation adds.

Links (`edges`: src --relation--> dst), each carrying the item it was learned from:

    person   authored   item       every item's author; everyone who wrote in a Slack thread
    person   reviewed   item       a PR's reviewers (authors of its reviews, not the PR's author)
    chunk    mentions   entity     what GLiNER found in the chunk, and Slack mentions
    person   decided    decision   the decision's people
    decision about      entity     the services, tools and projects the decision names

Writing a conversation first removes everything its items added before, so re-running adds
nothing twice and a re-read decision replaces the old one. Deleting an item deletes what was
learned from it (edges, chunks and decisions cascade with their item).
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.schema import Chunk, Decision, Edge, Item
from app.learning.chunk import AUTHOR
from app.learning.decisions import FoundDecision
from app.learning.entities import PERSON, FoundEntity
from app.learning.link import ACCOUNT, key, keys_in, link_entities, link_people
from app.learning.triage import is_bot

COLUMNS = ("src_type", "src_id", "relation", "dst_type", "dst_id", "item_id")


def write_graph(
    session: Session,
    conversation: Sequence[Item],
    chunks: Sequence[Chunk],
    found: Sequence[Sequence[FoundEntity]],
    decision: FoundDecision | None,
) -> Decision | None:
    """Save what one conversation says, replacing what its items said before.

    `conversation`: the root item, then its replies; `chunks`: their stored chunks; `found`: the
    entities in each chunk; `decision`: what the conversation decided, if anything.
    """
    root, ids = conversation[0], [item.id for item in conversation]
    session.execute(delete(Edge).where(Edge.item_id.in_(ids)))
    session.execute(delete(Decision).where(Decision.item_id.in_(ids)))

    writers = {item.id: _people(_writers(item)) for item in conversation}
    deciders = _people(decision.people) if decision else []
    people = link_people(session, [*(a for w in writers.values() for a in w), *deciders])
    links = []  # (src_type, src_id, relation, dst_type, dst_id, evidence item)

    for item in conversation:
        for account in writers[item.id]:
            links.append(("entity", people[account], "authored", "item", item.id, item.id))
        reviewer = item.author in people and item.author != root.author
        if item.type == "review" and root.type == "pr" and item is not root and reviewer:
            links.append(("entity", people[item.author], "reviewed", "item", root.id, item.id))

    entities = link_entities(session, [entity for chunk in found for entity in chunk])
    for chunk, chunk_entities in zip(chunks, found, strict=True):
        for e in chunk_entities:
            if (e.name, e.type) in entities:
                entity_id = entities[e.name, e.type]
                links.append(("chunk", chunk.id, "mentions", "entity", entity_id, chunk.item_id))

    row = None
    if decision:
        times = [i.updated_at or i.created_at for i in conversation]
        row = Decision(
            item_id=root.id,
            decision=decision.decision,
            reason=decision.reason or None,
            people=deciders,
            link=root.link,
            decided_at=max(filter(None, times), default=None),  # its last activity
        )
        session.add(row)
        session.flush()
        for account in deciders:
            links.append(("entity", people[account], "decided", "decision", row.id, root.id))
        named = keys_in(f"{decision.decision} {decision.reason}")
        for (name, type_), entity_id in entities.items():
            if type_ != PERSON and key(name) in named:
                links.append(("decision", row.id, "about", "entity", entity_id, root.id))

    if links:  # the same link twice (two names of one entity in a chunk) is stored once
        rows = [dict(zip(COLUMNS, link, strict=True)) for link in links]
        session.execute(insert(Edge).values(rows).on_conflict_do_nothing())
    return row


def _writers(item: Item) -> list[str | None]:
    """Who wrote `item`: its author, and for a Slack thread everyone with a message in it."""
    lines = (
        [a.removesuffix(": ") for a in AUTHOR.findall(item.text)] if item.type == "thread" else []
    )
    return [item.author, *lines]


def _people(accounts: Sequence[str | None]) -> list[str]:
    """Accounts that are people: `github:…`, `slack:…`, `jira:…`, no bots, each once."""
    return [a for a in dict.fromkeys(accounts) if a and ACCOUNT.fullmatch(a) and not is_bot(a)]
