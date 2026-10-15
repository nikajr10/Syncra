"""Triage (Task 2.2): keep useful items, drop noise, before chunking.

A rule pre-filter catches obvious noise (nothing to read, written by a bot); the SetFit classifier
trained on config/triage.yaml (`make train-triage`) decides the rest. Noise gets status "noise"
and is skipped by later stages; useful items stay "new" for the chunker.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import CONFIG_DIR
from app.db.schema import Item
from app.models import gateway

log = logging.getLogger("syncra.learning.triage")

Classify = Callable[[list[str]], list[str]]  # texts -> "useful" | "noise" each


def _model(texts: list[str]) -> list[str]:
    return gateway.classify("triage", texts)


def examples() -> tuple[list[str], list[str]]:
    """(texts, labels) from config/triage.yaml, whose top-level keys are the labels."""
    data = yaml.safe_load((CONFIG_DIR / "triage.yaml").read_text())
    pairs = [(text, label) for label, texts in data.items() for text in texts]
    return [text for text, _ in pairs], [label for _, label in pairs]


def train() -> float:
    """Train on 80% of the examples, save the classifier, return its accuracy on the other 20%."""
    from sklearn.model_selection import train_test_split

    texts, labels = examples()
    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, stratify=labels, random_state=42
    )
    gateway.train_setfit("triage", x_train, y_train)
    hits = sum(p == y for p, y in zip(gateway.classify("triage", x_test), y_test, strict=True))
    log.info("triage: trained on %d, %d/%d held-out right", len(x_train), hits, len(y_test))
    return hits / len(y_test)


def is_bot(author: str | None) -> bool:
    """GitHub apps (`github:…[bot]`) and Slack bots (`slack:B…`)."""
    author = author or ""
    return author.endswith("[bot]") or author.startswith("slack:B")


def is_obvious_noise(item: Item) -> bool:
    """Nothing to read, or written by a bot. A bot-started thread may still hold human replies."""
    return not item.full_text or (is_bot(item.author) and item.type != "thread")


def triage(items: Sequence[Item], classify: Classify = _model) -> list[str]:
    """Label each item "useful" or "noise": the rule pre-filter first, then the classifier."""
    labels = ["noise"] * len(items)
    keep = [n for n, item in enumerate(items) if not is_obvious_noise(item)]
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
