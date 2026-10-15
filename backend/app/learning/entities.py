"""Entity finder (Task 3.1): people, services, tools and projects named in each chunk (GLiNER).

Labels and the confidence threshold are the `entity_finder` role's `labels` / `threshold` in
config/models.yaml. Slack thread lines start with their author id (`slack:U01: …`); those
prefixes are removed first, or GLiNER reports "slack" as a tool in every thread.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.learning.chunk import AUTHOR
from app.models import gateway


@dataclass(frozen=True)
class FoundEntity:
    name: str  # as written in the text: "PaymentService", "Alice Chen"
    type: str  # one of the entity_finder labels
    score: float  # GLiNER confidence, at least the threshold


def find_entities(texts: list[str]) -> list[list[FoundEntity]]:
    """The entities named in each text, once per (name, type) with its best score."""
    found = []
    for hits in gateway.find_entities("entity_finder", [AUTHOR.sub("", t) for t in texts]):
        best: dict[tuple[str, str], float] = {}
        for name, label, score in hits:
            best[name, label] = max(score, best.get((name, label), 0.0))
        found.append([FoundEntity(name, label, score) for (name, label), score in best.items()])
    return found
