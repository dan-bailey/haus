from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.identity import (
    InvitationError,
    consume_recovery_grant,
    register_google_user,
)


router = APIRouter(prefix="/auth", tags=["authentication"])
oauth = OAuth()


def google_client():
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        return None
    if "google" not in oauth._clients:
        oauth.register(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url=(
                "https://accounts.google.com/.well-known/openid-configuration"
            ),
            client_kwargs={"scope": "openid email profile"},
        )
    return oauth.google


@router.get("/login")
async def login(request: Request, invite: str | None = None):
    client = google_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Google sign-in is not configured",
        )
    if invite:
        request.session["invitation_token"] = invite
    redirect_uri = request.url_for("auth_callback")
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/callback", name="auth_callback")
async def auth_callback(request: Request, session: Session = Depends(get_db)):
    client = google_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Google sign-in is not configured",
        )

    token = await client.authorize_access_token(request)
    claims = token.get("userinfo") or await client.userinfo(token=token)
    try:
        user = register_google_user(
            session,
            google_subject=claims["sub"],
            email=claims["email"],
            display_name=claims.get("name") or claims["email"],
            invitation_token=request.session.pop("invitation_token", None),
        )
        session.commit()
    except (KeyError, InvitationError) as error:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(error)) from error

    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=303)


@router.get("/recovery")
def recovery(
    request: Request,
    token: str,
    session: Session = Depends(get_db),
):
    try:
        user = consume_recovery_grant(session, raw_token=token)
        session.commit()
    except InvitationError as error:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(error)) from error

    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=303)