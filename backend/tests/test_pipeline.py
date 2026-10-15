"""Task 4.4: with mocked sources and Ollama, one run fills every store and a second run with no
new data changes nothing. A failing conversation doesn't stop the others and is retried; later
changes re-learn their conversation, or make it forgotten when they turn it into noise."""

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.engine import new_session
from app.db.schema import Source
from app.learning.connectors.base import RawItem
from app.learning.pipeline import learn
from app.models.gateway import OllamaClient
from tests.fakes import Feed, graph_links

MONDAY = datetime(2026, 10, 12, 9, tzinfo=UTC)
REPO, CHANNEL = ("github:repo:acme/payments",), ("slack:channel:C1",)
THREAD_ID = "1728000000.000100"


def _raw(external_id: str, type: str, author: str, body: str, minute: int, **fields) -> RawItem:
    when = MONDAY + timedelta(minutes=minute)
    return RawItem(
        external_id=external_id, type=type, author=author, text=body, created_at=when, **fields
    )


PR = _raw(
    "#42",
    "pr",
    "github:alice",
    "The payment provider times out under load. Alice Chen moved the PaymentService behind "
    "RabbitMQ so provider timeouts no longer fail orders.",
    0,
    title="Add a RabbitMQ queue between checkout and payments",
    access_tags=REPO,
)
REVIEW = _raw(
    "review:1", "review", "github:bob", "approved: LGTM, ship it", 5, parent_external_id="#42",
    title="PR #42 review: approved", access_tags=REPO,
)  # fmt: skip
THANKS = _raw(
    "comment:2", "comment", "github:carol", "thanks!", 6, parent_external_id="#42",
    access_tags=REPO,
)  # fmt: skip
COMMIT = _raw(
    "abc123", "commit", "github:alice", "Add payment queue consumer", 7,
    title="Add payment queue consumer", access_tags=REPO,
)  # fmt: skip
THREAD = _raw(
    THREAD_ID,
    "thread",
    "slack:U01",
    "slack:U01: payments-svc keeps timing out on Black Friday\n"
    "slack:U02: put RabbitMQ in front of payments-svc? <@U03> fyi\n"
    "slack:U01: agreed, RabbitMQ it is",
    0,
    title="payments-svc keeps timing out on Black Friday",
    access_tags=CHANNEL,
)
BOT = _raw("1728000100.000200", "message", "slack:B0CI", "Build #12 passed", 9, access_tags=CHANNEL)

DECISIONS = {  # what Ollama answers for the conversation containing the key
    "RabbitMQ it is": {
        "decision": "Put RabbitMQ in front of payments-svc",
        "reason": "",
        "people": ["slack:U01", "slack:U02"],
    },
    "LGTM, ship it": {
        "decision": "Put a RabbitMQ queue between checkout and the payment service",
        "reason": "The payment provider times out under load",
        "people": ["github:alice", "github:bob"],
    },
}
NOTHING = {"decision": "", "reason": "", "people": []}
STORES = ("items", "chunks", "entities", "entity_aliases", "edges", "decisions")


def _classify(texts: list[str]) -> list[str]:
    return ["noise" if t in ("thanks!", "slack:U01: +1") else "useful" for t in texts]


def _ollama(down: set[str]) -> tuple[OllamaClient, list[str]]:
    """Ollama answering from DECISIONS; unreachable for conversations containing a `down` text."""
    prompts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        prompt = json.loads(request.content)["prompt"]
        prompts.append(prompt)
        if any(text in prompt for text in down):
            raise httpx.ConnectError("refused")
        answer = next((d for key, d in DECISIONS.items() if key in prompt), NOTHING)
        return httpx.Response(200, json={"response": json.dumps(answer), "done": True})

    client = OllamaClient(base_url="http://ollama.test", transport=httpx.MockTransport(handler))
    return client, prompts


@pytest.fixture
def feeds(db_session: Session) -> dict[str, Feed]:
    db_session.add_all(
        [
            Source(kind="github", name="acme/payments", external_id="acme/payments"),
            Source(kind="slack", name="#eng", external_id="C1"),
        ]
    )
    db_session.commit()
    return {"acme/payments": Feed(PR, REVIEW, THANKS, COMMIT), "C1": Feed(THREAD, BOT)}


def _run(feeds: dict[str, Feed], client: OllamaClient) -> dict[str, int]:
    return learn(new_session, lambda source: feeds[source.external_id], _classify, client)


def _rows(session: Session, sql: str) -> list:
    return session.execute(text(sql)).all()


def _stores(session: Session) -> dict[str, list]:
    return {table: _rows(session, f"SELECT * FROM {table} ORDER BY id") for table in STORES}


def _status(session: Session) -> dict[str, str]:
    return dict(_rows(session, "SELECT external_id, status FROM items"))


def test_one_run_fills_every_store_and_a_second_run_changes_nothing(
    db_session: Session, feeds: dict[str, Feed]
) -> None:
    client, prompts = _ollama(down=set())

    assert _run(feeds, client) == {"sources": 2, "noise": 2, "learned": 3, "failed": 0}

    assert _status(db_session) == {
        "#42": "processed",
        "review:1": "processed",
        "comment:2": "noise",  # the classifier's call
        "abc123": "processed",
        THREAD_ID: "processed",
        "1728000100.000200": "noise",  # a bot: the rule's call
    }
    assert all(_stores(db_session).values())  # every store has rows
    [(chunks, unindexed)] = _rows(
        db_session, "SELECT count(*), count(*) - count(vector) FROM chunks"
    )
    assert (chunks, unindexed) == (4, 0)  # PR, review, commit, thread: each one chunk, embedded
    assert len(prompts) == 2  # the PR (with its review) and the thread; commits aren't read

    links = graph_links(db_session)
    assert {
        ("github:alice", "authored", "#42"),
        ("github:alice", "authored", "abc123"),
        ("github:bob", "reviewed", "#42"),
        ("slack:U02", "authored", THREAD_ID),
        ("github:alice", "decided", "decision on #42"),
        ("github:bob", "decided", "decision on #42"),
        ("decision on #42", "about", "RabbitMQ"),
        ("decision on #42", "about", "PaymentService"),
        ("slack:U01", "decided", f"decision on {THREAD_ID}"),
        (f"decision on {THREAD_ID}", "about", "PaymentService"),  # written payments-svc there
        ("chunk of #42", "mentions", "Alice Chen"),
        (f"chunk of {THREAD_ID}", "mentions", "PaymentService"),
        (f"chunk of {THREAD_ID}", "mentions", "slack:U03"),
    } <= set(links)
    assert len(links) == len(set(links))
    aliases = _rows(
        db_session,
        "SELECT e.type, a.alias FROM entities e JOIN entity_aliases a ON a.entity_id = e.id "
        "WHERE e.name = 'PaymentService'",
    )
    assert sorted(aliases) == [("service", "PaymentService"), ("service", "payments-svc")]

    before = _stores(db_session)
    assert _run(feeds, client) == {"sources": 2, "noise": 0, "learned": 0, "failed": 0}
    assert _stores(db_session) == before
    assert len(prompts) == 2  # no model was asked again


def test_a_failing_conversation_is_rolled_back_and_retried_next_run(
    db_session: Session, feeds: dict[str, Feed], caplog: pytest.LogCaptureFixture
) -> None:
    down = {"RabbitMQ it is"}  # Ollama fails while reading the Slack thread
    client, _ = _ollama(down)

    assert _run(feeds, client) == {"sources": 2, "noise": 2, "learned": 2, "failed": 1}
    assert _status(db_session)[THREAD_ID] == "failed"
    assert "learning failed for items" in caplog.text
    links = graph_links(db_session)
    assert not [link for link in links if THREAD_ID in str(link)]  # nothing half-stored
    assert ("github:bob", "decided", "decision on #42") in links  # the others went on

    down.clear()
    assert _run(feeds, client) == {"sources": 2, "noise": 0, "learned": 1, "failed": 0}
    assert _status(db_session)[THREAD_ID] == "processed"
    assert ("slack:U02", "decided", f"decision on {THREAD_ID}") in graph_links(db_session)


def test_a_new_reply_relearns_its_conversation_and_new_noise_is_forgotten(
    db_session: Session, feeds: dict[str, Feed]
) -> None:
    client, _ = _ollama(down=set())
    _run(feeds, client)

    feeds["acme/payments"].items.append(
        _raw(
            "review:3",
            "review",
            "github:dan",
            "approved: nice",
            30,
            parent_external_id="#42",
            title="PR #42 review: approved",
            access_tags=REPO,
        )
    )
    feeds["C1"].items.append(THREAD.model_copy(update={"text": "slack:U01: +1", "title": "+1"}))
    assert _run(feeds, client) == {"sources": 2, "noise": 1, "learned": 1, "failed": 0}

    links = graph_links(db_session)
    assert {("github:bob", "reviewed", "#42"), ("github:dan", "reviewed", "#42")} <= set(links)
    assert links.count(("github:alice", "authored", "#42")) == 1
    decisions = _rows(
        db_session, "SELECT i.external_id FROM decisions d JOIN items i ON i.id = d.item_id"
    )
    assert decisions == [("#42",)]  # re-read once, not added twice; the thread's is gone
    assert not [link for link in links if THREAD_ID in str(link)]
    chunked = _rows(
        db_session, "SELECT DISTINCT external_id FROM chunks JOIN items i ON i.id = item_id"
    )
    assert sorted(chunked) == [
        ("#42",),
        ("abc123",),
        ("review:1",),
        ("review:3",),
    ]  # not the thread
