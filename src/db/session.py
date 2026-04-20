from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import load_config


@lru_cache(maxsize=1)
def get_engine():
    cfg = load_config()
    return create_engine(cfg.database_url, future=True, pool_pre_ping=True)


@lru_cache(maxsize=1)
def _session_factory():
    return sessionmaker(bind=get_engine(), future=True, expire_on_commit=False)


def get_session():
    return _session_factory()()
