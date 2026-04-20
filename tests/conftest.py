import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db_engine():
    """SQLite in-memory engine for unit tests.
    Production uses Postgres; SQLite is fine for model-level unit tests."""
    engine = create_engine("sqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _fk_pragma_on_connect(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    from src.db.models import Base
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
