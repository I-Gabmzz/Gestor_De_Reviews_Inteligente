# T3 — Contrato común y persistencia de resultados de IA

Tarea [#3562](https://computacion.mxl.uabc.mx/openproject/work_packages/3562), HU-13. Implementada el 17 de octubre de 2026 en `feature/HU-13-clasificacion`, dentro del [PR #22](https://github.com/I-Gabmzz/Gestor_De_Reviews_Inteligente/pull/22).

## Contrato compartido

Cada review conserva una sola columna por resultado. No se añade otra tabla ni se duplica `categoria`.

| Campo | Almacenamiento | Salida del proveedor validada | Responsable de generación |
| --- | --- | --- | --- |
| `categoria` | `VARCHAR(50) NULL`, existente | `ClassificationResult`: Queja, Sugerencia, Felicitación o Consulta, exactas | David, HU-13 |
| `resumen` | `TEXT NULL`, nueva | `SummaryResult`: texto no vacío | Francisco, HU-14 |
| `tema` | `TEXT NULL`, nueva | `TopicResult`: texto no vacío | Diego, HU-15 |

Los tres modelos están en [`backend/app/schemas/ai.py`](../../backend/app/schemas/ai.py), heredan `AIResponse`, rechazan tipos incorrectos y propiedades adicionales. Los resultados de resumen/tema no aceptan cadenas compuestas solo de espacios. La validez estructural no garantiza fidelidad ni corrección semántica.

Los límites de 400/60 caracteres y las reglas de 1–2 frases/1–3 palabras siguen siendo propuestas para las tareas de definición de HU-14/HU-15. La persistencia usa `TEXT` para no imponer un catálogo o longitud todavía no confirmados. Sus responsables pueden añadir validaciones funcionales antes de guardar, reutilizando el contrato común.

`ReviewRead` añade `resumen` y `tema` opcionales a los campos anteriores. `GET /api/v1/reviews` y `GET /api/v1/reviews/{id}` los devuelven, inicialmente `null`. Las respuestas existentes que ya usan `ReviewRead`, como registro, edición y cambio de estado, también los incluyen. No se altera el contrato separado del dashboard.

Las categorías antiguas se leen sin reclasificarlas: `ReviewRead.categoria` conserva su tipo previo. El catálogo exacto se exige para nuevas escrituras de IA. Las reviews nuevas manuales/importadas siguen con resultados `null`.

## Escritura interna para las tres historias

El adaptador de T2 acepta estos modelos mediante `response_model`. El script de comprobación de T2 ahora los reutiliza; su evidencia histórica conserva las salidas y schemas originales.

```python
from app.schemas.ai import ClassificationResult

# El servicio obtiene tenant_id del contexto autenticado y verifica la review
# antes de llamar al proveedor. Instrucciones y reglas pertenecen a cada HU.
result = provider.generate_structured(
    review.contenido,
    instructions=instructions,
    response_model=ClassificationResult,
)
saved = repository.save_ai_result(review.id, tenant_id, result)
```

[`ReviewRepository.save_ai_result(review_id, tenant_id, result)`](../../backend/app/repositories/review_repository.py) admite exclusivamente las tres clases concretas del contrato. Revalida antes de escribir y actualiza solo la columna del resultado, con condiciones de `id` y `tenant_id`. Confirmada la transacción, devuelve la review refrescada. Una review inexistente o ajena devuelve `None` en ambos casos; el servicio lo traduce a su error habitual sin revelar existencia. Un fallo SQL revierte la transacción y se propaga para el tratamiento de la capa de aplicación.

Regenerar un resumen conserva categoría, tema, estado, prioridad y datos originales. Dos sesiones que guardan operaciones diferentes conservan ambos resultados; no se envía una copia completa de la review al `UPDATE`. Si se regenera el mismo campo, prevalece la última escritura confirmada. El método no realiza llamadas a IA ni decide permisos de roles: esas comprobaciones corresponden a los servicios/endpoints posteriores.

T4 añade el parámetro opcional `expected_content`: cuando se proporciona, el `UPDATE` exige que el contenido siga siendo el analizado. Un cambio de contenido durante la llamada también devuelve `None`, sin escritura, y el servicio lo traduce a conflicto. Los llamadores de T3 que no proporcionan ese parámetro conservan el contrato anterior.

`ReviewManualCreate` y `ReviewUpdate` rechazan `categoria`, `resumen` y `tema` con HTTP 422, incluso junto con un cambio permitido; no se guarda parcialmente la petición. El cambio de estado solo acepta `estado`. No se añade una ruta pública para escribir resultados arbitrarios.

## Actualización de bases existentes

[`init_db`](../../backend/app/db/init_db.py), usado al iniciar FastAPI y por el seed existente, crea las tablas nuevas y llama a una única [migración aditiva](../../backend/app/db/migrations.py). Inspecciona `reviews` y añade solo `resumen` y/o `tema` ausentes con `ALTER TABLE ... ADD COLUMN ... TEXT`. No elimina tablas, reconstruye filas ni modifica campos previos. Una actualización parcial conserva los resultados ya existentes; repetir el inicio no vuelve a añadir columnas.

SQLAlchemy indica que [`create_all` no modifica tablas existentes](https://docs.sqlalchemy.org/en/20/core/metadata.html#creating-and-dropping-database-tables). Por eso se añade esta actualización explícita, sin incorporar una dependencia nueva. Es una migración acotada a estas dos columnas, no un sistema general para cambios destructivos de esquema.

La creación e inspección se serializan: SQLite usa `BEGIN IMMEDIATE`; PostgreSQL usa un bloqueo asesor de transacción común antes del DDL. Los errores de migración detienen el inicio en vez de ocultar un esquema incompleto. Se verificó SQLite, incluido inicio simultáneo; no se ejecutó una instancia PostgreSQL y su validación operativa sigue pendiente.

Para actualizar una base existente del equipo:

1. Detener el backend y conservar una copia de la base. En SQLite, usar una copia consistente con el proceso detenido o la API de backup de SQLite.
2. Traer la rama de HU-13 y confirmar que `DATABASE_URL` apunta a la base deseada; no subir `.env` ni bases al repositorio.
3. Desde `backend`, activar el entorno y ejecutar `python -c "from app.db.init_db import init_db; init_db()"`, o iniciar FastAPI normalmente.
4. Comprobar las reviews anteriores por GET. Sus campos previos se conservan y los resultados nuevos empiezan en `null`.

Francisco y Diego reutilizan esta migración y los modelos; no necesitan crear columnas adicionales para sus historias. El PR sigue abierto para revisión: la publicación del contrato no implica que el equipo ya lo haya integrado o aceptado.

## Validación y límites

[`test_ai_persistence.py`](../../backend/tests/test_ai_persistence.py) comprueba base nueva y antigua, conservación de todos los valores previos, índices y claves foráneas, repetición y actualización parcial, inicio simultáneo, escritura independiente y regeneración, lectura en sesión nueva, aislamiento por tenant, sesión desactualizada, rollback, validación y protección HTTP. Las pruebas de edición existentes también contienen resultados reales de prueba en los tres campos protegidos.

La fixture HTTP dirige tanto las dependencias como el arranque de FastAPI a su base temporal. Ejecutar la suite no migra ni escribe la base local de desarrollo.

Resultado del 17 de octubre: **459 pruebas aprobadas**. Una copia temporal de la base local también conservó sus cinco reviews y todos los datos de usuarios/tenant tras dos ejecuciones de la migración. Ver [reporte de validación y límites](validacion-t3-2026-10-17.md).

T3 no implementa los servicios de generación ni sus endpoints, interfaz o aceptación semántica. No requiere nuevas llamadas al proveedor. Editar el contenido mantiene la política anterior y conserva los resultados existentes; antes de integrar el flujo completo, el equipo debe resolver cómo invalidar o señalar análisis desactualizados. No se introduce una política distinta sin acuerdo.
