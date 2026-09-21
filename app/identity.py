from datetime import datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    Invitation,
    LoginEvent,
    RecoveryGrant,
    User,
    UserRole,
    utc_now,
)


class InvitationError(ValueError):
    pass


def hash_invitation_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def create_invitation(
    session: Session,
    *,
    created_by: User,
    role: UserRole,
    lifetime: timedelta = timedelta(days=7),
    now: datetime | None = None,
) -> str:
    if created_by.role not in {
        UserRole.ADMINISTRATOR.value,
        UserRole.PARENT.value,
    }:
        raise InvitationError("only parents and administrators can invite users")

    raw_token = token_urlsafe(32)
    issued_at = now or utc_now()
    session.add(
        Invitation(
            token_hash=hash_invitation_token(raw_token),
            created_by_id=created_by.id,
            role=role.value,
            created_at=issued_at,
            expires_at=issued_at + lifetime,
        )
    )
    session.add(
        AuditEvent(
            actor_user_id=created_by.id,
            action="invitation.created",
            entity_type="invitation",
            details={"role": role.value},
            occurred_at=issued_at,
        )
    )
    session.flush()
    return raw_token


def consume_invitation(
    session: Session,
    *,
    raw_token: str,
    now: datetime | None = None,
) -> Invitation:
    invitation = session.scalar(
        select(Invitation).where(
            Invitation.token_hash == hash_invitation_token(raw_token)
        )
    )
    current_time = now or utc_now()
    if invitation is None or invitation.used_at is not None or invitation.revoked_at is not None:
        raise InvitationError("invitation is invalid or has already been used")
    if invitation.expires_at <= current_time:
        raise InvitationError("invitation has expired")

    invitation.used_at = current_time
    session.flush()
    return invitation


def revoke_invitation(
    session: Session,
    *,
    invitation_id: str,
    revoked_by: User,
    now: datetime | None = None,
) -> Invitation:
    if revoked_by.role not in {
        UserRole.ADMINISTRATOR.value,
        UserRole.PARENT.value,
    }:
        raise InvitationError("only parents and administrators can revoke invitations")
    invitation = session.get(Invitation, invitation_id)
    if invitation is None:
        raise InvitationError("invitation does not exist")
    if invitation.used_at is not None:
        raise InvitationError("used invitations cannot be revoked")
    if invitation.revoked_at is None:
        current_time = now or utc_now()
        invitation.revoked_at = current_time
        session.add(
            AuditEvent(
                actor_user_id=revoked_by.id,
                action="invitation.revoked",
                entity_type="invitation",
                entity_id=invitation.id,
                occurred_at=current_time,
            )
        )
        session.flush()
    return invitation


def register_google_user(
    session: Session,
    *,
    google_subject: str,
    email: str,
    display_name: str,
    invitation_token: str | None = None,
    now: datetime | None = None,
) -> User:
    current_time = now or utc_now()
    existing_user = session.scalar(
        select(User).where(User.google_subject == google_subject)
    )
    if existing_user is not None:
        existing_user.last_login_at = current_time
        session.add(
            LoginEvent(
                user_id=existing_user.id,
                succeeded=True,
                occurred_at=current_time,
                detail="existing user",
            )
        )
        session.flush()
        return existing_user

    has_users = session.scalar(select(func.count(User.id))) > 0
    invitation = None
    if has_users:
        if invitation_token is None:
            raise InvitationError("an invitation is required for this account")
        invitation = consume_invitation(
            session, raw_token=invitation_token, now=current_time
        )

    user = User(
        google_subject=google_subject,
        email=email,
        display_name=display_name,
        role=(
            UserRole.ADMINISTRATOR.value
            if not has_users
            else invitation.role
        ),
        created_at=current_time,
        last_login_at=current_time,
    )
    session.add(user)
    session.flush()
    session.add(
        LoginEvent(
            user_id=user.id,
            succeeded=True,
            occurred_at=current_time,
            detail="first administrator" if not has_users else "invited user",
        )
    )
    session.add(
        AuditEvent(
            actor_user_id=user.id,
            action="user.registered",
            entity_type="user",
            entity_id=user.id,
            details={"role": user.role},
            occurred_at=current_time,
        )
    )
    session.flush()
    return user


def create_recovery_grant(
    session: Session,
    *,
    administrator: User,
    lifetime: timedelta = timedelta(minutes=10),
    now: datetime | None = None,
) -> str:
    if administrator.role != UserRole.ADMINISTRATOR.value or not administrator.is_active:
        raise InvitationError("only an active administrator can use recovery")

    current_time = now or utc_now()
    raw_token = token_urlsafe(32)
    session.add(
        RecoveryGrant(
            token_hash=hash_invitation_token(raw_token),
            user_id=administrator.id,
            created_at=current_time,
            expires_at=current_time + lifetime,
        )
    )
    session.add(
        AuditEvent(
            actor_user_id=administrator.id,
            action="recovery.created",
            entity_type="recovery_grant",
            details={"expires_at": (current_time + lifetime).isoformat()},
            occurred_at=current_time,
        )
    )
    session.flush()
    return raw_token


def consume_recovery_grant(
    session: Session,
    *,
    raw_token: str,
    now: datetime | None = None,
) -> User:
    current_time = now or utc_now()
    grant = session.scalar(
        select(RecoveryGrant).where(
            RecoveryGrant.token_hash == hash_invitation_token(raw_token)
        )
    )
    if grant is None or grant.used_at is not None or grant.expires_at <= current_time:
        raise InvitationError("recovery grant is invalid or expired")

    user = session.get(User, grant.user_id)
    if user is None or user.role != UserRole.ADMINISTRATOR.value or not user.is_active:
        raise InvitationError("recovery administrator is unavailable")

    grant.used_at = current_time
    session.add(
        AuditEvent(
            actor_user_id=user.id,
            action="recovery.used",
            entity_type="recovery_grant",
            entity_id=grant.id,
            occurred_at=current_time,
        )
    )
    session.flush()
    return user