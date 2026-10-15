"""Task 4.3: saved chunks are found by raw SQL vector and full-text queries, through the indexes."""

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.schema import EMBEDDING_DIM, Chunk, Item, Source
from app.learning.chunk import chunk_item
from app.learning.embed import embed_chunks
from app.learning.index import save_chunks
from app.models import gateway

TEXTS = {
    "#42": "Add a RabbitMQ queue between checkout and payments\n\n"
    "The payment provider times out under load, so checkout now hands orders to a queue.",
    "PAY-1234": "Cap refund retries at 3: the bank rejects a fourth attempt as fraud.",
    "1728000000.000100": "slack:U01: the office coffee machine is broken again",
}
NEAREST = text("SELECT item_id FROM chunks ORDER BY vector <=> CAST(:q AS vector) LIMIT 1")
MATCHING = text("SELECT item_id FROM chunks WHERE tsv @@ websearch_to_tsquery('english', :q)")


def _items(session: Session) -> dict[str, Item]:
    source = Source(kind="github", name="acme/payments", external_id="acme/payments")
    session.add(source)
    session.flush()
    items = {
        external_id: Item(
            source_id=source.id,
            external_id=external_id,
            type="issue",
            text=body,
            access_tags=["public"],
        )
        for external_id, body in TEXTS.items()
    }
    session.add_all(items.values())
    session.flush()
    return items


def _plan(session: Session, query: text, q: str) -> str:
    rows = session.execute(text(f"EXPLAIN {query.text}"), {"q": q}).scalars()
    return "\n".join(rows)


def test_raw_vector_and_full_text_queries_find_the_right_chunk(db_session: Session) -> None:
    items = _items(db_session)
    chunks = [chunk for item in items.values() for chunk in chunk_item(item)]
    save_chunks(db_session, [i.id for i in items.values()], chunks, embed_chunks(chunks))
    db_session.execute(text("SET LOCAL enable_seqscan = off"))  # few rows: make the planner show
    by_id = {item.id: external_id for external_id, item in items.items()}

    [question] = gateway.embed("embedder", ["Why does checkout send orders through a queue?"])
    q = str(question)
    assert by_id[db_session.scalar(NEAREST, {"q": q})] == "#42"
    assert "ix_chunks_vector_hnsw" in _plan(db_session, NEAREST, q)

    assert [by_id[i] for i in db_session.scalars(MATCHING, {"q": "refunds"})] == ["PAY-1234"]
    assert "ix_chunks_tsv" in _plan(db_session, MATCHING, "refunds")


def test_saving_again_replaces_an_items_chunks(db_session: Session) -> None:
    items = list(_items(db_session).values())
    ids = [i.id for i in items]
    chunks = [chunk for item in items for chunk in chunk_item(item)]
    vectors = [[1.0] + [0.0] * (EMBEDDING_DIM - 1)] * len(chunks)

    save_chunks(db_session, ids, chunks, vectors)
    save_chunks(db_session, ids, chunks, vectors)
    assert db_session.scalar(select(func.count()).select_from(Chunk)) == len(chunks)

    save_chunks(db_session, ids[:1], [], [])  # e.g. its text was emptied
    remaining = set(db_session.scalars(select(Chunk.item_id)))
    assert remaining == set(ids[1:])
