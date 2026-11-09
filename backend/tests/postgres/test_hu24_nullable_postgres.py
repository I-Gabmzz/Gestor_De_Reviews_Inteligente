"""Solo se ejecuta con TEST_POSTGRES_URL y un esquema de prueba aislado."""
import pytest
from sqlalchemy import inspect

from app.db.init_db import init_db


def test_hu24_legacy_nullability_and_idempotence(postgres_engine):
    init_db(postgres_engine)
    with postgres_engine.begin() as c:
        c.exec_driver_sql("ALTER TABLE reviews ALTER COLUMN fecha SET NOT NULL")
        c.exec_driver_sql("ALTER TABLE reviews ALTER COLUMN puntuacion SET NOT NULL")
        c.exec_driver_sql("INSERT INTO tenants(id,nombre,estado) VALUES (10,'A','activo'),(20,'B','activo')")
        c.exec_driver_sql("INSERT INTO reviews(id,tenant_id,contenido,fecha,fuente,puntuacion,estado,resumen) VALUES (1,10,'A','2026-01-01','Google',5,'nueva','resumen'),(2,20,'B','2026-02-01','CSV',1,'atendida',NULL)")
        c.exec_driver_sql("INSERT INTO external_review_connections(tenant_id,source,business_data_id) VALUES (10,'Google','negocio')")
        c.exec_driver_sql("INSERT INTO external_review_identities(review_id,tenant_id,source,business_data_id,external_review_id,import_fingerprint) VALUES (1,10,'Google','negocio','externo', %s)", ('v1:' + 'a' * 64,))
        c.exec_driver_sql("INSERT INTO review_notifications(id,tenant_id,review_id,creada_en) VALUES (1,10,1,'2026-01-01')")
    with pytest.raises(RuntimeError, match='autorización'):
        init_db(postgres_engine, allow_review_nullable_migration=False)
    assert not {c['name']: c for c in inspect(postgres_engine).get_columns('reviews')}['fecha']['nullable']
    init_db(postgres_engine, allow_review_nullable_migration=True)
    init_db(postgres_engine, allow_review_nullable_migration=False)
    cols = {c['name']: c for c in inspect(postgres_engine).get_columns('reviews')}
    assert cols['fecha']['nullable'] and cols['puntuacion']['nullable']
    with postgres_engine.begin() as c:
        assert c.exec_driver_sql("SELECT count(*) FROM reviews WHERE id=1 AND tenant_id=10 AND fuente='Google' AND puntuacion=5 AND resumen='resumen'").scalar_one() == 1
        assert c.exec_driver_sql("SELECT count(*) FROM reviews WHERE id=2 AND tenant_id=20 AND fuente='CSV' AND estado='atendida'").scalar_one() == 1
        assert c.exec_driver_sql("SELECT count(*) FROM external_review_identities WHERE review_id=1 AND tenant_id=10 AND external_review_id='externo'").scalar_one() == 1
        assert c.exec_driver_sql("SELECT count(*) FROM review_notifications WHERE review_id=1 AND tenant_id=10").scalar_one() == 1
        c.exec_driver_sql("INSERT INTO reviews(id,tenant_id,contenido,fecha,fuente,puntuacion,estado) VALUES (3,10,'sin datos',NULL,'manual',NULL,'nueva')")
