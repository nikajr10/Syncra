"""Embedder (Task 3.4): one normalised EMBEDDING_DIM-long vector per chunk (Qwen3-Embedding)."""

from __future__ import annotations

from collections.abc import Sequence

from app.config.settings import ConfigError, get_settings
from app.learning.chunk import TextChunk
from app.models import gateway


def embed_chunks(chunks: Sequence[TextChunk]) -> list[list[float]]:
    """One vector per chunk, in order; gateway.embed runs the model in batches of 32."""
    vectors = gateway.embed("embedder", [chunk.text for chunk in chunks])
    dim = get_settings().embedding_dim
    if vectors and len(vectors[0]) != dim:  # chunks.vector is vector(EMBEDDING_DIM)
        raise ConfigError(f"The embedder makes {len(vectors[0])}-dim vectors; EMBEDDING_DIM={dim}")
    return vectors
