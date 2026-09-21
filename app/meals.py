from calendar import monthrange
from collections import Counter
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Dish,
    DishIngredient,
    DishCookingEvent,
    DishRating,
    Ingredient,
    MealDay,
    MealDayDish,
    MealDayStatus,
    User,
    UserRole,
    utc_now,
)


class MealPlanningError(ValueError):
    pass


def monday_for(day: date) -> date:
    return day.fromordinal(day.toordinal() - day.weekday())


def normalize_ingredient_name(name: str) -> str:
    normalized = " ".join(name.split())
    if not normalized:
        raise MealPlanningError("ingredient name cannot be empty")
    return normalized


def create_dish(
    session: Session,
    *,
    title: str,
    ingredients: list[str],
    recipe_url: str | None = None,
    monthly_limit: int = 0,
) -> Dish:
    title = title.strip()
    if not title:
        raise MealPlanningError("dish title cannot be empty")
    if monthly_limit < 0:
        raise MealPlanningError("monthly limit cannot be negative")

    dish = Dish(title=title, recipe_url=recipe_url, monthly_limit=monthly_limit)
    session.add(dish)
    normalized_names = dict.fromkeys(normalize_ingredient_name(name) for name in ingredients)
    for name in normalized_names:
        ingredient = session.scalar(select(Ingredient).where(Ingredient.name == name))
        if ingredient is None:
            ingredient = Ingredient(name=name)
            session.add(ingredient)
            session.flush()
        session.add(DishIngredient(dish_id=dish.id, ingredient_id=ingredient.id))
    session.flush()
    return dish


def create_meal_day(
    session: Session,
    *,
    actor: User,
    meal_date: date,
    dish_ids: list[str] | None = None,
    feral: bool = False,
    now: datetime | None = None,
) -> MealDay:
    if feral and actor.role == UserRole.CHILD.value:
        raise MealPlanningError("children cannot suggest Feral Days")
    if session.scalar(select(MealDay).where(MealDay.meal_date == meal_date)):
        raise MealPlanningError("a meal plan already exists for this date")

    is_reviewer = actor.role in {
        UserRole.ADMINISTRATOR.value,
        UserRole.PARENT.value,
    }
    meal_day = MealDay(
        meal_date=meal_date,
        week_start=monday_for(meal_date),
        status=(MealDayStatus.APPROVED.value if is_reviewer else MealDayStatus.PROPOSED.value),
        is_feral=feral,
        suggested_by_id=actor.id,
        reviewed_by_id=actor.id if is_reviewer else None,
        reviewed_at=(now or utc_now()) if is_reviewer else None,
    )
    session.add(meal_day)
    session.flush()
    for dish_id in dict.fromkeys(dish_ids or []):
        if session.get(Dish, dish_id) is None:
            raise MealPlanningError("dish does not exist")
        session.add(MealDayDish(meal_day_id=meal_day.id, dish_id=dish_id))
    session.flush()
    return meal_day


def review_meal_day(
    session: Session,
    *,
    reviewer: User,
    meal_day_id: str,
    status: MealDayStatus,
    rescheduled_to: date | None = None,
    now: datetime | None = None,
) -> MealDay:
    if reviewer.role not in {
        UserRole.ADMINISTRATOR.value,
        UserRole.PARENT.value,
    }:
        raise MealPlanningError("only parents and administrators can review meals")
    if status not in {
        MealDayStatus.APPROVED,
        MealDayStatus.DISAPPROVED,
        MealDayStatus.RESCHEDULED,
    }:
        raise MealPlanningError("invalid meal review status")
    if status == MealDayStatus.RESCHEDULED and rescheduled_to is None:
        raise MealPlanningError("rescheduled meals require a destination date")
    if status != MealDayStatus.RESCHEDULED and rescheduled_to is not None:
        raise MealPlanningError("only rescheduled meals can have a destination date")

    meal_day = session.get(MealDay, meal_day_id)
    if meal_day is None:
        raise MealPlanningError("meal day does not exist")
    meal_day.status = status.value
    meal_day.rescheduled_to = rescheduled_to
    meal_day.reviewed_by_id = reviewer.id
    meal_day.reviewed_at = now or utc_now()
    session.flush()
    return meal_day


def record_cooking_event(
    session: Session,
    *,
    dish_id: str,
    cooked_on: date,
    requested_by: User,
    cooked_by: User,
) -> DishCookingEvent:
    dish = session.get(Dish, dish_id)
    if dish is None:
        raise MealPlanningError("dish does not exist")
    month_start = cooked_on.replace(day=1)
    month_end = cooked_on.replace(day=monthrange(cooked_on.year, cooked_on.month)[1])
    cooked_count = session.scalar(
        select(func.count(DishCookingEvent.id)).where(
            DishCookingEvent.dish_id == dish_id,
            DishCookingEvent.cooked_on >= month_start,
            DishCookingEvent.cooked_on <= month_end,
        )
    ) or 0
    if dish.monthly_limit and cooked_count >= dish.monthly_limit:
        raise MealPlanningError("dish monthly limit reached")

    event = DishCookingEvent(
        dish_id=dish_id,
        cooked_on=cooked_on,
        requested_by_id=requested_by.id,
        cooked_by_id=cooked_by.id,
    )
    session.add(event)
    session.flush()
    return event


def rate_dish(
    session: Session,
    *,
    dish_id: str,
    user: User,
    rating: int,
) -> DishRating:
    if session.get(Dish, dish_id) is None:
        raise MealPlanningError("dish does not exist")
    if rating < 1 or rating > 5:
        raise MealPlanningError("rating must be between 1 and 5 stars")
    existing = session.scalar(
        select(DishRating).where(
            DishRating.dish_id == dish_id,
            DishRating.user_id == user.id,
        )
    )
    if existing is None:
        existing = DishRating(dish_id=dish_id, user_id=user.id, rating=rating)
        session.add(existing)
    else:
        existing.rating = rating
    session.flush()
    return existing


def shopping_list(session: Session, *, week_start: date) -> list[tuple[str, int]]:
    if monday_for(week_start) != week_start:
        raise MealPlanningError("shopping-list weeks must start on a Monday")
    week_end = week_start.fromordinal(week_start.toordinal() + 6)
    meal_days = session.scalars(
        select(MealDay).where(
            MealDay.week_start == week_start,
            MealDay.meal_date <= week_end,
            MealDay.status == MealDayStatus.APPROVED.value,
            MealDay.is_feral.is_(False),
        )
    ).all()
    dish_ids = session.scalars(
        select(MealDayDish.dish_id).where(
            MealDayDish.meal_day_id.in_([meal_day.id for meal_day in meal_days])
        )
    ).all()
    ingredient_names = session.scalars(
        select(Ingredient.name)
        .join(DishIngredient, DishIngredient.ingredient_id == Ingredient.id)
        .where(DishIngredient.dish_id.in_(dish_ids))
    ).all()
    return sorted(Counter(ingredient_names).items(), key=lambda item: item[0].lower())