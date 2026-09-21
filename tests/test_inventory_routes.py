from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, _engine_kwargs, get_db
from app.main import app
from app.models import User, UserRole
from app.permissions import get_current_user


def test_inventory_route_can_create_and_search_items(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'inventory-routes.db'}"
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
        location_response = client.post(
            "/inventory/locations",
            json={"room": "Garage", "container": "Cabinet"},
        )
        item_response = client.post(
            "/inventory/items",
            json={"name": "Cordless Drill", "location_id": location_response.json()["id"]},
        )
        search_response = client.get("/inventory", params={"query": "drill"})
    finally:
        app.dependency_overrides.clear()

    assert location_response.status_code == 201
    assert item_response.status_code == 201
    assert search_response.status_code == 200
    assert search_response.json()[0]["name"] == "Cordless Drill"