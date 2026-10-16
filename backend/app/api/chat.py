"""Chat endpoints: a user's chats and their messages (Task 5.2).

Every endpoint needs a login, and a user only ever sees their own chats: someone else's chat
answers 404, exactly like a chat that doesn't exist.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import DB, CurrentUser
from app.db.schema import ChatMessage, ChatSession, User

router = APIRouter(prefix="/chat")


class NewChat(BaseModel):
    title: str | None = Field(default=None, max_length=300)


def own_chat(session: Session, user: User, chat_id: int) -> ChatSession:
    chat = session.scalar(
        select(ChatSession).where(ChatSession.id == chat_id, ChatSession.user_id == user.id)
    )
    if chat is None:
        raise HTTPException(404, "Chat not found")
    return chat


@router.post("/sessions", status_code=201)
def new_chat(body: NewChat, user: CurrentUser, session: DB) -> dict[str, Any]:
    chat = ChatSession(user_id=user.id, title=body.title)
    session.add(chat)
    session.commit()
    return {"id": chat.id, "title": chat.title, "updated_at": chat.updated_at}


@router.get("/sessions")
def chats(user: CurrentUser, session: DB) -> list[dict[str, Any]]:
    """The user's chats, most recently used first."""
    rows = session.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
    )
    return [{"id": c.id, "title": c.title, "updated_at": c.updated_at} for c in rows]


@router.get("/sessions/{chat_id}/messages")
def messages(chat_id: int, user: CurrentUser, session: DB) -> list[dict[str, Any]]:
    """Every message of one of the user's chats, oldest first."""
    chat = own_chat(session, user, chat_id)
    rows = session.scalars(
        select(ChatMessage).where(ChatMessage.session_id == chat.id).order_by(ChatMessage.id)
    )
    return [
        {
            "role": m.role,
            "content": m.content,
            "sources": m.sources,
            "confidence": m.confidence,
            "created_at": m.created_at,
        }
        for m in rows
    ]
