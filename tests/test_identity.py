from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base, _engine_kwargs
from app.identity import (
    InvitationError,
    consume_invitation,
    consume_recovery_grant,
    create_invitation,
    create_recovery_grant,
    register_google_user,
    revoke_invitation,
)
from app.models import AuditEvent, Invitation, LoginEvent, User, UserRole


@pytest.fixture
def session(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    engine = create_engine(database_url, **_engine_kwargs(database_url))
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as database_session:
        yield database_session


def test_first_google_registration_bootstraps_administrator(session) -> None:
    user = register_google_user(
        session,
        google_subject="google-1",
        email="admin@example.test",
        display_name="Admin",
    )
    session.commit()

    assert user.role == UserRole.ADMINISTRATOR.value
    assert session.scalar(select(LoginEvent).where(LoginEvent.user_id == user.id))
    assert session.scalar(
        select(AuditEvent).where(AuditEvent.entity_id == user.id)
    )


def test_invited_registration_consumes_single_use_token(session) -> None:
    admin = register_google_user(
        session,
        google_subject="google-1",
        email="admin@example.test",
        display_name="Admin",
    )
    issued_at = datetime(2026, 9, 21, 12, 0, 0)
    token = create_invitation(
        session,
        created_by=admin,
        role=UserRole.CHILD,
        now=issued_at,
    )
    child = register_google_user(
        session,
        google_subject="google-2",
        email="child@example.test",
        display_name="Child",
        invitation_token=token,
        now=issued_at + timedelta(minutes=1),
    )
    session.commit()

    assert child.role == UserRole.CHILD.value
    invitation = session.scalar(select(Invitation))
    assert invitation is not None and invitation.used_at is not None
    with pytest.raises(InvitationError, match="already been used"):
        consume_invitation(
            session,
            raw_token=token,
            now=issued_at + timedelta(minutes=2),
        )


def test_registration_requires_invitation_after_bootstrap(session) -> None:
    register_google_user(
        session,
        google_subject="google-1",
        email="admin@example.test",
        display_name="Admin",
    )

    with pytest.raises(InvitationError, match="required"):
        register_google_user(
            session,
            google_subject="google-2",
            email="child@example.test",
            display_name="Child",
        )


def test_recovery_grant_is_single_use_and_short_lived(session) -> None:
    admin = register_google_user(
        session,
        google_subject="google-1",
        email="admin@example.test",
        display_name="Admin",
    )
    issued_at = datetime(2026, 9, 21, 12, 0, 0)
    token = create_recovery_grant(session, administrator=admin, now=issued_at)

    recovered = consume_recovery_grant(
        session,
        raw_token=token,
        now=issued_at + timedelta(minutes=1),
    )
    session.commit()

    assert recovered.id == admin.id
    with pytest.raises(InvitationError, match="invalid or expired"):
        consume_recovery_grant(
            session,
            raw_token=token,
            now=issued_at + timedelta(minutes=2),
        )


def test_parent_can_revoke_unused_invitation(session) -> None:
    admin = register_google_user(
        session,
        google_subject="google-1",
        email="admin@example.test",
        display_name="Admin",
    )
    token = create_invitation(session, created_by=admin, role=UserRole.CHILD)
    invitation = session.scalar(select(Invitation))

    assert invitation is not None
    revoke_invitation(session, invitation_id=invitation.id, revoked_by=admin)
    session.commit()

    with pytest.raises(InvitationError, match="already been used"):
        consume_invitation(session, raw_token=token)