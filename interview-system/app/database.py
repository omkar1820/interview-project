import logging
import time
from typing import Callable, TypeVar

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from .config import get_settings

log = logging.getLogger("db")
T = TypeVar("T")


class Base(DeclarativeBase):
    pass


def _make_engine():
    s = get_settings()
    url = s.sqlalchemy_url
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update(pool_size=10, max_overflow=20, pool_recycle=280)
        if s.db_ssl_ca:
            kwargs["connect_args"] = {"ssl": {"ca": s.db_ssl_ca}}
    return create_engine(url, **kwargs)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db


async def in_db(fn: Callable[[Session], T]) -> T:
    """Run a blocking DB unit of work in a worker thread (keeps the event loop free)."""

    def _run() -> T:
        with SessionLocal() as db:
            return fn(db)

    return await run_in_threadpool(_run)


def init_db(retries: int = 10, delay: float = 3.0) -> None:
    from . import models  # noqa: F401  (register tables)

    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except Exception as exc:  # RDS may still be warming up
            log.warning("DB not ready (%s/%s): %s", attempt, retries, exc)
            if attempt == retries:
                raise
            time.sleep(delay)


def db_ok() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
