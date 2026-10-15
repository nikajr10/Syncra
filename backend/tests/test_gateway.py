"""Task 0.5: mocked Ollama and a tiny real Hugging Face model, both through the gateway."""

import json
from pathlib import Path

import httpx
import pytest

from app.config.settings import get_models_config
from app.models import download, gateway
from app.models.gateway import OllamaClient, OllamaError


def _client(handler) -> OllamaClient:  # noqa: ANN001
    return OllamaClient(base_url="http://ollama.test", transport=httpx.MockTransport(handler))


def test_generate_sends_role_model_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        assert request.url.path == "/api/generate"
        return httpx.Response(
            200,
            json={
                "response": "Because of timeouts [E1].",
                "done": True,
                "eval_count": 5,
                "prompt_eval_count": 7,
            },  # fmt: skip
        )

    with caplog.at_level("INFO", logger="syncra.models"):
        text = _client(handler).generate("answer_writer", "why?", system="be brief")

    assert text == "Because of timeouts [E1]."
    assert seen["model"] == get_models_config()["answer_writer"].name == "qwen3:8b"
    assert seen["system"] == "be brief" and seen["stream"] is False and seen["think"] is False
    assert "format" not in seen
    assert "model=qwen3:8b" in caplog.text and "tokens=5" in caplog.text


def test_generate_json_uses_json_mode_and_parses() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["format"] == "json"
        return httpx.Response(200, json={"response": '{"decision": "add a queue"}', "done": True})

    assert _client(handler).generate_json("decision_reader", "read this") == {
        "decision": "add a queue"
    }


def test_generate_retries_then_succeeds_and_gives_up() -> None:
    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, text="boom")
        return httpx.Response(200, json={"response": "ok", "done": True})

    assert _client(flaky).generate("question_rewriter", "hi") == "ok"
    assert calls["n"] == 2

    def dead(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(OllamaError):
        _client(dead).generate("question_rewriter", "hi")


def test_stream_yields_pieces_in_order() -> None:
    lines = [
        {"response": "Hello", "done": False},
        {"response": " world", "done": False},
        {"response": "", "done": True, "eval_count": 2},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(200, content="\n".join(json.dumps(x) for x in lines))

    assert list(_client(handler).stream("answer_writer", "say hi")) == ["Hello", " world"]


def test_tiny_hf_model_loads_once_and_embeds() -> None:
    # entity_linker -> sentence-transformers/all-MiniLM-L6-v2 (small, 384-dim)
    model = gateway.load_sentence_transformer("entity_linker")
    assert gateway.load_sentence_transformer("entity_linker") is model  # cached
    vectors = gateway.embed("entity_linker", ["payment service", "payments-svc", "weather"])
    assert len(vectors) == 3 and len(vectors[0]) == 384
    dot = lambda a, b: sum(x * y for x, y in zip(a, b, strict=True))  # noqa: E731
    assert abs(dot(vectors[0], vectors[0]) - 1.0) < 1e-4  # normalised
    assert dot(vectors[0], vectors[1]) > dot(vectors[0], vectors[2])


def test_download_all_fetches_every_hf_model_and_skips_gated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fetched: list[str] = []

    def fake_download(repo_id: str, revision: str | None, token: str | None) -> str:
        fetched.append(repo_id)
        return str(tmp_path)

    monkeypatch.setattr(download.get_settings(), "hf_token", None)
    done, skipped = download.download_all(fake_download)

    expected = {m.name for m in download.hf_models().values() if not m.gated}
    assert set(done) == set(fetched) == expected
    assert len(fetched) == len(expected)  # each repo once, even if used by several roles
    assert skipped == ["meta-llama/Llama-Prompt-Guard-2-86M"]
