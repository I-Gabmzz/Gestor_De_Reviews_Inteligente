# HU-24 / T2 — Persistencia y migración de datos opcionales

Estado: cambios locales para revisión, sin commit ni despliegue. Base inicial: `61054513c6b98815b894e74506342cde1b62856d`. Según el responsable, T1 fue compartida y cerrada en OpenProject. No se modificó OpenProject ni se migró una base real.

## Alcance

`Review.fecha` y `Review.puntuacion` pasan de NOT NULL a NULL en bases nuevas; `autor` sigue admitiendo NULL. `contenido`, `fuente`, `estado` y `tenant_id` conservan NOT NULL. No se modifica el rango, ni se agrega CHECK. `ReviewRead` serializa valores ausentes como `null`. La entrada del registro manual, la edición y la importación conservan sus validaciones actuales; no se alteran fuentes, estados, datos históricos ni contratos de ingreso externo.

## Autorización y arranque

La auditoría encontró que una base existente podía transformarse al arrancar FastAPI sin autorización específica. El proyecto configura el entorno mediante `pydantic-settings`; se añadió `HU24_ALLOW_REVIEW_NULLABLE_MIGRATION`, booleano con valor predeterminado `false`, independientemente de `ENV` y del motor. La opción figura desactivada en `backend/.env.example`.

- Base nueva: `init_db` crea el esquema actualizado sin autorización.
- Base ya actualizada: se inicializa y se repite sin autorización.
- Base anterior con alguna de las dos columnas NOT NULL: por defecto se detiene con un error de autorización antes de ejecutar DDL o cambiar datos. Como FastAPI llama a `init_db()` en su ciclo de vida, el servicio no completa el arranque.
- Para una migración autorizada, establecer temporalmente `HU24_ALLOW_REVIEW_NULLABLE_MIGRATION=true` en el proceso que inicializa la base elegida. La opción habilita el intento: no omite validaciones, bloqueos, comprobaciones de integridad ni la revisión de triggers. Retirarla o volverla `false` después de confirmar la migración. También puede usarse `init_db(engine, allow_review_nullable_migration=True)` para pruebas o una invocación dirigida; el argumento tiene prioridad sobre la configuración. `False` deniega aunque la variable esté activa.

La autorización se comprueba bajo el bloqueo de inicialización y antes del DDL. La función de migración también exige autorización explícita. Con SQLite se inspecciona inicialmente la necesidad para decidir si desactivar FK en esa conexión y se vuelve a comprobar bajo `BEGIN IMMEDIATE`; PostgreSQL usa el bloqueo advisory existente. Las comprobaciones solo coordinan inicializadores que las utilizan, no sustituyen una ventana operativa ni el control de otros procesos.

## Migración y respaldo

Se reutiliza el inicializador existente sin Alembic ni dependencias nuevas. PostgreSQL utiliza `ALTER COLUMN ... DROP NOT NULL` únicamente para las columnas que lo necesitan, dentro de la transacción y bloqueo existentes; no elimina otras restricciones. **No se ha ejecutado ni validado en un servidor PostgreSQL real.** Un CHECK que mencione fecha o puntuación se rechaza para revisión.

SQLite desactiva temporalmente las FK en su conexión antes de la transacción, adquiere `BEGIN IMMEDIATE`, copia filas, recrea la tabla a partir del DDL original quitando los NOT NULL reconocidos, restaura datos e índices/triggers y ejecuta `foreign_key_check`. El estado previo de FK se restablece incluso ante error. La transacción revierte los errores probados. Se rechazan definiciones ambiguas, `AUTOINCREMENT`, columnas generadas, CHECK sobre las columnas y esquemas que no se reconozcan. No se reconstruyen las tablas hijas.

Antes de autorizar una base real, seleccionar explícitamente la base, detener o coordinar sus procesos, tomar una copia consistente y verificar su restauración en un entorno aislado. Para SQLite considerar WAL y utilizar el respaldo consistente del motor o detener escritores; para PostgreSQL ensayar el respaldo/restauración y bloqueo en una instancia autorizada. Probar migración y restauración en la copia, verificar datos, recuentos, índices, relaciones y `foreign_key_check`; acordar ventana y restauración de la copia completa ante fallo. No existe downgrade automático que invente fechas o puntuaciones. La autorización técnica no verifica que exista un respaldo ni sustituye este procedimiento.

## Triggers SQLite

La auditoría reprodujo que recrear triggers por nombre podía invertir su orden observado (`AZ` frente a `ZA`). SQLite no garantiza el orden entre triggers equivalentes. Antes de cualquier DDL, y de nuevo dentro de la migración, se inspeccionan los triggers persistentes asociados a `reviews`: se reconocen de forma conservadora sus cabeceras y se rechazan dos o más del mismo momento y evento, incluyendo `UPDATE OF` y el `BEFORE` implícito. Los triggers de eventos o momentos distintos admitidos se conservan. No se reordena para prometer un comportamiento que SQLite no garantiza.

También se rechaza un trigger temporal de `reviews` visible en la conexión de migración y cualquier cabecera no reconocida. La inspección no puede observar triggers TEMP privados de otras conexiones; cerrar o coordinar todas las conexiones antes de migrar. El guard no demuestra ausencia de dependencias semánticas complejas entre triggers de distintos eventos o tablas; revisar los esquemas personalizados y probarlos sobre una copia. Los esquemas no admitidos requieren intervención manual, no se eliminan triggers para continuar.

## Verificación

Pruebas ejecutadas desde `backend/`, con el entorno virtual existente de Sprint 3, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUTF8=1`, `DATABASE_URL=sqlite://`, autorización global desactivada y bases temporales aisladas. Los fixtures heredados de migración autorizan únicamente sus propias bases sintéticas. No se instalaron dependencias.

```text
python -m pytest tests/test_hu24_nullable_migration.py tests/test_external_review_migrations.py tests/test_ai_persistence.py::test_migration_preserves_legacy_rows_columns_indexes_and_foreign_keys tests/test_ai_persistence.py::test_migration_completes_partial_upgrade_without_replacing_results tests/test_ai_persistence.py::test_simultaneous_startups_serialize_sqlite_migration tests/test_review_schema.py tests/test_review_service.py tests/test_external_review_persistence.py tests/postgres/test_hu24_nullable_postgres.py -q -p no:cacheprovider --basetemp ..\.hu24-t2-regression-final
262 passed, 1 skipped, 94 warnings in 18.75s
```

El ejecutable fue `C:\Users\joser\Documents\GestorDeReviews_Sprint3\backend\.venv\Scripts\python.exe`. La omisión corresponde a PostgreSQL sin `TEST_POSTGRES_URL`; las advertencias son de deprecación de FastAPI. La prueba de PostgreSQL está preparada para el fixture de esquema aislado, pero no es evidencia de ejecución real.

Se comprobaron bases nuevas, antiguas sin autorización y con ella, ya actualizadas y migración repetida; configuración, ciclo de vida de FastAPI mediante invocación directa, persistencia y serialización de NULL, dos tenants, datos históricos, resultados IA, identidad externa, notificaciones, FK e índices. La reproducción sintética AZ/ZA verifica el cambio de orden, el rechazo de la migración y la conservación de esquema y filas; también se prueban triggers de eventos distintos, no reconocidos y temporales, y rollback ante un fallo inyectado. La prueba de ciclo de vida no es una prueba HTTP completa ni una simulación de caída del sistema.

Una ejecución ampliada anterior que incluyó toda la suite de persistencia IA se interrumpió al quedar detenida; no se declara aprobada. En la auditoría previa también se interrumpió la suite completa al quedar detenida en este entorno. No se presentan esas ejecuciones como aprobadas. Quedan pendientes la regresión HTTP completa, pruebas de interrupción real y PostgreSQL autorizado.

## Archivos y dependencias pendientes

- `backend/app/core/config.py`, `backend/.env.example`: autorización desactivada por defecto.
- `backend/app/db/init_db.py`, `backend/app/db/migrations.py`: comprobación previa, controles de triggers y migración.
- `backend/app/models/review.py`, `backend/app/schemas/review.py`: nullabilidad y respuesta.
- `backend/tests/test_hu24_nullable_migration.py`, `backend/tests/postgres/test_hu24_nullable_postgres.py`: casos de T2; fixtures sintéticos de `test_external_review_migrations.py` y `test_ai_persistence.py` autorizan la migración que ya probaban.
- `docs/hu-24/t2-persistencia-migraciones.md`: esta evidencia.

T3 debe acordar y adaptar alta y edición para ausencias sin valores ficticios. Dashboard, exportación y componentes visuales aún presuponen fecha o puntuación; los filtros y el orden de NULL no se cambiaron. Coordinar T3/T4 y HU-23 antes de habilitar registros incompletos en un entorno compartido; HU-22 también consume detalle. Persisten las decisiones de T1 sobre `manual`/«Manual», así como la validación de PostgreSQL, rendimiento y recuperación ante caída.
