"""events: what went wrong or was slow, for the admin view (Task 10.5)

Failed syncs, failed learning runs, model errors and slow answers, written by the API and the
worker alike. Only the last EVENTS_KEEP_DAYS are kept.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("details", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_events_created_at", "events", ["created_at"])


def downgrade() -> None:
    op.drop_table("events")
