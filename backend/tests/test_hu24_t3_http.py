"""Pruebas HTTP de T3 con usuarios y bases sintéticos del fixture común."""
from datetime import datetime

import pytest
from app.models import Review
from app.models.tenant import Tenant


def login(client, correo='usuario@example.com'):
    response = client.post('/api/v1/auth/login', json={'correo': correo, 'password': 'secret123'})
    assert response.status_code == 200
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


@pytest.mark.parametrize('correo', ['usuario@example.com', 'tenant@example.com'])
def test_http_create_read_edit_and_clear(client, seed_users, correo):
    http, sessions = client
    headers = login(http, correo)
    created = http.post('/api/v1/reviews', headers=headers, json={'contenido': 'Buena atención'})
    assert created.status_code == 201
    body = created.json()
    assert (body['autor'], body['fecha'], body['puntuacion'], body['fuente'], body['estado'], body['tenant_id']) == (None, None, None, 'manual', 'nueva', 10)
    review_id = body['id']
    assert http.get(f'/api/v1/reviews/{review_id}', headers=headers).json()['fecha'] is None
    changed = http.patch(f'/api/v1/reviews/{review_id}', headers=headers, json={'autor': 'Ana', 'fecha': '2026-09-24T10:30:00', 'puntuacion': 5})
    assert changed.status_code == 200
    assert changed.json()['fuente'] == 'manual' and changed.json()['estado'] == 'nueva'
    changed = http.patch(f'/api/v1/reviews/{review_id}', headers=headers, json={'fecha': None, 'puntuacion': None})
    assert changed.status_code == 200
    assert (changed.json()['autor'], changed.json()['fecha'], changed.json()['puntuacion']) == ('Ana', None, None)
    with sessions() as db:
        saved = db.get(Review, review_id)
        assert (saved.fecha, saved.puntuacion, saved.tenant_id) == (None, None, 10)


@pytest.mark.parametrize('payload', [
    {'contenido': ''}, {'contenido': '   '}, {'contenido': 'Bien', 'puntuacion': 0},
    {'contenido': 'Bien', 'puntuacion': 6}, {'contenido': 'Bien', 'tenant_id': 20},
    {'contenido': 'Bien', 'resumen': 'resultado IA'},
])
def test_http_invalid_create_rejected(client, seed_users, payload):
    http, _ = client
    assert http.post('/api/v1/reviews', headers=login(http), json=payload).status_code == 422


def test_http_roles_and_other_tenant_denied(client, seed_users):
    http, sessions = client
    with sessions() as db:
        db.add(Tenant(id=20, nombre='Otro', estado='activo'))
        db.add(Review(id=201, tenant_id=20, contenido='Ajena', fecha=datetime(2026, 1, 1), fuente='Google', puntuacion=5, estado='atendida'))
        db.commit()
    assert http.post('/api/v1/reviews', json={'contenido': 'Sin sesión'}).status_code == 401
    assert http.post('/api/v1/reviews', headers=login(http, 'general@example.com'), json={'contenido': 'Sin tenant'}).status_code == 403
    headers = login(http)
    assert http.get('/api/v1/reviews/201', headers=headers).status_code == 404
    assert http.patch('/api/v1/reviews/201', headers=headers, json={'fecha': None}).status_code == 404
