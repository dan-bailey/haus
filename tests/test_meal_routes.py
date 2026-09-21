from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db, _engine_kwargs
from app.main import app
from app.permissions import get_current_user
from app.models import User, UserRole
from app.meals import create_dish, create_meal_day


def test_week_calendar_returns_seven_monday_based_days(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'routes.db'}"
    engine = create_engine(database_url, **_engine_kwargs(database_url))
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    user = User(
        google_subject="parent-subject",
        email="parent@example.test",
        display_name="Parent",
        role=UserRole.PARENT.value,
    )
    with session_factory() as session:
        session.add(user)
        session.commit()

    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        client = TestClient(app)
        response = client.get("/meals/week", params={"week_start": "2026-09-21"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["week_start"] == "2026-09-21"
    assert len(response.json()["days"]) == 7


def test_calendar_page_renders_meals(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'calendar.db'}"
    engine = create_engine(database_url, **_engine_kwargs(database_url))
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    user = User(
        google_subject="parent-subject",
        email="parent@example.test",
        display_name="Parent",
        role=UserRole.PARENT.value,
    )
    with session_factory() as session:
        session.add(user)
        session.flush()
        dish = create_dish(session, title="Tacos", ingredients=["tortillas"])
        create_meal_day(
            session,
            actor=user,
            meal_date=date(2026, 9, 21),
            dish_ids=[dish.id],
        )
        session.commit()

    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = TestClient(app).get(
            "/meals/calendar", params={"week_start": "2026-09-21"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Tacos" in response.text
    assert "Meal calendar | Haus" in response.text