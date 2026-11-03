from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.db.base import Base
from app.db.connection import engine
from app.db.external_import_schema import verify_external_import_schema
from app.db.migrations import (
    add_ai_result_columns, add_solution_column, add_suggested_response_columns,
    ensure_external_review_parent_index, verify_external_review_schema,
)


def init_db(target_engine: Engine | None = None) -> None:
    import app.models  # noqa: F401

    database = target_engine if target_engine is not None else engine
    with database.begin() as connection:
        # Evita que dos procesos intenten añadir la misma columna al iniciar.
        if database.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        elif database.dialect.name == "postgresql":
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(32513562)")
        if inspect(connection).has_table("external_review_import_attempts"):
            verify_external_import_schema(connection)
        ensure_external_review_parent_index(connection)
        Base.metadata.create_all(bind=connection)
        add_ai_result_columns(connection)
        add_solution_column(connection)
        add_suggested_response_columns(connection)
        verify_external_review_schema(connection)
        verify_external_import_schema(connection)
