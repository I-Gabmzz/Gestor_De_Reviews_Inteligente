"""Contrato HU-23/T2: mismos criterios e IDs para listado y CSV."""

import csv
import io
from datetime import datetime

import pytest

from app.core.security import create_access_token
from app.models.review import Review
from app.models.tenant import Tenant
from app.models.user import User


LIST_URL = "/api/v1/reviews"
EXPORT_URL = f"{LIST_URL}/export"
CSV_HEADER = ["id", "contenido", "autor", "fecha", "fuente", "puntuacion", "categoria", "estado"]


def auth(subject=1, tenant=10, role="usuario_negocio"):
    token = create_access_token(subject=str(subject), rol=role, tenant_id=tenant)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def hu23_reviews(client, seed_users):
    # Matriz T1 adaptada al esquema actual: fechas/puntuaciones presentes.
    # 101 coincide por contenido y tema; 104/106 empatan en fecha y tienen
    # caracteres LIKE literales en el contenido. 106 está pendiente pero
    # no es urgente porque su prioridad es NULL.
    records = [
        (101, 10, "Ana", "Entrega puntual del envío", "Envío", 9, 5, "Alta", "nueva", "Google"),
        (102, 10, "Bruno", "Servicio lento", "Atención", 8, 3, "Alta", "en_revision", "manual"),
        (103, 10, "Carla", "Gracias", "Envío", 7, 4, "Alta", "atendida", "Google"),
        (104, 10, None, "Empaque del envío 100%", None, 6, 2, "Media", "nueva", "CSV"),
        (105, 10, "Ana", "Consulta loteXA", "Atención", 4, 2, "Baja", "en_revision", "manual"),
        (106, 10, "Eva", "Demora en atención lote_A", None, 6, 1, None, "nueva", "Google"),
        (201, 20, "Ana", "Entrega puntual del envío", "Envío", 9, 4, "Alta", "nueva", "Google"),
        (202, 20, None, "Atención lenta loteXA", None, 8, 3, "Alta", "en_revision", "manual"),
        (203, 20, "Luis", "Revisión", "Atención", 7, 2, "Media", "atendida", "CSV"),
    ]
    with client[1]() as db:
        db.add(Tenant(id=20, nombre="Negocio B ficticio", estado="activo"))
        db.flush()
        db.add(User(
            id=20, tenant_id=20, nombre="Operador B ficticio", correo="hu23-b@example.com",
            password_hash="no-se-usa-login-en-esta-prueba", rol="usuario_negocio", estado="activo",
        ))
        db.add_all(
            Review(
                id=rid, tenant_id=tenant, autor=author, contenido=content, tema=topic,
                fecha=datetime(2026, 11, day), puntuacion=score, prioridad=priority,
                estado=state, fuente=source,
            )
            for rid, tenant, author, content, topic, day, score, priority, state, source in records
        )
        db.commit()


def assert_list_and_csv(client, headers, params, expected_ids):
    listed = client.get(LIST_URL, params=params, headers=headers)
    exported = client.get(EXPORT_URL, params=params, headers=headers)
    assert listed.status_code == exported.status_code == 200
    assert listed.json()["total"] == len(expected_ids)
    assert [row["id"] for row in listed.json()["items"]] == expected_ids
    assert exported.headers["content-type"] == "text/csv; charset=utf-8"
    assert exported.headers["content-disposition"].startswith('attachment; filename="reviews_')
    header_bytes = ("\ufeff" + ",".join(CSV_HEADER) + "\r\n").encode()
    assert exported.content.startswith(header_bytes)
    header, *rows = csv.reader(io.StringIO(exported.content.decode("utf-8-sig"), newline=""))
    assert header == CSV_HEADER
    assert all(len(row) == len(CSV_HEADER) for row in rows)
    assert [int(row[0]) for row in rows] == expected_ids
    if not expected_ids:
        assert exported.content == header_bytes


@pytest.mark.parametrize(("params", "ids"), [
    ({}, [101, 102, 103, 106, 104, 105]),
    ({"busqueda": "ENTREGA PUNTUAL"}, [101]),
    ({"busqueda": "  bRuNo  "}, [102]),
    ({"busqueda": "envío"}, [101, 103, 104]),
    ({"busqueda": "Atención"}, [102, 106, 105]),
    ({"busqueda": "%"}, [104]),
    ({"busqueda": "lote_"}, [106]),
    ({"busqueda": ""}, [101, 102, 103, 106, 104, 105]),
    ({"busqueda": "   "}, [101, 102, 103, 106, 104, 105]),
    ({"busqueda": "inexistente"}, []),
    ({"busqueda": "' OR 1=1 --"}, []),
    ({"urgente": "true"}, [101, 102]),
    ({"urgente": "false"}, [101, 102, 103, 106, 104, 105]),
    ({"urgente": "false", "estado": "atendida"}, [103]),
    ({"urgente": "true", "estado": "nueva"}, [101]),
    ({"urgente": "true", "estado": "en_revision"}, [102]),
    ({"urgente": "true", "estado": "atendida"}, []),
    ({"urgente": "true", "puntuacion": 3}, [102]),
    ({"urgente": "true", "fuente": "Google"}, [101]),
    ({"urgente": "true", "busqueda": "envío"}, [101]),
    ({"urgente": "true", "busqueda": "Atención", "fecha_hasta": "2026-11-08"}, [102]),
])
def test_hu23_shared_filters_keep_list_count_order_and_csv(client, hu23_reviews, params, ids):
    assert_list_and_csv(client[0], auth(), params, ids)


@pytest.mark.parametrize("value", ["", "1", "0", "TRUE", "yes", " true ", "urgente"])
def test_hu23_urgent_literals_validated_by_both_routes(client, seed_users, value):
    responses = [client[0].get(url, params={"urgente": value}, headers=auth())
                 for url in (LIST_URL, EXPORT_URL)]
    assert all(response.status_code == 422 for response in responses)
    assert all(response.json()["detail"][0]["loc"] == ["query", "urgente"] for response in responses)


@pytest.mark.parametrize(("subject", "tenant", "foreign_tenant", "ids"), [
    (1, 10, 20, [101, 102]),
    (20, 20, 10, [201, 202]),
])
def test_hu23_tenant_query_cannot_override_authenticated_scope(
    client, hu23_reviews, subject, tenant, foreign_tenant, ids,
):
    assert_list_and_csv(client[0], auth(subject, tenant), {
        "urgente": "true", "tenant_id": foreign_tenant,
    }, ids)


def test_hu23_search_does_not_mix_lookalike_tenants(client, hu23_reviews):
    params = {"busqueda": "Ana", "urgente": "true"}
    assert_list_and_csv(client[0], auth(), params, [101])
    assert_list_and_csv(client[0], auth(20, 20), params, [201])


def test_hu23_new_filters_preserve_access_control(client, hu23_reviews):
    params = {"urgente": "true", "busqueda": "envío"}
    for url in (LIST_URL, EXPORT_URL):
        assert client[0].get(url, params=params).status_code == 401
        assert client[0].get(url, params=params, headers=auth(3, None, "admin_general")).status_code == 403
    assert_list_and_csv(client[0], auth(2, 10, "admin_tenant"), params, [101])
