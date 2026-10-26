"""Actualizaciones aditivas para bases creadas antes del análisis de IA."""

from sqlalchemy import Column, Text, inspect
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


def add_solution_column(connection: Connection) -> None:
    """HU-17: ampliación aditiva e idempotente, sin reescribir resultados."""
    existing = {column["name"] for column in inspect(connection).get_columns("reviews")}
    if "solucion" not in existing:
        definition = CreateColumn(Column("solucion", Text, nullable=True)).compile(
            dialect=connection.dialect
        )
        connection.exec_driver_sql(f"ALTER TABLE reviews ADD COLUMN {definition}")
