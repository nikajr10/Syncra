"""Chat pipeline (Tasks 5.6, 7.5): one user message in, a streamed reply out, the turn saved.

memory → guard → intent → small talk: an instant canned reply
                        → question: rewrite → guard → find evidence → answer (streamed)
                                    → check claims → confidence
                        → action: rewrite → guard → placeholder (approval cards: Phase 8)

The guard and the intent router read the message as the user wrote it, before the rewriter:
small talk never waits for an LLM, and an attack never reaches one. The rewritten question is
guarded too; if the history led the rewriter astray, the message is used as it is. A blocked
message isn't saved, so it never shows up in the history of later turns.

`stream` yields the answer's pieces (str) as the answer writer produces them, then one `Reply`:
the checked answer, its sources, confidence and follow-ups. The streamed text is the raw
draft; the `Reply` is what was saved and what the user should end up seeing.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.chat import answer, guard, intent, search
from app.chat.check import CITATION, check, confidence
from app.chat.intent import ACTION, QUESTION, SMALL_TALK
from app.chat.memory import add_message, last_turns
from app.chat.permissions import user_tags
from app.chat.rewrite import rewrite
from app.db.schema import ChatMessage, ChatSession
from app.models.gateway import OllamaClient, OllamaError

log = logging.getLogger("syncra.chat")

BLOCKED = "blocked"
ACTION_PLACEHOLDER = "Actions aren't built yet. Your request, as I understood it: {question}"
UNSUPPORTED = "I don't know: the evidence I found doesn't back up an answer."
UNAVAILABLE = "Sorry, I can't write an answer right now: the language model isn't reachable."
EXCERPT_CHARS = 300

Find = Callable[[str, list[str]], list[search.Evidence]]


@dataclass(frozen=True)
class Reply:
    path: Literal["small_talk", "question", "action", "blocked"]
    reply: str
    question: str | None = None  # the standalone question, on the question and action paths
    sources: list[dict[str, Any]] = field(default_factory=list)  # the evidence the reply cites
    confidence: str | None = None  # high | medium | low, on answers
    follow_ups: list[str] = field(default_factory=list)  # suggested next questions


def source(e: search.Evidence) -> dict[str, Any]:
    """What a reply shows (and the chat history keeps) of one piece of evidence."""
    return {
        "label": e.label,
        "title": e.title,
        "link": e.link,
        "type": e.type,
        "author": e.author,
        "date": e.created_at.date().isoformat() if e.created_at else None,
        "excerpt": e.text[:EXCERPT_CHARS],
    }


def stream(
    session: Session,
    chat: ChatSession,
    message: str,
    classify: intent.Classify = intent._model,
    detect: guard.Detect = guard._model,
    client: OllamaClient | None = None,
    find: Find = search.find_evidence,
) -> Iterator[str | Reply]:
    """The reply to one message in `chat`, piece by piece, then the `Reply`; saves the turn."""
    history = last_turns(session, chat.id)
    if guard.is_attack(message, detect):
        log.warning("prompt guard blocked a message in chat %s", chat.id)
        yield Reply(BLOCKED, guard.BLOCKED_REPLY)
        return
    path = intent.route(message, classify)
    if path == SMALL_TALK:
        done = Reply(SMALL_TALK, intent.small_talk_reply(message))
    else:
        question = rewrite(message, history, client)
        if question != message and guard.is_attack(question, detect):
            log.warning("prompt guard flagged the rewritten question in chat %s", chat.id)
            question = message
        if path == ACTION:
            done = Reply(ACTION, ACTION_PLACEHOLDER.format(question=question), question)
        else:
            done = yield from _answer(session, chat, question, history, client, find)
    add_message(session, chat, "user", message)
    if done.reply != UNAVAILABLE:  # an outage isn't an answer: the question stays unanswered
        add_message(session, chat, "assistant", done.reply, done.sources, done.confidence)
    session.commit()
    yield done


def _answer(
    session: Session,
    chat: ChatSession,
    question: str,
    history: list[ChatMessage],
    client: OllamaClient | None,
    find: Find,
) -> Iterator[str | Reply]:
    evidence = find(question, user_tags(session, chat.user_id))
    pieces = []
    try:
        for piece in answer.write(question, evidence, history, client):
            pieces.append(piece)
            yield piece
    except OllamaError:
        log.exception("answer writer failed in chat %s", chat.id)
        return Reply(QUESTION, UNAVAILABLE, question)
    draft, follow_ups = answer.split("".join(pieces))
    checked = check(draft, evidence)
    if checked.removed:
        log.info("claim checker removed %d claim(s) in chat %s", len(checked.removed), chat.id)
    text = checked.text or UNSUPPORTED
    cited = {label.strip() for m in CITATION.findall(text) for label in m.split(",")}
    sources = [source(e) for e in evidence if e.label in cited]
    return Reply(QUESTION, text, question, sources, confidence(checked, evidence), follow_ups)


def reply(session: Session, chat: ChatSession, message: str, **models: Any) -> Reply:
    """`stream`, without the pieces: the final `Reply`."""
    *_, done = stream(session, chat, message, **models)
    assert isinstance(done, Reply)
    return done
