"""Allow unused invitations to be revoked.

Revision ID: 0005_revoke_invitations
Revises: 0004_meal_history
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_revoke_invitations"
down_revision = "0004_meal_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invitations", sa.Column("revoked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("invitations", "revoked_at")