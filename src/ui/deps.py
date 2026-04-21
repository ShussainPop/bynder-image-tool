from contextlib import contextmanager
from typing import Any

from src.config import Config
from src.db.session import get_session


def build_supabase_client(cfg: Config) -> Any | None:
    """Return a supabase client when URL + service key are configured, else None."""
    if not (cfg.supabase_url and cfg.supabase_service_key):
        return None
    try:
        from supabase import create_client
        return create_client(cfg.supabase_url, cfg.supabase_service_key)
    except Exception:
        return None


@contextmanager
def session_scope():
    """Yield a SQLAlchemy session, closing it after render() completes.

    Streamlit reruns render() on every widget interaction; without this,
    each rerun leaks a Session into the connection pool.
    """
    session = get_session()
    try:
        yield session
    finally:
        session.close()
