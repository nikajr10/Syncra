"""Entity finder (Task 3.1): people, services, tools and projects named in each chunk (GLiNER).

Labels and the confidence threshold are the `entity_finder` role's `labels` / `threshold` in
config/models.yaml. Slack thread lines start with their author id (`slack:U01: …`); those
prefixes are removed first, or GLiNER reports "slack" as a tool in every thread. Slack mentions
(`<@U03>`) are people named by their account, `slack:U03` (Task 4.1 links accounts to people);
GLiNER sees only a mention's label (`<@U03|maria>` -> `maria`), or it reports `U03` as a person.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ml import gateway
from app.services.learning.chunk import AUTHOR

PERSON = "person"  # the entity_finder label for people
MENTION = re.compile(r"<@([UW][A-Z0-9]+)(?:\|([^>]*))?>")  # Slack: <@U03>, <@U03|maria>


@dataclass(frozen=True)
class FoundEntity:
    name: str  # as written in the text: "PaymentService", "Alice Chen"
    type: str  # one of the entity_finder labels
    score: float  # GLiNER confidence, at least the threshold


def find_entities(texts: list[str]) -> list[list[FoundEntity]]:
    """The entities named in each text, once per (name, type) with its best score."""
    found = []
    plain = [MENTION.sub(r"\2", AUTHOR.sub("", text)) for text in texts]
    hits_per_text = gateway.find_entities("entity_finder", plain)
    for text, hits in zip(texts, hits_per_text, strict=True):
        best: dict[tuple[str, str], float] = {}
        for name, label, score in hits:
            best[name, label] = max(score, best.get((name, label), 0.0))
        best |= {(f"slack:{user}", PERSON): 1.0 for user, _ in MENTION.findall(text)}
        found.append([FoundEntity(name, label, score) for (name, label), score in best.items()])
    return found
