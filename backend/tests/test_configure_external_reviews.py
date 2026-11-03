import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.connection import create_database_engine
from app.db.init_db import init_db
from app.models import ExternalReviewConnection, ExternalReviewImportAttempt, Review, Tenant
from scripts.configure_external_reviews import configure_connection


@pytest.fixture()
def database(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'connection.db'}")
    init_db(engine)
    with Session(engine) as db, db.begin():
        db.add(Tenant(id=1, nombre="Negocio sintético", estado="activo"))
    yield engine
    engine.dispose()


def configure(database, **changes):
    return configure_connection(database, **{
        "tenant_id": 1, "expected_name": "Negocio sintético", "business_data_id": "0xabc:0x123",
        "approval_reference": "Aprobación sintética para prueba", **changes,
    })


def test_creation_and_repeat_preserve_reference_and_never_create_reviews(database):
    assert configure(database) is True
    assert configure(database, approval_reference="Otra referencia") is False
    with Session(database) as db:
        row = db.scalar(select(ExternalReviewConnection))
        assert row.persistence_enabled and row.approval_reference == "Aprobación sintética para prueba"
        assert db.scalar(select(func.count()).select_from(Review)) == 0
        assert db.scalar(select(func.count()).select_from(Tenant)) == 1


@pytest.mark.parametrize("changes", [
    {"tenant_id": 2}, {"expected_name": "Otro negocio"}, {"tenant_id": True},
    {"approval_reference": " "}, {"approval_reference": "x" * 256}, {"business_data_id": "invalid"},
])
def test_wrong_scope_and_invalid_configuration_never_write(database, changes):
    with pytest.raises(ValueError):
        configure(database, **changes)
    with Session(database) as db:
        assert db.scalar(select(func.count()).select_from(ExternalReviewConnection)) == 0


def test_does_not_replace_existing_other_business_connection(database):
    configure(database)
    with pytest.raises(ValueError):
        configure(database, business_data_id="0xabc:0x456")
    with Session(database) as db:
        assert list(db.scalars(select(ExternalReviewConnection.business_data_id))) == ["0xabc:0x123"]


def test_inactive_business_is_not_enabled(database):
    with Session(database) as db, db.begin():
        db.get(Tenant, 1).estado = "inactivo"
    with pytest.raises(ValueError):
        configure(database)


def test_pending_operation_is_not_unlocked_or_overwritten(database):
    from datetime import datetime
    configure(database)
    with Session(database) as db, db.begin():
        db.add(ExternalReviewImportAttempt(operation_id="synthetic-operation", tenant_id=1,
               source="Google", business_data_id="0xabc:0x123", started_at=datetime.now(),
               reserved_requests=1, active=True, state="unknown"))
    with pytest.raises(ValueError):
        configure(database)
    with Session(database) as db:
        assert db.get(ExternalReviewImportAttempt, "synthetic-operation").active is True
