import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, _engine_kwargs
from datetime import date

from app.inventory import (
    InventoryError,
    create_item,
    create_location,
    loan_item,
    open_loans,
    release_item,
    released_items,
    return_item,
    search_items,
)
from app.models import User, UserRole


@pytest.fixture
def session(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'inventory.db'}"
    engine = create_engine(database_url, **_engine_kwargs(database_url))
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as database_session:
        yield database_session


def test_inventory_search_finds_active_items_by_name(session) -> None:
    location = create_location(session, room="Garage", container="Tool cabinet")
    toolbox = create_item(
        session,
        name="Blue Toolbox",
        location=location,
        category="Tools",
        serial_number="TB-42",
    )
    inactive = create_item(session, name="Old Toolbox", location=location)
    release_item(session, item_id=inactive.id, release_type="donated")
    session.commit()

    assert [item.id for item in search_items(session, query="blue tool")] == [toolbox.id]
    assert search_items(session, query="toolbox") == [toolbox]
    assert len(search_items(session, query="toolbox", include_inactive=True)) == 2


def test_inventory_rejects_blank_location_and_invalid_release(session) -> None:
    with pytest.raises(InventoryError, match="room and container"):
        create_location(session, room="", container="Shelf")
    location = create_location(session, room="Office", container="Desk")
    item = create_item(session, name="Notebook", location=location)
    with pytest.raises(InventoryError, match="donated or sold"):
        release_item(session, item_id=item.id, release_type="lost")


def test_loans_require_parent_return_and_reports_track_lifecycle(session) -> None:
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
    location = create_location(session, room="Garage", container="Shelf")
    item = create_item(session, name="Projector", location=location)
    loan = loan_item(
        session,
        item_id=item.id,
        loaned_to="Neighbor",
        loaned_on=date(2026, 9, 1),
    )
    assert open_loans(session) == [loan]
    with pytest.raises(InventoryError, match="only parents"):
        return_item(
            session,
            loan_id=loan.id,
            returned_by=child,
            returned_on=date(2026, 9, 5),
        )
    return_item(
        session,
        loan_id=loan.id,
        returned_by=parent,
        returned_on=date(2026, 9, 5),
    )
    donated = create_item(session, name="Old Lamp", location=location)
    donated.released_at = date(2026, 9, 6)
    release_item(session, item_id=donated.id, release_type="donated")
    session.commit()

    assert open_loans(session) == []
    assert len(released_items(session)) == 1