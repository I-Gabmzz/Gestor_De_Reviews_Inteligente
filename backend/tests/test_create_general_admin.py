import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.security import get_password_hash, verify_password
from app.db.connection import create_database_engine
from app.db.init_db import init_db
from app.models import Tenant, User
from scripts.create_general_admin import create_initial_general_admin

PASSWORD = "synthetic-initial-admin-password"


@pytest.fixture()
def database(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'initial-general.db'}")
    init_db(engine)
    with Session(engine) as db, db.begin():
        db.add(Tenant(id=1, nombre="Negocio de prueba", estado="activo"))
        db.flush()
        db.add(User(id=1, tenant_id=1, rol="admin_tenant", estado="activo", nombre="Cuenta de negocio",
                    correo="business@example.com", password_hash=get_password_hash(PASSWORD)))
    yield engine
    engine.dispose()


def test_initial_admin_has_no_tenant_and_repeat_preserves_password_and_business_account(database):
    identifier = create_initial_general_admin(database, email="general@example.com", password=PASSWORD)
    assert create_initial_general_admin(database, email="general@example.com", password="another-synthetic-password") == identifier
    with Session(database) as db:
        general = db.get(User, identifier)
        assert (general.rol, general.tenant_id, general.estado) == ("admin_general", None, "activo")
        assert verify_password(PASSWORD, general.password_hash)
        assert (db.get(User, 1).rol, db.get(User, 1).tenant_id) == ("admin_tenant", 1)
        assert db.scalar(select(func.count()).select_from(Tenant)) == 1


def test_existing_business_account_cannot_be_promoted_by_bootstrap(database):
    with pytest.raises(ValueError):
        create_initial_general_admin(database, email="business@example.com", password=PASSWORD)
    with Session(database) as db:
        assert db.get(User, 1).rol == "admin_tenant"
        assert db.scalar(select(func.count()).select_from(User)) == 1


def test_bootstrap_never_creates_another_general_admin(database):
    create_initial_general_admin(database, email="general@example.com", password=PASSWORD)
    with pytest.raises(ValueError):
        create_initial_general_admin(database, email="other@example.com", password=PASSWORD)


def test_short_password_never_creates_privileged_account(database):
    with pytest.raises(ValueError):
        create_initial_general_admin(database, email="general@example.com", password="short")
    with Session(database) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
