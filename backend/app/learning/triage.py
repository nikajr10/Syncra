"""Triage (Task 2.2): keep useful items, drop noise, before chunking.

A rule pre-filter catches obvious noise (nothing to read, written by a bot) and keeps PR reviews
with a verdict ("approved: LGTM" says who reviewed what, however short); the SetFit classifier
trained on config/triage.yaml (`make train-triage`) decides the rest. Noise gets status "noise"
and is skipped by later stages; useful items stay "new" for the chunker.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.schema import Item
from app.models import gateway

log = logging.getLogger("syncra.learning.triage")

Classify = Callable[[list[str]], list[str]]  # texts -> "useful" | "noise" each


def _model(texts: list[str]) -> list[str]:
    return gateway.classify("triage", texts)


def is_bot(author: str | None) -> bool:
    """GitHub apps (`github:…[bot]`) and Slack bots (`slack:B…`)."""
    author = author or ""
    return author.endswith("[bot]") or author.startswith("slack:B")


def is_obvious_noise(item: Item) -> bool:
    """Nothing to read, or written by a bot. A bot-started thread may still hold human replies."""
    return not item.full_text or (is_bot(item.author) and item.type != "thread")


def is_review_verdict(item: Item) -> bool:
    """A person approving or asking for changes on a PR: evidence for "who reviewed …?"."""
    verdict = item.text.lower().startswith(("approved", "changes requested"))
    return item.type == "review" and verdict and not is_bot(item.author)


def triage(items: Sequence[Item], classify: Classify = _model) -> list[str]:
    """Label each item "useful" or "noise": the rules first, then the classifier."""
    labels = ["useful" if is_review_verdict(item) else "noise" for item in items]
    keep = [
        n for n, item in enumerate(items) if labels[n] == "noise" and not is_obvious_noise(item)
    ]
    for n, label in zip(keep, classify([items[n].full_text for n in keep]), strict=True):
        labels[n] = label
    return labels


def triage_new_items(session: Session, classify: Classify = _model) -> list[Item]:
    """Triage every "new" item: noise gets status "noise"; returns the useful ones, still "new"."""
    items = session.scalars(select(Item).where(Item.status == "new").order_by(Item.id)).all()
    useful = []
    for item, label in zip(items, triage(items, classify), strict=True):
        if label == "noise":
            item.status = "noise"
        else:
            useful.append(item)
    session.commit()
    log.info("triage: %d new items, %d useful", len(items), len(useful))
    return useful
