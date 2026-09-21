from datetime import datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import Review, Tenant, User
from app.schemas.tenant import TenantBase


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


def make_user(**overrides: object) -> User:
    values = {
        "tenant_id": None,
        "nombre": "Usuario de prueba",
        "correo": "usuario@example.com",
        "password_hash": "hash-de-prueba",
        "rol": "admin_tenant",
        "estado": "activo",
    }
    values.update(overrides)
    return User(**values)


def make_review(**overrides: object) -> Review:
    values = {
        "tenant_id": 1,
        "autor": "Cliente",
        "contenido": "Excelente servicio",
        "fecha": datetime(2026, 1, 1),
        "fuente": "manual",
        "puntuacion": 5,
        "estado": "nueva",
        "categoria": None,
        "prioridad": None,
    }
    values.update(overrides)
    return Review(**values)


def test_tenant_valido_se_puede_representar_y_persistir(
    db_session: Session,
) -> None:
    data = TenantBase(nombre="Negocio de prueba", estado="activo")
    tenant = Tenant(**data.model_dump())

    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    assert tenant.id is not None
    assert tenant.nombre == "Negocio de prueba"
    assert tenant.estado == "activo"


def test_tenant_tiene_id_como_clave_primaria() -> None:
    mapper = inspect(Tenant)

    assert [column.key for column in mapper.primary_key] == ["id"]


def test_user_y_review_referencian_la_tabla_tenants() -> None:
    user_foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in inspect(User).columns.tenant_id.foreign_keys
    }
    review_foreign_keys = {
        foreign_key.target_fullname
        for foreign_key in inspect(Review).columns.tenant_id.foreign_keys
    }

    assert user_foreign_keys == {"tenants.id"}
    assert review_foreign_keys == {"tenants.id"}


def test_tenant_mantiene_asociaciones_con_users_y_reviews(
    db_session: Session,
) -> None:
    tenant = Tenant(nombre="Negocio relacionado", estado="activo")
    user = make_user(tenant=tenant)
    review = make_review(tenant=tenant)

    db_session.add(tenant)
    db_session.commit()
    tenant_id = tenant.id
    db_session.expunge_all()

    persisted_tenant = db_session.get(Tenant, tenant_id)

    assert persisted_tenant is not None
    assert len(persisted_tenant.users) == 1
    assert persisted_tenant.users[0].tenant is persisted_tenant
    assert len(persisted_tenant.reviews) == 1
    assert persisted_tenant.reviews[0].tenant is persisted_tenant


@pytest.mark.parametrize(
    "entity",
    [
        pytest.param(make_user(tenant_id=999), id="user"),
        pytest.param(make_review(tenant_id=999), id="review"),
    ],
)
def test_no_se_pueden_referenciar_tenants_inexistentes(
    db_session: Session,
    entity: User | Review,
) -> None:
    db_session.add(entity)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_estado_de_tenant_solo_acepta_activo_o_inactivo(
    db_session: Session,
) -> None:
    assert TenantBase(nombre="Activo", estado="activo").estado == "activo"
    assert TenantBase(nombre="Inactivo", estado="inactivo").estado == "inactivo"

    with pytest.raises(ValidationError):
        TenantBase(nombre="Inválido", estado="suspendido")

    db_session.add(Tenant(nombre="Inválido", estado="suspendido"))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_aplicacion_fastapi_continua_importando() -> None:
    from app.main import app

    assert app.title == "Gestor Inteligente de Reviews"
