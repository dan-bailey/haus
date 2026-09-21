from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.meals import MealPlanningError, create_meal_day, monday_for
from app.models import Dish, MealDay, MealDayDish, User
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
        return {"meal_date": None, "status": None, "feral": False, "dishes": []}
    dishes = session.scalars(
        select(Dish)
        .join(MealDayDish, MealDayDish.dish_id == Dish.id)
        .where(MealDayDish.meal_day_id == meal_day.id)
        .order_by(Dish.title)
    ).all()
    return {
        "meal_date": meal_day.meal_date,
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
    week_start: date,
    session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> HTMLResponse:
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
            "week_start": week_start,
            "previous_week": week_start.fromordinal(week_start.toordinal() - 7),
            "next_week": week_start.fromordinal(week_start.toordinal() + 7),
            "days": days,
        },
    )