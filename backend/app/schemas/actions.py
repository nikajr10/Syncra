from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Card(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int | None = Field(description="The chat it was planned in")
    kind: str = Field(description="What it does, e.g. create_jira_ticket")
    payload: dict[str, Any] = Field(description="Its details: project, title, description")
    status: str = Field(description="pending, approved, rejected, done or failed")
    result: dict[str, Any] | None = Field(
        description="Once run: the ticket's key and link, or the error"
    )
    created_at: datetime
