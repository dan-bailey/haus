from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


def _ensure_sqlite_parent(database_url: str) -> None:
    if database_url.startswith("sqlite:///") and not database_url.endswith(":memory:"):
        Path(database_url.removeprefix("sqlite:///" )).parent.mkdir(
            parents=True, exist_ok=True
        )


database_url = get_settings().database_url
_ensure_sqlite_parent(database_url)
engine = create_engine(database_url, **_engine_kwargs(database_url))
def configure_sqlite(connection) -> None:
    connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    connection.exec_driver_sql("PRAGMA journal_mode=WAL")
if engine.dialect.name == "sqlite":
    from sqlalchemy import event

    event.listen(engine, "connect", configure_sqlite)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session