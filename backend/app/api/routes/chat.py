"""Chat endpoints: a user's chats and their messages (Task 5.2), and sending one (Tasks 5.6, 7.5).

Every endpoint needs a login, and a user only ever sees their own chats: someone else's chat
answers 404, exactly like a chat that doesn't exist.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Sequence
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DB, UNAUTHORIZED, CurrentUser
from app.db.models import ChatMessage, ChatSession, Decision, Item, User
from app.db.session import new_session
from app.schemas.chat import Chat, Message, NewChat, NewMessage, Suggestions
from app.services.chat import pipeline
from app.services.chat.actions import jira_projects
from app.services.chat.permissions import user_tags, visible

router = APIRouter(prefix="/chat", tags=["Chats"], responses=UNAUTHORIZED)
NOT_FOUND = {404: {"description": "Not one of your chats"}}


def own_chat(session: Session, user: User, chat_id: int) -> ChatSession:
    chat = session.scalar(
        select(ChatSession).where(ChatSession.id == chat_id, ChatSession.user_id == user.id)
    )
    if chat is None:
        raise HTTPException(404, "Chat not found")
    return chat


JIRA_KEY = re.compile(r"[A-Z][A-Z0-9]+-\d+")
WHY_QUESTIONS = 3


def _words(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9-]+", title.lower()) if len(w) > 2}


def same_topic(a: str, b: str) -> bool:
    """A ticket and the PR that closes it share most of their words."""
    wa, wb = _words(a), _words(b)
    return bool(wa and wb) and len(wa & wb) / min(len(wa), len(wb)) >= 0.6


@router.get("/suggestions", summary="Suggested questions")
def suggestions(user: CurrentUser, session: DB) -> Suggestions:
    # From the newest decisions in tickets and PRs the user may see, plus the newest Jira ticket
    # on another topic. Titles are quoted as they are: some name a change, some a thing.
    tags = user_tags(session, user.id)
    titles = session.scalars(
        select(Item.title)
        .join(Decision, Decision.item_id == Item.id)
        .where(visible(tags), Item.type.in_(["pr", "issue"]), Item.title.is_not(None))
        .order_by(Decision.decided_at.desc().nulls_last(), Decision.id.desc())
        .limit(30)
    )
    topics: list[str] = []
    for title in titles:
        if len(topics) < WHY_QUESTIONS and not any(same_topic(title, t) for t in topics):
            topics.append(title.strip().rstrip("."))
    questions = [f'What did we decide about "{t}"?' for t in topics]
    tickets = session.execute(
        select(Item.external_id, Item.title)
        .where(visible(tags), Item.type == "issue")
        .order_by(Item.created_at.desc(), Item.id.desc())
        .limit(30)
    )
    for key, title in tickets:
        if JIRA_KEY.fullmatch(key) and not any(same_topic(title or "", t) for t in topics):
            questions.append(f"What does {key} say?")
            break
    projects = jira_projects(session, user.id)
    return Suggestions(questions=questions, ticket_project=next(iter(projects), None))


@router.post("/sessions", status_code=201, response_model=Chat, summary="Create chat")
def new_chat(body: NewChat, user: CurrentUser, session: DB) -> ChatSession:
    chat = ChatSession(user_id=user.id, title=body.title)
    session.add(chat)
    session.commit()
    return chat


@router.get("/sessions", response_model=list[Chat], summary="List chats")
def chats(user: CurrentUser, session: DB) -> Sequence[ChatSession]:
    """Most recently updated first."""
    return session.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
    ).all()


@router.get(
    "/sessions/{chat_id}/messages",
    response_model=list[Message],
    summary="List messages",
    responses=NOT_FOUND,
)
def messages(chat_id: int, user: CurrentUser, session: DB) -> Sequence[ChatMessage]:
    """Oldest first."""
    chat = own_chat(session, user, chat_id)
    return session.scalars(
        select(ChatMessage).where(ChatMessage.session_id == chat.id).order_by(ChatMessage.id)
    ).all()


@router.post("/sessions/{chat_id}/messages", summary="Send message", responses=NOT_FOUND)
def send(
    chat_id: int,
    body: NewMessage,
    user: CurrentUser,
    session: DB,
) -> pipeline.Reply:
    """`path` is one of `small_talk`, `question`, `action` or `blocked` (not saved)."""
    chat = own_chat(session, user, chat_id)
    return pipeline.reply(session, chat, body.message)


STREAM_DOC = {
    200: {
        "description": "Server-Sent Events: `token` events, then one `done` event with the "
        "reply, as from *Send message*.",
        "content": {"text/event-stream": {"example": 'event: token\ndata: {"text": "Alice"}\n\n'
                                          'event: done\ndata: {"path": "question", …}\n\n'}},
    },
    **NOT_FOUND,
}  # fmt: skip


def _event(name: str, data: object) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


@router.post(
    "/sessions/{chat_id}/messages/stream",
    summary="Send message (stream)",
    response_class=StreamingResponse,
    responses=STREAM_DOC,
)
def send_streamed(
    chat_id: int,
    body: NewMessage,
    user: CurrentUser,
    session: DB,
) -> StreamingResponse:
    """Same as *Send message*, streamed as Server-Sent Events. The `done` event carries the
    saved reply."""
    own_chat(session, user, chat_id)  # 404 before the stream starts

    def events() -> Iterator[str]:
        with new_session() as stream_session:  # the request's session may close first
            chat = stream_session.get(ChatSession, chat_id)
            for event in pipeline.stream(stream_session, chat, body.message):
                if isinstance(event, str):
                    yield _event("token", {"text": event})
                else:
                    yield _event("done", asdict(event))

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(events(), media_type="text/event-stream", headers=headers)
