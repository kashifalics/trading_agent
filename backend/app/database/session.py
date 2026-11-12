from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        memory = ":memory:" in url or url == "sqlite://"
        if memory:
            kwargs["poolclass"] = StaticPool
        eng = create_engine(url, **kwargs)
        if not memory:
            @event.listens_for(eng, "connect")
            def _sqlite_pragmas(dbapi_conn, _record):  # readers never block the writer (and vice versa); wait instead of failing
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA busy_timeout=10000")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.close()
        return eng
    return create_engine(url, pool_pre_ping=True)


def get_engine() -> Engine:
    global _engine, _factory
    if _engine is None:
        _engine = make_engine(get_settings().database_url)
        _factory = sessionmaker(_engine, expire_on_commit=False)
    return _engine


def set_engine(engine: Engine) -> None:
    """Used by tests to inject an in-memory engine."""
    global _engine, _factory
    _engine = engine
    _factory = sessionmaker(engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    get_engine()
    assert _factory is not None
    with _factory() as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    get_engine()
    assert _factory is not None
    with _factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
