"""Create meal planning tables.

Revision ID: 0003_meals
Revises: 0002_recovery_grants
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_meals"
down_revision = "0002_recovery_grants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingredients",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_ingredients_name", "ingredients", ["name"])
    op.create_table(
        "dishes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("recipe_url", sa.String(length=2048), nullable=True),
        sa.Column("monthly_limit", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("title"),
    )
    op.create_index("ix_dishes_title", "dishes", ["title"])
    op.create_table(
        "dish_ingredients",
        sa.Column("dish_id", sa.String(length=36), nullable=False),
        sa.Column("ingredient_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["dish_id"], ["dishes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("dish_id", "ingredient_id"),
    )
    op.create_table(
        "meal_days",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("meal_date", sa.Date(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_feral", sa.Boolean(), nullable=False),
        sa.Column("suggested_by_id", sa.String(length=36), nullable=False),
        sa.Column("reviewed_by_id", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("rescheduled_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["suggested_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meal_date"),
    )
    op.create_index("ix_meal_days_meal_date", "meal_days", ["meal_date"])
    op.create_index("ix_meal_days_week_start", "meal_days", ["week_start"])
    op.create_table(
        "meal_day_dishes",
        sa.Column("meal_day_id", sa.String(length=36), nullable=False),
        sa.Column("dish_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["meal_day_id"], ["meal_days.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dish_id"], ["dishes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("meal_day_id", "dish_id"),
    )


def downgrade() -> None:
    op.drop_table("meal_day_dishes")
    op.drop_index("ix_meal_days_week_start", table_name="meal_days")
    op.drop_index("ix_meal_days_meal_date", table_name="meal_days")
    op.drop_table("meal_days")
    op.drop_table("dish_ingredients")
    op.drop_index("ix_dishes_title", table_name="dishes")
    op.drop_table("dishes")
    op.drop_index("ix_ingredients_name", table_name="ingredients")
    op.drop_table("ingredients")