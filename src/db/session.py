from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from src.config import load_config


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    cfg = load_config()
    engine = create_engine(cfg.database_url, future=True, pool_pre_ping=True)
    # SQLite silently ignores FK constraints unless PRAGMA is set per-connection.
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _enable_sqlite_fks(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    return engine


@lru_cache(maxsize=1)
def _session_factory():
    return sessionmaker(bind=get_engine(), future=True, expire_on_commit=False)


def get_session():
    return _session_factory()()
