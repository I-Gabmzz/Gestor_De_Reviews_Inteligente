from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.db.base import Base
from app.db.connection import engine
from app.core.config import settings
from app.db.external_import_schema import verify_external_import_schema
from app.db.migrations import (
    add_ai_result_columns, add_solution_column, add_suggested_response_columns,
    ensure_external_review_parent_index, verify_external_review_schema,
    migrate_review_nullable, review_nullable_migration_needed,
    verify_sqlite_review_triggers,
)


def init_db(
    target_engine: Engine | None = None,
    *,
    allow_review_nullable_migration: bool | None = None,
) -> None:
    import app.models  # noqa: F401

    database = target_engine if target_engine is not None else engine
    authorized = (
        settings.hu24_allow_review_nullable_migration
        if allow_review_nullable_migration is None
        else allow_review_nullable_migration is True
    )
    with database.connect() as connection:
        sqlite = database.dialect.name == "sqlite"
        fk_enabled = False
        if sqlite:
            fk_enabled = bool(connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one())
            needs_rebuild = review_nullable_migration_needed(connection)
            connection.commit()
            if needs_rebuild and fk_enabled and authorized:
                # Fuera de una transacción, para evitar cascadas al sustituir reviews.
                connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
                connection.commit()
        try:
            with connection.begin():
                if sqlite:
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                elif database.dialect.name == "postgresql":
                    connection.exec_driver_sql("SELECT pg_advisory_xact_lock(32513562)")
                # Bajo el bloqueo y antes de cualquier DDL, también en PostgreSQL.
                if review_nullable_migration_needed(connection) and not authorized:
                    raise RuntimeError(
                        "La migración HU-24 requiere autorización explícita: "
                        "HU24_ALLOW_REVIEW_NULLABLE_MIGRATION=true"
                    )
                if sqlite and review_nullable_migration_needed(connection):
                    verify_sqlite_review_triggers(connection)
                if inspect(connection).has_table("external_review_import_attempts"):
                    verify_external_import_schema(connection)
                ensure_external_review_parent_index(connection)
                Base.metadata.create_all(bind=connection)
                add_ai_result_columns(connection)
                add_solution_column(connection)
                add_suggested_response_columns(connection)
                migrate_review_nullable(connection, authorized=authorized)
                verify_external_review_schema(connection)
                verify_external_import_schema(connection)
        finally:
            if sqlite and fk_enabled:
                if connection.in_transaction():
                    connection.rollback()
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()
