from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.auth import router as auth_router
from app.config import get_settings
from app.invitations import router as invitation_router
from app.inventory_routes import router as inventory_router
from app.meal_routes import router as meal_router

APP_VERSION = "0.1.0"

app = FastAPI(title="Haus", version=APP_VERSION)
app.add_middleware(SessionMiddleware, secret_key=get_settings().session_secret)
app.include_router(auth_router)
app.include_router(invitation_router)
app.include_router(inventory_router)
app.include_router(meal_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "haus", "version": APP_VERSION}


@app.get("/", tags=["system"])
def home() -> dict[str, str]:
    return {"service": "haus", "status": "running"}


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )