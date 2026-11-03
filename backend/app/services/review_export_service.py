"""Serialización CSV del contrato aprobado para HU-19."""

from __future__ import annotations

import csv
import io
import unicodedata
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.review import Review


CSV_HEADERS = (
    "id",
    "contenido",
    "autor",
    "fecha",
    "fuente",
    "puntuacion",
    "categoria",
    "estado",
)
FORMULA_PREFIXES = frozenset("=+-@")


def _safe_text(value: str | None) -> str:
    """Marca posibles fórmulas solo en el valor exportado, conservando el original."""
    if value is None:
        return ""
    for character in value:
        if character.isspace() or unicodedata.category(character) in {"Cc", "Cf"}:
            continue
        if character in FORMULA_PREFIXES:
            return "'" + value
        break
    return value


def serialize_reviews_csv(reviews: Iterable[Review]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=",", quotechar='"', lineterminator="\r\n")
    writer.writerow(CSV_HEADERS)
    for review in reviews:
        writer.writerow(
            (
                review.id,
                _safe_text(review.contenido),
                _safe_text(review.autor),
                review.fecha.isoformat(),
                _safe_text(review.fuente),
                review.puntuacion,
                _safe_text(review.categoria),
                _safe_text(review.estado),
            )
        )
    return output.getvalue().encode("utf-8-sig")
