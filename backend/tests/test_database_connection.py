import pytest
from sqlalchemy.engine import make_url

from app.db.connection import create_database_engine


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_render_urls_select_psycopg_without_changing_credentials_or_tls(scheme):
    original = make_url(f"{scheme}://demo:p%40ss%2Fword@localhost:5432/demo?sslmode=require&connect_timeout=8")
    database = create_database_engine(original)
    try:
        assert database.dialect.driver == "psycopg"
        assert database.url == original.set(drivername="postgresql+psycopg")
        assert database.url.password == "p@ss/word"
        assert database.hide_parameters is True
        assert database.pool._pre_ping is True
    finally:
        database.dispose()


def test_sqlite_preserves_files_and_enforces_foreign_keys(tmp_path):
    database = create_database_engine(f"sqlite:///{tmp_path / 'local.db'}")
    try:
        with database.begin() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            connection.exec_driver_sql("CREATE TABLE sample (value TEXT)")
            connection.exec_driver_sql("INSERT INTO sample VALUES ('conservado')")
        database.dispose()
        with database.connect() as connection:
            assert connection.exec_driver_sql("SELECT value FROM sample").scalar_one() == "conservado"
    finally:
        database.dispose()


def test_invalid_url_does_not_expose_its_value():
    with pytest.raises(ValueError) as caught:
        create_database_engine("valor-sintetico-privado-sin-esquema")
    assert str(caught.value) == "DATABASE_URL no tiene un formato válido"
