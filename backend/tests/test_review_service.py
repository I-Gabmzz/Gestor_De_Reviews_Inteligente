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
