"""Contrato T3 con datos sintéticos y bases SQLite aisladas."""
from datetime import datetime

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.dependencies import require_tenant_roles
from app.api.routers.reviews import create_manual_review, get_review, list_reviews, update_review
from app.db.init_db import init_db
from app.models import Review
from app.models.tenant import Tenant
from app.schemas.auth import AuthenticatedUser
from app.schemas.review import ReviewManualCreate, ReviewRead, ReviewUpdate


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 't3.db'}")
    init_db(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.add_all([Tenant(id=10, nombre='A', estado='activo'), Tenant(id=20, nombre='B', estado='activo')])
        session.commit()
        yield session
    engine.dispose()


def test_create_read_edit_clear_and_tenant_isolation(db):
    minimal = create_manual_review(ReviewManualCreate(contenido='Bien'), db, 10)
    full = create_manual_review(ReviewManualCreate(contenido='Completa', autor='Ana', fecha='2026-01-01T12:00:00', puntuacion=5), db, 10)
    external = Review(tenant_id=20, contenido='Ajena', fecha=datetime(2026, 1, 1), puntuacion=1, fuente='Google', estado='atendida')
    db.add(external)
    db.commit()
    assert (minimal.autor, minimal.fecha, minimal.puntuacion, minimal.fuente, minimal.estado, minimal.tenant_id) == (None, None, None, 'manual', 'nueva', 10)
    assert (full.autor, full.fecha, full.puntuacion) == ('Ana', datetime(2026, 1, 1, 12), 5)
    assert ReviewRead.model_validate(get_review(minimal.id, db, 10)).model_dump(mode='json')['fecha'] is None
    assert {item.id for item in list_reviews(db, 10).items} == {minimal.id, full.id}
    updated = update_review(full.id, ReviewUpdate(autor='Luis'), db, 10)
    assert (updated.fecha, updated.puntuacion, updated.fuente, updated.estado) == (datetime(2026, 1, 1, 12), 5, 'manual', 'nueva')
    cleared = update_review(full.id, ReviewUpdate(fecha=None, puntuacion=None, autor=None), db, 10)
    assert (cleared.fecha, cleared.puntuacion, cleared.autor, cleared.contenido) == (None, None, None, 'Completa')
    assert get_review(full.id, db, 10).fecha is None
    with pytest.raises(HTTPException) as error:
        get_review(external.id, db, 10)
    assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        update_review(external.id, ReviewUpdate(fecha=None), db, 10)
    assert error.value.status_code == 404
    assert (external.fuente, external.estado, external.puntuacion) == ('Google', 'atendida', 1)


@pytest.mark.parametrize('value', ['', '   ', None])
def test_content_required(value):
    with pytest.raises(ValidationError):
        ReviewManualCreate(contenido=value)


@pytest.mark.parametrize('score', [0, 6, 1.5, True, '5'])
def test_invalid_score_rejected(score):
    with pytest.raises(ValidationError):
        ReviewManualCreate(contenido='Texto', puntuacion=score)
    with pytest.raises(ValidationError):
        ReviewUpdate(puntuacion=score)


@pytest.mark.parametrize('payload', [{'tenant_id':20}, {'estado':'atendida'}, {'fuente':'Google'}, {'resumen':'ia'}])
def test_server_fields_rejected_on_create(payload):
    with pytest.raises(ValidationError):
        ReviewManualCreate(contenido='Texto', **payload)


def test_edit_distinguishes_omission_and_null():
    assert ReviewUpdate(autor='Ana').model_dump(exclude_unset=True) == {'autor': 'Ana'}
    assert ReviewUpdate(fecha=None, puntuacion=None).model_dump(exclude_unset=True) == {'fecha': None, 'puntuacion': None}
    for payload in ({'contenido': None}, {'contenido': '   '}, {'fuente': None}, {'tenant_id': 20}, {'resumen': 'ia'}):
        with pytest.raises(ValidationError):
            ReviewUpdate(**payload)


def test_edit_historical_google_preserves_source_status_and_ai(db):
    historical = Review(tenant_id=10, autor='Ana', contenido='  Texto histórico  ', fecha=datetime(2025, 1, 1),
                        puntuacion=3, fuente='Google', estado='atendida', resumen='Resumen previo')
    db.add(historical)
    db.commit()
    result = update_review(historical.id, ReviewUpdate(puntuacion=None), db, 10)
    assert (result.fuente, result.estado, result.contenido, result.resumen) == ('Google', 'atendida', '  Texto histórico  ', 'Resumen previo')
    assert result.fecha == datetime(2025, 1, 1) and result.puntuacion is None


def test_business_roles_only_and_tenant_from_context():
    dependency = require_tenant_roles('usuario_negocio', 'admin_tenant')
    for role in ('usuario_negocio', 'admin_tenant'):
        assert dependency(AuthenticatedUser(id=1, correo='a@example.com', rol=role, tenant_id=10)) == 10
    with pytest.raises(HTTPException) as error:
        dependency(AuthenticatedUser(id=2, correo='b@example.com', rol='admin_general', tenant_id=None))
    assert error.value.status_code == 403
