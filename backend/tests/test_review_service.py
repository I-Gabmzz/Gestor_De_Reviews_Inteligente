from collections.abc import Iterator
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.review import Review
from app.models.tenant import Tenant
from app.repositories.review_repository import ReviewRepository
from app.services.review_service import ReviewNotFoundError, ReviewService


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
) -> Review:
    review = Review(
        tenant_id=tenant_id,
        autor="Cliente",
        contenido=contenido,
        fecha=fecha,
        fuente="Google",
        puntuacion=5,
        estado="nueva",
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
