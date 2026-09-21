from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, _engine_kwargs
from app.meals import create_dish, create_meal_day, shopping_list
from app.models import User, UserRole
from app.shopping import shopping_pdf


def test_shopping_list_counts_approved_meal_ingredients_and_skips_feral_days(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'shopping.db'}"
    engine = create_engine(database_url, **_engine_kwargs(database_url))
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        parent = User(
            google_subject="parent-subject",
            email="parent@example.test",
            display_name="Parent",
            role=UserRole.PARENT.value,
        )
        session.add(parent)
        session.flush()
        tacos = create_dish(
            session, title="Tacos", ingredients=["tortillas", "cheese"]
        )
        quesadilla = create_dish(
            session, title="Quesadilla", ingredients=["tortillas", "cheese"]
        )
        create_meal_day(
            session,
            actor=parent,
            meal_date=date(2026, 9, 21),
            dish_ids=[tacos.id],
        )
        create_meal_day(
            session,
            actor=parent,
            meal_date=date(2026, 9, 22),
            dish_ids=[quesadilla.id],
        )
        create_meal_day(
            session,
            actor=parent,
            meal_date=date(2026, 9, 23),
            feral=True,
        )

        items = shopping_list(session, week_start=date(2026, 9, 21))
        pdf = shopping_pdf(session, week_start=date(2026, 9, 21))

    assert items == [("cheese", 2), ("tortillas", 2)]
    assert pdf.startswith(b"%PDF")