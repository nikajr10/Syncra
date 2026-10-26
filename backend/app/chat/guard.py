"""Prompt guard (Task 5.4): block prompt attacks before they reach a model (Prompt Guard 2).

Meta's Llama Prompt Guard 2 scores every chat message for jailbreak and prompt-injection
attempts. A message scoring at least the `prompt_guard` role's `threshold` in models.yaml is
blocked with a polite reply: it never reaches search or an LLM. Text longer than the model's
512-token window is scored window by window and the worst window counts, so padding can't push
an attack out of view.
"""

from __future__ import annotations

from app.config.settings import get_models_config
from app.models import gateway

BLOCKED_REPLY = (
    "Sorry, I can't help with that request. Ask me about your team's work: who built "
    "something, what was decided and why."
)


def is_attack(text: str) -> bool:
    # how likely `text` is an attack, 0–1
    score = gateway.label_scores("prompt_guard", [text], "MALICIOUS")[0]
    return score >= get_models_config()["prompt_guard"].threshold
