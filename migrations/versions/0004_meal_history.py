"""Create cooking history and dish ratings.

Revision ID: 0004_meal_history
Revises: 0003_meals
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_meal_history"
down_revision = "0003_meals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dish_cooking_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dish_id", sa.String(length=36), nullable=False),
        sa.Column("cooked_on", sa.Date(), nullable=False),
        sa.Column("requested_by_id", sa.String(length=36), nullable=False),
        sa.Column("cooked_by_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["dish_id"], ["dishes.id"]),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["cooked_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dish_cooking_events_cooked_on", "dish_cooking_events", ["cooked_on"])
    op.create_table(
        "dish_ratings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dish_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["dish_id"], ["dishes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dish_id", "user_id"),
    )


def downgrade() -> None:
    op.drop_table("dish_ratings")
    op.drop_index("ix_dish_cooking_events_cooked_on", table_name="dish_cooking_events")
    op.drop_table("dish_cooking_events")