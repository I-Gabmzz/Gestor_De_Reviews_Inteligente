"""HU-24/T6: recorrido HTTP con una base SQLite temporal y dos tenants sintéticos."""
import csv
import io

from app.core.security import get_password_hash
from app.models import Review, Tenant, User
from test_hu24_t4_import_export import make_file


def test_hu24_http_journey_two_tenants(client, seed_users):
    http, sessions = client
    with sessions() as db:
        db.add(Tenant(id=20, nombre='Tenant sintético B', estado='activo'))
        db.add(User(tenant_id=20, nombre='B', correo='hu24-b@example.com',
                    password_hash=get_password_hash('secret123'), rol='usuario_negocio', estado='activo'))
        db.commit()

    def login(email):
        response = http.post('/api/v1/auth/login', json={'correo': email, 'password': 'secret123'})
        assert response.status_code == 200
        return {'Authorization': 'Bearer ' + response.json()['access_token']}

    a, b = login('usuario@example.com'), login('hu24-b@example.com')
    minimal = http.post('/api/v1/reviews', headers=a, json={'contenido': 'Manual sin opcionales'})
    assert minimal.status_code == 201
    first = minimal.json()
    assert (first['autor'], first['fecha'], first['puntuacion'], first['tenant_id']) == (None, None, None, 10)
    complete = http.post('/api/v1/reviews', headers=a, json={
        'contenido': 'Manual completa', 'autor': 'Ana', 'fecha': '2026-01-02T12:00:00', 'puntuacion': 5,
    })
    assert complete.status_code == 201 and complete.json()['puntuacion'] == 5
    for payload in ({'contenido': '   '}, {'contenido': 'inválida', 'puntuacion': 0},
                    {'contenido': 'inválida', 'puntuacion': 3.5}):
        assert http.post('/api/v1/reviews', headers=a, json=payload).status_code == 422
    edited = http.patch(f"/api/v1/reviews/{first['id']}", headers=a, json={'contenido': 'Manual editada'})
    assert edited.status_code == 200
    assert (edited.json()['autor'], edited.json()['fecha'], edited.json()['puntuacion']) == (None, None, None)

    ids = {first['id'], complete.json()['id']}
    for ext in ('csv', 'xlsx'):
        content = make_file(ext, [{'contenido': f'Importada {ext}', 'fecha': '', 'puntuacion': '', 'tenant_id': 20}])
        response = http.post('/api/v1/reviews/import', headers=a, files={'file': (f'test.{ext}', content)})
        assert response.status_code == 200 and response.json()['filas_guardadas'] == 1
        invalid = make_file(ext, [{'contenido': f'No guardar {ext}', 'fecha': '', 'puntuacion': ''},
                                  {'contenido': 'Inválida', 'fecha': '', 'puntuacion': 6}])
        response = http.post('/api/v1/reviews/import', headers=a, files={'file': (f'bad.{ext}', invalid)})
        assert response.status_code == 200 and not response.json()['es_valido'] and response.json()['filas_guardadas'] == 0

    other = http.post('/api/v1/reviews', headers=b, json={'contenido': 'Manual editada'})
    assert other.status_code == 201
    assert http.get(f"/api/v1/reviews/{first['id']}", headers=b).status_code == 404
    assert http.patch(f"/api/v1/reviews/{first['id']}", headers=b, json={'contenido': 'Ajena'}).status_code == 404
    listing = http.get('/api/v1/reviews', headers=a).json()['items']
    assert len(listing) == 4 and ids.issubset({item['id'] for item in listing})
    assert all(not item['contenido'].startswith('No guardar') for item in listing)
    assert all(item['tenant_id'] == 10 for item in listing)
    exported = http.get('/api/v1/reviews/export', headers=a)
    assert exported.status_code == 200 and exported.content.startswith(b'\xef\xbb\xbf')
    rows = list(csv.reader(io.StringIO(exported.content.decode('utf-8-sig'), newline='')))
    assert rows[0] == ['id', 'contenido', 'autor', 'fecha', 'fuente', 'puntuacion', 'categoria', 'estado']
    assert [int(row[0]) for row in rows[1:]] == [item['id'] for item in listing]
    for row in rows[1:]:
        if row[1] != 'Manual completa':
            assert row[2] == row[3] == row[5] == ''
    other_listing = http.get('/api/v1/reviews', headers=b).json()['items']
    other_csv = http.get('/api/v1/reviews/export', headers=b)
    other_rows = list(csv.reader(io.StringIO(other_csv.content.decode('utf-8-sig'), newline='')))
    assert other_csv.status_code == 200
    assert [int(row[0]) for row in other_rows[1:]] == [other.json()['id']] == [item['id'] for item in other_listing]
    with sessions() as db:
        saved = db.get(Review, first['id'])
        assert (saved.autor, saved.fecha, saved.puntuacion, saved.tenant_id) == (None, None, None, 10)
