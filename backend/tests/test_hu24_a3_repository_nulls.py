"""Pruebas A3 de ordenamiento NULLS LAST y filtros con fechas nulas."""

import csv
import io
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import get_password_hash
from app.db.init_db import init_db
from app.models import Review, Tenant, User
from app.repositories.review_repository import ReviewRepository


@pytest.fixture()
def repo_sessions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'a3_nulls.db'}")
    init_db(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        db.add_all(
            [
                Tenant(id=10, nombre="Negocio A", estado="activo"),
                Tenant(id=20, nombre="Negocio B", estado="activo"),
            ]
        )
        db.flush()
        db.add_all(
            [
                Review(
                    id=101,
                    tenant_id=10,
                    contenido="Sin fecha antigua",
                    fecha=None,
                    fuente="manual",
                    puntuacion=None,
                    estado="nueva",
                ),
                Review(
                    id=102,
                    tenant_id=10,
                    contenido="Fecha 2026-09-25",
                    fecha=datetime(2026, 9, 25, 10, 0),
                    fuente="manual",
                    puntuacion=4,
                    estado="nueva",
                ),
                Review(
                    id=103,
                    tenant_id=10,
                    contenido="Empate 2026-09-27 menor id",
                    fecha=datetime(2026, 9, 27, 12, 0),
                    fuente="CSV",
                    puntuacion=5,
                    estado="en_revision",
                ),
                Review(
                    id=104,
                    tenant_id=10,
                    contenido="Sin fecha reciente",
                    fecha=None,
                    fuente="manual",
                    puntuacion=None,
                    estado="nueva",
                ),
                Review(
                    id=105,
                    tenant_id=10,
                    contenido="Empate 2026-09-27 mayor id",
                    fecha=datetime(2026, 9, 27, 12, 0),
                    fuente="Google",
                    puntuacion=3,
                    estado="atendida",
                ),
                Review(
                    id=106,
                    tenant_id=10,
                    contenido="Fecha maxima 9999-12-31",
                    fecha=datetime(9999, 12, 31, 23, 59, 59),
                    fuente="manual",
                    puntuacion=5,
                    estado="nueva",
                ),
                Review(
                    id=201,
                    tenant_id=20,
                    contenido="Tenant B sin fecha",
                    fecha=None,
                    fuente="manual",
                    puntuacion=None,
                    estado="nueva",
                ),
                Review(
                    id=202,
                    tenant_id=20,
                    contenido="Tenant B con fecha",
                    fecha=datetime(2026, 9, 28, 9, 0),
                    fuente="manual",
                    puntuacion=2,
                    estado="nueva",
                ),
            ]
        )
        db.commit()
    yield sessions
    engine.dispose()


def test_list_and_recent_order_dates_desc_nulls_last_and_id_desc(repo_sessions) -> None:
    with repo_sessions() as db:
        repo = ReviewRepository(db)
        listed = repo.list_by_tenant(10)
        recent_all = repo.list_recent_by_tenant(10, limit=10)
        recent_top = repo.list_recent_by_tenant(10, limit=4)

        assert [r.id for r in listed] == [106, 105, 103, 102, 104, 101]
        assert [r.id for r in recent_all] == [106, 105, 103, 102, 104, 101]
        # Las fechas nulas al final no desplazan reseñas con fecha en el límite reciente.
        assert [r.id for r in recent_top] == [106, 105, 103, 102]
        assert all(r.tenant_id == 10 for r in listed)

        listed_b = repo.list_by_tenant(20)
        recent_b = repo.list_recent_by_tenant(20, limit=5)
        assert [r.id for r in listed_b] == [202, 201]
        assert [r.id for r in recent_b] == [202, 201]


def test_unfiltered_and_non_date_filters_include_null_dates(repo_sessions) -> None:
    with repo_sessions() as db:
        repo = ReviewRepository(db)
        unfiltered = repo.list_by_tenant(10)
        by_status = repo.list_by_tenant(10, estado="nueva")
        by_search = repo.list_by_tenant(10, busqueda="Sin fecha")

        assert [r.id for r in unfiltered] == [106, 105, 103, 102, 104, 101]
        assert [r.id for r in by_status] == [106, 102, 104, 101]
        assert [r.id for r in by_search] == [104, 101]


@pytest.mark.parametrize(
    ("criteria", "expected_ids"),
    [
        ({"fecha_hasta": date.max}, [106, 105, 103, 102]),
        ({"fecha_desde": date(2026, 9, 27), "fecha_hasta": date.max}, [106, 105, 103]),
        ({"fecha_desde": date(2026, 9, 25)}, [106, 105, 103, 102]),
        ({"fecha_hasta": date(2026, 9, 27)}, [105, 103, 102]),
        ({"fecha_desde": date(2026, 9, 26), "fecha_hasta": date(2026, 9, 27)}, [105, 103]),
    ],
)
def test_date_filters_including_date_max_exclude_null_dates(
    repo_sessions, criteria, expected_ids
) -> None:
    with repo_sessions() as db:
        repo = ReviewRepository(db)
        reviews = repo.list_by_tenant(10, **criteria)

        assert [r.id for r in reviews] == expected_ids
        assert all(r.fecha is not None for r in reviews)
        assert all(r.tenant_id == 10 for r in reviews)


@pytest.mark.parametrize("dialect", [sqlite.dialect(), postgresql.dialect()])
def test_sql_compiles_nulls_last_and_date_max_not_null(repo_sessions, dialect) -> None:
    with repo_sessions() as db:
        captured: list[str] = []

        def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
            captured.append(statement)

        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", capture)
        try:
            repo = ReviewRepository(db)
            repo.list_by_tenant(10, fecha_hasta=date.max)
            repo.list_recent_by_tenant(10, limit=5)
        finally:
            event.remove(engine, "before_cursor_execute", capture)

        # Compilación explícita de las consultas del repositorio en ambos dialectos.
        from sqlalchemy import desc, select

        list_stmt = (
            select(Review)
            .where(Review.tenant_id == 10, Review.fecha.is_not(None))
            .order_by(Review.fecha.desc().nullslast(), Review.id.desc())
        )
        recent_stmt = (
            select(Review)
            .where(Review.tenant_id == 10)
            .order_by(desc(Review.fecha).nullslast(), desc(Review.id))
            .limit(5)
        )
        list_sql = str(list_stmt.compile(dialect=dialect))
        recent_sql = str(recent_stmt.compile(dialect=dialect))
        assert "ORDER BY reviews.fecha DESC NULLS LAST, reviews.id DESC" in list_sql
        assert "ORDER BY reviews.fecha DESC NULLS LAST, reviews.id DESC" in recent_sql
        assert "reviews.fecha IS NOT NULL" in list_sql
        assert any("NULLS LAST" in sql and "IS NOT NULL" in sql for sql in captured)


def test_http_list_and_export_preserve_null_order_date_max_and_tenant_isolation(
    client, seed_users
) -> None:
    http, sessions = client
    with sessions() as db:
        db.add(Tenant(id=20, nombre="Segundo negocio", estado="activo"))
        db.add(
            User(
                tenant_id=20,
                nombre="Usuario B",
                correo="usuario_b@example.com",
                password_hash=get_password_hash("secret123"),
                rol="usuario_negocio",
                estado="activo",
            )
        )
        db.add_all(
            [
                Review(
                    id=301,
                    tenant_id=10,
                    contenido="A sin fecha 1",
                    fecha=None,
                    fuente="manual",
                    puntuacion=None,
                    estado="nueva",
                ),
                Review(
                    id=302,
                    tenant_id=10,
                    contenido="A con fecha",
                    fecha=datetime(2026, 9, 27, 8, 0),
                    fuente="manual",
                    puntuacion=4,
                    estado="nueva",
                ),
                Review(
                    id=303,
                    tenant_id=10,
                    contenido="A sin fecha 2",
                    fecha=None,
                    fuente="manual",
                    puntuacion=None,
                    estado="nueva",
                ),
                Review(
                    id=401,
                    tenant_id=20,
                    contenido="B sin fecha",
                    fecha=None,
                    fuente="manual",
                    puntuacion=None,
                    estado="nueva",
                ),
            ]
        )
        db.commit()

    token_a = http.post(
        "/api/v1/auth/login",
        json={"correo": "usuario@example.com", "password": "secret123"},
    ).json()["access_token"]
    token_b = http.post(
        "/api/v1/auth/login",
        json={"correo": "usuario_b@example.com", "password": "secret123"},
    ).json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    listed_a = http.get("/api/v1/reviews", headers=headers_a)
    assert listed_a.status_code == 200
    assert [item["id"] for item in listed_a.json()["items"]] == [302, 303, 301]

    max_filtered_a = http.get(
        "/api/v1/reviews",
        params={"fecha_hasta": "9999-12-31"},
        headers=headers_a,
    )
    assert max_filtered_a.status_code == 200
    assert [item["id"] for item in max_filtered_a.json()["items"]] == [302]

    exported_a = http.get("/api/v1/reviews/export", headers=headers_a)
    assert exported_a.status_code == 200
    rows_a = list(csv.reader(io.StringIO(exported_a.content.decode("utf-8-sig"), newline="")))
    assert [row[0] for row in rows_a[1:]] == ["302", "303", "301"]

    exported_b = http.get(
        "/api/v1/reviews/export",
        params={"fecha_hasta": "9999-12-31"},
        headers=headers_b,
    )
    assert exported_b.status_code == 200
    rows_b = list(csv.reader(io.StringIO(exported_b.content.decode("utf-8-sig"), newline="")))
    assert len(rows_b) == 1
