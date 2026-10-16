"""Prompt guard (Task 5.4): block prompt attacks before they reach a model (Prompt Guard 2).

Meta's Llama Prompt Guard 2 scores every chat message for jailbreak and prompt-injection
attempts. A message scoring at least the `prompt_guard` role's `threshold` in models.yaml is
blocked with a polite reply: it never reaches search or an LLM. Text longer than the model's
512-token window is scored window by window and the worst window counts, so padding can't push
an attack out of view.
"""

from __future__ import annotations

from collections.abc import Callable

from app.config.settings import get_models_config
from app.models import gateway

Detect = Callable[[list[str]], list[float]]  # texts -> how likely each is an attack (0–1)

BLOCKED_REPLY = (
    "Sorry, I can't help with that request. Ask me about your team's work: who built "
    "something, what was decided and why."
)


def _model(texts: list[str]) -> list[float]:
    return gateway.label_scores("prompt_guard", texts, "MALICIOUS")


def is_attack(text: str, detect: Detect = _model) -> bool:
    return detect([text])[0] >= get_models_config()["prompt_guard"].threshold
