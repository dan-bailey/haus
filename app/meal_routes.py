from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.meals import (
    MealPlanningError,
    _check_monthly_limit,
    create_dish,
    create_meal_day,
    monday_for,
    review_meal_day,
)
from app.models import (
    Dish,
    DishCookingEvent,
    DishIngredient,
    DishRating,
    Ingredient,
    MealDay,
    MealDayDish,
    MealDayStatus,
    User,
    UserRole,
)
from app.permissions import get_current_user
from app.shopping import shopping_pdf


router = APIRouter(prefix="/meals", tags=["meals"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class MealDayRequest(BaseModel):
    meal_date: date
    dish_ids: list[str] = Field(default_factory=list)
    feral: bool = False


def _day_payload(session: Session, meal_day: MealDay | None) -> dict:
    if meal_day is None:
        return {"meal_date": None, "meal_day_id": None, "status": None, "feral": False, "dishes": []}
    dishes = session.scalars(
        select(Dish)
        .join(MealDayDish, MealDayDish.dish_id == Dish.id)
        .where(MealDayDish.meal_day_id == meal_day.id)
        .order_by(Dish.title)
    ).all()
    return {
        "meal_date": meal_day.meal_date,
        "meal_day_id": meal_day.id,
        "status": meal_day.status,
        "feral": meal_day.is_feral,
        "dishes": [
            {"id": dish.id, "title": dish.title, "recipe_url": dish.recipe_url}
            for dish in dishes
        ],
    }


@router.get("/week")
def week_calendar(
    week_start: date,
    session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> dict:
    if monday_for(week_start) != week_start:
        raise HTTPException(status_code=400, detail="week_start must be a Monday")
    meal_days = session.scalars(
        select(MealDay).where(MealDay.week_start == week_start)
    ).all()
    by_date = {meal_day.meal_date: meal_day for meal_day in meal_days}
    return {
        "week_start": week_start,
        "days": [
            _day_payload(session, by_date.get(date.fromordinal(week_start.toordinal() + offset)))
            for offset in range(7)
        ],
    }


@router.post("/days", status_code=201)
def create_calendar_day(
    payload: MealDayRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        meal_day = create_meal_day(
            session,
            actor=current_user,
            meal_date=payload.meal_date,
            dish_ids=payload.dish_ids,
            feral=payload.feral,
        )
        session.commit()
    except MealPlanningError as error:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _day_payload(session, meal_day)


@router.get("/shopping-list", response_class=Response)
def shopping_list_pdf(
    week_start: date,
    session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> Response:
    if monday_for(week_start) != week_start:
        raise HTTPException(status_code=400, detail="week_start must be a Monday")
    return Response(
        content=shopping_pdf(session, week_start=week_start),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="haus-shopping-{week_start.isoformat()}.pdf"'
            )
        },
    )


@router.get("/calendar", response_class=HTMLResponse, include_in_schema=False)
def calendar_page(
    request: Request,
    week_start: date | None = None,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    if week_start is None:
        week_start = monday_for(date.today())
    if monday_for(week_start) != week_start:
        raise HTTPException(status_code=400, detail="week_start must be a Monday")
    meal_days = session.scalars(
        select(MealDay).where(MealDay.week_start == week_start)
    ).all()
    by_date = {meal_day.meal_date: meal_day for meal_day in meal_days}
    days = [
        _day_payload(
            session,
            by_date.get(date.fromordinal(week_start.toordinal() + offset)),
        )
        for offset in range(7)
    ]
    return templates.TemplateResponse(
        request=request,
        name="calendar.html",
        context={
            "current_user": current_user,
            "week_start": week_start,
            "previous_week": week_start.fromordinal(week_start.toordinal() - 7),
            "next_week": week_start.fromordinal(week_start.toordinal() + 7),
            "days": days,
        },
    )


# ── Dish list ──────────────────────────────────────────────────────────────────

@router.get("/dishes", response_class=HTMLResponse, include_in_schema=False)
def dish_list(
    request: Request,
    q: str | None = None,
    session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    query = select(Dish).order_by(Dish.title)
    if q:
        query = query.where(Dish.title.ilike(f"%{q}%"))
    dishes = session.scalars(query).all()
    return templates.TemplateResponse(
        request=request,
        name="dishes.html",
        context={"dishes": dishes, "q": q},
    )


@router.get("/dishes/new", response_class=HTMLResponse, include_in_schema=False)
def dish_new_form(
    request: Request,
    _current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="dish_new.html",
        context={"form": {}, "error": None},
    )


@router.post("/dishes", response_class=HTMLResponse, include_in_schema=False)
def dish_create(
    request: Request,
    title: str = Form(""),
    ingredients: str = Form(""),
    recipe_url: str = Form(""),
    monthly_limit: int = Form(0),
    session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    ingredient_list = [line.strip() for line in ingredients.splitlines() if line.strip()]
    form_data = {"title": title, "ingredients": ingredients, "recipe_url": recipe_url, "monthly_limit": monthly_limit}
    try:
        create_dish(
            session,
            title=title,
            ingredients=ingredient_list,
            recipe_url=recipe_url.strip() or None,
            monthly_limit=monthly_limit,
        )
        session.commit()
    except MealPlanningError as exc:
        session.rollback()
        return templates.TemplateResponse(
            request=request,
            name="dish_new.html",
            context={"form": form_data, "error": str(exc)},
            status_code=422,
        )
    return RedirectResponse(url="/meals/dishes", status_code=303)


# ── Dish detail ────────────────────────────────────────────────────────────────

@router.get("/dishes/{dish_id}", response_class=HTMLResponse, include_in_schema=False)
def dish_detail(
    dish_id: str,
    request: Request,
    session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    dish = session.get(Dish, dish_id)
    if dish is None:
        raise HTTPException(status_code=404, detail="Dish not found")
    ingredients = session.scalars(
        select(Ingredient)
        .join(DishIngredient, DishIngredient.ingredient_id == Ingredient.id)
        .where(DishIngredient.dish_id == dish_id)
        .order_by(Ingredient.name)
    ).all()
    cooking_events_raw = session.scalars(
        select(DishCookingEvent)
        .where(DishCookingEvent.dish_id == dish_id)
        .order_by(DishCookingEvent.cooked_on.desc())
    ).all()
    cooking_events = []
    for event in cooking_events_raw:
        requester = session.get(User, event.requested_by_id)
        cooking_events.append({
            "cooked_on": event.cooked_on,
            "requested_by": requester.display_name if requester else "unknown",
        })
    ratings_raw = session.scalars(
        select(DishRating).where(DishRating.dish_id == dish_id)
    ).all()
    ratings = []
    for r in ratings_raw:
        user = session.get(User, r.user_id)
        ratings.append({"user": user.display_name if user else "unknown", "rating": r.rating})
    return templates.TemplateResponse(
        request=request,
        name="dish_detail.html",
        context={
            "dish": dish,
            "ingredients": [i.name for i in ingredients],
            "cooking_events": cooking_events,
            "ratings": ratings,
        },
    )


# ── Plan a day ─────────────────────────────────────────────────────────────────

@router.get("/days/plan", response_class=HTMLResponse, include_in_schema=False)
def plan_day_form(
    request: Request,
    meal_date: date,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    if session.scalar(select(MealDay).where(MealDay.meal_date == meal_date)):
        raise HTTPException(status_code=400, detail="A meal is already planned for this date")
    dishes = session.scalars(select(Dish).order_by(Dish.title)).all()
    can_feral = current_user.role in {UserRole.ADMINISTRATOR.value, UserRole.PARENT.value}
    return templates.TemplateResponse(
        request=request,
        name="day_plan.html",
        context={
            "meal_date": meal_date,
            "week_start": monday_for(meal_date),
            "dishes": dishes,
            "can_feral": can_feral,
            "error": None,
            "form_feral": False,
        },
    )


@router.post("/days/plan", response_class=HTMLResponse, include_in_schema=False)
def plan_day_submit(
    request: Request,
    meal_date: date = Form(...),
    dish_ids: list[str] = Form(default_factory=list),
    feral: str = Form(""),
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    week_start = monday_for(meal_date)
    is_feral = bool(feral)
    try:
        create_meal_day(
            session,
            actor=current_user,
            meal_date=meal_date,
            dish_ids=dish_ids if not is_feral else [],
            feral=is_feral,
        )
        session.commit()
    except MealPlanningError as exc:
        session.rollback()
        dishes = session.scalars(select(Dish).order_by(Dish.title)).all()
        can_feral = current_user.role in {UserRole.ADMINISTRATOR.value, UserRole.PARENT.value}
        return templates.TemplateResponse(
            request=request,
            name="day_plan.html",
            context={
                "meal_date": meal_date,
                "week_start": week_start,
                "dishes": dishes,
                "can_feral": can_feral,
                "error": str(exc),
                "form_feral": is_feral,
            },
            status_code=422,
        )
    return RedirectResponse(url=f"/meals/calendar?week_start={week_start}", status_code=303)


# ── Edit a day ─────────────────────────────────────────────────────────────────

@router.get("/days/{meal_day_id}/edit", response_class=HTMLResponse, include_in_schema=False)
def edit_day_form(
    meal_day_id: str,
    request: Request,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    meal_day = session.get(MealDay, meal_day_id)
    if meal_day is None:
        raise HTTPException(status_code=404, detail="Meal day not found")
    dishes = session.scalars(select(Dish).order_by(Dish.title)).all()
    selected_ids = set(session.scalars(
        select(MealDayDish.dish_id).where(MealDayDish.meal_day_id == meal_day_id)
    ).all())
    can_feral = current_user.role in {UserRole.ADMINISTRATOR.value, UserRole.PARENT.value}
    return templates.TemplateResponse(
        request=request,
        name="day_edit.html",
        context={
            "meal_day_id": meal_day_id,
            "meal_date": meal_day.meal_date,
            "week_start": meal_day.week_start,
            "dishes": dishes,
            "selected_dish_ids": selected_ids,
            "can_feral": can_feral,
            "form_feral": meal_day.is_feral,
            "error": None,
        },
    )


@router.post("/days/{meal_day_id}/edit", response_class=HTMLResponse, include_in_schema=False)
def edit_day_submit(
    meal_day_id: str,
    request: Request,
    dish_ids: list[str] = Form(default_factory=list),
    feral: str = Form(""),
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    meal_day = session.get(MealDay, meal_day_id)
    if meal_day is None:
        raise HTTPException(status_code=404, detail="Meal day not found")
    is_feral = bool(feral)
    if is_feral and current_user.role == UserRole.CHILD.value:
        dishes = session.scalars(select(Dish).order_by(Dish.title)).all()
        return templates.TemplateResponse(
            request=request,
            name="day_edit.html",
            context={
                "meal_day_id": meal_day_id,
                "meal_date": meal_day.meal_date,
                "week_start": meal_day.week_start,
                "dishes": dishes,
                "selected_dish_ids": set(dish_ids),
                "can_feral": False,
                "form_feral": False,
                "error": "Children cannot set Feral Days",
            },
            status_code=403,
        )
    # Validate monthly limits before making any changes
    if not is_feral:
        for dish_id in dict.fromkeys(dish_ids):
            dish = session.get(Dish, dish_id)
            if dish is None:
                continue
            try:
                _check_monthly_limit(
                    session,
                    dish=dish,
                    meal_date=meal_day.meal_date,
                    exclude_meal_day_id=meal_day_id,
                )
            except MealPlanningError as exc:
                dishes = session.scalars(select(Dish).order_by(Dish.title)).all()
                can_feral = current_user.role in {UserRole.ADMINISTRATOR.value, UserRole.PARENT.value}
                return templates.TemplateResponse(
                    request=request,
                    name="day_edit.html",
                    context={
                        "meal_day_id": meal_day_id,
                        "meal_date": meal_day.meal_date,
                        "week_start": meal_day.week_start,
                        "dishes": dishes,
                        "selected_dish_ids": set(dish_ids),
                        "can_feral": can_feral,
                        "form_feral": is_feral,
                        "error": str(exc),
                    },
                    status_code=422,
                )
    # Replace dishes
    session.query(MealDayDish).filter(MealDayDish.meal_day_id == meal_day_id).delete()
    meal_day.is_feral = is_feral
    for dish_id in dict.fromkeys(dish_ids if not is_feral else []):
        if session.get(Dish, dish_id) is None:
            continue
        session.add(MealDayDish(meal_day_id=meal_day_id, dish_id=dish_id))
    session.commit()
    return RedirectResponse(url=f"/meals/calendar?week_start={meal_day.week_start}", status_code=303)


# ── Approve / disapprove ───────────────────────────────────────────────────────

@router.post("/days/{meal_day_id}/approve", response_class=HTMLResponse, include_in_schema=False)
def approve_day(
    meal_day_id: str,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    meal_day = session.get(MealDay, meal_day_id)
    if meal_day is None:
        raise HTTPException(status_code=404, detail="Meal day not found")
    try:
        review_meal_day(session, reviewer=current_user, meal_day_id=meal_day_id, status=MealDayStatus.APPROVED)
        session.commit()
    except MealPlanningError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/meals/calendar?week_start={meal_day.week_start}", status_code=303)


@router.post("/days/{meal_day_id}/disapprove", response_class=HTMLResponse, include_in_schema=False)
def disapprove_day(
    meal_day_id: str,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    meal_day = session.get(MealDay, meal_day_id)
    if meal_day is None:
        raise HTTPException(status_code=404, detail="Meal day not found")
    try:
        review_meal_day(session, reviewer=current_user, meal_day_id=meal_day_id, status=MealDayStatus.DISAPPROVED)
        session.commit()
    except MealPlanningError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/meals/calendar?week_start={meal_day.week_start}", status_code=303)