from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class UserRole(StrEnum):
    ADMINISTRATOR = "administrator"
    PARENT = "parent"
    CHILD = "child"


class MealDayStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    DISAPPROVED = "disapproved"
    RESCHEDULED = "rescheduled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    google_subject: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(32), default=UserRole.CHILD.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(32), default=UserRole.CHILD.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LoginEvent(Base):
    __tablename__ = "login_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    succeeded: Mapped[bool] = mapped_column(Boolean)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class RecoveryGrant(Base):
    __tablename__ = "recovery_grants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)


class Dish(Base):
    __tablename__ = "dishes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    recipe_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    monthly_limit: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class DishIngredient(Base):
    __tablename__ = "dish_ingredients"

    dish_id: Mapped[str] = mapped_column(
        ForeignKey("dishes.id", ondelete="CASCADE"), primary_key=True
    )
    ingredient_id: Mapped[str] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE"), primary_key=True
    )


class MealDay(Base):
    __tablename__ = "meal_days"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    meal_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    week_start: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(
        String(32), default=MealDayStatus.PROPOSED.value
    )
    is_feral: Mapped[bool] = mapped_column(Boolean, default=False)
    suggested_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reviewed_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rescheduled_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class MealDayDish(Base):
    __tablename__ = "meal_day_dishes"

    meal_day_id: Mapped[str] = mapped_column(
        ForeignKey("meal_days.id", ondelete="CASCADE"), primary_key=True
    )
    dish_id: Mapped[str] = mapped_column(
        ForeignKey("dishes.id", ondelete="CASCADE"), primary_key=True
    )


class DishCookingEvent(Base):
    __tablename__ = "dish_cooking_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dish_id: Mapped[str] = mapped_column(ForeignKey("dishes.id"))
    cooked_on: Mapped[date] = mapped_column(Date, index=True)
    requested_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    cooked_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class DishRating(Base):
    __tablename__ = "dish_ratings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dish_id: Mapped[str] = mapped_column(ForeignKey("dishes.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    rating: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class InventoryLocation(Base):
    __tablename__ = "inventory_locations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    room: Mapped[str] = mapped_column(String(100), index=True)
    container: Mapped[str] = mapped_column(String(100), index=True)


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    serial_number: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    photo_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("inventory_locations.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    release_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class InventoryLoan(Base):
    __tablename__ = "inventory_loans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    item_id: Mapped[str] = mapped_column(ForeignKey("inventory_items.id"))
    loaned_to: Mapped[str] = mapped_column(String(200), index=True)
    loaned_on: Mapped[date] = mapped_column(Date, index=True)
    returned_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    returned_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)