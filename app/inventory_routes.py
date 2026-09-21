from datetime import date
from pathlib import Path
from secrets import token_hex

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.config import get_settings
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
from app.models import InventoryItem, InventoryLocation, InventoryLoan, User
from app.permissions import get_current_user


router = APIRouter(prefix="/inventory", tags=["inventory"])


class LocationRequest(BaseModel):
    room: str
    container: str


class ItemRequest(BaseModel):
    name: str
    location_id: str
    description: str | None = None
    category: str | None = None
    serial_number: str | None = None
    photo_path: str | None = None


class LoanRequest(BaseModel):
    loaned_to: str
    loaned_on: date


class ReturnRequest(BaseModel):
    returned_on: date


def _item_payload(item: InventoryItem) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "category": item.category,
        "serial_number": item.serial_number,
        "photo_path": item.photo_path,
        "location_id": item.location_id,
        "is_active": item.is_active,
    }


MAX_PHOTO_BYTES = 5 * 1024 * 1024


@router.get("")
def search_inventory(
    query: str = "",
    session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[dict]:
    return [_item_payload(item) for item in search_items(session, query=query)]


@router.post("/locations", status_code=201)
def add_location(
    payload: LocationRequest,
    session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    try:
        location = create_location(
            session, room=payload.room, container=payload.container
        )
        session.commit()
    except InventoryError as error:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"id": location.id, "room": location.room, "container": location.container}


@router.post("/items", status_code=201)
def add_item(
    payload: ItemRequest,
    session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> dict:
    location = session.get(InventoryLocation, payload.location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="inventory location does not exist")
    try:
        item = create_item(
            session,
            name=payload.name,
            location=location,
            description=payload.description,
            category=payload.category,
            serial_number=payload.serial_number,
            photo_path=payload.photo_path,
        )
        session.commit()
    except InventoryError as error:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _item_payload(item)


@router.post("/items/{item_id}/loans", status_code=201)
def loan_inventory_item(
    item_id: str,
    payload: LoanRequest,
    session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> dict:
    try:
        loan = loan_item(
            session,
            item_id=item_id,
            loaned_to=payload.loaned_to,
            loaned_on=payload.loaned_on,
        )
        session.commit()
    except InventoryError as error:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _loan_payload(loan)


@router.post("/loans/{loan_id}/return")
def return_inventory_item(
    loan_id: str,
    payload: ReturnRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        loan = return_item(
            session,
            loan_id=loan_id,
            returned_by=current_user,
            returned_on=payload.returned_on,
        )
        session.commit()
    except InventoryError as error:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _loan_payload(loan)


@router.get("/loans")
def list_open_loans(
    session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[dict]:
    return [_loan_payload(loan) for loan in open_loans(session)]


@router.get("/released")
def list_released_items(
    year: int | None = None,
    session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[dict]:
    return [_item_payload(item) for item in released_items(session, year=year)]


@router.post("/items/{item_id}/photo")
async def upload_item_photo(
    item_id: str,
    photo: UploadFile = File(...),
    session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    item = session.get(InventoryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="inventory item does not exist")
    if photo.content_type is None or not photo.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="photo must be an image")
    content = await photo.read(MAX_PHOTO_BYTES + 1)
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="photo exceeds 5 MB limit")

    media_root = Path(get_settings().media_dir).resolve()
    media_root.mkdir(parents=True, exist_ok=True)
    filename = f"{item.id}-{token_hex(8)}.bin"
    destination = media_root / filename
    destination.write_bytes(content)
    item.photo_path = str(destination.relative_to(media_root))
    session.commit()
    return {"item_id": item.id, "photo_path": item.photo_path}


def _loan_payload(loan: InventoryLoan) -> dict:
    return {
        "id": loan.id,
        "item_id": loan.item_id,
        "loaned_to": loan.loaned_to,
        "loaned_on": loan.loaned_on,
        "returned_on": loan.returned_on,
        "returned_by_id": loan.returned_by_id,
    }