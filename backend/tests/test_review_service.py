from collections.abc import Iterator
from datetime import date, datetime
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.review import Review
from app.models.tenant import Tenant
from app.repositories.review_repository import ReviewRepository
from app.services.review_service import (
    ReviewFilterValidationError,
    ReviewNotFoundError,
    ReviewService,
)


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


@pytest.fixture(params=["repository", "service"])
def review_reader(
    db: Session, request: pytest.FixtureRequest
) -> ReviewRepository | ReviewService:
    repository = ReviewRepository(db)
    if request.param == "service":
        return ReviewService(repository)
    return repository


def create_tenant(db: Session, nombre: str) -> Tenant:
    tenant = Tenant(nombre=nombre, estado="activo")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def create_review(
    db: Session,
    tenant_id: int,
    contenido: str,
    fecha: datetime,
    puntuacion: int = 5,
    estado: str = "nueva",
    fuente: str = "Google",
) -> Review:
    review = Review(
        tenant_id=tenant_id,
        autor="Cliente",
        contenido=contenido,
        fecha=fecha,
        fuente=fuente,
        puntuacion=puntuacion,
        estado=estado,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def test_listar_reviews_filtra_por_tenant_y_ordena_por_fecha(db: Session) -> None:
    tenant = create_tenant(db, "Tenant principal")
    other_tenant = create_tenant(db, "Otro tenant")
    older = create_review(db, tenant.id, "Review anterior", datetime(2026, 9, 18))
    newer = create_review(db, tenant.id, "Review reciente", datetime(2026, 9, 20))
    create_review(db, other_tenant.id, "Review ajena", datetime(2026, 9, 21))

    service = ReviewService(ReviewRepository(db))

    reviews = service.list_by_tenant(tenant.id)

    assert [review.id for review in reviews] == [newer.id, older.id]
    assert all(review.tenant_id == tenant.id for review in reviews)


def test_consultar_review_del_mismo_tenant(db: Session) -> None:
    tenant = create_tenant(db, "Tenant principal")
    review = create_review(db, tenant.id, "Contenido", datetime(2026, 9, 20))
    service = ReviewService(ReviewRepository(db))

    result = service.get_by_id(review.id, tenant.id)

    assert result.id == review.id
    assert result.contenido == "Contenido"


def test_consultar_review_de_otro_tenant_no_revela_su_existencia(db: Session) -> None:
    tenant = create_tenant(db, "Tenant principal")
    other_tenant = create_tenant(db, "Otro tenant")
    foreign_review = create_review(
        db,
        other_tenant.id,
        "Contenido privado",
        datetime(2026, 9, 20),
    )
    service = ReviewService(ReviewRepository(db))

    with pytest.raises(ReviewNotFoundError):
        service.get_by_id(foreign_review.id, tenant.id)


def test_consultar_review_inexistente_devuelve_el_mismo_error(db: Session) -> None:
    tenant = create_tenant(db, "Tenant principal")
    service = ReviewService(ReviewRepository(db))

    with pytest.raises(ReviewNotFoundError):
        service.get_by_id(999, tenant.id)


def test_listado_sin_busqueda_conserva_tenant_y_orden_hu07(db, review_reader) -> None:
    tenant = create_tenant(db, "Tenant principal")
    other_tenant = create_tenant(db, "Otro tenant")
    older = create_review(db, tenant.id, "Review anterior", datetime(2026, 9, 18))
    newer = create_review(db, tenant.id, "Review reciente", datetime(2026, 9, 20))
    tied = create_review(db, tenant.id, "Misma fecha", datetime(2026, 9, 20))
    create_review(db, other_tenant.id, "Review ajena", datetime(2026, 9, 21))

    reviews = review_reader.list_by_tenant(tenant.id)

    assert [review.id for review in reviews] == [tied.id, newer.id, older.id]
    assert all(review.tenant_id == tenant.id for review in reviews)


@pytest.mark.parametrize("busqueda", ["servicio", "SERVICIO", "SeRvIcIo"])
def test_busqueda_parcial_ignora_mayusculas(db, review_reader, busqueda) -> None:
    tenant = create_tenant(db, "Tenant principal")
    matching = create_review(
        db, tenant.id, "El servicio fue excelente", datetime(2026, 9, 20)
    )
    create_review(db, tenant.id, "Excelente producto", datetime(2026, 9, 21))

    reviews = review_reader.list_by_tenant(tenant.id, busqueda=busqueda)

    assert [review.id for review in reviews] == [matching.id]


def test_busqueda_sin_coincidencias_devuelve_lista_vacia(db, review_reader) -> None:
    tenant = create_tenant(db, "Tenant principal")
    create_review(db, tenant.id, "Excelente producto", datetime(2026, 9, 20))

    assert review_reader.list_by_tenant(tenant.id, busqueda="inexistente") == []


@pytest.mark.parametrize("busqueda", [None, "", "   ", "\t\n"])
def test_servicio_busqueda_vacia_equivale_a_no_buscar(db, busqueda) -> None:
    tenant = create_tenant(db, "Tenant principal")
    other_tenant = create_tenant(db, "Otro tenant")
    older = create_review(db, tenant.id, "Contenido anterior", datetime(2026, 9, 18))
    newer = create_review(db, tenant.id, "Contenido reciente", datetime(2026, 9, 20))
    create_review(db, other_tenant.id, "Contenido ajeno", datetime(2026, 9, 21))
    service = ReviewService(ReviewRepository(db))

    reviews = service.list_by_tenant(tenant.id, busqueda=busqueda)

    assert [review.id for review in reviews] == [newer.id, older.id]
    assert reviews == service.list_by_tenant(tenant.id)


def test_servicio_elimina_solo_espacios_exteriores(db) -> None:
    tenant = create_tenant(db, "Tenant principal")
    matching = create_review(
        db, tenant.id, "El servicio  lento fue un problema", datetime(2026, 9, 20)
    )
    create_review(db, tenant.id, "El servicio lento", datetime(2026, 9, 21))
    service = ReviewService(ReviewRepository(db))

    reviews = service.list_by_tenant(tenant.id, busqueda=" \tservicio  lento\n ")

    assert [review.id for review in reviews] == [matching.id]


def test_busqueda_varias_palabras_es_una_cadena_completa(db, review_reader) -> None:
    tenant = create_tenant(db, "Tenant principal")
    matching = create_review(
        db, tenant.id, "El servicio lento debe mejorar", datetime(2026, 9, 20)
    )
    for content in ["Buen servicio", "Proceso lento", "Servicio muy lento", "Lento servicio"]:
        create_review(db, tenant.id, content, datetime(2026, 9, 21))

    reviews = review_reader.list_by_tenant(tenant.id, busqueda="servicio lento")

    assert [review.id for review in reviews] == [matching.id]


@pytest.mark.parametrize(
    ("busqueda", "matching_content", "other_content"),
    [
        ("100%", "Satisfaccion al 100%", "Satisfaccion al 1000"),
        ("servicio_lento", "El servicio_lento", "El servicio lento"),
        ("100%_/", "Codigo 100%_/ confirmado", "Codigo 100XYZ/ confirmado"),
        ("ruta/archivo", "Ruta/archivo disponible", "Rutaarchivo disponible"),
        ("' OR 1=1 --", "Texto literal ' OR 1=1 --", "Otro contenido"),
    ],
)
def test_busqueda_caracteres_especiales_son_literales(
    db, review_reader, busqueda, matching_content, other_content
) -> None:
    tenant = create_tenant(db, "Tenant principal")
    matching = create_review(db, tenant.id, matching_content, datetime(2026, 9, 20))
    create_review(db, tenant.id, other_content, datetime(2026, 9, 21))

    reviews = review_reader.list_by_tenant(tenant.id, busqueda=busqueda)

    assert [review.id for review in reviews] == [matching.id]


def test_busqueda_opera_exclusivamente_sobre_contenido(db, review_reader) -> None:
    tenant = create_tenant(db, "palabra_reservada")
    non_matching = create_review(db, tenant.id, "Otro contenido", datetime(2026, 9, 21))
    non_matching.autor = "palabra_reservada"
    non_matching.fuente = "palabra_reservada"
    non_matching.categoria = "palabra_reservada"
    non_matching.prioridad = "palabra_reservada"
    db.commit()
    matching = create_review(
        db, tenant.id, "Contenido palabra_reservada", datetime(2026, 9, 20)
    )

    reviews = review_reader.list_by_tenant(tenant.id, busqueda="palabra_reservada")

    assert [review.id for review in reviews] == [matching.id]


def test_busqueda_mantiene_aislamiento_en_ambos_tenants(db, review_reader) -> None:
    tenant_a = create_tenant(db, "Tenant A")
    tenant_b = create_tenant(db, "Tenant B")
    review_a = create_review(db, tenant_a.id, "Buen servicio", datetime(2026, 9, 20))
    review_b = create_review(db, tenant_b.id, "Buen servicio", datetime(2026, 9, 21))
    create_review(db, tenant_b.id, "Coincidencia exclusiva", datetime(2026, 9, 22))

    results_a = review_reader.list_by_tenant(tenant_a.id, busqueda="servicio")
    results_b = review_reader.list_by_tenant(tenant_b.id, busqueda="servicio")

    assert [review.id for review in results_a] == [review_a.id]
    assert [review.id for review in results_b] == [review_b.id]
    assert review_reader.list_by_tenant(tenant_a.id, busqueda="exclusiva") == []


def test_busqueda_conserva_orden_por_fecha_e_id_descendentes(db, review_reader) -> None:
    tenant = create_tenant(db, "Tenant principal")
    older = create_review(db, tenant.id, "Servicio anterior", datetime(2026, 9, 18))
    newer = create_review(db, tenant.id, "Servicio reciente", datetime(2026, 9, 20))
    tied = create_review(db, tenant.id, "Servicio misma fecha", datetime(2026, 9, 20))
    create_review(db, tenant.id, "Producto mas reciente", datetime(2026, 9, 21))

    reviews = review_reader.list_by_tenant(tenant.id, busqueda="servicio")

    assert [review.id for review in reviews] == [tied.id, newer.id, older.id]


@pytest.fixture
def filter_reviews(db):
    tenant = create_tenant(db, "Tenant principal")
    other_tenant = create_tenant(db, "Otro tenant")
    rows = [
        (
            "anterior", "Servicio anterior", datetime(2026, 9, 26, 23, 59, 59, 999999),
            5, "nueva", "Google",
        ),
        ("inicio", "Servicio inicio", datetime(2026, 9, 27), 5, "nueva", "Google"),
        (
            "revision", "Servicio lento revision", datetime(2026, 9, 27, 12),
            4, "en_revision", "Facebook",
        ),
        (
            "final", "Servicio final", datetime(2026, 9, 27, 23, 59, 59, 999999),
            5, "nueva", "Google",
        ),
        (
            "empate", "Servicio final empate", datetime(2026, 9, 27, 23, 59, 59, 999999),
            5, "nueva", "Google",
        ),
        ("posterior", "Producto posterior", datetime(2026, 9, 28), 3, "atendida", "Google"),
        ("minuscula", "Servicio otra fuente", datetime(2026, 9, 29), 1, "nueva", "google"),
    ]
    reviews = {
        name: create_review(db, tenant.id, content, fecha, score, estado, fuente)
        for name, content, fecha, score, estado, fuente in rows
    }
    foreign = create_review(
        db, other_tenant.id, "Servicio exclusivo otro tenant", datetime(2026, 9, 27, 18)
    )
    return {
        "tenant_id": tenant.id,
        "other_tenant_id": other_tenant.id,
        "reviews": reviews,
        "foreign": foreign,
    }


@pytest.mark.parametrize(
    ("criteria", "expected_names"),
    [
        ({}, ["minuscula", "posterior", "empate", "final", "revision", "inicio", "anterior"]),
        (
            {"fecha_desde": date(2026, 9, 27)},
            ["minuscula", "posterior", "empate", "final", "revision", "inicio"],
        ),
        ({"fecha_hasta": date(2026, 9, 27)}, ["empate", "final", "revision", "inicio", "anterior"]),
        (
            {"fecha_desde": date(2026, 9, 27), "fecha_hasta": date(2026, 9, 28)},
            ["posterior", "empate", "final", "revision", "inicio"],
        ),
        (
            {"fecha_desde": date(2026, 9, 27), "fecha_hasta": date(2026, 9, 27)},
            ["empate", "final", "revision", "inicio"],
        ),
        ({"fecha_desde": date(2026, 9, 30)}, []),
        ({"fecha_hasta": date(2026, 9, 25)}, []),
        (
            {"fecha_hasta": date.max},
            ["minuscula", "posterior", "empate", "final", "revision", "inicio", "anterior"],
        ),
        ({"puntuacion": 1}, ["minuscula"]),
        ({"puntuacion": 5}, ["empate", "final", "inicio", "anterior"]),
        ({"puntuacion": 2}, []),
        ({"puntuacion": 3}, ["posterior"]),
        ({"puntuacion": 4}, ["revision"]),
        ({"estado": "nueva"}, ["minuscula", "empate", "final", "inicio", "anterior"]),
        ({"estado": "en_revision"}, ["revision"]),
        ({"estado": "atendida"}, ["posterior"]),
        ({"fuente": "Google"}, ["posterior", "empate", "final", "inicio", "anterior"]),
        ({"fuente": "google"}, ["minuscula"]),
        ({"fuente": "GOOGLE"}, []),
        ({"fuente": "Goo"}, []),
        ({"fuente": "Inexistente"}, []),
        (
            {
                "fecha_desde": date(2026, 9, 27),
                "fecha_hasta": date(2026, 9, 27),
                "puntuacion": 5,
            },
            ["empate", "final", "inicio"],
        ),
        ({"estado": "nueva", "fuente": "Google"}, ["empate", "final", "inicio", "anterior"]),
        ({"busqueda": "servicio", "puntuacion": 4}, ["revision"]),
        (
            {
                "busqueda": "servicio",
                "fecha_desde": date(2026, 9, 27),
                "fecha_hasta": date(2026, 9, 27),
                "puntuacion": 5,
                "estado": "nueva",
                "fuente": "Google",
            },
            ["empate", "final", "inicio"],
        ),
        ({"estado": "atendida", "fuente": "Facebook"}, []),
    ],
)
def test_filtros_y_combinaciones_conservan_orden_y_tenant(
    review_reader, filter_reviews, criteria, expected_names
) -> None:
    tenant_id = filter_reviews["tenant_id"]

    reviews = review_reader.list_by_tenant(tenant_id, **criteria)

    assert [review.id for review in reviews] == [
        filter_reviews["reviews"][name].id for name in expected_names
    ]
    assert all(review.tenant_id == tenant_id for review in reviews)


@pytest.mark.parametrize("fuente", [" Google ", "\tGoogle\n"])
def test_servicio_normaliza_fuente_con_espacios_exteriores(db, filter_reviews, fuente) -> None:
    service = ReviewService(ReviewRepository(db))

    reviews = service.list_by_tenant(filter_reviews["tenant_id"], fuente=fuente)

    assert [review.id for review in reviews] == [
        filter_reviews["reviews"][name].id
        for name in ["posterior", "empate", "final", "inicio", "anterior"]
    ]


@pytest.mark.parametrize("fuente", [None, "", "   ", "\t\n"])
def test_servicio_fuente_vacia_equivale_a_ausencia(db, filter_reviews, fuente) -> None:
    service = ReviewService(ReviewRepository(db))
    tenant_id = filter_reviews["tenant_id"]

    assert service.list_by_tenant(tenant_id, fuente=fuente) == service.list_by_tenant(tenant_id)
    assert service.list_by_tenant(
        tenant_id, busqueda="servicio", fuente=fuente
    ) == service.list_by_tenant(
        tenant_id, busqueda="servicio"
    )


def test_servicio_combina_normalizacion_de_busqueda_y_fuente(db, filter_reviews) -> None:
    service = ReviewService(ReviewRepository(db))

    reviews = service.list_by_tenant(
        filter_reviews["tenant_id"],
        busqueda="  SERVICIO  ",
        fecha_desde=date(2026, 9, 27),
        fecha_hasta=date(2026, 9, 27),
        puntuacion=5,
        estado="nueva",
        fuente=" Google ",
    )

    assert [review.id for review in reviews] == [
        filter_reviews["reviews"][name].id for name in ["empate", "final", "inicio"]
    ]


@pytest.mark.parametrize(
    "criteria",
    [
        {"fecha_desde": date(2026, 9, 28), "fecha_hasta": date(2026, 9, 27)},
        {"fecha_desde": "2026-09-27"},
        {"fecha_hasta": datetime(2026, 9, 27, 12)},
        {"puntuacion": 0},
        {"puntuacion": 6},
        {"puntuacion": 4.5},
        {"puntuacion": "5"},
        {"puntuacion": True},
        {"estado": "Nueva"},
        {"estado": "En revisión"},
        {"estado": "Atendida"},
        {"estado": "desconocido"},
        {"estado": ""},
        {"fuente": 5},
    ],
)
def test_servicio_rechaza_criterios_invalidos_antes_de_consultar(criteria) -> None:
    repository = Mock(spec=ReviewRepository)
    service = ReviewService(repository)

    with pytest.raises(ReviewFilterValidationError):
        service.list_by_tenant(10, **criteria)

    repository.list_by_tenant.assert_not_called()


def test_filtro_estado_sin_coincidencias_en_tenant_autorizado(review_reader, filter_reviews) -> None:
    assert review_reader.list_by_tenant(
        filter_reviews["other_tenant_id"], estado="atendida"
    ) == []


def test_todos_los_filtros_conservan_aislamiento_en_ambos_sentidos(
    review_reader, filter_reviews
) -> None:
    criteria = {
        "busqueda": "servicio",
        "fecha_desde": date(2026, 9, 27),
        "fecha_hasta": date(2026, 9, 27),
        "puntuacion": 5,
        "estado": "nueva",
        "fuente": "Google",
    }

    results_a = review_reader.list_by_tenant(filter_reviews["tenant_id"], **criteria)
    results_b = review_reader.list_by_tenant(filter_reviews["other_tenant_id"], **criteria)

    assert [review.id for review in results_a] == [
        filter_reviews["reviews"][name].id for name in ["empate", "final", "inicio"]
    ]
    assert [review.id for review in results_b] == [filter_reviews["foreign"].id]
    assert review_reader.list_by_tenant(
        filter_reviews["tenant_id"], **(criteria | {"busqueda": "exclusivo"})
    ) == []
