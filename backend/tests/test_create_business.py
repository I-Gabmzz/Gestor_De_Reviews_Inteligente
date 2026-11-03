import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.db.connection import create_database_engine
from app.db.init_db import init_db
from app.models import Tenant, User
from scripts import create_business as setup


PASSWORD = "synthetic-business-password"
EMAIL = "admin.demo@example.com"
URL = "postgresql://demo:synthetic-db-password@dpg-demo.oregon-postgres.render.com/demo"


@pytest.fixture()
def database(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'business.db'}")
    init_db(engine)
    yield engine
    engine.dispose()


def provision(database, **changes):
    return setup.create_business(database, **{
        "name": "Negocio sintético", "email": EMAIL, "password": PASSWORD, **changes,
    })


def test_atomic_setup_creates_active_business_and_hashed_administrator(database):
    result = provision(database, email=EMAIL.upper())
    with Session(database) as db:
        user = db.get(User, result.user_id)
        tenant = db.get(Tenant, result.tenant_id)
        assert (tenant.nombre, tenant.estado) == ("Negocio sintético", "activo")
        assert (user.correo, user.rol, user.estado, user.tenant_id) == (
            EMAIL, "admin_tenant", "activo", tenant.id,
        )
        assert user.password_hash != PASSWORD
        assert verify_password(PASSWORD, user.password_hash)


def test_repeat_keeps_ids_password_and_existing_data(database):
    first = provision(database)
    second = provision(database, password="another-synthetic-password")
    assert (first.tenant_id, first.user_id) == (second.tenant_id, second.user_id)
    assert not second.business_created and not second.administrator_created
    with Session(database) as db:
        assert db.scalar(select(func.count()).select_from(Tenant)) == 1
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert verify_password(PASSWORD, db.get(User, first.user_id).password_hash)


def test_existing_email_cannot_be_reassigned_or_promoted_and_new_tenant_rolls_back(database):
    first = provision(database)
    with Session(database) as db, db.begin():
        db.get(User, first.user_id).rol = "usuario_negocio"
    with pytest.raises(ValueError):
        provision(database, name="Otro negocio")
    with Session(database) as db:
        user = db.get(User, first.user_id)
        assert (user.tenant_id, user.rol) == (first.tenant_id, "usuario_negocio")
        assert db.scalar(select(func.count()).select_from(Tenant)) == 1


@pytest.mark.parametrize("state", ["inactive", "ambiguous"])
def test_inactive_or_ambiguous_business_is_not_modified(database, state):
    with Session(database) as db, db.begin():
        db.add(Tenant(nombre="Negocio sintético", estado="inactivo" if state == "inactive" else "activo"))
        if state == "ambiguous":
            db.add(Tenant(nombre="Negocio sintético", estado="activo"))
    with pytest.raises(ValueError):
        provision(database)
    with Session(database) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.parametrize("changes", [{"name": " "}, {"email": "invalid"}, {"password": "short"}])
def test_invalid_input_does_not_write(database, changes):
    with pytest.raises(ValueError):
        provision(database, **changes)
    with Session(database) as db:
        assert db.scalar(select(func.count()).select_from(Tenant)) == 0


def test_external_url_requires_postgres_external_render_host_and_tls():
    url = setup.external_database_url(URL)
    assert url.drivername == "postgresql+psycopg"
    assert url.query == {"sslmode": "require", "connect_timeout": "15"}
    assert url.password == "synthetic-db-password"
    assert setup.external_database_url(URL + "?sslmode=verify-full").query["sslmode"] == "verify-full"
    for invalid in ["sqlite:///local.db", "postgresql://demo:private@dpg-internal/demo",
                    URL + "?sslmode=disable", "invalid-private-url"]:
        with pytest.raises(ValueError) as error:
            setup.external_database_url(invalid)
        assert invalid not in str(error.value)
        assert "private" not in str(error.value)


def test_cli_requires_private_terminal(monkeypatch, capsys):
    monkeypatch.setattr(setup.sys.stdin, "isatty", lambda: False)
    assert setup.main(["--name", "Demo", "--email", EMAIL]) == 2
    assert "terminal interactiva" in capsys.readouterr().out


def test_cli_cancellation_never_opens_database(monkeypatch, capsys):
    monkeypatch.setattr(setup.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(setup, "getpass", lambda _: URL)
    monkeypatch.setattr("builtins.input", lambda _: "cancelar")
    monkeypatch.setattr(setup, "create_database_engine", lambda _: pytest.fail("No debe conectar"))
    assert setup.main(["--name", "Demo", "--email", EMAIL]) == 0
    assert "synthetic-db-password" not in capsys.readouterr().out


def test_cli_failure_does_not_print_connection_password_or_traceback(monkeypatch, capsys):
    monkeypatch.setattr(setup.sys.stdin, "isatty", lambda: True)
    answers = iter([URL, PASSWORD, PASSWORD])
    monkeypatch.setattr(setup, "getpass", lambda _: next(answers))
    monkeypatch.setattr("builtins.input", lambda _: "CREAR")
    def fail(_):
        raise OperationalError("sensitive SQL", {"password": PASSWORD}, Exception(URL))
    monkeypatch.setattr(setup, "create_database_engine", fail)
    assert setup.main(["--name", "Demo", "--email", EMAIL]) == 1
    output = capsys.readouterr().out
    assert URL not in output and PASSWORD not in output
    assert "synthetic-db-password" not in output and "sensitive SQL" not in output


def test_cli_success_uses_private_prompts_and_never_prints_secrets(database, monkeypatch, capsys):
    monkeypatch.setattr(setup.sys.stdin, "isatty", lambda: True)
    answers = iter([URL, PASSWORD, PASSWORD])
    monkeypatch.setattr(setup, "getpass", lambda _: next(answers))
    monkeypatch.setattr("builtins.input", lambda _: "CREAR")
    monkeypatch.setattr(setup, "create_database_engine", lambda _: database)
    assert setup.main(["--name", "Demo", "--email", EMAIL]) == 0
    output = capsys.readouterr().out
    assert "Negocio listo" in output and EMAIL in output
    assert URL not in output and PASSWORD not in output and "synthetic-db-password" not in output
    with Session(database) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1


def test_hidden_input_failure_cancels_before_reading_unprotected_secret(monkeypatch, capsys):
    monkeypatch.setattr(setup.sys.stdin, "isatty", lambda: True)
    def unavailable(_):
        import warnings
        warnings.warn("Cannot control echo", setup.GetPassWarning)
        pytest.fail("No debe continuar con entrada visible")
    monkeypatch.setattr(setup, "getpass", unavailable)
    assert setup.main(["--name", "Demo", "--email", EMAIL]) == 2
    assert "No se pudo ocultar" in capsys.readouterr().out


def test_new_administrator_can_login_and_read_its_business(client):
    browser, sessions = client
    with sessions() as db:
        database = db.get_bind()
    result = provision(database)
    response = browser.post("/api/v1/auth/login", json={"correo": EMAIL, "password": PASSWORD})
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["rol"] == "admin_tenant"
    assert data["user"]["tenant_id"] == result.tenant_id
    response = browser.get("/api/v1/tenants/" + str(result.tenant_id),
                           headers={"Authorization": "Bearer " + data["access_token"]})
    # El administrador del negocio no obtiene privilegios de administrador general.
    assert response.status_code == 403
    response = browser.get("/api/v1/dashboard",
                           headers={"Authorization": "Bearer " + data["access_token"]})
    assert response.status_code == 200
