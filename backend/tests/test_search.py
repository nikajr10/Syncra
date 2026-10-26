"""Phase 6: vector, keyword and graph search find the right evidence, and only visible evidence."""

from functools import cache

from sqlalchemy.orm import Session

from app.chat import search
from app.db.schema import Chunk, Item, Source
from app.models import gateway

PUBLIC = ["public"]
DOCS = {  # external id -> (text, access tags)
    "#42": ("Add a RabbitMQ queue between checkout and payments. The payment provider times out "
            "under load, so checkout now hands orders to a queue.", PUBLIC),
    "PAY-1234": ("Cap refund retries at 3: the bank rejects a fourth attempt as fraud. "
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
