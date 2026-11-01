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
