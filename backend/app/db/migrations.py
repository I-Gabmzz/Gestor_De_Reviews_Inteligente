"""Actualizaciones aditivas para bases creadas antes del análisis de IA."""

import re

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

def review_nullable_migration_needed(connection: Connection) -> bool:
    inspector = inspect(connection)
    if not inspector.has_table("reviews"):
        return False
    columns = {column["name"]: column for column in inspector.get_columns("reviews")}
    if not {"fecha", "puntuacion"} <= columns.keys():
        raise RuntimeError("El esquema de reviews no contiene las columnas esperadas")
    return any(not columns[name]["nullable"] for name in ("fecha", "puntuacion"))


def verify_sqlite_review_triggers(connection: Connection) -> None:
    """No reconstruir si no se puede descartar un orden de triggers ambiguo."""
    if connection.exec_driver_sql(
        "SELECT 1 FROM sqlite_temp_schema WHERE type='trigger' AND tbl_name='reviews' LIMIT 1"
    ).first():
        raise RuntimeError("Un trigger temporal de reviews requiere revisión manual")
    identifier = r'(?:"(?:[^"]|"")*"|`(?:[^`]|``)*`|\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_$]*)'
    header = re.compile(
        rf'^\s*CREATE\s+TRIGGER\s+(?:IF\s+NOT\s+EXISTS\s+)?'
        rf'(?:{identifier}\s*\.\s*)?{identifier}\s+'
        rf'(?:(BEFORE|AFTER)\s+)?(INSERT|DELETE|UPDATE)\b'
        rf'(?:\s+OF\s+{identifier}(?:\s*,\s*{identifier})*)?\s+ON\s+'
        rf'(?:"reviews"|`reviews`|\[reviews\]|reviews)(?=\s|$)',
        re.I,
    )
    seen: set[tuple[str, str]] = set()
    definitions = connection.exec_driver_sql(
        "SELECT sql FROM sqlite_schema WHERE type='trigger' AND tbl_name='reviews'"
    ).scalars()
    for definition in definitions:
        match = header.match(definition or "")
        if not match:
            raise RuntimeError("El trigger SQLite de reviews requiere revisión manual")
        key = ((match.group(1) or "BEFORE").upper(), match.group(2).upper())
        if key in seen:
            raise RuntimeError(
                f"Triggers SQLite ambiguos en reviews: {key[0]} {key[1]}; requiere revisión manual"
            )
        seen.add(key)


def _sqlite_nullable_ddl(ddl: str, missing: set[str]) -> str:
    """Transformar únicamente definiciones reconocibles; rechazar SQL ambiguo."""
    if not ddl or re.search(r"--|/\*|\*/|\bAUTOINCREMENT\b", ddl, re.I):
        raise RuntimeError("El esquema SQLite de reviews requiere revisión manual")
    match = re.match(r'(?is)^\s*CREATE\s+TABLE\s+(?:"reviews"|`reviews`|\[reviews\]|reviews)\s*\(', ddl)
    if not match:
        raise RuntimeError("El esquema SQLite de reviews requiere revisión manual")
    start = match.end()
    pieces = []
    depth = 0
    quote = None
    begin = start
    end = None
    i = start
    while i < len(ddl):
        c = ddl[i]
        if quote:
            if c == quote:
                if quote != "]" and i + 1 < len(ddl) and ddl[i + 1] == quote:
                    i += 1
                else:
                    quote = None
        elif c in ("'", '"', '`', '['):
            quote = ']' if c == '[' else c
        elif c == '(':
            depth += 1
        elif c == ')':
            if depth == 0:
                pieces.append(ddl[begin:i]); end = i; break
            depth -= 1
        elif c == ',' and depth == 0:
            pieces.append(ddl[begin:i]); begin = i + 1
        i += 1
    if end is None or quote or depth:
        raise RuntimeError("El esquema SQLite de reviews requiere revisión manual")
    for name in missing:
        dtype = 'DATETIME' if name == 'fecha' else 'INTEGER'
        pattern = re.compile(rf'(?is)^(\s*(?:"{name}"|`{name}`|\[{name}\]|{name})\s+{dtype}\s+)NOT\s+NULL\b')
        hits = [i for i, piece in enumerate(pieces) if pattern.match(piece)]
        if len(hits) != 1:
            raise RuntimeError("La nulabilidad de reviews requiere revisión manual")
        pieces[hits[0]] = pattern.sub(r'\1', pieces[hits[0]], count=1)
    return ddl[:start] + ','.join(pieces) + ddl[end:]


def migrate_review_nullable(connection: Connection, *, authorized: bool = False) -> None:
    """Relajar solo fecha/puntuación en la transacción del inicializador."""
    if not review_nullable_migration_needed(connection):
        return
    if authorized is not True:
        raise RuntimeError("La migración HU-24 requiere autorización explícita")
    columns = {c["name"]: c for c in inspect(connection).get_columns("reviews")}
    missing = {name for name in ("fecha", "puntuacion") if not columns[name]["nullable"]}
    # Un CHECK histórico podría seguir rechazando NULL incluso tras el ALTER.
    for check in inspect(connection).get_check_constraints("reviews"):
        expression = check.get("sqltext") or ""
        if any(re.search(rf"\b{name}\b", expression, re.I) for name in ("fecha", "puntuacion")):
            raise RuntimeError("La restricción de fecha o puntuación requiere revisión manual")
    if connection.dialect.name == "postgresql":
        for name in sorted(missing):
            connection.exec_driver_sql(f'ALTER TABLE reviews ALTER COLUMN "{name}" DROP NOT NULL')
        return
    if connection.dialect.name != "sqlite":
        raise RuntimeError("Motor no compatible con la migración de reviews")
    verify_sqlite_review_triggers(connection)
    if connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one():
        raise RuntimeError("La migración SQLite requiere desactivar FK antes de la transacción")
    try:
        violations = connection.exec_driver_sql("PRAGMA foreign_key_check").first()
    except SQLAlchemyError:
        raise RuntimeError("La base SQLite tiene relaciones inválidas antes de migrar") from None
    if violations is not None:
        raise RuntimeError("La base SQLite tiene relaciones inválidas antes de migrar")
    if connection.exec_driver_sql("SELECT 1 FROM sqlite_schema WHERE name = 'hu24_reviews_backup'").first():
        raise RuntimeError("La tabla temporal de migración ya existe")
    ddl = connection.exec_driver_sql("SELECT sql FROM sqlite_schema WHERE type='table' AND name='reviews'").scalar_one()
    updated = _sqlite_nullable_ddl(ddl, missing)
    objects = connection.exec_driver_sql("SELECT sql FROM sqlite_schema WHERE tbl_name='reviews' AND type IN ('index','trigger') AND sql IS NOT NULL ORDER BY type, name").scalars().all()
    names = [c["name"] for c in connection.exec_driver_sql('PRAGMA table_xinfo("reviews")').mappings()]
    hidden = [c for c in connection.exec_driver_sql('PRAGMA table_xinfo("reviews")').mappings() if c["hidden"]]
    if hidden:
        raise RuntimeError("Las columnas generadas de reviews requieren revisión manual")
    quoted = ', '.join(connection.dialect.identifier_preparer.quote_identifier(n) for n in names)
    # Copia sin reinterpretar el esquema; el original se recrea con sus restricciones.
    connection.exec_driver_sql(f'CREATE TABLE hu24_reviews_backup AS SELECT {quoted} FROM reviews')
    connection.exec_driver_sql('DROP TABLE reviews')
    connection.exec_driver_sql(updated)
    connection.exec_driver_sql(f'INSERT INTO reviews ({quoted}) SELECT {quoted} FROM hu24_reviews_backup')
    connection.exec_driver_sql('DROP TABLE hu24_reviews_backup')
    for sql in objects:
        connection.exec_driver_sql(sql)
    if connection.exec_driver_sql("PRAGMA foreign_key_check").first() is not None:
        raise RuntimeError("La migración SQLite dejó relaciones inválidas")
