"""Knowledge store tables (description.md §7). One PostgreSQL database for everything.

Indexes, generated columns and the vector extension are defined in `migrations/versions/`;
this module is the ORM view used by queries.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, get_args

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy import (
    text as sqltext,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config.settings import get_settings

EMBEDDING_DIM = get_settings().embedding_dim

# Allowed values (kept here so every writer agrees; small enough not to need config)
SourceKind = Literal["github", "jira", "slack"]
ItemType = Literal["pr", "commit", "review", "issue", "comment", "message", "thread"]
SOURCE_KINDS = get_args(SourceKind)
ITEM_TYPES = get_args(ItemType)
ITEM_STATUSES = ("new", "processed", "noise", "failed")
ACTION_STATUSES = ("pending", "approved", "rejected", "done", "failed")


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _updated_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(Text)
    is_admin: Mapped[bool] = mapped_column(Boolean, server_default=sqltext("false"))
    created_at: Mapped[datetime] = _created_at()


class AuthToken(Base):
    """One login: the SHA-256 of the bearer token POST /auth/login handed out (migration 0003)."""

    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class UserSourceIdentity(Base):
    """Maps a Syncra user to their GitHub / Jira / Slack account."""

    __tablename__ = "user_source_identities"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source_kind: Mapped[str] = mapped_column(String(20))
    external_id: Mapped[str] = mapped_column(
        String(200)
    )  # github login / jira accountId / slack id
    display_name: Mapped[str | None] = mapped_column(String(200))


class Source(Base):
    """A connected GitHub repo, Jira project or Slack channel."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))  # "org/repo", "PAY", "#eng-payments"
    external_id: Mapped[str] = mapped_column(
        String(200)
    )  # repo full name / project key / channel id
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sqltext("'{}'::jsonb"))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=sqltext("true"))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    members: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=sqltext("'{}'::text[]")
    )  # accounts that may see its items, refreshed every sync (migration 0004)
    created_at: Mapped[datetime] = _created_at()

    @property
    def access_tag(self) -> str:
        """The tag its items carry: `github:repo:org/x`, `jira:project:PAY`, `slack:channel:C1`."""
        return access_tag(self.kind, self.external_id)


TAG_SCOPE = {"github": "repo", "jira": "project", "slack": "channel"}


def access_tag(kind: str, external_id: str) -> str:
    """The tag every item of a source carries, e.g. `slack:channel:C1`."""
    return f"{kind}:{TAG_SCOPE[kind]}:{external_id}"


class SyncCursor(Base):
    __tablename__ = "sync_cursors"

    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True
    )
    cursor: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = _updated_at()


class Item(Base):
    """A raw, already-scrubbed item from a source (PR, issue, Slack thread, ...)."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    external_id: Mapped[str] = mapped_column(String(300))
    type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(200))  # "github:alice", "slack:U123"
    link: Mapped[str | None] = mapped_column(Text)
    parent_external_id: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # at the source
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # at the source
    access_tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=sqltext("'{}'::text[]")
    )  # who can see it, e.g. ["github:repo:org/x"], ["slack:channel:C1"], ["public"]
    content_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), server_default=sqltext("'new'"))
    ingested_at: Mapped[datetime] = _created_at()

    @property
    def full_text(self) -> str:
        """What triage and the chunker read: title (unless the text already has it), then text.
        An issue's or PR's title starts with its reference (`PAY-131 …`, `#42 …`), so keyword
        search finds it by the id people quote."""
        title = self.title or ""
        ref = self.external_id or ""
        if self.type in ("issue", "pr") and ref not in f"{title} {self.text}":
            title = f"{ref} {title}".strip()
        if title and title not in self.text:
            return f"{title}\n\n{self.text}".strip()
        return self.text.strip()


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("items.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    vector: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    tsv: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', text)", persisted=True)
    )
    created_at: Mapped[datetime] = _created_at()


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(20))  # an entity_finder label in config/models.yaml
    name: Mapped[str] = mapped_column(String(300))  # canonical name
    created_at: Mapped[datetime] = _created_at()


class EntityAlias(Base):
    __tablename__ = "entity_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    alias: Mapped[str] = mapped_column(String(300))
    source_kind: Mapped[str | None] = mapped_column(String(20))


class Edge(Base):
    """Knowledge-graph link between two nodes of any node table.

    (src_type, src_id) --relation--> (dst_type, dst_id); node types: entity, item, chunk, decision.
    Relations: authored, reviewed, mentions, decided, about (written by app/learning/graph.py);
    owns, depends_on (reserved). Each link is deleted with the item it was learned from.
    """

    __tablename__ = "edges"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    src_type: Mapped[str] = mapped_column(String(20))
    src_id: Mapped[int] = mapped_column(BigInteger)
    relation: Mapped[str] = mapped_column(String(30))
    dst_type: Mapped[str] = mapped_column(String(20))
    dst_id: Mapped[int] = mapped_column(BigInteger)
    item_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("items.id", ondelete="CASCADE"), index=True
    )  # evidence the link came from (migration 0002)
    created_at: Mapped[datetime] = _created_at()


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("items.id", ondelete="CASCADE"))
    decision: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    people: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=sqltext("'{}'::text[]"))
    link: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=sqltext("'[]'::jsonb")
    )
    confidence: Mapped[str | None] = mapped_column(String(10))  # high | medium | low
    created_at: Mapped[datetime] = _created_at()


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(50))  # e.g. create_jira_ticket
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sqltext("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(20), server_default=sqltext("'pending'"))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class Event(Base):
    """Something an admin should see: a failed sync or learning run, a model error, a slow
    answer (migration 0005, written by app/monitor.py)."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))  # sync_failed | learn_failed | model_error | …
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sqltext("'{}'::jsonb"))
    created_at: Mapped[datetime] = _created_at()
