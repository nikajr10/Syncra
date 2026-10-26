from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings


class NewChat(BaseModel):
    title: str | None = Field(default=None, max_length=300, examples=["payments"])


class Chat(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    updated_at: datetime = Field(description="Last message time")


class Message(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str = Field(description="user or assistant")
    content: str
    sources: list[dict[str, Any]] = Field(description="Cited sources")
    confidence: str | None = Field(description="high, medium or low")
    created_at: datetime


class NewMessage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(
        min_length=1,
        max_length=get_settings().chat_message_max_chars,
        examples=["who built the payment service?"],
    )


class Suggestions(BaseModel):
    questions: list[str] = Field(
        examples=[
            ['What did we decide about "Rate limit the public API"?', "What does PAY-160 say?"]
        ],
    )
    ticket_project: str | None = Field(
        description="Jira project the user can create tickets in", examples=["PAY"]
    )
