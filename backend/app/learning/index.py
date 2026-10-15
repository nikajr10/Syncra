"""Search indexes (Task 4.3): chunks with their vectors, ready for vector and keyword search.

Saving a row is indexing it: `chunks.vector` sits in the pgvector HNSW index (cosine) and
`chunks.tsv`, generated from the text, in the GIN full-text index (both from migration 0001).
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.schema import Chunk
from app.learning.chunk import TextChunk


def save_chunks(
    session: Session,
    item_ids: Sequence[int],
    chunks: Sequence[TextChunk],
    vectors: Sequence[list[float]],
) -> list[Chunk]:
    """Replace the chunks of `item_ids` with `chunks`, each with its vector (same order)."""
    session.execute(delete(Chunk).where(Chunk.item_id.in_(item_ids)))
    rows = [
        Chunk(item_id=chunk.item_id, position=chunk.position, text=chunk.text, vector=vector)
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    session.add_all(rows)
    session.flush()  # ids, for the graph's `mentions` links
    return rows
