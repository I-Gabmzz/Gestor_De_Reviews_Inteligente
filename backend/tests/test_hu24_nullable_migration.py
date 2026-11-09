"""Pruebas de migración únicamente con bases SQLite sintéticas."""
import pytest
from sqlalchemy import event, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.db.connection import create_database_engine
from app.db.init_db import init_db
from app.models import Review
from app.schemas.review import ReviewManualCreate, ReviewRead
from app.repositories.review_repository import ReviewRepository
from app.api.routers.reviews import list_reviews
from app.models.tenant import Tenant
from app.core.config import Settings, settings
from app.db.migrations import migrate_review_nullable


@pytest.fixture
def engine(tmp_path):
    db = create_database_engine(f"sqlite:///{tmp_path / 'synthetic.db'}")
    init_db(db)
    yield db
    db.dispose()


def prepare_legacy(engine):
    with engine.connect() as c:
        c.exec_driver_sql("PRAGMA foreign_keys=OFF")
        c.commit()
        with c.begin():
            c.exec_driver_sql("BEGIN IMMEDIATE")
            ddl = c.exec_driver_sql("SELECT sql FROM sqlite_schema WHERE name='reviews'").scalar_one()
            ddl = ddl.replace("fecha DATETIME,", "fecha DATETIME NOT NULL,")
            ddl = ddl.replace("puntuacion INTEGER,", "puntuacion INTEGER NOT NULL,")
            c.exec_driver_sql("DROP TABLE reviews")
            c.exec_driver_sql(ddl)
            c.exec_driver_sql("CREATE UNIQUE INDEX uq_reviews_id_tenant ON reviews(id,tenant_id)")
        c.exec_driver_sql("PRAGMA foreign_keys=ON")
        c.commit()
    with engine.begin() as c:
        c.exec_driver_sql("INSERT INTO tenants(id,nombre,estado) VALUES (10,'A','activo'),(20,'B','activo')")
        c.exec_driver_sql("INSERT INTO reviews (id,tenant_id,autor,contenido,fecha,fuente,puntuacion,estado,categoria,resumen,tema,prioridad,respuesta_sugerida,respuesta_sugerida_version,solucion) VALUES (1,10,'Ana','Texto A','2026-01-01 10:00:00','Google',5,'en_revision','cat','resumen','tema','Alta','respuesta',3,'solucion'), (2,20,NULL,'Texto B','2026-02-02 00:00:00','CSV',1,'atendida',NULL,NULL,NULL,NULL,NULL,0,NULL)")
        c.exec_driver_sql("INSERT INTO external_review_connections(tenant_id,source,business_data_id) VALUES (10,'Google','negocio')")
        c.exec_driver_sql("INSERT INTO external_review_identities(review_id,tenant_id,source,business_data_id,external_review_id,import_fingerprint) VALUES (1,10,'Google','negocio','externo',?)", ('v1:' + 'a' * 64,))
        c.exec_driver_sql("INSERT INTO review_notifications(id,tenant_id,review_id,creada_en) VALUES (1,10,1,'2026-01-01')")
        c.exec_driver_sql("CREATE INDEX ix_hu24_source ON reviews(fuente)")
        c.exec_driver_sql("CREATE TRIGGER hu24_review_trigger AFTER UPDATE ON reviews BEGIN SELECT 1; END")


def snapshot(engine):
    with engine.connect() as c:
        return {table: c.exec_driver_sql(f'SELECT * FROM {table} ORDER BY 1').all() for table in ('reviews', 'tenants', 'external_review_connections', 'external_review_identities', 'review_notifications')}


def test_migrate_preserves_rows_relations_and_is_idempotent(engine):
    prepare_legacy(engine)
    assert not {c['name']: c for c in inspect(engine).get_columns('reviews')}['fecha']['nullable']
    before = snapshot(engine)
    init_db(engine, allow_review_nullable_migration=True)
    init_db(engine, allow_review_nullable_migration=False)
    assert snapshot(engine) == before
    columns = {c['name']: c for c in inspect(engine).get_columns('reviews')}
    assert columns['fecha']['nullable'] and columns['puntuacion']['nullable'] and columns['autor']['nullable']
    assert not columns['contenido']['nullable'] and not columns['tenant_id']['nullable']
    with engine.connect() as c:
        assert c.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
        assert c.exec_driver_sql('PRAGMA foreign_key_check').all() == []
        assert c.exec_driver_sql("SELECT count(*) FROM sqlite_schema WHERE name IN ('uq_reviews_id_tenant','ix_hu24_source','hu24_review_trigger')").scalar_one() == 3
    with Session(engine) as db:
        db.add(Review(tenant_id=10, contenido='Sin datos', autor=None, fecha=None, puntuacion=None, fuente='manual', estado='nueva'))
        db.commit()
        review = db.scalar(select(Review).where(Review.contenido == 'Sin datos'))
        assert review.fecha is None and review.puntuacion is None
        payload = ReviewRead.model_validate(review).model_dump(mode='json')
        assert payload['fecha'] is None and payload['puntuacion'] is None and payload['autor'] is None
        assert ReviewRepository(db).get_by_id_for_tenant(2, 10) is None
        assert ReviewRepository(db).get_by_id_for_tenant(2, 20).fuente == 'CSV'
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            c.exec_driver_sql("UPDATE external_review_identities SET tenant_id=20 WHERE review_id=1")


def test_new_schema_and_manual_input_remains_unchanged(engine):
    columns = {c['name']: c for c in inspect(engine).get_columns('reviews')}
    assert columns['fecha']['nullable'] and columns['puntuacion']['nullable']
    with pytest.raises(ValidationError):
        ReviewManualCreate(contenido='texto')


def test_old_database_requires_authorization_before_any_schema_change(engine, monkeypatch):
    prepare_legacy(engine)
    monkeypatch.setattr(settings, 'hu24_allow_review_nullable_migration', False)
    before = snapshot(engine)
    with engine.connect() as c:
        schema = c.exec_driver_sql("SELECT type,name,sql FROM sqlite_schema ORDER BY type,name").all()
    with pytest.raises(RuntimeError, match='HU24_ALLOW_REVIEW_NULLABLE_MIGRATION'):
        init_db(engine)
    assert snapshot(engine) == before
    with engine.connect() as c:
        assert c.exec_driver_sql("SELECT type,name,sql FROM sqlite_schema ORDER BY type,name").all() == schema
        assert c.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
        with pytest.raises(RuntimeError, match='autorización'):
            migrate_review_nullable(c)


def test_settings_opt_in_is_false_by_default(monkeypatch):
    monkeypatch.delenv('HU24_ALLOW_REVIEW_NULLABLE_MIGRATION', raising=False)
    assert Settings(_env_file=None).hu24_allow_review_nullable_migration is False
    monkeypatch.setenv('HU24_ALLOW_REVIEW_NULLABLE_MIGRATION', 'true')
    assert Settings(_env_file=None).hu24_allow_review_nullable_migration is True


def test_fastapi_lifespan_gate_for_new_old_and_updated_database(engine, monkeypatch):
    from app.main import lifespan
    import app.main as main

    monkeypatch.setattr(main, 'init_db', lambda: init_db(engine))
    monkeypatch.setattr(settings, 'hu24_allow_review_nullable_migration', False)

    async def startup():
        async with lifespan(None):
            pass

    def run_startup():
        coroutine = startup()
        with pytest.raises(StopIteration):
            coroutine.send(None)

    run_startup()
    prepare_legacy(engine)
    before = snapshot(engine)
    with pytest.raises(RuntimeError, match='autorización'):
        run_startup()
    assert snapshot(engine) == before
    monkeypatch.setattr(settings, 'hu24_allow_review_nullable_migration', True)
    run_startup()
    monkeypatch.setattr(settings, 'hu24_allow_review_nullable_migration', False)
    run_startup()
    assert snapshot(engine) == before


def test_unsupported_schema_rolls_back_and_restores_fk(engine):
    prepare_legacy(engine)
    with engine.begin() as c:
        c.exec_driver_sql("ALTER TABLE reviews ADD COLUMN extra TEXT GENERATED ALWAYS AS (contenido) VIRTUAL")
    before = snapshot(engine)
    with pytest.raises(RuntimeError):
        init_db(engine, allow_review_nullable_migration=True)
    assert snapshot(engine) == before
    with engine.connect() as c:
        assert c.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
        assert c.exec_driver_sql('PRAGMA foreign_key_check').all() == []
        assert c.exec_driver_sql("SELECT count(*) FROM sqlite_schema WHERE name='hu24_reviews_backup'").scalar_one() == 0


def test_failure_after_rebuild_rolls_back_data_and_schema(engine):
    prepare_legacy(engine)
    before = snapshot(engine)
    with engine.connect() as c:
        schema = c.exec_driver_sql("SELECT type,name,sql FROM sqlite_schema ORDER BY type,name").all()

    def fail_after_copy(conn, cursor, statement, parameters, context, executemany):
        if statement == 'DROP TABLE hu24_reviews_backup':
            raise RuntimeError('fallo sintético')

    event.listen(engine, 'before_cursor_execute', fail_after_copy)
    try:
        with pytest.raises(RuntimeError, match='fallo sintético'):
            init_db(engine, allow_review_nullable_migration=True)
    finally:
        event.remove(engine, 'before_cursor_execute', fail_after_copy)
    assert snapshot(engine) == before
    with engine.connect() as c:
        assert c.exec_driver_sql("SELECT type,name,sql FROM sqlite_schema ORDER BY type,name").all() == schema
        assert c.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
        assert c.exec_driver_sql('PRAGMA foreign_key_check').all() == []


def test_check_constraint_on_nullable_field_requires_review(engine):
    prepare_legacy(engine)
    with engine.begin() as c:
        c.exec_driver_sql("ALTER TABLE reviews ADD COLUMN extra INTEGER CHECK (fecha IS NOT NULL)")
    before = snapshot(engine)
    with pytest.raises(RuntimeError, match='restricción'):
        init_db(engine, allow_review_nullable_migration=True)
    assert snapshot(engine) == before
    assert not {c['name']: c for c in inspect(engine).get_columns('reviews')}['fecha']['nullable']


def test_ambiguous_triggers_az_za_rejected_without_changes(engine):
    prepare_legacy(engine)
    with engine.begin() as c:
        c.exec_driver_sql('DROP TRIGGER hu24_review_trigger')
        c.exec_driver_sql('CREATE TABLE trigger_log (v TEXT)')
        c.exec_driver_sql("CREATE TRIGGER zz_first AFTER UPDATE ON reviews BEGIN INSERT INTO trigger_log VALUES ('Z'); END")
        c.exec_driver_sql("CREATE TRIGGER aa_second AFTER UPDATE ON reviews BEGIN INSERT INTO trigger_log VALUES ('A'); END")
        c.exec_driver_sql('UPDATE reviews SET contenido=contenido WHERE id=1')
        assert ''.join(c.exec_driver_sql('SELECT v FROM trigger_log ORDER BY rowid').scalars()) == 'AZ'
        c.exec_driver_sql('DELETE FROM trigger_log')
        c.exec_driver_sql('SAVEPOINT simulated_reorder')
        c.exec_driver_sql('DROP TRIGGER zz_first')
        c.exec_driver_sql('DROP TRIGGER aa_second')
        c.exec_driver_sql("CREATE TRIGGER aa_second AFTER UPDATE ON reviews BEGIN INSERT INTO trigger_log VALUES ('A'); END")
        c.exec_driver_sql("CREATE TRIGGER zz_first AFTER UPDATE ON reviews BEGIN INSERT INTO trigger_log VALUES ('Z'); END")
        c.exec_driver_sql('UPDATE reviews SET contenido=contenido WHERE id=1')
        assert ''.join(c.exec_driver_sql('SELECT v FROM trigger_log ORDER BY rowid').scalars()) == 'ZA'
        c.exec_driver_sql('ROLLBACK TO simulated_reorder')
        c.exec_driver_sql('RELEASE simulated_reorder')
    before = snapshot(engine)
    with engine.connect() as c:
        schema = c.exec_driver_sql('SELECT type,name,sql FROM sqlite_schema ORDER BY type,name').all()
    with pytest.raises(RuntimeError, match='Triggers SQLite ambiguos.*AFTER UPDATE'):
        init_db(engine, allow_review_nullable_migration=True)
    assert snapshot(engine) == before
    with engine.connect() as c:
        assert c.exec_driver_sql('SELECT type,name,sql FROM sqlite_schema ORDER BY type,name').all() == schema
        assert c.exec_driver_sql('PRAGMA foreign_key_check').all() == []
        assert c.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1


def test_distinct_trigger_events_are_preserved(engine):
    prepare_legacy(engine)
    with engine.begin() as c:
        c.exec_driver_sql('CREATE TRIGGER other_trigger BEFORE INSERT ON reviews BEGIN SELECT 1; END')
        triggers = c.exec_driver_sql("SELECT name,sql FROM sqlite_schema WHERE type='trigger' AND tbl_name='reviews' ORDER BY name").all()
    init_db(engine, allow_review_nullable_migration=True)
    with engine.connect() as c:
        assert c.exec_driver_sql("SELECT name,sql FROM sqlite_schema WHERE type='trigger' AND tbl_name='reviews' ORDER BY name").all() == triggers
        assert c.exec_driver_sql('PRAGMA foreign_key_check').all() == []


def test_unrecognized_trigger_header_fails_closed(engine):
    prepare_legacy(engine)
    with engine.begin() as c:
        c.exec_driver_sql('CREATE TRIGGER strange /* no se analiza */ BEFORE INSERT ON reviews BEGIN SELECT 1; END')
    before = snapshot(engine)
    with pytest.raises(RuntimeError, match='trigger SQLite.*revisión'):
        init_db(engine, allow_review_nullable_migration=True)
    assert snapshot(engine) == before


@pytest.mark.parametrize('first,second', [
    ('BEFORE INSERT', 'INSERT'),
    ('AFTER UPDATE OF fuente', 'AFTER UPDATE OF contenido'),
])
def test_equivalent_trigger_event_and_timing_are_ambiguous(engine, first, second):
    prepare_legacy(engine)
    with engine.begin() as c:
        c.exec_driver_sql('DROP TRIGGER hu24_review_trigger')
        c.exec_driver_sql(f'CREATE TRIGGER a {first} ON reviews BEGIN SELECT 1; END')
        c.exec_driver_sql(f'CREATE TRIGGER b {second} ON reviews BEGIN SELECT 1; END')
    before = snapshot(engine)
    with pytest.raises(RuntimeError, match='Triggers SQLite ambiguos'):
        init_db(engine, allow_review_nullable_migration=True)
    assert snapshot(engine) == before


def test_temporary_trigger_fails_closed(engine):
    prepare_legacy(engine)
    with engine.connect() as c:
        c.exec_driver_sql('CREATE TEMP TRIGGER temp_review AFTER UPDATE ON reviews BEGIN SELECT 1; END')
        c.commit()
    before = snapshot(engine)
    with pytest.raises(RuntimeError, match='trigger temporal'):
        init_db(engine, allow_review_nullable_migration=True)
    assert snapshot(engine) == before


def test_router_read_serializes_null_and_scopes_tenant(engine):
    with Session(engine) as db:
        db.add_all([Tenant(id=10, nombre='A', estado='activo'), Tenant(id=20, nombre='B', estado='activo')])
        db.add_all([
            Review(id=1, tenant_id=10, autor=None, contenido='A', fecha=None, puntuacion=None, fuente='manual', estado='nueva'),
            Review(id=2, tenant_id=20, autor=None, contenido='B', fecha=None, puntuacion=None, fuente='CSV', estado='nueva'),
        ])
        db.commit()
        payload = list_reviews(db=db, tenant_id=10).model_dump(mode='json')
        assert [row['id'] for row in payload['items']] == [1]
        assert all(payload['items'][0][field] is None for field in ('autor', 'fecha', 'puntuacion'))
