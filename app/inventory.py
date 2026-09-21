from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import InventoryItem, InventoryLoan, InventoryLocation, User, UserRole, utc_now


class InventoryError(ValueError):
    pass


def create_location(session: Session, *, room: str, container: str) -> InventoryLocation:
    room = room.strip()
    container = container.strip()
    if not room or not container:
        raise InventoryError("room and container are required")
    existing = session.scalar(
        select(InventoryLocation).where(
            func.lower(InventoryLocation.room) == room.lower(),
            func.lower(InventoryLocation.container) == container.lower(),
        )
    )
    if existing is not None:
        return existing
    location = InventoryLocation(room=room, container=container)
    session.add(location)
    session.flush()
    return location


def create_item(
    session: Session,
    *,
    name: str,
    location: InventoryLocation,
    description: str | None = None,
    category: str | None = None,
    serial_number: str | None = None,
    photo_path: str | None = None,
) -> InventoryItem:
    name = name.strip()
    if not name:
        raise InventoryError("item name is required")
    item = InventoryItem(
        name=name,
        location_id=location.id,
        description=description,
        category=category,
        serial_number=serial_number,
        photo_path=photo_path,
    )
    session.add(item)
    session.flush()
    return item


def search_items(
    session: Session,
    *,
    query: str,
    include_inactive: bool = False,
) -> list[InventoryItem]:
    query = query.strip()
    statement = select(InventoryItem).order_by(InventoryItem.name)
    if query:
        statement = statement.where(InventoryItem.name.ilike(f"%{query}%"))
    if not include_inactive:
        statement = statement.where(InventoryItem.is_active.is_(True))
    return list(session.scalars(statement).all())


def release_item(
    session: Session,
    *,
    item_id: str,
    release_type: str,
) -> InventoryItem:
    if release_type not in {"donated", "sold"}:
        raise InventoryError("release type must be donated or sold")
    item = session.get(InventoryItem, item_id)
    if item is None:
        raise InventoryError("inventory item does not exist")
    if not item.is_active:
        raise InventoryError("inventory item is already inactive")
    item.is_active = False
    item.release_type = release_type
    item.released_at = utc_now()
    session.flush()
    return item


def loan_item(
    session: Session,
    *,
    item_id: str,
    loaned_to: str,
    loaned_on: date,
) -> InventoryLoan:
    loaned_to = loaned_to.strip()
    if not loaned_to:
        raise InventoryError("borrower is required")
    item = session.get(InventoryItem, item_id)
    if item is None or not item.is_active:
        raise InventoryError("active inventory item does not exist")
    open_loan = session.scalar(
        select(InventoryLoan).where(
            InventoryLoan.item_id == item_id,
            InventoryLoan.returned_on.is_(None),
        )
    )
    if open_loan is not None:
        raise InventoryError("inventory item is already on loan")
    loan = InventoryLoan(item_id=item_id, loaned_to=loaned_to, loaned_on=loaned_on)
    session.add(loan)
    session.flush()
    return loan


def return_item(
    session: Session,
    *,
    loan_id: str,
    returned_by: User,
    returned_on: date,
) -> InventoryLoan:
    if returned_by.role not in {UserRole.ADMINISTRATOR.value, UserRole.PARENT.value}:
        raise InventoryError("only parents and administrators can return items")
    loan = session.get(InventoryLoan, loan_id)
    if loan is None:
        raise InventoryError("inventory loan does not exist")
    if loan.returned_on is not None:
        raise InventoryError("inventory loan is already closed")
    loan.returned_on = returned_on
    loan.returned_by_id = returned_by.id
    session.flush()
    return loan


def open_loans(session: Session) -> list[InventoryLoan]:
    return list(
        session.scalars(
            select(InventoryLoan)
            .where(InventoryLoan.returned_on.is_(None))
            .order_by(InventoryLoan.loaned_on)
        ).all()
    )


def released_items(session: Session, *, year: int | None = None) -> list[InventoryItem]:
    statement = select(InventoryItem).where(InventoryItem.is_active.is_(False))
    if year is not None:
        statement = statement.where(
            func.strftime("%Y", InventoryItem.released_at) == str(year)
        )
    return list(session.scalars(statement.order_by(InventoryItem.released_at)).all())