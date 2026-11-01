from datetime import datetime

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.init_db import init_db
from app.models.notification import ReviewNotification
from app.models.review import Review
from app.models.tenant import Tenant
from app.repositories.notification_repository import NotificationRepository
from app.repositories.notification_repository import high_notification_insert
from app.repositories.review_repository import ReviewRepository
from app.schemas.ai import ClassificationResult, PriorityResult


@pytest.fixture()
def notification_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'notifications.db'}", connect_args={"check_same_thread": False})
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.commit()
    init_db(engine)
    with Session(engine) as db:
        db.add(Tenant(id=10, nombre="Negocio sintético", estado="activo"))
        db.flush()
        db.add(Review(id=101, tenant_id=10, contenido="Me cobraron dos veces.", fecha=datetime(2026, 11, 1),
                      fuente="manual", puntuacion=2, estado="en_revision", prioridad="Alta"))
        db.commit()
    yield engine
    engine.dispose()


def test_repeated_initialization_preserves_reviews_and_adds_no_notifications(notification_engine):
    with Session(notification_engine) as db:
        original = (db.get(Review, 101).contenido, db.get(Review, 101).estado, db.get(Review, 101).prioridad)
    init_db(notification_engine)
    init_db(notification_engine)
    assert "review_notifications" in inspect(notification_engine).get_table_names()
    with Session(notification_engine) as db:
        assert (db.get(Review, 101).contenido, db.get(Review, 101).estado, db.get(Review, 101).prioridad) == original
        assert db.query(ReviewNotification).count() == 0


def test_database_constraint_and_delete_cascade(notification_engine):
    with Session(notification_engine) as db:
        NotificationRepository(db).add_for_high_review(101, 10)
        db.commit()
        db.add(ReviewNotification(tenant_id=10, review_id=101))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.delete(db.get(Review, 101))
        db.commit()
        assert db.query(ReviewNotification).count() == 0


def test_repeated_high_preserves_event_id_and_creation_time(notification_engine):
    with Session(notification_engine) as db:
        repository = ReviewRepository(db)
        repository.save_ai_result(101, 10, PriorityResult(prioridad="Alta"))
        first = db.query(ReviewNotification).one()
        identity = (first.id, first.creada_en)
        for _ in range(3):
            repository.save_ai_result(101, 10, PriorityResult(prioridad="Alta"))
            saved = db.query(ReviewNotification).one()
            assert (saved.id, saved.creada_en) == identity
        assert db.get(Review, 101).estado == "en_revision"


def test_priority_cycle_reuses_one_event_and_only_shows_current_high(notification_engine):
    with Session(notification_engine) as db:
        repository = ReviewRepository(db)
        feed = NotificationRepository(db)
        for priority in ("Baja", "Media"):
            repository.save_ai_result(101, 10, PriorityResult(prioridad=priority))
            assert feed.list_for_tenant(10, limit=20, offset=0) == ([], 0)
        repository.save_ai_result(101, 10, PriorityResult(prioridad="Alta"))
        first = db.query(ReviewNotification).one()
        identity = (first.id, first.creada_en)
        repository.save_ai_result(101, 10, PriorityResult(prioridad="Media"))
        assert feed.list_for_tenant(10, limit=20, offset=0) == ([], 0)
        repository.save_ai_result(101, 10, PriorityResult(prioridad="Alta"))
        saved = db.query(ReviewNotification).one()
        assert (saved.id, saved.creada_en) == identity
        assert feed.list_for_tenant(10, limit=20, offset=0)[1] == 1


def test_other_analyses_and_content_conflict_never_create_events(notification_engine):
    with Session(notification_engine) as db:
        repository = ReviewRepository(db)
        repository.save_ai_result(101, 10, ClassificationResult(categoria="Queja"))
        assert db.query(ReviewNotification).count() == 0
        assert repository.save_ai_result(101, 10, PriorityResult(prioridad="Alta"), expected_content="Texto anterior") is None
        assert db.query(ReviewNotification).count() == 0


@pytest.mark.parametrize("failure", ["insert", "commit", "unavailable"])
def test_priority_and_event_rollback_together(notification_engine, monkeypatch, failure):
    from sqlalchemy.exc import SQLAlchemyError

    with Session(notification_engine) as db:
        review = db.get(Review, 101)
        review.prioridad = "Media"
        db.commit()
        repository = ReviewRepository(db)
        with monkeypatch.context() as patch:
            if failure == "commit":
                patch.setattr(db, "commit", lambda: (_ for _ in ()).throw(SQLAlchemyError("Fallo simulado")))
            elif failure == "insert":
                patch.setattr(NotificationRepository, "add_for_high_review", lambda *args: (_ for _ in ()).throw(SQLAlchemyError("Fallo simulado")))
            else:
                patch.setattr(NotificationRepository, "add_for_high_review", lambda *args: None)
            with pytest.raises(SQLAlchemyError):
                repository.save_ai_result(101, 10, PriorityResult(prioridad="Alta"))
        assert db.get(Review, 101).prioridad == "Media"
        assert db.query(ReviewNotification).count() == 0


def test_concurrent_high_writes_generate_one_event(notification_engine):
    from concurrent.futures import ThreadPoolExecutor

    def save(_):
        with Session(notification_engine) as db:
            result = ReviewRepository(db).save_ai_result(101, 10, PriorityResult(prioridad="Alta"))
            assert result.prioridad == "Alta"

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(save, range(4)))
    with Session(notification_engine) as db:
        assert db.query(ReviewNotification).count() == 1
        assert db.get(Review, 101).estado == "en_revision"


def test_conditional_idempotent_insert_compiles_for_postgresql():
    from sqlalchemy.dialects import postgresql

    compiled = str(high_notification_insert("postgresql", 101, 10).compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (tenant_id, review_id) DO NOTHING" in compiled
    assert "reviews.tenant_id" in compiled and "reviews.prioridad" in compiled
