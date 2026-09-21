from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.identity import (
    InvitationError,
    create_invitation,
    hash_invitation_token,
    revoke_invitation,
)
from app.models import Invitation, User, UserRole
from app.permissions import get_current_user, require_roles


router = APIRouter(prefix="/invitations", tags=["invitations"])


class InvitationRequest(BaseModel):
    role: UserRole = UserRole.CHILD


class InvitationResponse(BaseModel):
    invitation_url: str
    expires_at: datetime


class InvitationSummary(BaseModel):
    id: str
    role: str
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None
    revoked_at: datetime | None


@router.get("/me")
def current_user(current_user: User = Depends(get_current_user)) -> dict[str, str]:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "display_name": current_user.display_name,
        "role": current_user.role,
    }


@router.get(
    "",
    response_model=list[InvitationSummary],
    dependencies=[Depends(require_roles("administrator", "parent"))],
)
def list_invitations(session: Session = Depends(get_db)) -> list[InvitationSummary]:
    invitations = session.scalars(
        select(Invitation).order_by(Invitation.created_at.desc())
    ).all()
    return [InvitationSummary.model_validate(inv, from_attributes=True) for inv in invitations]


@router.post(
    "",
    response_model=InvitationResponse,
    dependencies=[Depends(require_roles("administrator", "parent"))],
)
def issue_invitation(
    payload: InvitationRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvitationResponse:
    role = payload.role
    if role == UserRole.ADMINISTRATOR:
        role = UserRole.PARENT
    raw_token = create_invitation(session, created_by=current_user, role=role)
    invitation = session.scalar(
        select(Invitation).where(
            Invitation.token_hash == hash_invitation_token(raw_token)
        )
    )
    if invitation is None:
        raise RuntimeError("created invitation could not be loaded")
    session.commit()
    settings = get_settings()
    invitation_url = (
        f"https://{settings.household_hostname}/auth/login?invite={quote(raw_token)}"
    )
    return InvitationResponse(
        invitation_url=invitation_url,
        expires_at=invitation.expires_at,
    )


@router.delete(
    "/{invitation_id}",
    status_code=204,
    dependencies=[Depends(require_roles("administrator", "parent"))],
)
def revoke(
    invitation_id: str,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    try:
        revoke_invitation(
            session,
            invitation_id=invitation_id,
            revoked_by=current_user,
        )
        session.commit()
    except InvitationError as error:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(error)) from error