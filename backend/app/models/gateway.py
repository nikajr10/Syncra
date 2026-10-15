"""Model gateway: every model call goes through here.

- `ollama()` -> `OllamaClient`: generate (normal + streaming), JSON mode, timeout, retry.
- `load_sentence_transformer(role)` / `load_cross_encoder(role)`: Hugging Face models loaded once,
  cached in memory, on GPU (cuda / mps) when available.
- `train_setfit(role, ...)` / `classify(role, texts)`: SetFit classifiers trained here from the
  `<role>_base` body and saved under TRAINED_MODELS_DIR.
- `load_gliner(role)` / `find_entities(role, texts)`: GLiNER entity finder.

Models are addressed by **role** from config/models.yaml (e.g. "answer_writer"), never by name.
Every call logs model name, time taken and token / item count.
"""

from __future__ import annotations

import json
import logging
import tempfile
import time
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from app.config.settings import ConfigError, get_models_config, get_settings

log = logging.getLogger("syncra.models")


class OllamaError(RuntimeError):
    """Ollama was unreachable or returned a bad response after all retries."""


def _log_call(model: str, started: float, **counts: Any) -> None:
    ms = (time.perf_counter() - started) * 1000
    extra = " ".join(f"{k}={v}" for k, v in counts.items() if v is not None)
    log.info("model=%s took=%.0fms %s", model, ms, extra)


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        retries: int = 2,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.retries = retries
        self._client = httpx.Client(
            base_url=base_url or settings.ollama_base_url,
            timeout=timeout or settings.ollama_timeout_seconds,
            transport=transport,
        )

    @staticmethod
    def _body(
        role: str,
        prompt: str,
        *,
        system: str | None,
        json_mode: bool | dict[str, Any],
        options: dict[str, Any] | None,
        think: bool,
        stream: bool,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": get_models_config()[role].name,
            "prompt": prompt,
            "stream": stream,
            "think": think,  # Qwen3 "thinking" off by default: faster, and JSON stays clean
        }
        if system:
            body["system"] = system
        if json_mode:
            body["format"] = json_mode if isinstance(json_mode, dict) else "json"
        if options:
            body["options"] = options
        return body

    def generate(
        self,
        role: str,
        prompt: str,
        *,
        system: str | None = None,
        json_mode: bool | dict[str, Any] = False,
        options: dict[str, Any] | None = None,
        think: bool = False,
    ) -> str:
        """Return the full response text. `json_mode=True` (or a JSON schema) forces JSON output."""
        body = self._body(
            role, prompt, system=system, json_mode=json_mode, options=options, think=think,
            stream=False,
        )  # fmt: skip
        for attempt in range(self.retries + 1):
            started = time.perf_counter()
            try:
                response = self._client.post("/api/generate", json=body)
                response.raise_for_status()
                data = response.json()
                text = data["response"]
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                if attempt == self.retries:
                    raise OllamaError(f"Ollama generate failed for {body['model']}: {exc}") from exc
                log.warning("ollama %s failed (%s), retrying", body["model"], exc)
                continue
            _log_call(
                body["model"],
                started,
                prompt_tokens=data.get("prompt_eval_count"),
                tokens=data.get("eval_count"),
            )
            return text
        raise AssertionError("unreachable")

    def generate_json(self, role: str, prompt: str, **kwargs: Any) -> Any:
        """`generate` in JSON mode, parsed. Raises `ValueError` when the model's JSON is invalid."""
        kwargs.setdefault("json_mode", True)
        return json.loads(self.generate(role, prompt, **kwargs))

    def stream(
        self,
        role: str,
        prompt: str,
        *,
        system: str | None = None,
        options: dict[str, Any] | None = None,
        think: bool = False,
    ) -> Iterator[str]:
        """Yield response text piece by piece. Retries only if nothing was yielded yet."""
        body = self._body(
            role, prompt, system=system, json_mode=False, options=options, think=think,
            stream=True,
        )  # fmt: skip
        for attempt in range(self.retries + 1):
            started = time.perf_counter()
            yielded = False
            try:
                with self._client.stream("POST", "/api/generate", json=body) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        if data.get("done"):
                            _log_call(
                                body["model"],
                                started,
                                prompt_tokens=data.get("prompt_eval_count"),
                                tokens=data.get("eval_count"),
                            )
                            return
                        yielded = True
                        yield data.get("response", "")
                return
            except (httpx.HTTPError, ValueError) as exc:
                if yielded or attempt == self.retries:
                    raise OllamaError(f"Ollama stream failed for {body['model']}: {exc}") from exc
                log.warning("ollama %s stream failed (%s), retrying", body["model"], exc)


@lru_cache
def ollama() -> OllamaClient:
    return OllamaClient()


# --- Hugging Face ---------------------------------------------------------------------------


@lru_cache
def device() -> str:
    """cuda > mps > cpu, unless DEVICE is set explicitly."""
    configured = get_settings().device
    if configured != "auto":
        return configured
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@lru_cache
def load_sentence_transformer(role: str):  # noqa: ANN201 - heavy import kept lazy
    from sentence_transformers import SentenceTransformer

    spec = get_models_config()[role]
    started = time.perf_counter()
    model = SentenceTransformer(
        spec.name, revision=spec.revision, device=device(), token=get_settings().hf_token
    )
    _log_call(spec.name, started, loaded_on=device())
    return model


@lru_cache
def load_cross_encoder(role: str):  # noqa: ANN201 - heavy import kept lazy
    from sentence_transformers import CrossEncoder

    spec = get_models_config()[role]
    started = time.perf_counter()
    model = CrossEncoder(
        spec.name, revision=spec.revision, device=device(), token=get_settings().hf_token
    )
    _log_call(spec.name, started, loaded_on=device())
    return model


def embed(role: str, texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """Normalised embeddings for `texts` with the model configured for `role`."""
    started = time.perf_counter()
    model = load_sentence_transformer(role)
    vectors = model.encode(
        texts, batch_size=batch_size, normalize_embeddings=True, convert_to_numpy=True
    )
    _log_call(get_models_config()[role].name, started, items=len(texts))
    return vectors.tolist()


@lru_cache
def load_gliner(role: str):  # noqa: ANN201 - heavy import kept lazy
    """GLiNER with its encoder's tokenizer and config from the pinned `<role>_encoder`.

    The GLiNER repo holds only weights + gliner_config.json; left alone, GLiNER would fetch the
    rest from the encoder repo's moving `main` branch. The config is rewritten to point at the
    pinned copy instead.
    """
    from gliner import GLiNER
    from huggingface_hub import snapshot_download

    spec, encoder = get_models_config()[role], get_models_config()[f"{role}_encoder"]
    token = get_settings().hf_token
    started = time.perf_counter()
    model_dir = Path(snapshot_download(spec.name, revision=spec.revision, token=token))
    config = json.loads((model_dir / "gliner_config.json").read_text())
    config["model_name"] = snapshot_download(
        encoder.name, revision=encoder.revision, token=token, allow_patterns=encoder.files
    )
    with tempfile.TemporaryDirectory() as tmp:
        for file in model_dir.iterdir():
            if file.name != "gliner_config.json":
                (Path(tmp) / file.name).symlink_to(file)
        (Path(tmp) / "gliner_config.json").write_text(json.dumps(config))
        model = GLiNER.from_pretrained(tmp, local_files_only=True, map_location=device())
    _log_call(spec.name, started, loaded_on=device())
    return model


def find_entities(role: str, texts: list[str]) -> list[list[tuple[str, str, float]]]:
    """(name, label, score) hits per text for the role's labels; hits under threshold dropped."""
    if not texts:
        return []
    spec = get_models_config()[role]
    started = time.perf_counter()
    hits = load_gliner(role).inference(texts, spec.labels, threshold=spec.threshold)
    _log_call(spec.name, started, items=len(texts))
    return [[(h["text"], h["label"], h["score"]) for h in text_hits] for text_hits in hits]


def rerank(role: str, query: str, candidates: list[str]) -> list[float]:
    """One relevance score per candidate from the cross-encoder configured for `role`."""
    started = time.perf_counter()
    model = load_cross_encoder(role)
    scores = model.predict([(query, c) for c in candidates], convert_to_numpy=True)
    _log_call(get_models_config()[role].name, started, items=len(candidates))
    return [float(s) for s in scores]


# --- SetFit (classifiers we train) ----------------------------------------------------------


def setfit_dir(role: str) -> Path:
    return get_settings().trained_models_dir / role


def train_setfit(role: str, texts: list[str], labels: list[str]) -> None:
    """Fine-tune a SetFit classifier on the `<role>_base` body; save it to `setfit_dir(role)`."""
    from datasets import Dataset
    from setfit import SetFitModel, Trainer, TrainingArguments
    from sklearn.linear_model import LogisticRegression

    started = time.perf_counter()
    # A fresh copy of the pinned body: training changes its weights, so not the cached one.
    # (SetFitModel.from_pretrained would load the body ignoring the pinned revision.)
    body = load_sentence_transformer.__wrapped__(f"{role}_base")
    model = SetFitModel(model_body=body, model_head=LogisticRegression())
    with tempfile.TemporaryDirectory() as checkpoints:
        args = TrainingArguments(
            output_dir=checkpoints,
            num_iterations=5,  # pairs per example: as accurate as 20 on the triage data, 4x faster
            report_to="none",
            save_strategy="no",
            logging_strategy="no",
        )
        dataset = Dataset.from_dict({"text": texts, "label": labels})
        Trainer(model=model, args=args, train_dataset=dataset).train()
    model.save_pretrained(setfit_dir(role))
    load_setfit.cache_clear()
    _log_call(f"setfit:{role}", started, items=len(texts))


@lru_cache
def load_setfit(role: str):  # noqa: ANN201 - heavy import kept lazy
    """The trained classifier. Loaded by hand: SetFitModel.from_pretrained asks the Hub about it."""
    import joblib
    from sentence_transformers import SentenceTransformer
    from setfit import SetFitModel

    path = setfit_dir(role)
    if not (path / "model_head.pkl").exists():
        raise ConfigError(f"No trained {role} classifier in {path}: run `make train-{role}`")
    started = time.perf_counter()
    model = SetFitModel(
        model_body=SentenceTransformer(str(path), device=device()),
        model_head=joblib.load(path / "model_head.pkl"),  # pickle: only ever our own file
    )
    _log_call(f"setfit:{role}", started, loaded_on=device())
    return model


def classify(role: str, texts: list[str]) -> list[str]:
    """One label per text from the SetFit classifier trained for `role`."""
    if not texts:
        return []
    started = time.perf_counter()
    labels = [str(label) for label in load_setfit(role).predict(texts)]
    _log_call(f"setfit:{role}", started, items=len(texts))
    return labels
