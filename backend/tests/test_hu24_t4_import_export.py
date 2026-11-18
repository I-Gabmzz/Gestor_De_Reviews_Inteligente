"""Contratos T4 usando solo SQLite temporal y datos sintéticos."""
import csv
import io
from datetime import date, datetime

import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routers.reviews import export_reviews, list_reviews
from app.core.security import get_password_hash
from app.db.init_db import init_db
from app.models import Review
from app.models.tenant import Tenant
from app.models.user import User
from app.services.import_service import process_and_store_import
from app.services.review_export_service import serialize_reviews_csv


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'synthetic.db'}")
    init_db(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.add_all([Tenant(id=10, nombre='A', estado='activo'), Tenant(id=20, nombre='B', estado='activo')])
        session.commit()
        yield session
    engine.dispose()


def make_file(extension, rows, headers=None):
    headers = headers or ['contenido', 'autor', 'fecha', 'puntuacion', 'fuente', 'tenant_id']
    if extension == 'csv':
        output = io.StringIO(newline='')
        writer = csv.DictWriter(output, fieldnames=headers, lineterminator='\r\n')
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue().encode('utf-8-sig')
    output = io.BytesIO()
    workbook = Workbook()
    workbook.active.append(headers)
    for row in rows:
        workbook.active.append([row.get(header) for header in headers])
    workbook.save(output)
    workbook.close()
    return output.getvalue()


@pytest.mark.parametrize('extension', ['csv', 'xlsx'])
def test_optional_fields_historical_values_sources_and_tenant(db, extension):
    rows = [
        {'contenido': 'Niño, "excelente"\nservicio', 'autor': 'Ana', 'fecha': '2026-09-24', 'puntuacion': 5, 'fuente': ' Google ', 'tenant_id': 20},
        {'contenido': 'Sin fecha', 'autor': ' ', 'fecha': '', 'puntuacion': 4, 'fuente': '', 'tenant_id': 20},
        {'contenido': 'Sin puntuación', 'autor': None, 'fecha': '2026-09-25', 'puntuacion': None, 'fuente': 'Facebook', 'tenant_id': 20},
        {'contenido': 'Sin ambos', 'autor': None, 'fecha': None, 'puntuacion': None, 'fuente': None, 'tenant_id': 20},
    ]
    result = process_and_store_import(make_file(extension, rows), f'synthetic.{extension}', 10, db)
    assert result['es_valido'] and result['filas_guardadas'] == 4
    reviews = {r.contenido: r for r in db.scalars(select(Review)).all()}
    assert (reviews[rows[0]['contenido']].autor, reviews[rows[0]['contenido']].fecha, reviews[rows[0]['contenido']].puntuacion, reviews[rows[0]['contenido']].fuente) == ('Ana', datetime(2026, 9, 24), 5, 'Google')
    assert (reviews['Sin fecha'].autor, reviews['Sin fecha'].fecha, reviews['Sin fecha'].puntuacion, reviews['Sin fecha'].fuente) == (None, None, 4, 'CSV' if extension == 'csv' else 'Excel')
    assert reviews['Sin puntuación'].puntuacion is None and reviews['Sin puntuación'].fuente == 'Facebook'
    assert reviews['Sin ambos'].fecha is None and reviews['Sin ambos'].puntuacion is None and reviews['Sin ambos'].autor is None
    assert {r.tenant_id for r in reviews.values()} == {10}


@pytest.mark.parametrize('extension', ['csv', 'xlsx'])
@pytest.mark.parametrize('invalid', [
    {'contenido': '  ', 'fecha': '', 'puntuacion': ''},
    {'contenido': 'Inválida', 'fecha': '', 'puntuacion': 0},
    {'contenido': 'Inválida', 'fecha': '', 'puntuacion': 6},
    {'contenido': 'Inválida', 'fecha': 'fecha inválida', 'puntuacion': ''},
    {'contenido': 'Inválida', 'fecha': '', 'puntuacion': 1.5},
    {'contenido': 'Inválida', 'fecha': '', 'puntuacion': '1.0000000000000001'},
    {'contenido': 'Inválida', 'fecha': '', 'puntuacion': '5.0000000000000001'},
])
def test_invalid_row_preserves_atomic_import(db, extension, invalid):
    rows = [{'contenido': 'Válida', 'fecha': '', 'puntuacion': ''}, invalid]
    result = process_and_store_import(make_file(extension, rows), f'example.{extension}', 10, db)
    assert not result['es_valido'] and result['filas_guardadas'] == 0
    assert result['filas_validas'] == 1 and result['errores_por_fila']
    assert db.scalars(select(Review)).all() == []


@pytest.mark.parametrize('extension', ['csv', 'xlsx'])
@pytest.mark.parametrize('missing', ['fecha', 'puntuacion', 'contenido'])
def test_required_headers_remain_required(db, extension, missing):
    headers = [h for h in ['contenido', 'fecha', 'puntuacion'] if h != missing]
    row = {h: ('Bien' if h == 'contenido' else '2026-01-01' if h == 'fecha' else 5) for h in headers}
    result = process_and_store_import(make_file(extension, [row], headers), f'example.{extension}', 10, db)
    assert not result['es_valido'] and result['filas_guardadas'] == 0
    assert missing in ' '.join(result['errores_globales'])


@pytest.mark.parametrize('extension', ['csv', 'xlsx'])
def test_missing_author_column_and_optional_blank_cells(db, extension):
    headers = ['contenido', 'fecha', 'puntuacion']
    data = make_file(extension, [{'contenido': 'Sin autor', 'fecha': '  ', 'puntuacion': '  '}], headers)
    result = process_and_store_import(data, f'test.{extension}', 10, db)
    assert result['es_valido'] and result['filas_guardadas'] == 1
    review = db.scalar(select(Review))
    assert (review.autor, review.fecha, review.puntuacion) == (None, None, None)


def test_boolean_xlsx_rating_is_invalid(db):
    data = make_file('xlsx', [{'contenido': 'Inválida', 'fecha': '', 'puntuacion': True}])
    result = process_and_store_import(data, 'test.xlsx', 10, db)
    assert not result['es_valido'] and result['filas_guardadas'] == 0


def table_file(extension, headers, values):
    if extension == 'csv':
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerow(values)
        return stream.getvalue().encode('utf-8-sig')
    stream = io.BytesIO()
    workbook = Workbook()
    workbook.active.append(headers)
    workbook.active.append(values)
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


@pytest.mark.parametrize('extension', ['csv', 'xlsx'])
@pytest.mark.parametrize('second', ['fecha', 'date'])
@pytest.mark.parametrize('dates', [('2026-01-01', ''), ('', '2026-01-01')])
def test_duplicate_identical_or_alias_headers_rejected_before_row_dict(db, extension, second, dates):
    data = table_file(extension, ['contenido', 'fecha', second, 'puntuacion'], ['Bien', *dates, 5])
    result = process_and_store_import(data, f'duplicate.{extension}', 10, db)
    assert result['es_valido'] is False and result['filas_guardadas'] == 0
    assert 'duplicado' in result['errores_globales'][0].lower()
    assert db.scalars(select(Review)).all() == []


@pytest.mark.parametrize('extension', ['csv', 'xlsx'])
@pytest.mark.parametrize('headers,values', [
    (['contenido', 'fecha', 'puntuacion', 'score'], ['Bien', '', 5, '']),
    (['contenido', 'review', 'fecha', 'puntuacion'], ['Bien', '', '', 5]),
    (['contenido', 'fecha', ' FECHA ', 'puntuacion'], ['Bien', '2026-01-01', '', 5]),
])
def test_duplicate_other_aliases_are_rejected(db, extension, headers, values):
    result = process_and_store_import(table_file(extension, headers, values), f'duplicate.{extension}', 10, db)
    assert not result['es_valido'] and result['filas_guardadas'] == 0
    assert 'duplicado' in result['errores_globales'][0].lower()
    assert db.scalars(select(Review)).all() == []


@pytest.mark.parametrize('extension', ['csv', 'xlsx'])
def test_header_only_duplicates_are_rejected(db, extension):
    if extension == 'csv':
        data = b'contenido,fecha,date,puntuacion\n'
    else:
        stream = io.BytesIO()
        workbook = Workbook()
        workbook.active.append(['contenido', 'fecha', 'date', 'puntuacion'])
        workbook.save(stream)
        workbook.close()
        data = stream.getvalue()
    result = process_and_store_import(data, f'headers.{extension}', 10, db)
    assert not result['es_valido'] and result['filas_guardadas'] == 0
    assert 'duplicado' in result['errores_globales'][0].lower()


@pytest.mark.parametrize('extension', ['csv', 'xlsx'])
@pytest.mark.parametrize('score,expected', [(1, 1), (5, 5), ('3.0', 3), ('3e0', 3)])
def test_score_accepted_with_exact_integer_conversion(db, extension, score, expected):
    data = make_file(extension, [{'contenido': 'Bien', 'fecha': '', 'puntuacion': score}])
    result = process_and_store_import(data, f'score.{extension}', 10, db)
    assert result['es_valido'] and db.scalar(select(Review)).puntuacion == expected


@pytest.mark.parametrize('extension', ['csv', 'xlsx'])
@pytest.mark.parametrize('score', ['1_', '_1', '1__', '1_.0', '3.5', 'NaN', 'Infinity', '0', '6'])
def test_ambiguous_or_invalid_scores_are_controlled_errors(db, extension, score):
    data = make_file(extension, [{'contenido': 'Bien', 'fecha': '', 'puntuacion': score}])
    result = process_and_store_import(data, f'score.{extension}', 10, db)
    assert not result['es_valido'] and result['filas_guardadas'] == 0
    assert result['errores_por_fila'][0]['campo'] == 'puntuacion'
    assert db.scalars(select(Review)).all() == []


@pytest.mark.parametrize('extension', ['csv', 'xlsx'])
@pytest.mark.parametrize('length,valid', [(255, True), (256, False)])
def test_author_length_validation_is_atomic(db, extension, length, valid):
    data = make_file(extension, [
        {'contenido': 'Bien', 'autor': 'A' * length, 'fecha': '', 'puntuacion': ''},
        {'contenido': 'Otra', 'fecha': '', 'puntuacion': ''},
    ])
    result = process_and_store_import(data, f'author.{extension}', 10, db)
    assert result['es_valido'] is valid
    assert result['filas_guardadas'] == (2 if valid else 0)
    if valid:
        assert len(db.scalar(select(Review).where(Review.contenido == 'Bien')).autor) == 255
    else:
        assert result['errores_por_fila'][0]['campo'] == 'autor'
        assert db.scalars(select(Review)).all() == []


def test_database_insert_error_rolls_back_whole_import(db):
    db.connection().exec_driver_sql("CREATE TRIGGER synthetic_failure BEFORE INSERT ON reviews WHEN NEW.contenido='Fallar' BEGIN SELECT RAISE(ABORT, 'synthetic'); END")
    db.commit()
    data = make_file('csv', [{'contenido': 'Primera', 'fecha': '', 'puntuacion': 5}, {'contenido': 'Fallar', 'fecha': '', 'puntuacion': 4}])
    with pytest.raises(SQLAlchemyError):
        process_and_store_import(data, 'rollback.csv', 10, db)
    assert db.scalars(select(Review)).all() == []


def test_import_does_not_refresh_after_commit(db, monkeypatch):
    def forbidden_refresh(*args, **kwargs):
        raise SQLAlchemyError('refresh no debe ejecutarse')
    monkeypatch.setattr(db, 'refresh', forbidden_refresh)
    data = make_file('csv', [{'contenido': 'Primera', 'fecha': '', 'puntuacion': 5}, {'contenido': 'Segunda', 'fecha': '', 'puntuacion': ''}])
    result = process_and_store_import(data, 'no-refresh.csv', 10, db)
    assert result['es_valido'] and result['filas_guardadas'] == 2
    assert len(db.scalars(select(Review)).all()) == 2


def test_commit_failure_may_have_unknown_outcome(db, monkeypatch):
    real_commit = db.commit
    def unknown_commit():
        real_commit()
        raise SQLAlchemyError('resultado incierto simulado')
    monkeypatch.setattr(db, 'commit', unknown_commit)
    data = make_file('csv', [{'contenido': 'Guardada', 'fecha': '', 'puntuacion': ''}])
    with pytest.raises(SQLAlchemyError):
        process_and_store_import(data, 'unknown.csv', 10, db)
    assert len(db.scalars(select(Review)).all()) == 1


def test_export_nulls_encoding_csv_escaping_and_formula_protection():
    rows = [
        Review(id=1, tenant_id=10, contenido='Niño, "bien"\ncontinúa', autor=None, fecha=None, puntuacion=None, fuente='manual', estado='nueva'),
        Review(id=2, tenant_id=10, contenido='  =SUMA(1,1)', autor='@Autor', fecha=datetime(2026, 1, 2), puntuacion=5, fuente='Google', estado='atendida'),
    ]
    data = serialize_reviews_csv(rows)
    assert data.startswith(b'\xef\xbb\xbf') and b'\r\n' in data
    parsed = list(csv.reader(io.StringIO(data.decode('utf-8-sig'), newline='')))
    assert parsed[0] == ['id', 'contenido', 'autor', 'fecha', 'fuente', 'puntuacion', 'categoria', 'estado']
    assert parsed[1] == ['1', rows[0].contenido, '', '', 'manual', '', '', 'nueva']
    assert parsed[2] == ['2', "'  =SUMA(1,1)", "'@Autor", '2026-01-02T00:00:00', 'Google', '5', '', 'atendida']


@pytest.mark.parametrize('criteria', [
    {}, {'busqueda': 'mismo'}, {'puntuacion': 5}, {'estado': 'nueva'}, {'fuente': 'Google'},
    {'fecha_desde': date(2025, 1, 1)}, {'fecha_hasta': date(2026, 12, 31)},
    {'busqueda': 'mismo', 'puntuacion': 5, 'estado': 'nueva'},
])
def test_list_export_parity_and_two_tenants(db, criteria):
    db.add_all([
        Review(id=1, tenant_id=10, contenido='mismo texto', fecha=None, puntuacion=None, fuente='Google', estado='nueva'),
        Review(id=2, tenant_id=10, contenido='mismo texto', fecha=datetime(2026, 1, 1), puntuacion=5, fuente='Google', estado='nueva'),
        Review(id=3, tenant_id=20, contenido='mismo texto', fecha=datetime(2026, 1, 2), puntuacion=5, fuente='Google', estado='nueva'),
    ])
    db.commit()
    listing = list_reviews(db=db, tenant_id=10, **criteria)
    response = export_reviews(db=db, tenant_id=10, **criteria)
    parsed = list(csv.reader(io.StringIO(response.body.decode('utf-8-sig'), newline='')))
    assert [int(row[0]) for row in parsed[1:]] == [item.id for item in listing.items]
    assert all(row[0] != '3' for row in parsed[1:])
    if 'fecha_desde' in criteria or 'fecha_hasta' in criteria:
        assert [int(row[0]) for row in parsed[1:]] == [2]


def test_http_import_and_export_scope_is_from_authenticated_user(client, seed_users):
    http, sessions = client
    with sessions() as db:
        db.add(Tenant(id=20, nombre='B', estado='activo'))
        db.add(User(tenant_id=20, nombre='B', correo='b@example.com', password_hash=get_password_hash('secret123'), rol='usuario_negocio', estado='activo'))
        db.commit()

    def headers(correo):
        response = http.post('/api/v1/auth/login', json={'correo': correo, 'password': 'secret123'})
        assert response.status_code == 200
        return {'Authorization': 'Bearer ' + response.json()['access_token']}

    data = make_file('csv', [{'contenido': 'mismo texto', 'fecha': '', 'puntuacion': '', 'tenant_id': 20}])
    first = http.post('/api/v1/reviews/import?tenant_id=20', headers=headers('usuario@example.com'), files={'file': ('test.csv', data, 'text/csv')})
    second = http.post('/api/v1/imports/upload?tenant_id=10', headers=headers('b@example.com'), files={'file': ('test.csv', data, 'text/csv')})
    assert first.json()['filas_guardadas'] == second.json()['filas_guardadas'] == 1
    for correo, other in [('usuario@example.com', 'b@example.com'), ('b@example.com', 'usuario@example.com')]:
        auth = headers(correo)
        listing = http.get('/api/v1/reviews', headers=auth).json()['items']
        response = http.get('/api/v1/reviews/export', headers=auth)
        parsed = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'), newline='')))
        assert len(listing) == 1 and len(parsed) == 2 and parsed[1][0] == str(listing[0]['id'])
        assert parsed[1][2:4] == ['', ''] and parsed[1][5] == ''
        assert int(parsed[1][0]) not in [row['id'] for row in http.get('/api/v1/reviews', headers=headers(other)).json()['items']]


@pytest.mark.parametrize('kind', ['duplicate', 'score', 'author'])
def test_http_validation_reports_errors_without_saving(client, seed_users, kind):
    http, sessions = client
    response = http.post('/api/v1/auth/login', json={'correo': 'usuario@example.com', 'password': 'secret123'})
    headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
    if kind == 'duplicate':
        data = table_file('csv', ['contenido', 'fecha', 'date', 'puntuacion'], ['Bien', '2026-01-01', '', 5])
    elif kind == 'score':
        data = make_file('csv', [{'contenido': 'Bien', 'fecha': '', 'puntuacion': '1_'}])
    else:
        data = make_file('csv', [{'contenido': 'Bien', 'autor': 'A' * 256, 'fecha': '', 'puntuacion': ''}])
    imported = http.post('/api/v1/reviews/import', headers=headers, files={'file': ('test.csv', data, 'text/csv')})
    assert imported.status_code == 200
    assert not imported.json()['es_valido'] and imported.json()['filas_guardadas'] == 0
    with sessions() as db:
        assert db.scalars(select(Review)).all() == []
