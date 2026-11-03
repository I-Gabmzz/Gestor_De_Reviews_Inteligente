# HU-21 — A-21B: API de importación externa controlada

Fecha: 2026-11-03. Base comprobada después de `git fetch origin`:
`b67608de658526856ecea8e9d5201e4ed031365e` (`origin/main`).
Rama de trabajo: `feature/HU-21-importacion-externa-api`.

Esta entrega implementa el recorrido backend con pruebas sintéticas. No acredita
derechos de almacenamiento/visualización ni constituye autorización para consumir
SerpApi. No modifica frontend, OpenProject, credenciales, conexiones reales o BD
de desarrollo. No incluye commit, publicación o PR.

## Contrato técnico

`POST /api/v1/integrations/google/reviews/import`, síncrono, JSON y Bearer JWT.

Solicitud exclusivamente:

```json
{"business_data_id": "0xabc:0x123"}
```

El identificador de ejemplo es sintético. Debe tener formato `0xHEX:0xHEX`,
longitud máxima 128 y coincidir exactamente con una conexión del servidor para
el tenant autenticado y fuente `Google`. No hay búsqueda por nombre, selección
libre de URL, motor ni proveedor. No se normalizan mayúsculas o espacios de IDs.

El schema rechaza campos adicionales, incluidos `tenant_id`, `source`,
`persistence_enabled`, `approval_reference`, `allow_incomplete` y límites de
paginación. No existe una ruta de aprovisionamiento, aprobación o habilitación.

Autenticación: se reutiliza `get_current_user`, que consulta el usuario y tenant
vigentes; los claims de rol y tenant del JWT no eligen el ámbito. Se permiten
`usuario_negocio` y `admin_tenant`; `admin_general` no tiene acceso a esta ruta.
La dependencia de esta operación cierra su sesión antes de devolver el DTO del
usuario, sin retener la sesión de autenticación durante el HTTP externo.

### Respuesta confirmada: HTTP 200

```json
{
  "operation_id": "UUID de operación",
  "outcome": "committed",
  "control_status": "released",
  "source": "Google",
  "input_count": 5,
  "inserted": 2,
  "repeated": 1,
  "changed": 0,
  "omitted": 1,
  "rejected": 1,
  "batch_duplicates": 0,
  "request_count": 1,
  "incomplete": false,
  "limited": false,
  "stop_reason": "no_next_token"
}
```

`input_count = inserted + repeated + changed + omitted + rejected`.
`batch_duplicates` es un subconjunto de `repeated`, no se suma de nuevo.
`changed` informa cambios externos sin reemplazar valores locales. Se conservan
la política de omitir reseñas sin texto y la identidad original de #3834.

`request_count` son intentos HTTP, nunca una medida de créditos facturados.
`no_next_token` no garantiza que se hayan obtenido todas las reseñas públicas.
La respuesta no serializa DTO nativo, contenido, autores, IDs de reviews,
warnings, posiciones conflictivas, tokens, credenciales o referencias de aprobación.
Las reseñas confirmadas se consultan por los endpoints existentes de reviews.

Si el commit de reviews se confirmó pero falla el cierre del registro de admisión,
se conserva HTTP 200 y los contadores confirmados, con
`control_status="reconciliation_required"`. No se transforma un éxito confirmado
en un supuesto rollback. Una nueva operación puede seguir bloqueada.

### Errores

Los errores propios de la operación usan `{"detail": {...}}` con los campos:

- `code`, `message`: código estable y mensaje fijo, sin excepciones originales.
- `operation_id`: UUID si se inició/reservó una operación; puede ser nulo antes.
- `outcome`: `rejected`, `rolled_back` o `unknown`.
- `committed_count`: 0 cuando se sabe que no se guardaron reviews; nulo si es incierto.
- `control_status`: `released` o `reconciliation_required`.
- `request_count`, `obtained`: intentos y registros de páginas válidas adquiridas.
- `incomplete`, `limited`, `stop_reason`: diagnóstico si existe resultado adquirido.

Los rechazos de autenticación conservan el contrato compartido de la aplicación
(`detail` de texto), incluidos sus rechazos de rol/estado y la configuración
inválida de usuario (500). Los errores propios de A-21B siempre usan el objeto
estructurado, incluida la política inválida (`policy_unavailable`, 503).
Los errores de schema conservan el 422 de FastAPI (`detail` como lista); el 422
funcional de persistencia usa `detail` como objeto (`persistence_rejected`).
OpenAPI declara esas dos alternativas y todos los estados de la tabla siguiente;
no se cambia el manejador global de autenticación o validación de FastAPI.

| HTTP | Situación / códigos propios |
| --- | --- |
| 401 | Autenticación ausente, inválida o usuario inexistente |
| 403 | Rol/contexto inactivo o no autorizado; `import_disabled`, `persistence_disabled`, `unauthorized_context` |
| 404 | `connection_unavailable`; conexión ajena e inexistente indistinguibles |
| 409 | `import_in_progress`, `incomplete_acquisition`, `persistence_conflict` |
| 422 | Solicitud inválida; `persistence_rejected` para lote no persistible |
| 429 | `budget_exhausted` local, antes de construir el cliente |
| 500 | `internal_error`, sanitizado; resultado conservador si se inició persistencia |
| 502 | `place_unverified`, `normalization_failed`, `provider_response` |
| 503 | `policy_unavailable`, `admission_schema_invalid`, `admission_unavailable`, `provider_unavailable`, `persistence_failed` |
| 504 | `provider_timeout` |

Un 401/403/429 del proveedor se presenta como indisponibilidad de la integración
(503), no como expiración de la sesión del usuario ni presupuesto local agotado.
No se publican sus cuerpos ni URLs autenticadas. No hay reintentos automáticos.

## Flujo y reutilización

1. Autenticar, consultar estados vigentes y comprobar rol; cerrar esa sesión.
2. Comprobar `ExternalImportSettings.enabled`, deshabilitado por defecto.
3. En una transacción corta de admisión, revalidar actor, tenant y conexión de
   `ExternalReviewConnection`: persistencia habilitada y aprobación no vacía.
4. Comprobar exclusión por conexión y presupuesto; reservar el máximo de intentos
   permitido antes de HTTP, confirmar y cerrar la sesión.
5. Construir `SerpApiClient`, llamar `fetch_reviews` y cerrar el transporte.
6. Exigir `place_info.data_id` de primera página y `place_data_id` de **cada**
   página iguales al establecimiento solicitado. Ausencia, vacío, tipo inválido o
   contradicción en cualquier página rechazan el lote completo antes de persistir;
   el nombre no acredita identidad. No se rellena un ID desde el solicitado.
7. Rechazar adquisiciones incompletas sin persistir, incluso por máximo de páginas,
   token repetido o página vacía con token. No se habilita `allow_incomplete`.
8. Reutilizar `normalize_serpapi_result`.
9. Abrir una sesión nueva y exclusiva para `ExternalReviewPersistenceService.persist`.
   Ese servicio revalida actor/conexión y conserva commit, rollback e idempotencia.
10. Cerrar el registro de admisión en otra transacción corta. Ante commit incierto,
    conservar la exclusión y exigir reconciliación manual.

H1 requiere ampliar el contrato interno `SerpApiPage` con `place_data_id` opcional,
excluido de repr y obtenido exclusivamente de la respuesta de esa página. El
cliente lo conserva sin cambiar el `place_info` histórico de primera página,
peticiones, paginación o errores. El cliente genérico sigue permitiendo ausencia
de metadata; la política estricta de todas las páginas pertenece al orquestador.
No se modifican normalizador, servicio de persistencia ni repositorio de reviews.
Las pruebas verifican que no hay conexiones de autenticación
o admisión retenidas al construir el cliente o enviar cada página simulada.

## Admisión compartida y límites conservadores

Nueva tabla `external_review_import_attempts`: UUID, tenant, fuente,
establecimiento, fecha UTC sin zona, máximo de intentos reservado y estado.
No contiene reseñas, IDs de reseñas, claves ni tokens del proveedor.

Se incorpora mediante el registro de modelos y el `create_all` ya usado por
`init_db`, dentro de su bloqueo/transacción de inicialización existente. No se ha
ejecutado esa inicialización sobre una BD real en esta entrega. El registro no
crea ni habilita conexiones, y preserva las referencias de aprobación existentes.

La FK compuesta referencia la conexión del mismo tenant. La unicidad de
`tenant_id + source + business_data_id + active` permite una sola operación activa;
las finalizadas usan NULL. Un CHECK independiente admite sólo `TRUE/1` o NULL,
excluyendo 0, 2 y otros valores. Otro mantiene la coherencia de estado y actividad.
El estado usa comparación exacta BINARY/C igual que los IDs opacos.

H2 valida columnas, tipos, longitudes, nulabilidad, PK, FK compuesta, UNIQUE y el
contenido de los CHECK, no sólo sus nombres. Se comprueban antes del DDL si la
tabla ya existe, después de inicializar y dentro de admisión antes de adquirir.
También se rechazan reservas/estados inválidos y huérfanos existentes.

El validador compara árboles de una gramática limitada a estos CHECK: conserva
literales, agrupación y precedencia AND/OR; reconoce la expansión de BETWEEN y
casts textuales de PostgreSQL. Nunca ejecuta SQL reflejado. Expresiones desconocidas,
collations incompatibles, CHECK deshabilitados en SQLite y restricciones PostgreSQL
no validadas, diferibles, no exigidas o con índice inválido se rechazan sin reparar.

La base original de `main` no contiene esta tabla: se crea con el esquema corregido.
Una tabla válida preexistente se conserva. Una tabla de la versión previa no
publicada de A-21B, con el dominio débil de active, queda bloqueada y requiere
revisión/migración administrativa explícita fuera de esta entrega. No se elimina,
reconstruye ni modifica silenciosamente ningún registro para hacerla compatible.

SQLite serializa admisión con `BEGIN IMMEDIATE` y exige FK habilitadas.
PostgreSQL usa `pg_advisory_xact_lock(32513563)` durante la transacción corta de
reserva; todos los trabajadores de esta API usan ese mismo bloqueo antes de
comprobar/sumar presupuesto. Otros dialectos se rechazan antes de HTTP.

Configuración nueva exclusivamente del entorno del servidor; no lee `.env`:

| Variable | Predeterminado | Validación |
| --- | --- | --- |
| `EXTERNAL_IMPORT_ENABLED` | false | Habilitación operativa independiente de la conexión |
| `EXTERNAL_IMPORT_PAGE_SIZE` | 5 | 1–20 |
| `EXTERNAL_IMPORT_MAX_PAGES` | 1 | 1–5 |
| `EXTERNAL_IMPORT_TENANT_REQUEST_BUDGET` | 1 | 1–10000 |
| `EXTERNAL_IMPORT_ACCOUNT_REQUEST_BUDGET` | 5 | 1–10000 |
| `EXTERNAL_IMPORT_BUDGET_WINDOW_SECONDS` | 3600 | 60–86400 |

Estos predeterminados son conservadores para código todavía deshabilitado; no
constituyen una cuota comercial aprobada. Los límites de página no pueden superar
la configuración `SERPAPI_*` del cliente existente. Si ese cliente rechaza una
combinación, no hace HTTP y se comunica indisponibilidad, sin reintentar.

Se reserva `max_pages` completo, aunque se obtengan menos páginas o falle el
proveedor; no hay devoluciones automáticas de presupuesto. La ventana móvil suma
reservas recientes de todos los tenants para la cuenta global y del tenant actual.
La configuración y el reloj UTC deben ser coherentes entre trabajadores.

El presupuesto es común a esta API y a los procesos que comparten su misma BD;
no mide saldo/facturación ni limita llamadas realizadas por otros sistemas,
otras BD o invocaciones directas al cliente. No se consulta la API de cuenta.

## Interrupciones y reconciliación

Estados: `running` y `unknown` retienen `active=True`; `finished` usa NULL.
No hay vencimiento automático: expirar un bloqueo mientras un proveedor lento
continúa ejecutándose permitiría duplicar consumo. Una operación vieja no se
considera terminada únicamente por el tiempo transcurrido.

Si falla la confirmación de admisión, no se inicia HTTP. El UUID se devuelve para
inspeccionar si quedó una reserva confirmada. Si falla el commit de reviews, se
conserva `outcome=unknown`, `committed_count=null` y el bloqueo por conexión.
Un cierre del registro fallido también exige revisión, aunque las reviews estén
confirmadas. El presupuesto consumido/reservado no se restituye automáticamente.

La recuperación es una operación administrativa fuera de este endpoint: comprobar
que no hay trabajador activo, revisar exclusivamente el tenant/establecimiento
autorizado y sus identidades, y determinar el resultado con evidencia suficiente
antes de cerrar la admisión o autorizar otra adquisición. Si no puede determinarse,
mantener el bloqueo. No se ofrece un endpoint público para borrar/desbloquear.
No se retiene el lote, por lo que no hay reintento de persistencia sin nueva
adquisición a través de esta ruta. La nueva adquisición requeriría presupuesto
y autorización; la idempotencia de datos sigue en el servicio existente.

## Decisiones y bloqueos pendientes del PO / responsable autorizado

- Continúan los bloqueos de #3831/#3835 sobre derechos de almacenamiento,
  visualización, retención y cualquier transferencia/procesamiento con IA.
- `approval_reference` no vacía es una barrera técnica, no una prueba automática
  de derechos. Su registro y validación corresponden a un operador autorizado.
- La habilitación global no sustituye esa evidencia. No se ha establecido en
  esta entrega ni se modificó ninguna conexión real.
- Aprobar límites de frecuencia/consumo y confirmar el procedimiento administrativo
  de habilitación/reconciliación antes de una operación real.
- Confirmar si se mantiene rechazo de identidad ausente y de adquisiciones
  incompletas. Hasta entonces ambas se rechazan.
- Resolver credencial previamente expuesta, saldo y autorización específica para
  una futura prueba real. Esta entrega no carga credenciales reales en el cliente
  ni consulta al proveedor.
- PostgreSQL real permanece sin validar; compilar DDL no acredita migraciones,
  advisory locks, concurrencia o recuperación en un servidor PostgreSQL real.
- La descarga/JSON conserva los límites y riesgos del cliente existente; los
  límites textuales de persistencia no limitan bytes descargados previamente.
- No hay frontend ni cambio de timeout React en A-21B. Una futura interfaz debe
  contemplar el tiempo síncrono y evitar reintentos automáticos de adquisición.

## Pruebas y evidencia

`backend/tests/test_external_review_import_api.py` usa el registro real de routers,
autenticación real del proyecto y los componentes de HU-21, con SQLite nuevo por
test y `httpx.MockTransport` con credencial ficticia. No inicia el lifespan de la
aplicación real. Sólo las conexiones de fixtures sintéticos se habilitan.

La suite cubre autenticación, roles/estados vigentes, schema restrictivo, conexión
ajena/inexistente, habilitación/aprobación, identidad ausente/contradictoria,
paginación/incompletas, errores y timeout antes/después de una página, contadores,
consulta posterior, idempotencia, cambios locales, aislamiento, claims falsos,
revocación durante HTTP, rollback, commit incierto de admisión y de reviews,
fallo de cierre del registro, concurrencia, presupuesto compartido, ventana móvil,
interrupciones antiguas, privacidad de logs y creación aditiva de la tabla.

El ejecutor de esta validación usa `DATABASE_URL=sqlite:///:memory:`, desactiva
bytecode, caché y plugins externos de pytest, elimina claves/configuración
heredadas del proceso, impide leer `backend/.env` y sólo permite abrir SQLite en
un directorio temporal nuevo fuera del repositorio. Una barrera adicional bloquea
DNS/conexiones externas, permitiendo loopback para TestClient. Los fixtures nuevos
también bloquean transportes HTTP reales. Estas barreras no pretenden ser un
aislamiento universal del SO o de cualquier posible subproceso.

### Resultados verificados

| Verificación | Resultado |
| --- | --- |
| Suite focalizada A-21B | 62 aprobadas; 5.56 s |
| Regresión backend completa, incluyendo A-21B | 1440 aprobadas; 321.99 s |
| Advertencias en cada ejecución final | 1, deprecación existente Starlette/HTTPX |
| Intentos de DNS/conexión externa del ejecutor final | 0 |
| Sintaxis Python, AST y compilación en memoria | 9 archivos correctos, sin bytecode |
| `git diff --check` y revisión de espacios de los 7 archivos nuevos | Correctos |
| Manifiesto de 283 archivos previos | 280 sin cambios; sólo 3 modificaciones autorizadas |

La suite completa incluye las 62 pruebas nuevas y las regresiones CSV/Excel; los
recuentos no se suman como pruebas distintas. Base sintética de esa ejecución:
`C:/Users/PC OSTRICH/AppData/Local/Temp/a21b-tests-28e5dcbba5ec444e94fb617d28885182`.

La primera ejecución del ejecutor rechazó las BD temporales por comparar un alias
Windows 8.3 con la ruta larga; se corrigió la comparación del ejecutor. La primera
regresión detectó una aserción existente que enumeraba exactamente las tablas:
se añadió únicamente la nueva tabla de admisión a su conjunto esperado.

Otra ejecución de regresión se detuvo con 603 pruebas aprobadas por ausencia de
`tzdata`/`America/Tijuana` en este Python de Windows. Se reutilizaron datos horarios
locales de una validación anterior mediante `PYTHONTZPATH` sólo para el proceso,
sin instalar paquetes ni modificar código/dependencias. Se comprobó primero que
pasaban las 3 pruebas de `test_priority_verification.py`. Sus directorios temporales
internos se dirigieron al mismo directorio nuevo del ejecutor; después pasó la
suite completa. Ninguno de esos ajustes habilitó conexiones externas o BD reales.

El manifiesto incluye archivos sin seguimiento previos, `.env` y bases locales;
no se imprimen sus hashes ni contenidos. Las únicas modificaciones previas son
los registros de routers/modelos y la aserción del catálogo de tablas de migración.
Esos resultados describen la versión inicial anterior a corregir H1-H4. El cliente
y su DTO se amplían justificadamente para H1; normalizador, persistencia,
repositorio de reviews y frontend permanecen intactos. Los resultados y el alcance
actualizados se registran en `a-21b-correcciones-h1-h4.md`. Sin commit/push/PR.
