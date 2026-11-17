import csv
import io
from datetime import datetime

import pytest

from app.models.review import Review
from app.services.review_export_service import CSV_HEADERS, serialize_reviews_csv


@pytest.mark.parametrize(
    ("fecha", "puntuacion", "fecha_csv", "puntuacion_csv"),
    [
        (None, None, "", ""),
        (None, 4, "", "4"),
        (datetime(2026, 11, 16, 9, 30), None, "2026-11-16T09:30:00", ""),
        (datetime(2026, 11, 16, 9, 30), 4, "2026-11-16T09:30:00", "4"),
    ],
)
def test_csv_conserva_reseñas_con_campos_opcionales(fecha, puntuacion, fecha_csv, puntuacion_csv):
    review = Review(
        id=101,
        tenant_id=10,
        contenido="Prueba de campos opcionales",
        fecha=fecha,
        puntuacion=puntuacion,
        fuente="manual",
        estado="nueva",
    )

    result = serialize_reviews_csv([review])

    assert result.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(result.decode("utf-8-sig"), newline="")))
    assert rows == [
        list(CSV_HEADERS),
        ["101", review.contenido, "", fecha_csv, "manual", puntuacion_csv, "", "nueva"],
    ]
