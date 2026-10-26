from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import Account

Kind = Literal["github", "jira", "slack"]


class NewSource(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    kind: Kind
    external_id: str = Field(
        description="GitHub owner/repo, Jira project key or Slack channel id",
        examples=["acme/payments"],
    )
    name: str | None = Field(default=None, max_length=200, description="Display name")


class SourceChange(BaseModel):
    enabled: bool


class SourceView(BaseModel):
    id: int
    kind: str
    name: str
    external_id: str
    enabled: bool
    last_synced_at: datetime | None
    last_error: str | None = Field(description="Last sync error")
    items: int = Field(description="Stored item count")
    members: int = Field(description="Member count at last sync")


class Sources(BaseModel):
    tools: dict[str, bool] = Field(description="Tools with credentials configured")
    sources: list[SourceView]


class EventView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str = Field(description="sync_failed, learn_failed, model_error or slow_answer")
    message: str
    details: dict[str, Any]
    created_at: datetime


class Status(BaseModel):
    items: dict[str, int] = Field(
        description="Stored items by status: new, processed, noise, failed"
    )
    sources: list[SourceView]
    events: list[EventView] = Field(description="Newest first")


class NewAccount(BaseModel):
    tool: Kind
    account_id: str = Field(examples=["alice"])
    display_name: str = ""


class UserView(BaseModel):
    username: str
    display_name: str | None
    is_admin: bool
    accounts: list[Account]
