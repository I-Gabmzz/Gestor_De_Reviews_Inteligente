# HU-18 / T3 #3818 — API segura y persistencia de respuesta sugerida

**Estado: implementada y probada con proveedor simulado; pendiente de revisión y autorización para commit.** No se inicia frontend, T4 ni T5.

Responsable: Diego Erik Alfonso Montoya. Rama: `feature/HU-18-respuesta-sugerida`. Base: `604a255d5c4fa9b33dc444101ec40996209dee50`. Se conservan sin cambios el [contrato aprobado de T1](contrato-respuesta-sugerida.md), el [servicio y schema de T2](t2-servicio-respuesta-sugerida.md) y su evidencia original. La aprobación de las tareas anteriores no se presenta como aprobación de T3.

## Arquitectura implementada

```text
POST autenticado
  -> require_tenant_roles
  -> SuggestedResponseAnalysisService
  -> ReviewRepository.get_by_id_for_tenant
  -> SuggestedResponseService.generate (T2)
  -> proveedor IA compartido y validación de T2
  -> ReviewRepository.save_suggested_response
  -> ReviewRead
```

El nuevo coordinador obtiene contenido y versión desde la base autorizada; el cliente no aporta texto para generar, tenant ni un resultado. T2 sigue siendo un servicio sin base de datos. No se duplican su configuración, transporte, minimización o reglas de generación, ni se ejecutan otras operaciones IA como dependencia.

## Contrato HTTP y consulta posterior

- Endpoint: `POST /api/v1/reviews/{review_id}/respuesta-sugerida`.
- `review_id` entero positivo. Autenticación Bearer oficial; cuerpo omitido o `{}`.
- `SuggestedResponseRequest` prohíbe propiedades adicionales: se rechazan contenido, resultado, tenant, estado, publicación y versión suministrados en el body.
- Los query parameters desconocidos no seleccionan el negocio; en particular `tenant_id` no forma parte del contrato. Se probó que su envío manual no permite cambiar el ámbito autenticado.
- Éxito: 200 y `ReviewRead` con `respuesta_sugerida: string | null`. La generación exitosa persiste texto válido. `null` expresa ausencia/invalidez posterior de un resultado almacenado, no una generación exitosa vacía.
- `GET /api/v1/reviews/{review_id}` y el listado existente recuperan el campo; no se crea un GET paralelo. El contador interno no aparece en `ReviewRead` ni se acepta en solicitudes.
- La API devuelve un borrador almacenado: no equivale a publicación, envío ni modificación de seguimiento. La visualización de solo lectura pertenece a T4, aún sin implementar.

## Autorización y aislamiento

Se reutiliza `require_tenant_roles("usuario_negocio", "admin_tenant")`, sin cambiar sus reglas ni las de otros endpoints. El rol, usuario y tenant activo se verifican desde la identidad vigente en servidor; `admin_general` no obtiene acceso global a reviews. La consulta inicial restringe por id y tenant antes de llamar a IA. Review ajena e inexistente dan 404, sin consumir el proveedor.

La escritura vuelve a restringir por id y tenant, además del contenido y versión analizados. La lectura posterior mantiene la autorización existente. Las pruebas cubren los dos roles permitidos, usuario inactivo, tenant inactivo, cambio de rol después de emitir el token, 401, administración general denegada, aislamiento A hacia B y B hacia A y parámetros de autoridad rechazados o ignorados de forma segura.

## Modelo, persistencia y evolución del esquema

Se incorporan a `Review`:

| Columna | Definición | Uso |
| --- | --- | --- |
| `respuesta_sugerida` | `TEXT NULL` | Última sugerencia válida; no hay tabla o historial de borradores. |
| `respuesta_sugerida_version` | `INTEGER NOT NULL DEFAULT 0` | Revisión interna para concurrencia; no contiene textos anteriores ni se expone a clientes. |

`save_suggested_response` admite exclusivamente `SuggestedResponseResult`, revalida sus datos y ejecuta una actualización condicionada por id, tenant, contenido original y versión. Solo modifica la sugerencia y su contador interno; no cambia `Review.estado`, categoría, resumen, tema, prioridad ni datos originales. Un commit fallido hace rollback.

Se añadió una operación específica en el repositorio existente en lugar de ampliar `AIResult` y `save_ai_result()`: estos conservan su comportamiento y los tipos actuales. Evita dependencias circulares con el schema de T2 y limita solapamientos con HU-16. Los resultados existentes y la prioridad almacenada permanecen compatibles; no se trae código de HU-16 a esta rama.

`add_suggested_response_columns` amplía el mecanismo aditivo de `migrations.py`; inspecciona columnas y añade solo las ausentes. `init_db` lo ejecuta bajo la transacción y serialización de inicialización ya existentes: `BEGIN IMMEDIATE` en SQLite y bloqueo asesor transaccional en PostgreSQL. Se preservan datos, índices, claves foráneas y resultados previos; repetir o completar una actualización parcial no sustituye valores existentes.

Agregar campos al modelo no se usa como sustituto de migrar tablas existentes. Al iniciar en el futuro el backend actualizado se aplicará esta evolución. **Durante estas validaciones solo se inicializaron bases SQLite temporales/en memoria; no se inició el servidor ni se migró la base local del equipo.**

## Invalidación al editar contenido

La auditoría encontró una ruta existente de edición de contenido, `PATCH /reviews/{review_id}`, que delega en `ReviewRepository.update`. Registro manual e importación crean nuevas reviews y no actualizan contenido previo. Se implementa la invalidación en el punto común del repositorio.

Cuando una escritura incluye contenido, un `CASE` SQL compara el texto entrante con el valor actual en base de datos. Si realmente difiere, la misma actualización limpia `respuesta_sugerida` e incrementa su versión. Esto evita basarse únicamente en una entidad ORM que pudiera estar desactualizada.

Si el texto normalizado es el mismo, no se invalida ni avanza el contador. Ediciones de autor, fuente, puntuación o fecha y cambios de estado conservan la sugerencia. La decisión de invalidar no borra clasificación, resumen, tema o prioridad y no ejecuta regeneración automática. Una nueva generación requiere siempre otra solicitud explícita.

Las escrituras SQL externas o cambios directos fuera de los repositorios de la aplicación no constituyen una ruta de edición soportada por este mecanismo. El contador no pretende ser un registro de auditoría de modificaciones.

## Regeneración y concurrencia

1. Leer el contenido exacto y la versión de la review autorizada.
2. Generar con T2, sin borrar la sugerencia anterior ni mantener un bloqueo de escritura durante la llamada al proveedor.
3. Ejecutar `UPDATE` solo si coinciden id, tenant, contenido y versión capturados; guardar el resultado válido e incrementar la versión en esa misma operación.
4. Si ninguna fila coincide, hacer rollback y devolver 409, sin sobrescribir la sugerencia actual. Puede significar edición, eliminación, traslado o regeneración concurrente.

Dos solicitudes que parten de la misma versión no pueden reemplazarse entre sí: gana la primera escritura que confirma; la otra recibe conflicto y debe consultar nuevamente antes de reintentar de forma explícita. Una solicitud iniciada tras esa escritura captura la nueva versión y puede regenerar normalmente. No se asigna prioridad por orden de llegada ni se promete que gane la última solicitud iniciada.

El contador también avanza si una generación devuelve el mismo texto anterior y si se cambia contenido para luego restaurarlo. Por ello una respuesta antigua no puede eludir el control solo porque el texto o sugerencia vuelva a coincidir. Las pruebas cubren esas carreras y sesiones ORM desactualizadas. No hay bloqueo global, cola, mecanismo distribuido ni historial de sugerencias; la condición atómica está en la base de datos.

Los errores de Gemini, rechazos y resultados inválidos no escriben. Un fallo de commit conserva el valor anterior y su versión mediante rollback. Si hay un fallo de comunicación o lectura posterior a una escritura confirmada, el cliente debe consultar el estado actual antes de repetir; no se introduce un reintento automático con resultados inciertos.

## Errores HTTP

| HTTP | Situación |
| --- | --- |
| 401 | Token ausente o inválido. |
| 403 | Rol/usuario/tenant no autorizado, incluidos usuario o tenant inactivos. |
| 404 | Review inexistente o no disponible para el tenant. |
| 409 | Cambió contenido, versión o disponibilidad de la review durante la generación. |
| 422 | Body o id incompatibles, contenido vacío/no analizable, rechazo por privacidad o bloqueo del proveedor. |
| 500 | Error controlado de acceso/persistencia. |
| 502 | Salida no válida o petición rechazada por el proveedor; error IA desconocido con mensaje saneado. |
| 503 | Configuración, credenciales del proveedor, cuota o indisponibilidad. |
| 504 | Timeout del proveedor. |

Se conserva `{"detail": "mensaje"}`. Los mensajes no incluyen claves, contenido privado ni detalles técnicos del proveedor o SQL. No se devuelve una sugerencia inventada para ocultar un fallo.

## Archivos afectados

Nuevos:

- `backend/app/api/routers/suggested_responses.py`.
- `backend/app/schemas/suggested_response_request.py`.
- `backend/app/services/suggested_response_analysis_service.py`.
- `backend/tests/test_suggested_response_api.py`.
- `backend/tests/test_suggested_response_persistence.py`.
- Este documento.

Modificados:

- `backend/app/api/routers/__init__.py`: registro de la ruta.
- `backend/app/models/review.py` y `backend/app/schemas/review.py`: almacenamiento y lectura.
- `backend/app/repositories/review_repository.py`: persistencia condicional e invalidación.
- `backend/app/db/init_db.py` y `backend/app/db/migrations.py`: evolución aditiva.
- `backend/tests/test_ai_persistence.py`, `test_reviews_api.py` y `test_review_status_api.py`: expectativas exactas ampliadas con las nuevas columnas/campo. Se conservan las comprobaciones previas y no se cambian las operaciones de otras HUs para hacer pasar pruebas.

HU-16 tiene trabajo remoto pendiente en el registro de routers, el repositorio, schemas IA y pruebas de persistencia, además del frontend. Se inspeccionó sin integrarlo. La implementación de HU-18 no modifica `schemas/ai.py` ni los tipos permitidos por `save_ai_result`; esos archivos compartidos deberán revisarse al integrar las ramas posteriormente. El fetch también descubrió una rama HU-17; no se cambia ni se incorpora a esta entrega.

## Pruebas y resultados reales

Todos los contenidos, usuarios y salidas usados son ficticios. La generación usa `httpx.MockTransport` o dobles inyectados. El comando de regresión sustituye los transportes HTTP reales de httpx por una función que falla ante cualquier intento de usarlos. No hubo llamadas reales a Gemini ni APIs de publicación.

| Validación ejecutada | Resultado |
| --- | --- |
| Primera ejecución de los dos archivos T3 con HTTP real bloqueado | 78 passed; antes de añadir tres casos de entrada vacía/sensible. |
| Primera suite backend completa con HTTP real bloqueado | 906 passed, 3 failed: el test parametrizado de estado todavía esperaba un JSON sin `respuesta_sugerida`. Los otros doce campos coincidían; se añadió únicamente el nuevo campo opcional a esa expectativa. |
| `python -m pytest -q tests/test_review_status_api.py tests/test_suggested_response_api.py tests/test_suggested_response_persistence.py` | 98 passed: 81 casos de T3 y 17 de cambio de estado. |
| Suite backend completa posterior con HTTP real bloqueado | **912 passed**, sin fallos; incluye las 92 pruebas de T2 y las regresiones de las otras HUs. |
| `python -m compileall -q app tests/test_suggested_response_api.py tests/test_suggested_response_persistence.py` | OK. |

Ambas suites completas mostraron los dos avisos de deprecación conocidos de Starlette/httpx/anyio. No se ocultaron fallos ni se eliminaron pruebas. El comando con bloqueo de red se ejecutó en memoria desde `backend`, mediante `python -c`, con este contenido:

```python
import httpx
import pytest
from unittest.mock import patch

def deny_real_http(*args, **kwargs):
    raise AssertionError('HTTP real bloqueado durante la regresión HU-18/T3')

with patch.object(httpx.HTTPTransport, 'handle_request', deny_real_http), patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', deny_real_http):
    raise SystemExit(pytest.main(['-q']))
```

Los casos T3 comprueban generación, GET/listado y sesión posterior, regeneración, persistencia de otros campos, versiones, rollback, entradas controladas por servidor, roles, autorización previa a IA, aislamiento en ambos sentidos, id inválido, errores HTTP, resultado inválido, privacidad, OpenAPI e inexistencia de parámetros de tenant. La concurrencia se comprueba con dos sesiones y también con dos generaciones simultáneas sincronizadas mediante una barrera.

SQLite: base nueva, anterior, actualización parcial, repetición de inicialización, inicialización concurrente, conservación de datos/índices/claves y operaciones reales de escritura condicional. PostgreSQL: se compilaron las definiciones de columna y las expresiones SQL reales de guardado e invalidación para ese dialecto. **No se ejecutó PostgreSQL real**; su validación operativa queda pendiente.

No hay pruebas de fidelidad semántica nuevas con Gemini real. Las limitaciones de minimización y validación de T2 permanecen; esta tarea verifica integración segura, no elimina por sí sola sus falsos positivos o datos personales no reconocidos. No se modificó frontend ni se hizo una validación UI de T4/T5.

## Entrega y revisión

T3 queda preparada para revisión técnica y posterior autorización de commit. No se hace staging, commit, push, PR ni cambios en OpenProject. El endpoint genera y conserva únicamente un borrador: no envía correos, mensajes o respuestas a plataformas, no cambia el seguimiento y no llama automáticamente otras operaciones IA. La implementación del frontend y la validación funcional final requieren autorización separada.
