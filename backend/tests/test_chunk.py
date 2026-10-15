"""Task 2.3: chunks fit, overlap a little, and keep code blocks and Slack messages whole."""

import re
from datetime import UTC, datetime

from app.db.schema import Item
from app.learning.chunk import chunk_item, split_text

SENTENCES = [f"Sentence {n} says the payment queue retries three times." for n in range(60)]


def test_long_text_becomes_small_overlapping_chunks() -> None:
    chunks = split_text(" ".join(SENTENCES), size=300, overlap=80)

    assert len(chunks) > 5 and all(len(c) <= 300 for c in chunks)
    for before, after in zip(chunks, chunks[1:], strict=False):
        first_sentence = after[: after.index(".") + 1]
        assert before.endswith(first_sentence)  # each chunk repeats the previous one's end
    assert all(any(s in c for c in chunks) for s in SENTENCES)  # nothing lost


def test_code_blocks_stay_whole_unless_bigger_than_a_chunk() -> None:
    code = "```python\n" + "\n".join(f"retry_limit_{n} = {n}" for n in range(8)) + "\n```"
    text = " ".join(SENTENCES[:4]) + "\n\n" + code + "\n\n" + " ".join(SENTENCES[4:8])
    chunks = split_text(text, size=300, overlap=80)
    assert any(code in c for c in chunks)
    assert all(c.count("```") in (0, 2) for c in chunks)  # no chunk holds half a block

    lines = [f"line {n}: " + "x" * 40 for n in range(30)]
    big = "```\n" + "\n".join(lines) + "\n```"
    chunks = split_text(big, size=300, overlap=80)
    assert len(chunks) > 1 and all(len(c) <= 300 for c in chunks)
    for chunk in chunks:  # too big for one chunk: cut between lines, never inside one
        assert all(
            line == "```" or re.fullmatch(r"line \d+: x{40}", line) for line in chunk.split("\n")
        )


def test_very_short_text_is_one_chunk() -> None:
    assert split_text("thanks, confirmed on staging", 1500, 200) == ["thanks, confirmed on staging"]
    assert split_text(" \n ", 1500, 200) == []


def test_slack_thread_keeps_messages_whole_and_in_order() -> None:
    messages = [
        f"slack:U{n}: " + f"Message {n} is about moving billing to gRPC. " * 3 for n in range(12)
    ]
    messages[5] = "slack:U5: the config we agreed on:\n```\nretries: 3\ntimeout: 5s\n```\nok?"
    text = "\n".join(m.strip() for m in messages)
    chunks = split_text(text, size=400, overlap=150)

    assert len(chunks) > 2
    joined = "\n".join(chunks)
    positions = [joined.index(m.strip()) for m in messages]  # ValueError if a message was cut
    assert positions == sorted(positions)
    assert sum(m.strip() in c for m in messages for c in chunks) > len(messages)  # some overlap


def test_chunks_keep_the_items_details() -> None:
    when = datetime(2026, 10, 1, tzinfo=UTC)
    item = Item(
        id=7,
        type="pr",
        title="Add queue between checkout and payments",
        text=" ".join(SENTENCES),
        author="github:alice",
        link="https://github.com/acme/pay/pull/7",
        created_at=when,
        access_tags=["github:repo:acme/pay"],
    )
    chunks = chunk_item(item)  # default CHUNK_SIZE / CHUNK_OVERLAP

    assert len(chunks) > 1 and [c.position for c in chunks] == list(range(len(chunks)))
    assert chunks[0].text.startswith("Add queue between checkout and payments\n\nSentence 0")
    details = {(c.item_id, c.link, c.author, c.created_at, c.access_tags) for c in chunks}
    assert details == {(7, item.link, "github:alice", when, ("github:repo:acme/pay",))}
