from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Login(BaseModel):
    username: str = Field(max_length=100, examples=["alice"])
    password: str = Field(max_length=1024, examples=["password"])


class Token(BaseModel):
    token: str = Field(description="`Authorization: Bearer <token>`")
    expires_at: datetime


class Account(BaseModel):
    tool: str = Field(examples=["slack"], description="github, jira or slack")
    id: str = Field(examples=["U0123ABCD"], description="ID in that tool")
    display_name: str | None = Field(examples=["Alice Chen"])


class Me(BaseModel):
    username: str = Field(examples=["alice"])
    display_name: str | None = Field(examples=["Alice Chen"])
    is_admin: bool
    accounts: list[Account] = Field(description="Linked accounts")
