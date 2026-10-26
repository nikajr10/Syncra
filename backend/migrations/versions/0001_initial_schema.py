"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-15
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = get_settings().embedding_dim


def _ts(name: str, **kw: object) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, **kw
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200)),
        sa.Column("password_hash", sa.Text),
        sa.Column("is_admin", sa.Boolean, server_default=sa.text("false"), nullable=False),
        _ts("created_at"),
    )

    op.create_table(
        "user_source_identities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("source_kind", sa.String(20), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(200)),
        sa.UniqueConstraint("source_kind", "external_id"),
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column(
            "config", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text),
        _ts("created_at"),
        sa.UniqueConstraint("kind", "external_id"),
    )

    op.create_table(
        "sync_cursors",
        sa.Column(
            "source_id",
            sa.Integer,
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("cursor", sa.Text),
        _ts("updated_at"),
    )

    op.create_table(
        "items",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "source_id", sa.Integer, sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("external_id", sa.String(300), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("title", sa.Text),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("author", sa.String(200)),
        sa.Column("link", sa.Text),
        sa.Column("parent_external_id", sa.String(300)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column(
            "access_tags",
            postgresql.ARRAY(sa.Text),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("status", sa.String(20), server_default=sa.text("'new'"), nullable=False),
        _ts("ingested_at"),
        sa.UniqueConstraint("source_id", "external_id"),
    )
    op.create_index("ix_items_status", "items", ["status"])
    op.create_index("ix_items_access_tags", "items", ["access_tags"], postgresql_using="gin")

    op.create_table(
        "chunks",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "item_id", sa.BigInteger, sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("vector", Vector(EMBEDDING_DIM)),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR,
            sa.Computed("to_tsvector('english', text)", persisted=True),
        ),
        _ts("created_at"),
        sa.UniqueConstraint("item_id", "position"),
    )
    op.create_index("ix_chunks_item_id", "chunks", ["item_id"])
    op.create_index(
        "ix_chunks_vector_hnsw",
        "chunks",
        ["vector"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"vector": "vector_cosine_ops"},
    )
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], postgresql_using="gin")

    op.create_table(
        "entities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        _ts("created_at"),
        sa.UniqueConstraint("type", "name"),
    )

    op.create_table(
        "entity_aliases",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "entity_id",
            sa.Integer,
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias", sa.String(300), nullable=False),
        sa.Column("source_kind", sa.String(20)),
        sa.UniqueConstraint("entity_id", "alias"),
    )
    op.create_index("ix_entity_aliases_alias_lower", "entity_aliases", [sa.text("lower(alias)")])

    op.create_table(
        "edges",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("src_type", sa.String(20), nullable=False),
        sa.Column("src_id", sa.BigInteger, nullable=False),
        sa.Column("relation", sa.String(30), nullable=False),
        sa.Column("dst_type", sa.String(20), nullable=False),
        sa.Column("dst_id", sa.BigInteger, nullable=False),
        sa.Column("item_id", sa.BigInteger, sa.ForeignKey("items.id", ondelete="SET NULL")),
        _ts("created_at"),
        sa.UniqueConstraint("src_type", "src_id", "relation", "dst_type", "dst_id"),
    )
    op.create_index("ix_edges_src", "edges", ["src_type", "src_id"])
    op.create_index("ix_edges_dst", "edges", ["dst_type", "dst_id"])

    op.create_table(
        "decisions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "item_id", sa.BigInteger, sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("decision", sa.Text, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column(
            "people",
            postgresql.ARRAY(sa.Text),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("link", sa.Text),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        _ts("created_at"),
        sa.UniqueConstraint("item_id", "decision"),
    )

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(300)),
        _ts("created_at"),
        _ts("updated_at"),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer,
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "sources", postgresql.JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("confidence", sa.String(10)),
        _ts("created_at"),
    )
    op.create_index(
        "ix_chat_messages_session_created", "chat_messages", ["session_id", "created_at"]
    )

    op.create_table(
        "actions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("chat_sessions.id", ondelete="SET NULL")),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("status", sa.String(20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("result", postgresql.JSONB),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_actions_status", "actions", ["status"])


def downgrade() -> None:
    for table in (
        "actions",
        "chat_messages",
        "chat_sessions",
        "decisions",
        "edges",
        "entity_aliases",
        "entities",
        "chunks",
        "items",
        "sync_cursors",
        "sources",
        "user_source_identities",
        "users",
    ):
        op.drop_table(table)
