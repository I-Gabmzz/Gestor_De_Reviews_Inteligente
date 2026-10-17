from sqlalchemy.engine import Engine

from app.db.base import Base
from app.db.connection import engine
from app.db.migrations import add_ai_result_columns


def init_db(target_engine: Engine | None = None) -> None:
    import app.models  # noqa: F401

    database = target_engine if target_engine is not None else engine
    with database.begin() as connection:
        # Evita que dos procesos intenten añadir la misma columna al iniciar.
        if database.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        elif database.dialect.name == "postgresql":
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(32513562)")
        Base.metadata.create_all(bind=connection)
        add_ai_result_columns(connection)
