"""Decision reader (Task 3.3): what a whole thread or PR decided, why and by whom (Qwen3).

It reads whole conversations, never single chunks: a Slack thread or message, or a PR / issue with
its reviews and comments. Short ones are skipped. The model's JSON is validated against
`FoundDecision`; bad output is retried once, then dropped. Ollama being down raises instead, so
the item can be retried later.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Sequence
from string import Template

from pydantic import BaseModel, ConfigDict, ValidationError

from app.config.settings import get_prompt, get_settings
from app.db.schema import Item
from app.learning.chunk import AUTHOR
from app.learning.entities import FoundEntity
from app.models import gateway
from app.models.gateway import OllamaClient

log = logging.getLogger("syncra.learning.decisions")

CONVERSATIONS = ("pr", "issue", "thread", "message")  # comments, reviews: read with their parent
TAG = re.compile(r"</?thread>", re.I)  # quoted data must not close its own quotes


class FoundDecision(BaseModel):
    """The JSON the decision reader must answer with. An empty decision = nothing was decided."""

    model_config = ConfigDict(str_strip_whitespace=True)

    decision: str
    reason: str
    people: list[str]


SCHEMA = FoundDecision.model_json_schema()


def read_decision(
    thread: Sequence[Item],
    entities: Iterable[FoundEntity] = (),
    client: OllamaClient | None = None,
) -> FoundDecision | None:
    """The decision `thread` records, or None.

    `thread[0]` is the PR / issue / Slack thread / message, the rest its replies, oldest first.
    None when nothing was decided, the conversation is too short, or the answer was bad twice.
    """
    settings = get_settings()
    root = thread[0]
    if root.type not in CONVERSATIONS:
        return None
    if sum(len(item.full_text) for item in thread) < settings.decision_min_chars:
        return None
    text = TAG.sub("", "\n\n".join(_render(item) for item in thread))
    if len(text) > settings.decision_max_chars:  # keep the opening and the conclusion
        half = settings.decision_max_chars // 2
        text = f"{text[:half]}\n[…]\n{text[-half:]}"
    names = dict.fromkeys(f"{e.name} ({e.type})" for e in entities)
    prompt = get_prompt("decision_reader")
    user = Template(prompt.prompt).substitute(entities=", ".join(names) or "none", thread=text)
    client = client or gateway.ollama()
    for attempt in (1, 2):  # bad output: one retry, then drop
        reply = client.generate("decision_reader", user, system=prompt.system, json_mode=SCHEMA)
        try:
            found = FoundDecision.model_validate_json(reply)
        except ValidationError as exc:
            log.warning("decision reader: bad output, item %s try %d: %s", root.id, attempt, exc)
            continue
        if not found.decision:
            return None
        authors = _authors(thread)  # only people who wrote here: injected text can't forge names
        found.people = list(dict.fromkeys(p for p in found.people if p in authors))
        return found
    log.warning("decision reader: dropped item %s after 2 bad outputs", root.id)
    return None


def _render(item: Item) -> str:
    """A Slack thread's lines already start with their authors; anything else gets one."""
    if item.type == "thread":
        return item.full_text
    return f"{item.author or 'unknown'} ({item.type}): {item.full_text}"


def _authors(thread: Sequence[Item]) -> set[str | None]:
    lines = {author.removesuffix(": ") for item in thread for author in AUTHOR.findall(item.text)}
    return {item.author for item in thread} | lines
