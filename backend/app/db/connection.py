from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def create_database_engine(database_url: str | URL) -> Engine:
    """Admite URLs de Render con Psycopg 3 y conserva el entorno local SQLite."""
    try:
        url = make_url(database_url)
    except (ArgumentError, ValueError):
        raise ValueError("DATABASE_URL no tiene un formato válido") from None

    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")

    engine_options: dict[str, object] = {"hide_parameters": True}
    if url.get_backend_name() == "sqlite":
        engine_options["connect_args"] = {"check_same_thread": False}
    elif url.get_backend_name() == "postgresql":
        # Comprueba conexiones reutilizadas después de reinicios del servidor.
        engine_options["pool_pre_ping"] = True

    database = create_engine(url, **engine_options)

    if url.get_backend_name() == "sqlite":
        @event.listens_for(database, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return database


engine = create_database_engine(settings.database_url)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Generador de sesión de base de datos para FastAPI Depends()."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
