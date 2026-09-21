"""Create one-time administrator recovery grants.

Revision ID: 0002_recovery_grants
Revises: 0001_identity
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_recovery_grants"
down_revision = "0001_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recovery_grants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_recovery_grants_token_hash", "recovery_grants", ["token_hash"])


def downgrade() -> None:
    op.drop_index("ix_recovery_grants_token_hash", table_name="recovery_grants")
    op.drop_table("recovery_grants")