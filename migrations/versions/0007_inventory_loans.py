"""Create inventory loan history.

Revision ID: 0007_inventory_loans
Revises: 0006_inventory
"""
from alembic import op
import sqlalchemy as sa


revision = "0007_inventory_loans"
down_revision = "0006_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_loans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column("loaned_to", sa.String(length=200), nullable=False),
        sa.Column("loaned_on", sa.Date(), nullable=False),
        sa.Column("returned_on", sa.Date(), nullable=True),
        sa.Column("returned_by_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.id"]),
        sa.ForeignKeyConstraint(["returned_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventory_loans_loaned_to", "inventory_loans", ["loaned_to"])
    op.create_index("ix_inventory_loans_loaned_on", "inventory_loans", ["loaned_on"])


def downgrade() -> None:
    op.drop_index("ix_inventory_loans_loaned_on", table_name="inventory_loans")
    op.drop_index("ix_inventory_loans_loaned_to", table_name="inventory_loans")
    op.drop_table("inventory_loans")