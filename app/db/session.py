from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.settings import settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={"connect_timeout": 10},
            echo=settings.sql_echo,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    return sessionmaker(bind=get_engine())


def get_session():
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
