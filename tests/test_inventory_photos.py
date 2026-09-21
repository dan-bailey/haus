from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, _engine_kwargs, get_db
from app.inventory import create_item, create_location
from app.main import app
from app.models import User, UserRole
from app.permissions import get_current_user


def test_inventory_photo_upload_is_image_only_and_stays_in_media_root(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'photos.db'}"
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
        location = create_location(session, room="Office", container="Shelf")
        item = create_item(session, name="Camera", location=location)
        item_id = item.id
        session.commit()

    media_root = tmp_path / "media"
    monkeypatch.setenv("HAUS_MEDIA_DIR", str(media_root))
    from app.config import get_settings

    get_settings.cache_clear()

    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        client = TestClient(app)
        response = client.post(
            f"/inventory/items/{item_id}/photo",
            files={"photo": ("../../unsafe.jpg", b"fake-image", "image/jpeg")},
        )
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert response.status_code == 200
    relative_path = response.json()["photo_path"]
    assert ".." not in relative_path
    assert (media_root / relative_path).read_bytes() == b"fake-image"