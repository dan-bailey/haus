from datetime import date

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.auth import router as auth_router
from app.config import get_settings
from app.db import get_db
from app.invitations import router as invitation_router
from app.inventory_routes import router as inventory_router
from app.meal_routes import router as meal_router
from app.meals import monday_for
from app.models import InventoryLoan, MealDay, User
from app.permissions import get_current_user

APP_VERSION = "0.1.0"

app = FastAPI(title="Haus", version=APP_VERSION)
app.add_middleware(SessionMiddleware, secret_key=get_settings().session_secret)
app.include_router(auth_router)
app.include_router(invitation_router)
app.include_router(inventory_router)
app.include_router(meal_router)

templates = Jinja2Templates(directory="app/templates")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "haus", "version": APP_VERSION}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(
    request: Request,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    week_start = monday_for(date.today())
    meal_days = session.scalars(
        select(MealDay).where(MealDay.week_start == week_start)
    ).all()
    open_loans = session.scalar(
        select(func.count(InventoryLoan.id)).where(InventoryLoan.returned_on.is_(None))
    )
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "current_user": current_user,
            "meal_days_planned": len(meal_days),
            "feral_days": sum(1 for d in meal_days if d.is_feral),
            "open_loans": open_loans or 0,
        },
    )


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )