"""Create inventory locations and items.

Revision ID: 0006_inventory
Revises: 0005_revoke_invitations
"""
from alembic import op
import sqlalchemy as sa


revision = "0006_inventory"
down_revision = "0005_revoke_invitations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_locations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("room", sa.String(length=100), nullable=False),
        sa.Column("container", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventory_locations_room", "inventory_locations", ["room"])
    op.create_index(
        "ix_inventory_locations_container", "inventory_locations", ["container"]
    )
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("serial_number", sa.String(length=200), nullable=True),
        sa.Column("photo_path", sa.String(length=2048), nullable=True),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("release_type", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["inventory_locations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventory_items_name", "inventory_items", ["name"])
    op.create_index("ix_inventory_items_category", "inventory_items", ["category"])
    op.create_index(
        "ix_inventory_items_serial_number", "inventory_items", ["serial_number"]
    )
    op.create_index("ix_inventory_items_is_active", "inventory_items", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_inventory_items_is_active", table_name="inventory_items")
    op.drop_index("ix_inventory_items_serial_number", table_name="inventory_items")
    op.drop_index("ix_inventory_items_category", table_name="inventory_items")
    op.drop_index("ix_inventory_items_name", table_name="inventory_items")
    op.drop_table("inventory_items")
    op.drop_index("ix_inventory_locations_container", table_name="inventory_locations")
    op.drop_index("ix_inventory_locations_room", table_name="inventory_locations")
    op.drop_table("inventory_locations")