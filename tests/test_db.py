from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, _engine_kwargs


def test_sqlite_metadata_can_initialize(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'haus.db'}"
    engine = create_engine(database_url, **_engine_kwargs(database_url))

    Base.metadata.create_all(engine)

    with sessionmaker(bind=engine)() as session:
        assert session.is_active