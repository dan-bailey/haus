from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_identity_migration_creates_expected_tables(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'haus.db'}"
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")

    inspector = inspect(create_engine(database_url))
    assert set(inspector.get_table_names()) == {
        "alembic_version",
        "audit_events",
        "dish_ingredients",
        "dish_cooking_events",
        "dish_ratings",
        "dishes",
        "ingredients",
        "invitations",
        "inventory_items",
        "inventory_locations",
        "inventory_loans",
        "login_events",
        "meal_day_dishes",
        "meal_days",
        "recovery_grants",
        "users",
    }