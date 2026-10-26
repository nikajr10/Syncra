"""Chat endpoints: a user's chats and their messages (Task 5.2), and sending one (Tasks 5.6, 7.5).

Every endpoint needs a login, and a user only ever sees their own chats: someone else's chat
answers 404, exactly like a chat that doesn't exist.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import DB, UNAUTHORIZED, CurrentUser
from app.chat import pipeline
from app.config.settings import get_settings
from app.db.engine import new_session
from app.db.schema import ChatMessage, ChatSession, User

router = APIRouter(prefix="/chat", tags=["Chat"], responses=UNAUTHORIZED)
NOT_FOUND = {404: {"description": "Not one of your chats"}}


class NewChat(BaseModel):
    title: str | None = Field(default=None, max_length=300, examples=["payments"])


class Chat(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    updated_at: datetime = Field(description="When a message was last sent")


class Message(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str = Field(description="user or assistant")
    content: str
    sources: list[dict[str, Any]] = Field(description="The evidence an answer cites")
    confidence: str | None = Field(description="high, medium or low, on answers")
    created_at: datetime


class NewMessage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(
        min_length=1,
        max_length=get_settings().chat_message_max_chars,
        examples=["who built the payment service?"],
    )


def chat_models() -> dict[str, Any]:
    """Models for `pipeline.reply` instead of its defaults: none. Tests override this."""
    return {}


def own_chat(session: Session, user: User, chat_id: int) -> ChatSession:
    chat = session.scalar(
        select(ChatSession).where(ChatSession.id == chat_id, ChatSession.user_id == user.id)
    )
    if chat is None:
        raise HTTPException(404, "Chat not found")
    return chat


@router.post("/sessions", status_code=201, response_model=Chat, summary="Start a chat")
def new_chat(body: NewChat, user: CurrentUser, session: DB) -> ChatSession:
    chat = ChatSession(user_id=user.id, title=body.title)
    session.add(chat)
    session.commit()
    return chat


@router.get("/sessions", response_model=list[Chat], summary="List my chats")
def chats(user: CurrentUser, session: DB) -> Sequence[ChatSession]:
    """The user's chats, most recently used first."""
    return session.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
    ).all()


@router.get(
    "/sessions/{chat_id}/messages",
    response_model=list[Message],
    summary="Read a chat",
    responses=NOT_FOUND,
)
def messages(chat_id: int, user: CurrentUser, session: DB) -> Sequence[ChatMessage]:
    """Every message of one of the user's chats, oldest first."""
    chat = own_chat(session, user, chat_id)
    return session.scalars(
        select(ChatMessage).where(ChatMessage.session_id == chat.id).order_by(ChatMessage.id)
    ).all()


@router.post("/sessions/{chat_id}/messages", summary="Send a message", responses=NOT_FOUND)
def send(
    chat_id: int,
    body: NewMessage,
    user: CurrentUser,
    session: DB,
    models: Annotated[dict[str, Any], Depends(chat_models)],
) -> pipeline.Reply:
    """Reply to one message and save the turn. `path` says how it was handled: `small_talk`
    (an instant reply), `question` (an answer citing its `sources` as [E1]…, with a
    `confidence` and `follow_ups`) or `action`, or `blocked` (a prompt attack, not saved).
    `question` is the message rewritten to stand on its own."""
    chat = own_chat(session, user, chat_id)
    return pipeline.reply(session, chat, body.message, **models)


STREAM_DOC = {
    200: {
        "description": "Server-Sent Events: `token` events (`{\"text\": …}`) while the answer is "
        "written, then one `done` event with the reply, as from *Send a message*.",
        "content": {"text/event-stream": {"example": 'event: token\ndata: {"text": "Alice"}\n\n'
                                          'event: done\ndata: {"path": "question", …}\n\n'}},
    },
    **NOT_FOUND,
}  # fmt: skip


def _event(name: str, data: object) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


@router.post(
    "/sessions/{chat_id}/messages/stream",
    summary="Send a message, streamed",
    response_class=StreamingResponse,
    responses=STREAM_DOC,
)
def send_streamed(
    chat_id: int,
    body: NewMessage,
    user: CurrentUser,
    session: DB,
    models: Annotated[dict[str, Any], Depends(chat_models)],
) -> StreamingResponse:
    """Like *Send a message*, but the answer arrives word by word as Server-Sent Events. The
    streamed words are the draft; the `done` event carries the checked reply that was saved."""
    own_chat(session, user, chat_id)  # 404 before the stream starts

    def events() -> Iterator[str]:
        with new_session() as stream_session:  # the request's session may close first
            chat = stream_session.get(ChatSession, chat_id)
            for event in pipeline.stream(stream_session, chat, body.message, **models):
                if isinstance(event, str):
                    yield _event("token", {"text": event})
                else:
                    yield _event("done", asdict(event))

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(events(), media_type="text/event-stream", headers=headers)
