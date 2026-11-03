"""Actualizaciones aditivas para bases creadas antes del análisis de IA."""

from sqlalchemy import Column, Index, Integer, MetaData, Table, Text, inspect
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import CreateColumn


def add_ai_result_columns(connection: Connection) -> None:
    """Añade solo columnas ausentes; conserva filas, índices y campos previos.

    init_db serializa la inspección y el DDL en una misma transacción.
    Las definiciones se mantienen explícitas para no alterar esta migración
    al modificar el modelo en una historia posterior.
    """
    existing = {column["name"] for column in inspect(connection).get_columns("reviews")}
    for name in ("resumen", "tema"):
        if name not in existing:
            definition = CreateColumn(Column(name, Text, nullable=True)).compile(
                dialect=connection.dialect
            )
            connection.exec_driver_sql(f"ALTER TABLE reviews ADD COLUMN {definition}")


def add_solution_column(connection: Connection) -> None:
    """HU-17: ampliación aditiva e idempotente, sin reescribir resultados."""
    existing = {column["name"] for column in inspect(connection).get_columns("reviews")}
    if "solucion" not in existing:
        definition = CreateColumn(Column("solucion", Text, nullable=True)).compile(
            dialect=connection.dialect
        )
        connection.exec_driver_sql(f"ALTER TABLE reviews ADD COLUMN {definition}")


def add_suggested_response_columns(connection: Connection) -> None:
    """Evolución aditiva HU-18; el contador es interno, sin historial de textos."""
    existing = {column["name"] for column in inspect(connection).get_columns("reviews")}
    columns = (
        Column("respuesta_sugerida", Text, nullable=True),
        Column("respuesta_sugerida_version", Integer, nullable=False, server_default="0"),
    )
    for column in columns:
        if column.name not in existing:
            definition = CreateColumn(column).compile(dialect=connection.dialect)
            connection.exec_driver_sql(f"ALTER TABLE reviews ADD COLUMN {definition}")



def _external_parent_keys(connection: Connection) -> list[dict]:
    """SQLite omite índices de expresiones en Inspector: inspeccionar PRAGMA."""
    if connection.dialect.name == "sqlite":
        indexes = []
        for index in connection.exec_driver_sql('PRAGMA index_list("reviews")').mappings():
            quoted = connection.dialect.identifier_preparer.quote_identifier(index["name"])
            columns = connection.exec_driver_sql(f"PRAGMA index_xinfo({quoted})").mappings()
            keys = sorted((column for column in columns if column["key"]), key=lambda column: column["seqno"])
            indexes.append({
                "name": index["name"], "unique": bool(index["unique"]),
                "column_names": [column["name"] if column["cid"] >= 0 else None for column in keys],
                "dialect_options": {"sqlite_where": True if index["partial"] else None},
            })
        return indexes
    inspector = inspect(connection)
    return inspector.get_indexes("reviews") + [
        {**constraint, "unique": True} for constraint in inspector.get_unique_constraints("reviews")
    ]


def _is_complete_parent_key(index: dict) -> bool:
    options = index.get("dialect_options") or {}
    return (
        bool(index.get("unique"))
        # La unicidad completa respalda la FK también con el orden invertido.
        and index.get("column_names") in (["id", "tenant_id"], ["tenant_id", "id"])
        and not index.get("expressions")
        and not index.get("include_columns")
        and not options.get("postgresql_include")
        and not options.get("postgresql_ops")
        and options.get("postgresql_using", "btree") == "btree"
        and all(value is None or value is False for key, value in options.items() if key.endswith("_where"))
    )


def ensure_external_review_parent_index(connection: Connection) -> None:
    """Aceptar claves completas; no reparar ni borrar índices incompatibles."""
    if not inspect(connection).has_table("reviews"):
        return
    indexes = _external_parent_keys(connection)
    reserved = [index for index in indexes if index["name"] == "uq_reviews_id_tenant"]
    if any(not _is_complete_parent_key(index) for index in reserved):
        raise RuntimeError("El índice de identidad externa tiene una definición incompatible")
    if any(_is_complete_parent_key(index) for index in indexes):
        return
    # Definición congelada de esta migración, independiente de futuros modelos.
    parent = Table("reviews", MetaData(), Column("id", Integer), Column("tenant_id", Integer))
    Index("uq_reviews_id_tenant", parent.c.id, parent.c.tenant_id, unique=True).create(connection)


def verify_external_review_schema(connection: Connection) -> None:
    """No aceptar silenciosamente tablas parciales con integridad degradada."""
    inspector = inspect(connection)
    expected_columns = {
        "external_review_connections": {"tenant_id", "source", "business_data_id", "persistence_enabled", "approval_reference"},
        "external_review_identities": {"review_id", "tenant_id", "source", "business_data_id", "external_review_id", "import_fingerprint"},
    }
    for table, required in expected_columns.items():
        columns = {column["name"]: column for column in inspector.get_columns(table)}
        if not required <= columns.keys() or any(
            columns[name]["nullable"] for name in required - {"approval_reference"}
        ):
            raise RuntimeError("El esquema externo está incompleto o es incompatible")
    if inspector.get_pk_constraint("external_review_connections")["constrained_columns"] != ["tenant_id", "source", "business_data_id"]:
        raise RuntimeError("La clave de conexión externa no es compatible")
    if inspector.get_pk_constraint("external_review_identities")["constrained_columns"] != ["review_id"]:
        raise RuntimeError("La clave de identidad externa no es compatible")
    connection_fk = inspector.get_foreign_keys("external_review_connections")
    if not any(item["constrained_columns"] == ["tenant_id"] and item["referred_table"] == "tenants" and item["referred_columns"] == ["id"] for item in connection_fk):
        raise RuntimeError("Falta la relación de conexión con el tenant")
    for table, names in {
        "external_review_connections": {"ck_external_connection_source", "ck_external_connection_business", "ck_external_connection_approval"},
        "external_review_identities": {"ck_external_identity_id_length", "ck_external_identity_fingerprint"},
    }.items():
        if not names <= {item["name"] for item in inspector.get_check_constraints(table)}:
            raise RuntimeError("Faltan restricciones del esquema externo")
    unique = inspector.get_unique_constraints("external_review_identities")
    if not any(item["column_names"] == ["tenant_id", "source", "business_data_id", "external_review_id"] for item in unique):
        raise RuntimeError("Falta la unicidad de identidad externa")
    foreign = inspector.get_foreign_keys("external_review_identities")
    expected_fk = {
        (("review_id", "tenant_id"), "reviews", ("id", "tenant_id")),
        (("tenant_id", "source", "business_data_id"), "external_review_connections", ("tenant_id", "source", "business_data_id")),
    }
    actual_fk = {(tuple(item["constrained_columns"]), item["referred_table"], tuple(item["referred_columns"])) for item in foreign}
    if not expected_fk <= actual_fk:
        raise RuntimeError("Faltan relaciones de integridad externa")
    if connection.dialect.name == "sqlite":
        # Sólo devuelve un booleano: no registrar IDs de filas históricas. SQLite
        # valida también que las colaciones del índice padre respalden la FK.
        valid = False
        try:
            valid = bool(connection.exec_driver_sql(
                "SELECT NOT EXISTS (SELECT 1 FROM pragma_foreign_key_check('external_review_identities'))"
            ).scalar_one())
        except SQLAlchemyError:
            pass
        if not valid:
            raise RuntimeError("La relación externa no tiene integridad referencial compatible")
