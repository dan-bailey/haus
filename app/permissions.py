from collections.abc import Callable

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User


def get_current_user(
    request: Request,
    session: Session = Depends(get_db),
) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="authentication required")

    user = session.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="authentication required")
    return user


def require_roles(*allowed_roles: str) -> Callable:
    def role_dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="insufficient permissions")
        return current_user

    return role_dependency