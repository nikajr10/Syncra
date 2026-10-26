"""Phase 6: vector, keyword and graph search find the right evidence, and only visible evidence."""

from functools import cache

from sqlalchemy.orm import Session

from app.chat import search
from app.db.schema import Chunk, Item, Source
from app.learning.decisions import FoundDecision
from app.learning.entities import FoundEntity
from app.learning.graph import write_graph
from app.models import gateway

PUBLIC = ["public"]
DOCS = {  # external id -> (text, access tags)
    "#42": ("Add a RabbitMQ queue between checkout and payments. The payment provider times out "
            "under load, so checkout now hands orders to a queue.", PUBLIC),
    "PAY-1234": ("PAY-1234: cap refund retries at 3: the bank rejects a fourth attempt as fraud. "
                 "See charge_card() and error E4012.", PUBLIC),
    "#7": ("Move the docs site from Jekyll to MkDocs because the Ruby toolchain keeps breaking.",
           PUBLIC),
    "1728000000.000100": ("slack:U01: the office coffee machine is broken again", PUBLIC),
    "secret": ("Why checkout hands orders to a queue: the payment provider times out. "
               "Private notes from the payments leads.", ["github:repo:acme/secret"]),
}  # fmt: skip


@cache
def _vectors() -> dict[str, list[float]]:
    texts = [text for text, _ in DOCS.values()]
    return dict(zip(DOCS, gateway.embed("embedder", texts), strict=True))


def corpus(session: Session) -> dict[str, Item]:
    """One item with one embedded chunk per DOCS entry."""
    source = Source(kind="github", name="acme/payments", external_id="acme/payments")
    session.add(source)
    session.flush()
    items = {}
    for external_id, (body, tags) in DOCS.items():
        items[external_id] = row = Item(
            source_id=source.id, external_id=external_id, type="issue", text=body,
            access_tags=tags, title=external_id,
        )  # fmt: skip
        session.add(row)
        session.flush()
        session.add(Chunk(item_id=row.id, position=0, text=body, vector=_vectors()[external_id]))
    session.commit()
    return items


def _titles(found: list[search.Evidence]) -> list[str | None]:
    return [e.title for e in found]


def test_vector_search_finds_by_meaning(db_session: Session) -> None:
    corpus(db_session)
    found = search.vector_search(db_session, PUBLIC, "why do we use a message broker for payments?")
    assert _titles(found)[0] == "#42"
    assert "secret" not in _titles(found)  # closer still, but not visible
    assert found[0].score > found[-1].score and found[0].kind == "chunk"
    everything = search.vector_search(
        db_session, [*PUBLIC, "github:repo:acme/secret"], "why queue?"
    )
    assert "secret" in _titles(everything)


def test_keyword_search_finds_exact_terms(db_session: Session) -> None:
    corpus(db_session)
    for question in ("what does PAY-1234 say?", "who wrote charge_card()?", "what is error E4012"):
        assert _titles(search.keyword_search(db_session, PUBLIC, question)) == ["PAY-1234"]
    assert search.keyword_search(db_session, PUBLIC, "what about PAY-9999?") == []
    found = search.keyword_search(db_session, PUBLIC, "why did the docs move to MkDocs?")
    assert _titles(found)[0] == "#7"
    queue = search.keyword_search(db_session, PUBLIC, "checkout queue")
    assert "#42" in _titles(queue) and "secret" not in _titles(queue)  # not visible
    assert search.keyword_search(db_session, PUBLIC, "the and of?") == []  # only stop words


def _pr(session: Session, repo: str, tags: list[str]) -> list[Item]:
    """A PR about the payment queue by alice, reviewed by bob, learned into the graph."""
    source = Source(kind="github", name=repo, external_id=repo)
    session.add(source)
    session.flush()
    rows = [
        Item(source_id=source.id, external_id="#42", type="pr", author="github:alice",
             title="Add the payment queue", text="Orders go through the payment queue now.",
             access_tags=tags),
        Item(source_id=source.id, external_id="review:1", type="review", author="github:bob",
             text="approved: LGTM, the retry limit looks right", parent_external_id="#42",
             access_tags=tags),
    ]  # fmt: skip
    session.add_all(rows)
    session.flush()
    chunks = [Chunk(item_id=i.id, position=0, text=i.full_text) for i in rows]
    session.add_all(chunks)
    session.flush()
    found = [[FoundEntity("payment queue", "service", 0.9)], []]
    decision = FoundDecision(decision="Send orders through the payment queue",
                             reason="the provider times out", people=["github:alice"])  # fmt: skip
    write_graph(session, rows, chunks, found, decision)
    session.commit()
    return rows


def test_graph_search_follows_links_to_the_review(db_session: Session) -> None:
    _pr(db_session, "acme/payments", PUBLIC)

    found = search.graph_search(db_session, PUBLIC, "who reviewed the payment queue PR?")

    texts = [e.text for e in found]
    assert "approved: LGTM, the retry limit looks right" in texts  # two links: entity → PR → review
    review = next(e for e in found if e.text.startswith("approved"))
    assert review.author == "github:bob" and review.score == 0.5
    decision = next(e for e in found if e.kind == "decision")
    assert decision.text.startswith("Decision: Send orders through the payment queue")
    assert decision.score == 1.0  # about the payment queue: one link
    assert len({e.key for e in found}) == len(found)
    assert search.graph_search(db_session, PUBLIC, "who likes coffee?") == []


def test_graph_search_respects_permissions(db_session: Session) -> None:
    _pr(db_session, "acme/secret", ["github:repo:acme/secret"])
    assert search.graph_search(db_session, PUBLIC, "who reviewed the payment queue PR?") == []
    assert search.graph_search(db_session, ["github:repo:acme/secret"], "payment queue") != []
