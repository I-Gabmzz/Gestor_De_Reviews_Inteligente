import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import get_password_hash
from app.db.base import Base
from app.db.connection import get_db
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User


@pytest.fixture()
def client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, testing_session
    app.dependency_overrides.clear()


@pytest.fixture()
def seed_users(client):
    _, session_factory = client
    with session_factory() as db:
        db.add(Tenant(id=10, nombre="Negocio de prueba", estado="activo"))
        db.add_all(
            [
                User(
                    tenant_id=10,
                    nombre="Usuario negocio",
                    correo="usuario@example.com",
                    password_hash=get_password_hash("secret123"),
                    rol="usuario_negocio",
                    estado="activo",
                ),
                User(
                    tenant_id=10,
                    nombre="Administrador tenant",
                    correo="tenant@example.com",
                    password_hash=get_password_hash("secret123"),
                    rol="admin_tenant",
                    estado="activo",
                ),
                User(
                    tenant_id=None,
                    nombre="Administrador general",
                    correo="general@example.com",
                    password_hash=get_password_hash("secret123"),
                    rol="admin_general",
                    estado="activo",
                ),
                User(
                    tenant_id=10,
                    nombre="Usuario inactivo",
                    correo="inactive@example.com",
                    password_hash=get_password_hash("secret123"),
                    rol="usuario_negocio",
                    estado="inactivo",
                ),
            ]
        )
        db.commit()
