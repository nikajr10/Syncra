"""Chunker (Task 2.3): cut an item's text into small, slightly overlapping chunks for the embedder.

The text is cut into pieces: a Slack message or a fenced code block stays whole when it fits in a
chunk; everything else is cut at line breaks and sentence ends (a giant sentence at spaces).
Pieces are packed into chunks of at most CHUNK_SIZE characters, and each chunk starts with up to
CHUNK_OVERLAP characters of whole pieces from the end of the previous one. Every chunk keeps its
item's id, link, author, time and permissions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from app.core.config import get_settings
from app.db.models import Item

AUTHOR = re.compile(r"^(?:slack:\w+|unknown): ", re.M)  # starts each message in a Slack thread
MESSAGE = re.compile(f"(?={AUTHOR.pattern})", re.M)  # a message line in a Slack thread
CODE = re.compile(r"(```.*?```)", re.S)  # fenced code block
SENTENCE = re.compile(r"(?<=\n)|(?<=[.!?])(?=\s)")
WORD = re.compile(r"(?<=\s)(?=\S)")


@dataclass(frozen=True)
class TextChunk:
    item_id: int
    position: int  # 0, 1, 2 … within the item
    text: str
    link: str | None
    author: str | None
    created_at: datetime | None
    access_tags: tuple[str, ...]


def chunk_item(item: Item) -> list[TextChunk]:
    """The item's title and text as chunks sized by CHUNK_SIZE / CHUNK_OVERLAP."""
    settings = get_settings()
    texts = split_text(item.full_text, settings.chunk_size, settings.chunk_overlap)
    return [
        TextChunk(
            item.id, n, text, item.link, item.author, item.created_at, tuple(item.access_tags)
        )
        for n, text in enumerate(texts)
    ]


def split_text(text: str, size: int, overlap: int) -> list[str]:
    """Chunks of at most `size` characters; each repeats up to `overlap` from the one before."""
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for piece in _pieces(text, size):
        if current and length + len(piece) > size:
            chunks.append("".join(current))
            current, length = _tail(current, min(overlap, size - len(piece)))
        current.append(piece)
        length += len(piece)
    chunks.append("".join(current))
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _pieces(text: str, size: int) -> list[str]:
    """`text` cut into consecutive pieces of at most `size` characters."""
    pieces: list[str] = []
    for message in _split(MESSAGE, text):
        if len(message) <= size and MESSAGE.match(message):
            pieces.append(message)
            continue
        for part in _split(CODE, message):
            if len(part) <= size and part.startswith("```"):
                pieces.append(part)
                continue
            for sentence in _split(SENTENCE, part):
                if len(sentence) <= size:
                    pieces.append(sentence)
                    continue
                for word in _split(WORD, sentence):
                    pieces += [word[i : i + size] for i in range(0, len(word), size)]
    return pieces


def _split(pattern: re.Pattern[str], text: str) -> list[str]:
    return [part for part in pattern.split(text) if part]


def _tail(pieces: list[str], limit: int) -> tuple[list[str], int]:
    """Whole pieces from the end of `pieces`, at most `limit` characters together."""
    tail: list[str] = []
    length = 0
    for piece in reversed(pieces):
        if length + len(piece) > limit:
            break
        tail.insert(0, piece)
        length += len(piece)
    return tail, length
