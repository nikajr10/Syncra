"""Task 3.4: Qwen3-Embedding turns chunks into 1024-long, normalised vectors."""

import pytest

from app.config.settings import ConfigError, get_settings
from app.learning.chunk import TextChunk
from app.learning.embed import embed_chunks


def _chunk(text: str) -> TextChunk:
    return TextChunk(1, 0, text, None, None, None, ("public",))


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_chunks_become_normalised_1024_vectors_close_in_meaning() -> None:
    queue, same, other = embed_chunks(
        [
            _chunk("We put a queue between checkout and payments: the provider times out."),
            _chunk("Checkout reaches payments via RabbitMQ since the provider kept timing out."),
            _chunk("The office coffee machine is broken again, someone call facilities."),
        ]
    )

    assert len(queue) == len(same) == len(other) == 1024
    assert all(abs(_dot(v, v) - 1) < 1e-2 for v in (queue, same, other))  # bf16 weights
    assert _dot(queue, same) > _dot(queue, other) + 0.2
    assert embed_chunks([]) == []


def test_a_vector_size_other_than_embedding_dim_is_a_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "embedding_dim", 384)
    with pytest.raises(ConfigError, match="EMBEDDING_DIM=384"):
        embed_chunks([_chunk("payments")])
