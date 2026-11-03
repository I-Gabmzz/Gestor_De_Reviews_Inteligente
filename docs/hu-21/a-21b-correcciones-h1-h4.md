# A-21B — Correcciones de H1–H4

Fecha: 2026-11-03. Rama `feature/HU-21-importacion-externa-api`.
HEAD/base conservados: `b67608de658526856ecea8e9d5201e4ed031365e`.

## Alcance y preservación

Estado inicial: 3 archivos versionados modificados y 7 nuevos de A-21B; staging
vacío, junto con documentos/metricas/temporales previos sin seguimiento que no
pertenecen a la entrega. Se registró un manifiesto de 285 archivos no ignorados
antes de corregir. No se leen credenciales ni se abren bases de desarrollo.

No se crea commit, push o PR ni se modifica OpenProject/frontend. No se habilita
la ejecución externa ni se crea/modifica una conexión real. La configuración global
permanece deshabilitada por defecto. Todas las conexiones habilitadas usadas en
validación pertenecen exclusivamente a fixtures sintéticos nuevos.

## H1 — Identidad en todas las páginas

`SerpApiPage.place_data_id` conserva el ID recibido en esa página; su valor por
defecto es None para preservar constructores anteriores y se excluye de repr.
Un ID ausente/no textual se conserva como no verificable, sin sustituirlo por el
ID solicitado. `SerpApiResult.place_info` sigue siendo el de primera página.

El orquestador exige coincidencia exacta en cada página antes de normalizar o
persistir. Cualquier contradicción o ausencia rechaza todo el lote, incluidas las
reseñas válidas de páginas anteriores. No usa nombres comerciales como evidencia.
Se conserva el transporte, endpoint, parámetros, límites, cierre y errores del
cliente. La modificación del cliente/DTO es necesaria porque antes se descartaba
la identidad de páginas posteriores y el consumidor no podía comprobarla.

Pruebas: dos páginas correctas, segunda contradictoria, segunda sin identidad y
segunda con ID de tipo inválido; cero escrituras ante rechazo. Pruebas del cliente
verifican procedencia por página, metadata histórica y repr sin IDs.

## H2 — Esquema y datos de admisión

Nuevo validador de sólo lectura en `app/db/external_import_schema.py`:

- Comprueba columnas, tipos/longitudes, nulabilidad, PK, FK compuesta al mismo
  contexto, unicidad completa y contenido de CHECK.
- Compara una gramática limitada de expresiones booleanas, preservando literales,
  agrupación y precedencia. Acepta reflexión compatible de SQLite/PostgreSQL;
  no acepta una tautología por tener el nombre esperado ni ejecuta DDL reflejado.
- Comprueba collations de comparación exacta, integridad de las filas y referencias
  existentes, y que SQLite no ignore CHECK.
- En PostgreSQL inspecciona flags de validación/exigencia de constraints y validez
  de índices. `to_jsonb` permite comprobar `conenforced` cuando existe sin exigir
  esa columna a versiones anteriores. Referencia de catálogo:
  https://www.postgresql.org/docs/17/catalog-pg-constraint.html
- Se ejecuta antes de DDL sobre tabla preexistente, después de crear esquema y
  antes de adquirir, dentro de la transacción corta de reserva.
- Toda incompatibilidad se rechaza; por HTTP utiliza `admission_schema_invalid`,
  503 sanitizado, sin construir el cliente ni adquirir reseñas.

No hay reparación automática, reconstrucción, eliminación de tablas ni ajuste de
reservas/estados existentes. La base original carece de la tabla, por lo que se
crea correctamente desde cero. El esquema débil de la implementación no publicada
se rechaza: una instalación que lo haya creado requiere una migración explícita
revisada por un administrador antes de habilitar la operación. Esta entrega no
ejecuta una migración de tablas con datos ni oculta ese bloqueo.

Pruebas: tabla nueva/valida preexistente, sin FK/UNIQUE/CHECK, FK equivocada,
CHECK inválido/tautológico con nombre correcto, cambio de agrupación, tipo o
nulabilidad incompatible, collation NOCASE, CHECK deshabilitados, presupuestos
negativos/estados inválidos y huérfanos conservados sin modificación.

## H3 — Dominio canónico de actividad

CHECK independiente `active IS NULL OR active = true`, coherente con el UNIQUE y
la consulta de actividad. Estados running/unknown exigen actividad no nula y
finished exige NULL. `state` tiene collation BINARY/C.

SQL directo verifica rechazo de 2, -1, 0, texto, estados incoherentes y presupuestos
inválidos; también actividad duplicada para una conexión, separación por tenant y
varias operaciones finalizadas con NULL. DDL se compila para ambos motores.
Ninguna fila previa se normaliza silenciosamente a 1 o NULL.

## H4 — Contrato REST y OpenAPI

La política inválida usa ahora `policy_unavailable` y el mismo objeto estructurado
que los errores propios de A-21B. Se conservan el 401/403 y 500 del contexto de
autenticación compartido con detail textual, sin modificar sus dependencias.

OpenAPI declara 401, 403, 404, 409, 422, 429, 500, 502, 503 y 504 además de 200.
El 422 es una unión de validación FastAPI (lista en detail) y rechazo funcional
(objeto en detail). El 403/500 reconoce también el contrato compartido de texto.
Los errores de dominio mantienen códigos fijos y nunca serializan excepciones,
DDL, payloads de proveedor o credenciales.

Pruebas comprueban cuerpos HTTP de política inválida, ambos 422, autenticación,
rol, habilitación y fallo interno; se inspeccionan estados, modelos, uniones y
seguridad Bearer del OpenAPI generado.

## Archivos de esta corrección

Se ajustaron nueve archivos ya presentes al comenzar esta tarea:

- `backend/app/schemas/serpapi.py`: identidad recibida por página.
- `backend/app/services/serpapi_client.py`: conservación de esa identidad.
- `backend/app/services/external_review_import_service.py`: rechazo integral y verificación previa de esquema.
- `backend/app/models/external_review_import_attempt.py`: dominio de actividad y estado exacto.
- `backend/app/db/init_db.py`: comprobación antes y después de inicializar.
- `backend/app/schemas/external_review_import.py`: modelos de errores y uniones.
- `backend/app/api/routers/external_reviews.py`: política sanitizada y respuestas OpenAPI.
- `backend/tests/unit/test_serpapi_client.py`: cuatro regresiones de procedencia por página.
- `docs/hu-21/a-21b-api-importacion-externa.md`: contrato actualizado.

Se agregaron tres archivos:

- `backend/app/db/external_import_schema.py`: verificación de sólo lectura.
- `backend/tests/test_external_review_import_fixes.py`: 62 casos de regresión H1–H4.
- `docs/hu-21/a-21b-correcciones-h1-h4.md`: esta evidencia.

Los registros de router/modelos, la prueba previa de migraciones, la configuración
y las 62 pruebas originales de A-21B se conservaron como estaban al inicio.

## Validación

Ejecutor aislado: datos sintéticos, HTTP simulado, bases SQLite bajo un directorio
temporal nuevo; `DATABASE_URL` en memoria para el engine por defecto; claves reales
fuera del proceso y apertura de `.env` bloqueada. Se deshabilitan bytecode, caché
y plugins automáticos de pytest. Se bloquean conexiones/DNS externos, permitiendo
loopback de TestClient. Datos horarios locales se usan sólo mediante PYTHONTZPATH,
sin instalar paquetes ni cambiar dependencias. No se consulta SerpApi o IA real.

Resultados focalizados: 124 aprobadas (62 originales A-21B y 62 de H1–H4).
Regresiones relacionadas: 435 aprobadas (cliente/configuración/normalizador,
migraciones, persistencia e integración sintética). Cada ejecución final registra
una advertencia previa Starlette/HTTPX y cero intentos externos.

Suite completa: **1506 aprobadas**, una advertencia Starlette/HTTPX, 391.42 s;
contador de intentos externos: **0**. Los 66 casos nuevos de esta corrección
(62 H1–H4 y cuatro del cliente) se suman a las 1440 pruebas anteriores. Los
resultados focalizados y relacionados son subconjuntos de esta suite, no deben
sumarse entre sí. La advertencia de dependencia no causó fallos ni cambios de
dependencias.

Evidencia temporal de la ejecución completa, conservada sin borrar:
`C:\Users\PC OSTRICH\AppData\Local\Temp\a21b-h1h4-db4e3927af8b407b8e28026bcacc0f63`.

Verificación final: 15 archivos Python de A-21B compilan en memoria, sin crear
bytecode. `git diff --check` pasa para los archivos versionados; también se
comprueban los diez nuevos con `git diff --no-index --check`, sin errores de
espacios. El manifiesto inicial/final pasa de 285 a 288 archivos: exactamente
nueve ajustados y tres nuevos de esta tarea; ninguna eliminación ni cambio ajeno.

Estado Git final de A-21B: siete archivos versionados modificados y diez nuevos,
incluyendo los cambios previos. Rama y HEAD/base permanecen iguales y staging
vacío. Los documentos, auditorías, métricas y temporales previos ajenos a A-21B
permanecen sin cambios y fuera del alcance.

Las validaciones focalizadas corrigieron una expresión del verificador de
collations que inicialmente rechazaba el DDL válido con BINARY entre comillas.
La clave sintética del ejecutor se amplió para evitar advertencias de longitud;
ninguno de esos ajustes tocó credenciales reales o configuración del proyecto.

## Pendientes y límites de la evidencia

PostgreSQL real sigue pendiente: compilar DDL, reconocer ejemplos de reflexión y
simular flags de catálogo no acredita su ejecución, advisory locks, migraciones,
aislamiento, recuperación o contención en un servidor PostgreSQL.
La reflexión y comprobación de filas dentro de la reserva incrementan el trabajo
bajo bloqueo; su coste con un historial grande tampoco se ha medido.

Permanecen derechos de almacenamiento/visualización/retención, seguridad de clave,
autorización de consumo, límites operativos y recuperación administrativa de
running/unknown. No hay expiración automática ni reintento de proveedor. Se
mantienen los límites previos de descarga/memoria y la política de rechazar
adquisiciones incompletas. Estas correcciones no levantan dichos bloqueos.

El resultado solicitado es preparación para una nueva autoauditoría. Las pruebas
aprobadas, por sí solas, no autorizan commit, publicación o datos reales.

## N1 — Corrección focalizada posterior a la segunda autoauditoría

Fecha: 2026-11-03. Los apartados H1–H4 y sus resultados anteriores se conservan
como antecedentes; este apartado registra la corrección posterior de N1.

### Causa y reproducción

El contrato de columnas utilizaba inclusión de las ocho esperadas y permitía
columnas adicionales. SQLite puede resolver `true` como una columna existente:
el CHECK textual `active = true` dejaba entonces de exigir el valor canónico 1.
La validación de filas reutilizaba esa expresión y también aceptaba el dato.
Una fila `unknown`, `active=2`, `true=2` quedaba fuera de la consulta ORM de
actividad, permitiendo nuevas adquisiciones para la misma conexión.

La nueva regresión recrea exclusivamente una tabla vacía del fixture temporal
con el CHECK anterior, agrega `true` e inserta el contraejemplo con SQL directo,
sin deshabilitar CHECK. Antes de corregir, falló porque `init_db` no lo rechazaba.

### Corrección aplicada y alcance

- Contrato cerrado de exactamente ocho columnas, aplicado antes de interpretar
  restricciones o consultar registros, tanto para SQLite como para PostgreSQL.
  Se rechaza cualquier columna adicional, sin listas especiales de nombres.
- El modelo usa una expresión booleana SQLAlchemy que compila a
  `active IS NULL OR active = 1` en SQLite y a
  `active IS NULL OR active = true` en PostgreSQL. No se compara un booleano
  PostgreSQL contra un entero. El CHECK nuevo SQLite resiste columnas `true` y
  `false` incluso sin ejecutar el verificador.
- La comprobación de filas también usa 1/0 en SQLite y true/false en PostgreSQL,
  evitando resolución de nombres booleanos SQLite en sus predicados.
- Una tabla anterior con las ocho columnas y restricciones válidas sigue siendo
  compatible. No se reconstruyen tablas, corrigen filas ni cambian reservas.
  El esquema extendido se rechaza aunque sus filas sean válidas.
- El servicio de importación y `init_db` no requieren cambios: sus llamadas
  existentes al verificador ya garantizan rechazo antes de construir el cliente.
  Se conservan H1, H4, el presupuesto y los controles de tenant/estado.

Archivos ajustados en esta tarea:

1. `backend/app/models/external_review_import_attempt.py`: CHECK compilado por dialecto.
2. `backend/app/db/external_import_schema.py`: columnas exactas y predicados de filas.
3. `backend/tests/test_external_review_import_fixes.py`: DDL por dialecto y caso de
   columna adicional en el catálogo PostgreSQL simulado.
4. `docs/hu-21/a-21b-correcciones-h1-h4.md`: esta evidencia, sin sustituir antecedentes.

Archivo nuevo: `backend/tests/test_external_review_import_n1.py`.

### Pruebas adversariales y resultados

Se agregaron 18 casos SQLite y uno de catálogo PostgreSQL simulado:

- Contraejemplo original `true=2`, `active=2`, `unknown` sobre el CHECK anterior.
  Arranque rechazado y dos solicitudes HTTP rechazadas con
  `503 admission_schema_invalid`; cero construcciones de cliente, cero solicitudes
  al proveedor y cero reseñas persistidas. DDL y registros se conservan intactos.
- Columnas adicionales `true`, `TRUE`, `TrUe`, `false`, `FALSE`, `null`,
  `extra_flag`, y una columna `true` generada virtual; rechazo aun con filas válidas.
- SQL directo con el CHECK nuevo y columnas que sombrean true/false: rechazo de
  0, 2, -1 y texto; aceptación de 1 independiente de los valores de esas columnas.
  El verificador rechaza en todo caso la estructura extendida.
- Esquema canónico con running/unknown bloqueados y finished admitido; varias
  finalizadas, unicidad activa por conexión, aislamiento por tenant y presupuesto
  reservado válido de hasta cinco. Se conserva compatibilidad con el CHECK
  anterior cuando el conjunto de columnas es exacto.
- Compilación DDL SQLite/PostgreSQL y rechazo de columnas adicionales en reflexión
  PostgreSQL simulada. No se utiliza un servidor PostgreSQL real.

Resultados finales: N1 SQLite, 18 aprobadas; suite focalizada, 143
aprobadas (62 originales, 63 H1–H4/catálogo y 18 N1); regresiones relacionadas,
435 aprobadas. Cada ejecución registra una advertencia previa Starlette/HTTPX
y cero intentos de red externa.

Suite backend completa: **1525 aprobadas**, una advertencia Starlette/HTTPX,
410.92 s, cero intentos de red externa. Las 19 regresiones nuevas de N1
(18 SQLite y una de catálogo PostgreSQL simulado) se suman a las 1506 anteriores.
Los resultados focalizados/relacionados son subconjuntos y no se suman al total.
Ejecución completa conservada en el directorio temporal nuevo
`C:\Users\PC OSTRICH\AppData\Local\Temp\a21b-n1-c8c9a5c08d634c53b820307dee617d16`.

Sintaxis: 16 archivos Python de A-21B compilan en memoria sin bytecode.
`git diff --check` y la revisión de espacios de los once archivos nuevos de A-21B
pasan. No se modifican dependencias ni configuración del proyecto para ejecutar.

Control Git de N1: inicialmente siete archivos versionados modificados y diez
nuevos de A-21B; al terminar, siete modificados y once nuevos. Rama y HEAD de
referencia se conservan, staging vacío. El manifiesto pasa de 288 a 289 archivos:
únicamente los cuatro ajustes y el nuevo test enumerados arriba; ninguna
eliminación ni cambio ajeno. El hash del prefijo documental anterior al apartado
N1 confirma la conservación de los antecedentes H1–H4.

### Riesgos y límites conservados

Toda extensión futura de columnas requiere una decisión explícita de esquema;
no hay compatibilidad automática con extensiones locales. Las tablas incompatibles
requieren revisión/migración administrativa fuera de esta corrección.

PostgreSQL real, advisory locks, contención y recuperación siguen pendientes de
validación de activación. La comprobación del historial continúa dentro de la
reserva y no se optimiza aquí. La segunda autoauditoría midió crecimiento local
del coste; no es una estimación de capacidad de producción.

Persisten los bloqueos de derechos, habilitación, consumo real y reconciliación
administrativa de running/unknown. Este resultado prepara una nueva revisión;
no autoriza commit, despliegue ni almacenamiento de reseñas reales.
