"""Task 4.2: a sample PR + Slack thread give the expected nodes and links, exactly once."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.schema import Chunk, Decision, Entity, Item, Source
from app.learning.chunk import chunk_item
from app.learning.decisions import FoundDecision
from app.learning.entities import FoundEntity
from app.learning.graph import write_graph
from tests.fakes import graph_links

MONDAY = datetime(2026, 10, 12, 9, tzinfo=UTC)
PR_DECISION = FoundDecision(
    decision="Put a RabbitMQ queue between checkout and the payment service",
    reason="The payment provider times out under load",
    people=["github:alice", "github:bob"],
)
THREAD_DECISION = FoundDecision(
    decision="Put RabbitMQ in front of payments-svc", reason="", people=["slack:U01", "slack:U02"]
)


def _conversations(session: Session) -> tuple[list[Item], list[Item]]:
    github = Source(kind="github", name="acme/payments", external_id="acme/payments")
    slack = Source(kind="slack", name="#eng", external_id="C1")
    session.add_all([github, slack])
    session.flush()
    tags = ["github:repo:acme/payments"]
    pr = [
        Item(
            source_id=github.id,
            external_id="#42",
            type="pr",
            author="github:alice",
            title="Add a queue between checkout and payments",
            text="The provider times out under load; RabbitMQ in front of PaymentService fixes it.",
            created_at=MONDAY,
            access_tags=tags,
        ),
        Item(
            source_id=github.id,
            external_id="review:1",
            type="review",
            author="github:bob",
            text="approved: LGTM",
            parent_external_id="#42",
            created_at=MONDAY,
            access_tags=tags,
        ),
        Item(  # alice answering bob's inline comment on her own PR: not a review by alice
            source_id=github.id,
            external_id="review_comment:2",
            type="review",
            author="github:alice",
            title="app/queue.py",
            text="done, renamed it",
            parent_external_id="#42",
            created_at=MONDAY,
            updated_at=datetime(2026, 10, 13, tzinfo=UTC),
            access_tags=tags,
        ),
    ]
    thread = [
        Item(
            source_id=slack.id,
            external_id="1728000000.000100",
            type="thread",
            author="slack:U01",
            text="slack:U01: payments-svc keeps timing out\n"
            "slack:B0CI: build #12 passed\n"
            "slack:U02: put RabbitMQ in front of it? <@U03> fyi\n"
            "slack:U01: agreed, RabbitMQ it is",
            created_at=MONDAY,
            access_tags=["slack:channel:C1"],
        )
    ]
    session.add_all(pr + thread)
    session.flush()
    return pr, thread


def _chunks(session: Session, items: list[Item]) -> list[Chunk]:
    rows = [
        Chunk(item_id=c.item_id, position=c.position, text=c.text)
        for item in items
        for c in chunk_item(item)
    ]
    session.add_all(rows)
    session.flush()
    return rows


EXPECTED = sorted(
    [
        ("github:alice", "authored", "#42"),
        ("github:bob", "authored", "review:1"),
        ("github:alice", "authored", "review_comment:2"),
        ("github:bob", "reviewed", "#42"),
        ("chunk of #42", "mentions", "checkout"),
        ("chunk of #42", "mentions", "payment service"),  # also written PaymentService there
        ("chunk of #42", "mentions", "RabbitMQ"),
        ("github:alice", "decided", "decision on #42"),
        ("github:bob", "decided", "decision on #42"),
        ("decision on #42", "about", "checkout"),
        ("decision on #42", "about", "payment service"),
        ("decision on #42", "about", "RabbitMQ"),
        ("slack:U01", "authored", "1728000000.000100"),  # the bot's line is not a person
        ("slack:U02", "authored", "1728000000.000100"),
        ("chunk of 1728000000.000100", "mentions", "payment service"),  # as payments-svc
        ("chunk of 1728000000.000100", "mentions", "RabbitMQ"),
        ("chunk of 1728000000.000100", "mentions", "slack:U03"),
        ("slack:U01", "decided", "decision on 1728000000.000100"),
        ("slack:U02", "decided", "decision on 1728000000.000100"),
        ("decision on 1728000000.000100", "about", "payment service"),
        ("decision on 1728000000.000100", "about", "RabbitMQ"),
    ]
)


def test_a_pr_and_a_slack_thread_give_each_node_and_link_once(db_session: Session) -> None:
    pr, thread = _conversations(db_session)
    pr_chunks, thread_chunks = _chunks(db_session, pr), _chunks(db_session, thread)
    pr_found = [
        [
            FoundEntity("payment service", "service", 0.9),
            FoundEntity("PaymentService", "service", 0.8),
            FoundEntity("RabbitMQ", "tool", 0.9),
            FoundEntity("checkout", "service", 0.7),
        ],
        [],
        [],
    ]
    thread_found = [
        [
            FoundEntity("payments-svc", "service", 0.9),
            FoundEntity("RabbitMQ", "service", 0.8),
            FoundEntity("slack:U03", "person", 1.0),
        ]
    ]
    assert len(pr_chunks) == len(pr_found) and len(thread_chunks) == len(thread_found)

    for _ in range(2):  # re-running must not create duplicates
        write_graph(db_session, pr, pr_chunks, pr_found, PR_DECISION)
        write_graph(db_session, thread, thread_chunks, thread_found, THREAD_DECISION)
        db_session.commit()

        assert graph_links(db_session) == EXPECTED
        entities = {(e.type, e.name) for e in db_session.scalars(select(Entity))}
        assert entities == {
            ("service", "payment service"),
            ("service", "checkout"),
            ("tool", "RabbitMQ"),
            *{("person", p) for p in ("github:alice", "github:bob", "slack:U01", "slack:U02")},
            ("person", "slack:U03"),
        }
        [pr_decision, _] = db_session.scalars(select(Decision).order_by(Decision.id)).all()
        assert pr_decision.people == ["github:alice", "github:bob"]
        assert pr_decision.decided_at == datetime(2026, 10, 13, tzinfo=UTC)  # last activity
        assert pr_decision.link is None and pr_decision.reason == PR_DECISION.reason

    # A re-read decision replaces the old one and its links.
    write_graph(db_session, pr, pr_chunks, pr_found, None)
    db_session.commit()
    assert [d.item_id for d in db_session.scalars(select(Decision))] == [thread[0].id]
    assert not [link for link in graph_links(db_session) if link[2] == "decision on #42"]

    # Deleting a source deletes everything learned from it.
    db_session.delete(db_session.get(Source, thread[0].source_id))
    db_session.commit()
    assert not [link for link in graph_links(db_session) if "1728000000.000100" in str(link)]
