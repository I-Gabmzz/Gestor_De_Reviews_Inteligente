"""Actualizaciones aditivas para bases creadas antes del análisis de IA."""

from sqlalchemy import Column, Integer, Text, inspect
from sqlalchemy.engine import Connection
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
