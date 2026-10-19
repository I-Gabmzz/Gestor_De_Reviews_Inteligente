# T5 — Endpoint de clasificación autorizado

Tarea [#3564](https://computacion.mxl.uabc.mx/openproject/work_packages/3564), HU-13. Rama `feature/HU-13-clasificacion`, dentro del [PR #22](https://github.com/I-Gabmzz/Gestor_De_Reviews_Inteligente/pull/22).

## Contrato para la integración del frontend

```http
POST /api/v1/reviews/{review_id}/clasificacion
Authorization: Bearer <token_de_la_sesion>
```

No requiere cuerpo. También admite `{}` o JSON `null`; no admite propiedades editables. Un `review_id` debe ser entero positivo. El servidor obtiene el contenido de la review guardada y el tenant del usuario autenticado. Enviar `tenant_id`, `contenido`, `categoria`, `review_id`, `resumen` o `tema` en el cuerpo produce 422 antes de llamar a IA. Un parámetro de consulta `tenant_id` no modifica el ámbito autenticado y no forma parte del contrato.

**Respuesta 200:** `ReviewRead` completo con `categoria` persistida. Incluye los datos anteriores y `resumen`/`tema`. La categoría es exactamente Queja, Sugerencia, Felicitación o Consulta. El posterior `GET /api/v1/reviews/{review_id}` permite recuperar el mismo resultado.

El endpoint llama a [`ClassificationService`](../../backend/app/services/classification_service.py) de T4 y conserva estado, prioridad, resumen, tema y datos originales. Repetir POST regenera solo la categoría y puede consumir cuota otra vez. No se añaden reintentos automáticos ni una operación que ejecute los tres análisis de IA.

Para HU-13/T6, Diego puede consumir este POST con el token existente y sustituir la review de la vista por la respuesta confirmada; mostrar carga y el mensaje `detail` si hay error. La implementación de ese botón y su comportamiento visual corresponden a T6. José dispone del contrato y los errores para T7.

## Autenticación y autorización

[`reviews.py`](../../backend/app/api/routers/reviews.py) usa las dependencias reutilizables ya implementadas en HU-04/T3, siguiendo la [matriz de permisos](../hu-04/matriz-permisos-t2.md) y el ámbito operativo de reviews:

| Actor | Resultado |
| --- | --- |
| `usuario_negocio` activo, tenant activo, review propia | Puede clasificar |
| `admin_tenant` activo, tenant activo, review propia | Puede clasificar |
| `admin_general` | 403; no obtiene acceso global a reviews |
| Usuario o tenant inactivo, incluso con token previo | 403 |
| Token ausente, incorrecto o cuenta inexistente | 401 |
| Review ajena o inexistente | 404 con el mismo formato; sin llamada a IA |

El rol, estado y tenant se leen del usuario vigente en base de datos. Los atributos de autoridad de un token o del cliente no sustituyen ese registro. La pertenencia de la review se comprueba antes de crear el proveedor. La nueva ruta aplica estos controles por sí misma; no se considera terminada la aplicación de permisos a otras rutas de HU-04/T4.

## Errores HTTP

Todos los errores de aplicación usan `{"detail":"mensaje"}` sin claves, tokens, SQL ni cuerpo técnico del proveedor. Los errores de validación propios de FastAPI conservan su formato 422 habitual.

| HTTP | Situación |
| --- | --- |
| 401 | Token ausente/inválido o cuenta no encontrada; incluye `WWW-Authenticate: Bearer` |
| 403 | Usuario inactivo, tenant inactivo o rol sin ámbito autorizado |
| 404 | Review inexistente o ajena |
| 409 | El contenido, pertenencia o existencia de la review cambió durante el análisis |
| 422 | Id/cuerpo inválido, contenido vacío, no analizable o bloqueo de contenido |
| 500 | No pudo completarse la consulta/escritura de persistencia |
| 502 | Salida inválida o solicitud rechazada por el proveedor; error de IA desconocido con mensaje genérico seguro |
| 503 | Clave/configuración ausente o rechazada, cuota agotada o proveedor indisponible |
| 504 | Timeout del proveedor |

Una credencial de Gemini rechazada produce 503, no un error de autorización del usuario. Las funciones generales de la aplicación siguen disponibles si falta configuración de IA. Ante un fallo no se reemplaza la categoría previa por una aparente; T4/T3 controlan validación, escritura y rollback.

La documentación OpenAPI incorpora la operación, autenticación Bearer, cuerpo opcional sin campos, respuesta `ReviewRead` y estos códigos. No expone las credenciales del proveedor.

## Validación

[`test_classification_api.py`](../../backend/tests/test_classification_api.py) contiene **42 casos nuevos** sobre peticiones HTTP, usando autenticación real y SQLite temporal. Cubre los dos roles permitidos, regeneración, lectura posterior, ausencia/invalidez de token, rol general, usuario/tenant inactivo, token con tenant suplantado, aislamiento, campos de cuerpo rechazados, ids inválidos, mapeo de errores, respuesta inválida/no analizable, cuota, configuración ausente y conflicto por edición concurrente.

La suite completa del 17 de octubre de 2026 aprobó **537 pruebas**, sin fallos ni omisiones, en 37.92 segundos. Permanece el aviso de deprecación de Starlette/TestClient ya observado en T4. También se verificaron importación de FastAPI, OpenAPI, sintaxis, enlaces locales y diff sin errores.

La [evidencia HTTP con Gemini](evidencia-api-t5-2026-10-17.json) registra **8/8 casos esperados**: 401 sin token, 403 para administrador general, 404 para review ajena/inexistente, 422 para cuerpo con campos no editables, 200 con los dos roles del negocio y 403 para tenant desactivado usando un token previo. Solo los dos casos autorizados abrieron el proveedor; ambos guardaron Queja y coincidieron con GET posterior en sesión independiente. Se conservaron el resto de campos y la review de otro negocio.

La comprobación usa FastAPI `TestClient` en proceso con router, autenticación, servicio y proveedor Gemini reales. Sobrescribe exclusivamente la sesión/arranque hacia SQLite temporal y la carga explícita de configuración privada; no sustituye el servicio ni el proveedor por respuestas ficticias. No inicia un servidor desplegado ni modifica la base local. Los usuarios/reviews son sintéticos y no se publican contraseñas ni tokens.

Para repetirla, usar la clave privada del backend y una ruta de evidencia nueva:

```bash
backend/.venv/bin/python backend/scripts/verify_classification_api_t5.py
```

Cada ejecución consume cuota con dos llamadas autorizadas. El script conserva la evidencia previa y detiene el recorrido ante errores 5xx. Las pruebas no acreditan precisión general, despliegue, interfaz de T6 ni aceptación integrada de T7. PostgreSQL sigue pendiente de validación operativa. La política de invalidación por ediciones posteriores del contenido continúa pendiente del equipo; se conserva el comportamiento previo.
