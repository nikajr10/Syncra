"""Model gateway: every model call goes through here.

- `ollama()` -> `OllamaClient`: generate (normal + streaming), JSON mode, timeout, retry.
- `load_sentence_transformer(role)` / `load_cross_encoder(role)`: Hugging Face models loaded once,
  cached in memory, on GPU (cuda / mps) when available.
- `train_setfit(role, ...)` / `classify(role, texts)`: SetFit classifiers trained here from the
  `<role>_base` body and saved under TRAINED_MODELS_DIR; `train_setfit_held_out(role)` trains
  one on its labelled examples in config/<role>.yaml and scores it.
- `load_gliner(role)` / `find_entities(role, texts)`: GLiNER entity finder.
- `rerank(role, query, texts)` / `nli(role, pairs)`: cross-encoders (reranker, claim checker).
- `load_classifier(role)` / `label_scores(role, texts, label)`: Hugging Face text classifiers
  (Prompt Guard 2), scored over the whole text in model-sized windows.

Models are addressed by **role** from config/models.yaml (e.g. "answer_writer"), never by name.
Every call logs model name, time taken and token / item count.
"""

from __future__ import annotations

import json
import logging
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

import httpx
import yaml

from app.config.settings import CONFIG_DIR, ConfigError, get_models_config, get_settings

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
        spec = get_models_config()[role]
        body: dict[str, Any] = {
            "model": spec.name,
            "prompt": prompt,
            "stream": stream,
            "think": think,  # Qwen3 "thinking" off by default: faster, and JSON stays clean
            "keep_alive": get_settings().ollama_keep_alive,  # reloading qwen3:8b costs seconds
        }
        if system:
            body["system"] = system
        if json_mode:
            body["format"] = json_mode if isinstance(json_mode, dict) else "json"
        options = {**spec.options, **(options or {})}  # the role's options from models.yaml
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


@lru_cache
def chat_ollama() -> OllamaClient:
    """For the chat's calls: CHAT_TIMEOUT_SECONDS and one retry, since a user is waiting."""
    return OllamaClient(timeout=get_settings().chat_timeout_seconds, retries=1)


# --- Hugging Face ---------------------------------------------------------------------------

# One Hugging Face model call at a time, loads included. The API serves requests on many threads
# and warms models up on another; two at once on Apple's GPU (MPS) abort the whole process with
# a Metal assertion, and lru_cache alone would load the same model twice.
# ponytail: one global lock; per-device locks if the API ever runs models on several GPUs.
_HF_LOCK = threading.Lock()
P = ParamSpec("P")
R = TypeVar("R")


def _one_at_a_time(fn: Callable[P, R]) -> Callable[P, R]:
    @wraps(fn)
    def locked(*args: P.args, **kwargs: P.kwargs) -> R:
        with _HF_LOCK:
            return fn(*args, **kwargs)

    return locked


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


@_one_at_a_time
def embed(
    role: str, texts: list[str], batch_size: int = 32, prompt_name: str | None = None
) -> list[list[float]]:
    """Normalised embeddings for `texts` with the model configured for `role`. `prompt_name`
    picks one of the model's own prompts, e.g. "query" for a search question (Qwen3-Embedding)."""
    started = time.perf_counter()
    model = load_sentence_transformer(role)
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        prompt_name=prompt_name,
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


@_one_at_a_time
def find_entities(role: str, texts: list[str]) -> list[list[tuple[str, str, float]]]:
    """(name, label, score) hits per text for the role's labels; hits under threshold dropped."""
    if not texts:
        return []
    spec = get_models_config()[role]
    started = time.perf_counter()
    hits = load_gliner(role).inference(texts, spec.labels, threshold=spec.threshold)
    _log_call(spec.name, started, items=len(texts))
    return [[(h["text"], h["label"], h["score"]) for h in text_hits] for text_hits in hits]


@lru_cache
def load_classifier(role: str):  # noqa: ANN201 - heavy import kept lazy
    """(tokenizer, model) of a Hugging Face text classifier, e.g. Prompt Guard 2."""
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    spec = get_models_config()[role]
    token = get_settings().hf_token
    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(spec.name, revision=spec.revision, token=token)
    model = AutoModelForSequenceClassification.from_pretrained(
        spec.name, revision=spec.revision, token=token
    )
    model.to(device()).eval()
    _log_call(spec.name, started, loaded_on=device())
    return tokenizer, model


@_one_at_a_time
def label_scores(
    role: str, texts: list[str], label: str, window: int = 512, overlap: int = 64
) -> list[float]:
    """How likely each text is `label` (0-1). A text longer than the model's `window` tokens is
    read in windows that overlap by `overlap` tokens, and its highest-scoring window counts."""
    if not texts:
        return []
    import torch

    tokenizer, model = load_classifier(role)
    started = time.perf_counter()
    pieces = tokenizer(
        texts,
        truncation=True,
        max_length=window,
        stride=overlap,
        return_overflowing_tokens=True,
        padding=True,
        return_tensors="pt",
    )
    owners = pieces.pop("overflow_to_sample_mapping").tolist()  # piece -> index of its text
    with torch.no_grad():
        probabilities = model(**pieces.to(device())).logits.softmax(-1)
    scores = [0.0] * len(texts)
    wanted = probabilities[:, model.config.label2id[label]].tolist()
    for owner, p in zip(owners, wanted, strict=True):
        scores[owner] = max(scores[owner], p)
    _log_call(get_models_config()[role].name, started, items=len(texts), pieces=len(owners))
    return scores


@_one_at_a_time
def rerank(role: str, query: str, candidates: list[str]) -> list[float]:
    """One relevance score per candidate from the cross-encoder configured for `role`."""
    started = time.perf_counter()
    model = load_cross_encoder(role)
    scores = model.predict([(query, c) for c in candidates], convert_to_numpy=True)
    _log_call(get_models_config()[role].name, started, items=len(candidates))
    return [float(s) for s in scores]


@_one_at_a_time
def nli(role: str, pairs: list[tuple[str, str]]) -> list[dict[str, float]]:
    """{label: probability} per (premise, hypothesis) from the NLI cross-encoder for `role`,
    e.g. {"entailment": 0.97, "neutral": 0.02, "contradiction": 0.01}."""
    if not pairs:
        return []
    started = time.perf_counter()
    model = load_cross_encoder(role)
    labels = model.model.config.id2label
    probabilities = model.predict(pairs, apply_softmax=True, convert_to_numpy=True)
    _log_call(get_models_config()[role].name, started, items=len(pairs))
    return [{labels[i]: float(p) for i, p in enumerate(row)} for row in probabilities]


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
            num_iterations=get_models_config()[f"{role}_base"].iterations,  # pairs per example
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
        command = f"make train-{role.replace('_', '-')}"
        raise ConfigError(f"No trained {role} classifier in {path}: run `{command}`")
    started = time.perf_counter()
    model = SetFitModel(
        model_body=SentenceTransformer(str(path), device=device()),
        model_head=joblib.load(path / "model_head.pkl"),  # pickle: only ever our own file
    )
    _log_call(f"setfit:{role}", started, loaded_on=device())
    return model


@_one_at_a_time
def classify(role: str, texts: list[str]) -> list[str]:
    """One label per text from the SetFit classifier trained for `role`."""
    if not texts:
        return []
    started = time.perf_counter()
    labels = [str(label) for label in load_setfit(role).predict(texts)]
    _log_call(f"setfit:{role}", started, items=len(texts))
    return labels


def setfit_examples(role: str) -> tuple[list[str], list[str]]:
    """(texts, labels) from config/<role>.yaml, whose top-level keys are the labels."""
    data = yaml.safe_load((CONFIG_DIR / f"{role}.yaml").read_text())
    pairs = [(text, label) for label, texts in data.items() for text in texts]
    return [text for text, _ in pairs], [label for _, label in pairs]


def train_setfit_held_out(role: str) -> float:
    """Train on a stratified 80% of config/<role>.yaml, save; return accuracy on the other 20%."""
    from sklearn.model_selection import train_test_split

    texts, labels = setfit_examples(role)
    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, stratify=labels, random_state=42
    )
    train_setfit(role, x_train, y_train)
    hits = sum(p == y for p, y in zip(classify(role, x_test), y_test, strict=True))
    log.info("setfit:%s trained on %d, %d/%d held-out right", role, len(x_train), hits, len(y_test))
    return hits / len(y_test)


def warm_up() -> None:
    """Load every model a chat message needs, so the first question isn't the slow one: the
    Hugging Face models into memory, the Ollama ones into Ollama (an empty prompt loads a model
    without generating). A model that can't load is logged and left for the first message."""
    from app.config.settings import get_models_config

    started = time.perf_counter()
    loaders = {
        "embedder": load_sentence_transformer, "reranker": load_cross_encoder,
        "claim_checker": load_cross_encoder, "intent_router": load_setfit,
        "prompt_guard": load_classifier,
    }  # fmt: skip
    for role, load in loaders.items():
        try:
            with _HF_LOCK:
                load(role)
        except Exception as exc:  # e.g. Prompt Guard without HF_TOKEN
            log.warning("warm-up: %s not loaded: %s", role, exc)
    client = chat_ollama()
    for name in {get_models_config()[r].name for r in ("question_rewriter", "answer_writer")}:
        try:
            body = {"model": name, "keep_alive": get_settings().ollama_keep_alive}
            client._client.post("/api/generate", json=body).raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("warm-up: Ollama model %s not loaded: %s", name, exc)
    _log_call("warm-up", started)
