"""Lazy SQLAlchemy engine so tests can point DATABASE_URL at a temporary file."""

from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.database.base import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def reset_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def get_engine() -> Engine:
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        connect_args: dict = {}
        if settings.is_sqlite:
            connect_args["check_same_thread"] = False
        _engine = create_engine(
            settings.database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            future=True,
        )
        if settings.is_sqlite:
            @event.listens_for(_engine, "connect")
            def _sqlite_fk(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    settings = get_settings()
    settings.data_path.mkdir(parents=True, exist_ok=True)
    (settings.data_path / "reports").mkdir(parents=True, exist_ok=True)
    (settings.data_path / "uploads").mkdir(parents=True, exist_ok=True)
    # Import models so metadata is populated.
    import app.models.entities  # noqa: F401

    if settings.auto_create_tables:
        Base.metadata.create_all(bind=get_engine())


def check_db() -> bool:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
