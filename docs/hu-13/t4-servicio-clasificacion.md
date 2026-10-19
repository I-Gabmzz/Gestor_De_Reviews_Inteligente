# T4 — Servicio de clasificación automática

Tarea [#3563](https://computacion.mxl.uabc.mx/openproject/work_packages/3563), HU-13. Implementación en `feature/HU-13-clasificacion`, dentro del [PR #22](https://github.com/I-Gabmzz/Gestor_De_Reviews_Inteligente/pull/22).

## Operación disponible

[`ClassificationService.classify(review_id, tenant_id)`](../../backend/app/services/classification_service.py) procesa una review existente y devuelve el modelo `Review` con su categoría confirmada en la base de datos.

1. Consulta la review mediante `get_by_id_for_tenant`; inexistente y ajena producen el mismo `ReviewNotFoundError`, antes de crear el proveedor.
2. Rechaza contenido vacío o formado solo por espacios sin llamar a IA.
3. Crea el adaptador común de T2 y envía exclusivamente el contenido original como datos. No envía nombre del autor, tenant, puntuación ni resultados anteriores.
4. Aplica las instrucciones de intención principal y casos mixtos de T1: Queja, Sugerencia, Felicitación o Consulta. Un elogio accesorio no desplaza una queja; una petición de mejora en forma de pregunta sigue siendo sugerencia. Solo ante empate real se usa Queja > Sugerencia > Consulta > Felicitación.
5. Revalida la decisión y construye el `ClassificationResult` común de T3. Guarda únicamente `categoria`, conservando estado, prioridad, resumen, tema y datos originales.

La construcción del servicio no carga la clave ni abre conexiones. La fábrica del proveedor es inyectable para pruebas y se ejecuta después de comprobar pertenencia y contenido. El adaptador se cierra mediante contexto tanto ante éxito como ante errores de generación.

```python
from app.repositories.review_repository import ReviewRepository
from app.services.classification_service import ClassificationService

# tenant_id se obtiene del contexto autenticado y autorizado en T5.
service = ClassificationService(ReviewRepository(db))
review = service.classify(review_id, tenant_id)
```

T4 es un servicio interno. El endpoint, los controles de rol/usuario/tenant activo y el mapeo de errores HTTP se implementan en T5; este método no sustituye esas comprobaciones.

## Contenido no analizable y salida válida

El catálogo persistido mantiene exactamente las cuatro categorías de T1. Para poder rechazar contenido sin intención interpretable, la salida **interna** del proveedor usa [`ClassificationDecision`](../../backend/app/schemas/classification.py): campo obligatorio `categoria`, con una categoría del catálogo o `null`, sin propiedades adicionales. `null` produce `ClassificationContentError`; nunca se guarda ni se interpreta como quinta categoría.

La salida exitosa y el modelo de escritura siguen siendo `{"categoria":"Queja"}` conforme a `ClassificationResult`. Una propiedad ausente, categoría desconocida, tipo incorrecto o campo adicional es respuesta inválida. La decisión también se revalida en el servicio para no depender de una instancia construida sin validación por otro adaptador.

La señal `null` concreta el rechazo previsto en T1; no cambia la clasificación anterior. Determinar que un texto tiene intención interpretable sigue dependiendo del modelo y requiere ampliar los ejemplos de aceptación. El caso sintético probado no garantiza rechazo correcto de cualquier texto ambiguo.

## Persistencia y errores

El repositorio incorpora `expected_content` opcional. T4 guarda mediante un `UPDATE` condicionado por id, tenant y el contenido exacto enviado al proveedor. Si durante la llamada cambia el contenido, se mueve la review de tenant o se elimina, no se guarda una clasificación para el registro anterior: se devuelve `ClassificationConflictError`. Actualizaciones de resumen/tema realizadas por otra operación se conservan.

| Situación | Resultado del servicio |
| --- | --- |
| Review inexistente o ajena | `ReviewNotFoundError`; sin llamada a IA |
| Contenido vacío o decisión interna `null` | `ClassificationContentError`, código `not_analyzable`; sin escritura |
| JSON/categoría/estructura inválidos | `AIInvalidResponseError`; sin escritura |
| Credenciales, cuota, red, timeout o bloqueo | Error controlado del adaptador de T2; conserva valores previos |
| Cambio o desaparición de la review durante el análisis | `ClassificationConflictError`, código `review_changed`; sin guardar resultado obsoleto |
| Fallo de consulta o escritura SQL | `ClassificationPersistenceError`, código `persistence`; no expone detalles de SQL ni credenciales. El repositorio revierte la escritura fallida. |

No se añaden reintentos automáticos ni una clasificación de respaldo aparente. El control de contenido durante la llamada no invalida análisis que queden antiguos por una edición posterior; esa política sigue pendiente de acuerdo del equipo.

## Validación realizada

Suite completa del 17 de octubre de 2026: **495 pruebas aprobadas**, incluidas **36 nuevas** en [`test_classification_service.py`](../../backend/tests/test_classification_service.py). Se conserva el aviso de deprecación de Starlette/TestClient ya presente. Los tests del servicio usan el adaptador HTTPX real con transporte simulado y SQLite temporal para comprobar resultados, fallos, aislamiento, carreras con edición/tenant/eliminación, conservación de otras operaciones y rollback.

La [comprobación con Gemini](evidencia-servicio-t4-2026-10-17.json) del 17 de octubre a las 14:28, hora de Tijuana, ejecutó el servicio con siete reseñas ficticias en SQLite temporal: **7/7 resultados esperados**. Se verificaron cuatro categorías, dos casos mixtos y rechazo de texto no interpretable. Cada resultado se leyó en una sesión nueva y conservó todos los campos ajenos a categoría; el rechazo conservó la categoría anterior. Una review de otro tenant también permaneció intacta. No se modificó la base local de desarrollo.

Para repetir la comprobación, usar una ruta nueva de evidencia y la clave privada del backend:

```bash
backend/.venv/bin/python backend/scripts/verify_gemini_t4.py
```

Cada ejecución consume cuota. El script rechaza sobrescribir evidencia anterior, no imprime credenciales y detiene las llamadas ante un error del proveedor. Esta muestra pequeña acredita el flujo servicio → proveedor → validación → persistencia; no es una medición general de precisión ni prueba del endpoint o interfaz. La base verificada es SQLite; PostgreSQL continúa pendiente de validación operativa.
