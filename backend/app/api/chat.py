"""Chat endpoints: a user's chats and their messages (Task 5.2).

Every endpoint needs a login, and a user only ever sees their own chats: someone else's chat
answers 404, exactly like a chat that doesn't exist.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import DB, UNAUTHORIZED, CurrentUser
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
