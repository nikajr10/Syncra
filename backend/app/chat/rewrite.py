"""Question rewriter (Task 5.3): a follow-up becomes a question that stands on its own (Qwen3 4B).

After a chat about the payment service, "who reviewed it?" becomes "Who reviewed the payment
service?", so search can find it. A first message has no history and is used as it is, without a
model call. The history and the message are quoted data in the prompt (tags inside them are
removed). Only the newest REWRITER_MAX_CHARS characters of history are sent. When the model's
answer is unusable or Ollama is down, the message is used as it is: a follow-up searched
literally beats no answer at all.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from string import Template

from pydantic import BaseModel, ConfigDict, ValidationError

from app import monitor
from app.config.settings import get_prompt, get_settings
from app.db.schema import ChatMessage
from app.models import gateway
from app.models.gateway import OllamaError

log = logging.getLogger("syncra.chat.rewrite")

TAG = re.compile(r"</?(?:history|message)>", re.I)  # quoted data must not close its own quotes


class Rewritten(BaseModel):
    """The JSON the rewriter must answer with."""

    model_config = ConfigDict(str_strip_whitespace=True)

    question: str


SCHEMA = Rewritten.model_json_schema()


def rewrite(message: str, history: Sequence[ChatMessage]) -> str:
    """`message` as a standalone question, using the chat `history` (oldest first)."""
    if not history:
        return message
    text = TAG.sub("", "\n".join(f"{m.role}: {m.content}" for m in history))
    limit = get_settings().rewriter_max_chars
    if len(text) > limit:  # the newest turns matter most
        text = f"[…]{text[-limit:]}"
    prompt = get_prompt("question_rewriter")
    user = Template(prompt.prompt).substitute(history=text, message=TAG.sub("", message))
    try:
        reply = gateway.chat_ollama().generate(
            "question_rewriter", user, system=prompt.system, json_mode=SCHEMA
        )
        question = Rewritten.model_validate_json(reply).question
    except (OllamaError, ValidationError) as exc:
        log.warning("question rewriter failed, using the message as it is: %s", exc)
        monitor.record("model_error", f"Question rewriter: {exc}")
        return message
    return question or message
