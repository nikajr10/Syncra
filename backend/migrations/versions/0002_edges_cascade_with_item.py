"""edges cascade with their evidence item, indexed by it

Every link is learned from one item (`edges.item_id`). Deleting the item (or its source) now
deletes what was learned from it, and the graph writer replaces a conversation's links by item.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-15
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("edges_item_id_fkey", "edges", type_="foreignkey")
    op.create_foreign_key(
        "edges_item_id_fkey", "edges", "items", ["item_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_edges_item_id", "edges", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_edges_item_id", "edges")
    op.drop_constraint("edges_item_id_fkey", "edges", type_="foreignkey")
    op.create_foreign_key(
        "edges_item_id_fkey", "edges", "items", ["item_id"], ["id"], ondelete="SET NULL"
    )
