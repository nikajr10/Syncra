"""Chat memory (Task 5.2): every message is saved, and the chat reads back the last turns.

A turn is one user message and the replies that follow it. The chat pipeline sees only the last
CHAT_MEMORY_TURNS turns of a chat (10), oldest first: that is the history the question rewriter
and the answer writer get. Messages are ordered by id, because two messages saved in one
transaction share the same `created_at`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.schema import ChatMessage, ChatSession


def add_message(
    session: Session,
    chat: ChatSession,
    role: str,
    content: str,
    sources: list[dict[str, Any]] | None = None,
    confidence: str | None = None,
) -> ChatMessage:
    """Save one message (role "user" or "assistant"); the caller commits."""
    message = ChatMessage(
        session_id=chat.id, role=role, content=content, sources=sources or [],
        confidence=confidence,
    )  # fmt: skip
    session.add(message)
    chat.updated_at = func.now()  # the chat list shows recently used chats first
    session.flush()
    return message


def last_turns(session: Session, chat_id: int, turns: int | None = None) -> Sequence[ChatMessage]:
    """The messages of the chat's last `turns` turns (CHAT_MEMORY_TURNS), oldest first."""
    turns = turns or get_settings().chat_memory_turns
    first = session.scalar(  # the user message that starts the oldest turn to keep
        select(ChatMessage.id)
        .where(ChatMessage.session_id == chat_id, ChatMessage.role == "user")
        .order_by(ChatMessage.id.desc())
        .offset(turns - 1)
        .limit(1)
    )
    query = select(ChatMessage).where(ChatMessage.session_id == chat_id)
    if first is not None:
        query = query.where(ChatMessage.id >= first)
    return session.scalars(query.order_by(ChatMessage.id)).all()
