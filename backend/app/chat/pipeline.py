"""Chat pipeline (Tasks 5.6, 7.5): one user message in, a streamed reply out, the turn saved.

memory → guard → intent → small talk: an instant canned reply
                        → question: rewrite → guard → find evidence → answer (streamed)
                                    → check claims → confidence
                        → action: rewrite → guard → plan a pending action (approval card)

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

from app import monitor
from app.chat import actions, answer, guard, intent, search
from app.chat.check import CITATION, check, confidence
from app.chat.intent import ACTION, QUESTION, SMALL_TALK
from app.chat.memory import add_message, last_turns
from app.chat.permissions import user_tags
from app.chat.rewrite import rewrite
from app.config.settings import get_settings
from app.db.schema import ChatMessage, ChatSession
from app.models.gateway import OllamaClient, OllamaError

log = logging.getLogger("syncra.chat")

BLOCKED = "blocked"
PLANNED = (
    'I can create this Jira ticket in {project}: "{title}". Nothing happens until you approve it.'
)
CANT_DO = (
    "I can only create Jira tickets so far, in Jira projects you can see. Try: "
    '"open a Jira ticket to add monitoring for the payment queue".'
)
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
    action: dict[str, Any] | None = None  # the approval card, on the action path


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
    """The reply to one message in `chat`, piece by piece, then the `Reply`; saves the turn.
    Logs the time each stage took; a reply slower than SLOW_ANSWER_SECONDS is recorded."""
    timer = monitor.Timer()
    history = last_turns(session, chat.id)
    timer.lap("memory")
    if guard.is_attack(message, detect):
        log.warning("prompt guard blocked a message in chat %s", chat.id)
        yield Reply(BLOCKED, guard.BLOCKED_REPLY)
        return
    timer.lap("guard")
    path = intent.route(message, classify)
    timer.lap("intent")
    if path == SMALL_TALK:
        done = Reply(SMALL_TALK, intent.small_talk_reply(message))
    else:
        question = rewrite(message, history, client)
        if question != message and guard.is_attack(question, detect):
            log.warning("prompt guard flagged the rewritten question in chat %s", chat.id)
            question = message
        timer.lap("rewrite")
        if path == ACTION:
            done = _plan(session, chat, question, client)
            timer.lap("plan")
        else:
            done = yield from _answer(session, chat, question, history, client, find, timer)
    add_message(session, chat, "user", message)
    if done.reply != UNAVAILABLE:  # an outage isn't an answer: the question stays unanswered
        add_message(session, chat, "assistant", done.reply, done.sources, done.confidence)
    session.commit()
    _timed(chat, path, timer)
    yield done


def _timed(chat: ChatSession, path: str, timer: monitor.Timer) -> None:
    timings = {**timer.stages, "total": timer.total()}
    log.info("chat %s %s took %s", chat.id, path, timings, extra={"timings": timings})
    if timings["total"] > get_settings().slow_answer_seconds:
        monitor.record("slow_answer", f"A {path} reply took {timings['total']:.1f}s",
                       chat_id=chat.id, timings=timings)  # fmt: skip


def _answer(
    session: Session,
    chat: ChatSession,
    question: str,
    history: list[ChatMessage],
    client: OllamaClient | None,
    find: Find,
    timer: monitor.Timer,
) -> Iterator[str | Reply]:
    evidence = find(question, user_tags(session, chat.user_id))
    timer.lap("search")
    pieces = []
    try:
        for piece in answer.write(question, evidence, history, client):
            if not pieces:
                timer.lap("first_word")
            pieces.append(piece)
            yield piece
    except OllamaError as exc:
        log.exception("answer writer failed in chat %s", chat.id)
        monitor.record("model_error", f"Answer writer: {exc}", chat_id=chat.id)
        return Reply(QUESTION, UNAVAILABLE, question)
    timer.lap("answer")
    draft, follow_ups = answer.split("".join(pieces))
    checked = check(draft, evidence)
    timer.lap("check")
    if checked.removed:
        log.info("claim checker removed %d claim(s) in chat %s", len(checked.removed), chat.id)
    text = checked.text or UNSUPPORTED
    cited = {label.strip() for m in CITATION.findall(text) for label in m.split(",")}
    sources = [source(e) for e in evidence if e.label in cited]
    return Reply(QUESTION, text, question, sources, confidence(checked, evidence), follow_ups)


def _plan(session: Session, chat: ChatSession, request: str, client: OllamaClient | None) -> Reply:
    try:
        action = actions.plan(session, chat, request, client)
    except OllamaError as exc:
        log.exception("action planner failed in chat %s", chat.id)
        monitor.record("model_error", f"Action planner: {exc}", chat_id=chat.id)
        return Reply(ACTION, UNAVAILABLE, request)
    if action is None:
        return Reply(ACTION, CANT_DO, request)
    text = PLANNED.format(project=action.payload["project"], title=action.payload["title"])
    return Reply(ACTION, text, request, action=actions.card(action))


def reply(session: Session, chat: ChatSession, message: str, **models: Any) -> Reply:
    """`stream`, without the pieces: the final `Reply`."""
    *_, done = stream(session, chat, message, **models)
    assert isinstance(done, Reply)
    return done
