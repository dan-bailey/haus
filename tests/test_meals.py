from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base, _engine_kwargs
from app.meals import (
    MealPlanningError,
    create_dish,
    create_meal_day,
    monday_for,
    rate_dish,
    record_cooking_event,
    review_meal_day,
)
from app.models import DishCookingEvent, DishIngredient, MealDayStatus, User, UserRole


@pytest.fixture
def session(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'meals.db'}"
    engine = create_engine(database_url, **_engine_kwargs(database_url))
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as database_session:
        yield database_session


@pytest.fixture
def users(session):
    parent = User(
        google_subject="parent-subject",
        email="parent@example.test",
        display_name="Parent",
        role=UserRole.PARENT.value,
    )
    child = User(
        google_subject="child-subject",
        email="child@example.test",
        display_name="Child",
        role=UserRole.CHILD.value,
    )
    session.add_all([parent, child])
    session.flush()
    return parent, child


def test_monday_for_uses_monday_through_sunday_weeks() -> None:
    assert monday_for(date(2026, 9, 21)) == date(2026, 9, 21)
    assert monday_for(date(2026, 9, 27)) == date(2026, 9, 21)
    assert monday_for(date(2026, 9, 20)) == date(2026, 9, 14)


def test_dish_reuses_named_ingredients_and_keeps_recipe_metadata(session) -> None:
    dish = create_dish(
        session,
        title="Tacos",
        ingredients=[" tortillas ", "ground beef", "tortillas"],
        recipe_url="https://example.test/tacos",
    )
    session.commit()

    assert dish.recipe_url == "https://example.test/tacos"
    assert session.scalars(select(DishIngredient)).all().__len__() == 2


def test_parent_meal_is_approved_and_child_meal_is_proposed(session, users) -> None:
    parent, child = users
    dish = create_dish(session, title="Soup", ingredients=["broth"])
    parent_day = create_meal_day(
        session, actor=parent, meal_date=date(2026, 9, 22), dish_ids=[dish.id]
    )
    child_day = create_meal_day(
        session, actor=child, meal_date=date(2026, 9, 23), dish_ids=[dish.id]
    )

    assert parent_day.status == MealDayStatus.APPROVED.value
    assert child_day.status == MealDayStatus.PROPOSED.value


def test_child_cannot_create_feral_day(session, users) -> None:
    _, child = users

    with pytest.raises(MealPlanningError, match="cannot suggest Feral Days"):
        create_meal_day(
            session, actor=child, meal_date=date(2026, 9, 24), feral=True
        )


def test_parent_can_review_and_reschedule_child_suggestion(session, users) -> None:
    parent, child = users
    day = create_meal_day(session, actor=child, meal_date=date(2026, 9, 24))

    reviewed = review_meal_day(
        session,
        reviewer=parent,
        meal_day_id=day.id,
        status=MealDayStatus.RESCHEDULED,
        rescheduled_to=date(2026, 9, 26),
    )

    assert reviewed.status == MealDayStatus.RESCHEDULED.value
    assert reviewed.rescheduled_to == date(2026, 9, 26)


def test_cooking_limit_is_per_month_and_zero_is_unlimited(session, users) -> None:
    parent, child = users
    limited = create_dish(
        session, title="Limited", ingredients=["rice"], monthly_limit=1
    )
    event = record_cooking_event(
        session,
        dish_id=limited.id,
        cooked_on=date(2026, 9, 1),
        requested_by=child,
        cooked_by=parent,
    )
    assert event.cooked_on == date(2026, 9, 1)
    with pytest.raises(MealPlanningError, match="monthly limit"):
        record_cooking_event(
            session,
            dish_id=limited.id,
            cooked_on=date(2026, 9, 20),
            requested_by=child,
            cooked_by=parent,
        )
    unlimited = create_dish(
        session, title="Unlimited", ingredients=["beans"], monthly_limit=0
    )
    record_cooking_event(
        session,
        dish_id=unlimited.id,
        cooked_on=date(2026, 9, 20),
        requested_by=child,
        cooked_by=parent,
    )
    assert session.scalars(select(DishCookingEvent)).all().__len__() == 2


def test_rating_is_one_to_five_and_updates_per_user(session, users) -> None:
    parent, _ = users
    dish = create_dish(session, title="Curry", ingredients=["spices"])

    rating = rate_dish(session, dish_id=dish.id, user=parent, rating=4)
    updated = rate_dish(session, dish_id=dish.id, user=parent, rating=5)

    assert rating.id == updated.id
    assert updated.rating == 5
    with pytest.raises(MealPlanningError, match="between 1 and 5"):
        rate_dish(session, dish_id=dish.id, user=parent, rating=6)