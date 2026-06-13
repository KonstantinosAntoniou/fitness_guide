from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings


class Base(DeclarativeBase):
    pass


def new_engine(url: str | None = None) -> Engine:
    url = url or settings.database_url
    if not url.startswith("sqlite"):
        return create_engine(url)
    connect_args = {"check_same_thread": False}
    # In-memory SQLite must share ONE connection across threads, otherwise each
    # thread (e.g. FastAPI's sync-endpoint threadpool) gets a separate empty DB.
    if url in ("sqlite://", "sqlite:///:memory:"):
        return create_engine(url, connect_args=connect_args, poolclass=StaticPool)
    return create_engine(url, connect_args=connect_args)


def new_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


engine = new_engine()
SessionLocal = new_session_factory(engine)


def init_db() -> None:
    import app.models  # noqa: F401  (register mappers)
    Base.metadata.create_all(engine)


def get_session():
    """FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
