"""source members: who may see each source's items (Task 6.1)

Every sync stores the accounts that can see the source (`slack:U01`, `github:alice`,
`jira:<accountId>`). A user may see an item when one of their linked accounts is a member of a
source carrying one of the item's access tags, or when the item is tagged `public`.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column(
            "members", ARRAY(sa.Text), server_default=sa.text("'{}'::text[]"), nullable=False
        ),
    )
    op.create_index("ix_sources_members", "sources", ["members"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_sources_members", "sources")
    op.drop_column("sources", "members")
