"""Answer writer (Task 7.2): evidence + chat history + question -> a cited answer, streamed.

qwen3:8b answers only from the evidence (`search.find_evidence`), citing it as [E1]…[E8], and
ends with a "Follow-ups:" line and 2–3 suggested questions (config/prompts/answer_writer.v2.yaml).
The text is streamed piece by piece as Ollama writes it; `split` separates the answer from the
follow-ups once it is complete. Without evidence there is nothing to answer from: the reply is
"I don't know" at once, without a model call.

The evidence, the history and the question are quoted data in the prompt; tags inside them are
removed so a planted Slack message can't close its quotes and pose as instructions.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from string import Template

from app.chat.search import Evidence
from app.config.settings import get_prompt, get_settings
from app.db.schema import ChatMessage
from app.models import gateway

TAG = re.compile(r"</?\s*(?:evidence|history|question)\b[^>]*>", re.I)
FOLLOW_UPS = re.compile(r"^\W*follow[- ]?ups?\W*$", re.I | re.M)
NO_EVIDENCE = (
    "I don't know: I couldn't find anything about that in the sources you can see.\n"
    "Follow-ups:\n- What has the team decided recently?\n- Who has worked on this area?"
)


def _quote(text: str) -> str:
    return TAG.sub("", text).replace('"', "'")


def render_evidence(evidence: Sequence[Evidence]) -> str:
    blocks = []
    for e in evidence:
        date = f' date="{e.created_at:%Y-%m-%d}"' if e.created_at else ""
        blocks.append(
            f'<evidence id="{e.label}" source="{_quote(e.header)}"{date}>\n'
            f"{TAG.sub('', e.text)}\n</evidence>"
        )
    return "\n".join(blocks)


def render_history(history: Sequence[ChatMessage]) -> str:
    text = TAG.sub("", "\n".join(f"{m.role}: {m.content}" for m in history))
    limit = get_settings().answer_history_max_chars
    return f"[…]{text[-limit:]}" if len(text) > limit else text  # the newest turns matter most


def write(
    question: str,
    evidence: Sequence[Evidence],
    history: Sequence[ChatMessage] = (),
) -> Iterator[str]:
    """The answer to `question` from `evidence` (labelled E1…), piece by piece."""
    if not evidence:
        yield NO_EVIDENCE
        return
    prompt = get_prompt("answer_writer")
    user = Template(prompt.prompt).substitute(
        evidence=render_evidence(evidence),
        history=render_history(history),
        question=TAG.sub("", question),
    )
    yield from gateway.chat_ollama().stream("answer_writer", user, system=prompt.system)


def split(text: str) -> tuple[str, list[str]]:
    """(answer, follow-up questions) of a complete answer."""
    parts = FOLLOW_UPS.split(text, maxsplit=1)
    follow_ups = parts[1].splitlines() if len(parts) > 1 else []
    questions = [line.strip().lstrip("-*•0123456789.) ").strip() for line in follow_ups]
    return parts[0].strip(), [q for q in questions if q][:3]
