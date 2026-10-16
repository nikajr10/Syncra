"""Chat pipeline (Task 5.6): one user message in, one reply out, and the turn saved.

memory → guard → intent → small talk: an instant canned reply
                        → question / action: rewrite → guard → placeholder reply
(search and answers come in Phases 6–7, approval cards in Phase 8).

The guard and the intent router read the message as the user wrote it, before the rewriter:
small talk never waits for an LLM, and an attack never reaches one. The rewritten question is
guarded too; if the history led the rewriter astray, the message is used as it is. A blocked
message isn't saved, so it never shows up in the history of later turns.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.chat import guard, intent
from app.chat.intent import ACTION, QUESTION, SMALL_TALK
from app.chat.memory import add_message, last_turns
from app.chat.rewrite import rewrite
from app.db.schema import ChatSession
from app.models.gateway import OllamaClient

log = logging.getLogger("syncra.chat")

BLOCKED = "blocked"
PLACEHOLDER = {  # until Phases 6–8 replace them
    QUESTION: "Answering questions isn't built yet. Your question, as I understood it: {question}",
    ACTION: "Actions aren't built yet. Your request, as I understood it: {question}",
}


@dataclass(frozen=True)
class Reply:
    path: Literal["small_talk", "question", "action", "blocked"]
    reply: str
    question: str | None = None  # the standalone question, on the question and action paths


def reply(
    session: Session,
    chat: ChatSession,
    message: str,
    classify: intent.Classify = intent._model,
    detect: guard.Detect = guard._model,
    client: OllamaClient | None = None,
) -> Reply:
    """Answer one message in `chat` and save the turn (a blocked one is not saved)."""
    history = last_turns(session, chat.id)
    if guard.is_attack(message, detect):
        log.warning("prompt guard blocked a message in chat %s", chat.id)
        return Reply(BLOCKED, guard.BLOCKED_REPLY)
    path = intent.route(message, classify)
    question = None
    if path == SMALL_TALK:
        text = intent.small_talk_reply(message)
    else:
        question = rewrite(message, history, client)
        if question != message and guard.is_attack(question, detect):
            log.warning("prompt guard flagged the rewritten question in chat %s", chat.id)
            question = message
        text = PLACEHOLDER[path].format(question=question)
    add_message(session, chat, "user", message)
    add_message(session, chat, "assistant", text)
    session.commit()
    return Reply(path, text, question)
