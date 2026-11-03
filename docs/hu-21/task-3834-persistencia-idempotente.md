# HU-21 — Task #3834: persistencia idempotente y multi-tenant

## Alcance y estado

Implementación técnica para datos sintéticos, con correcciones P2 pendientes de
revisión pre-commit. La Task no se declara completada en este documento.
Base: `d616f3df6c3a1e33bbbf6438b60c7eb0de3b087a`, rama
`feature/HU-21-integraciones-externas`. Fecha de validación: 2026-11-02.

Se conserva Services → Repositories → SQLAlchemy. No se modifican contratos
públicos, routers, frontend, cliente SerpApi, normalizador ni servicios Gemini.
No se implementa #3835 ni se habilita la persistencia de reseñas reales.

Proveedor técnico: SerpApi. Origen de las reseñas admitidas: Google Maps,
representado por el valor exacto `Google`. Son conceptos distintos.

## Tablas y relaciones

### external_review_connections

Asociación controlada por el servidor entre tenant, origen y establecimiento:

| Columna | Regla |
| --- | --- |
| `tenant_id` | Parte de PK compuesta, FK a `tenants.id` |
| `source` | Parte de PK, valor restringido a `Google` |
| `business_data_id` | Parte de PK, hasta 128 caracteres |
| `persistence_enabled` | Obligatorio, valor Python y valor de servidor `False` |
| `approval_reference` | Referencia de aprobación; requerida y no vacía al habilitar |

La PK `(tenant_id, source, business_data_id)` impide conexiones duplicadas y
permite que dos tenants tengan asociaciones independientes con un mismo negocio.
No hay API de alta o activación. La migración no crea conexiones ni las habilita.
Los únicos registros habilitados creados en esta ejecución pertenecen a fixtures
sintéticos dentro de bases efímeras de pruebas.

### external_review_identities

| Columna | Regla |
| --- | --- |
| `review_id` | PK, un enlace externo por reseña; no genera otro identificador |
| `tenant_id` | Obligatorio, mismo tenant que la reseña enlazada |
| `source` | Origen inmutable de la identidad, independiente de `Review.fuente` |
| `business_data_id` | Establecimiento de la conexión autorizada |
| `external_review_id` | ID opaco sin recortar, cambiar mayúsculas ni sustituir |
| `import_fingerprint` | Huella versionada `v1:` seguida de SHA-256 hexadecimal |

Restricciones:

- `UNIQUE(tenant_id, source, business_data_id, external_review_id)`.
- FK compuesta `(review_id, tenant_id)` → `reviews(id, tenant_id)`.
- FK compuesta `(tenant_id, source, business_data_id)` → conexión externa.
- Índice único adicional `uq_reviews_id_tenant` en `reviews(id, tenant_id)`
  para respaldar la primera FK, sin añadir columnas a `Review`.
- Identificadores y claves textuales usan comparación exacta: `BINARY` en SQLite
  y `C` en PostgreSQL, con tipos VARCHAR que preservan espacios significativos.
- No hay cascadas de borrado o reasignación: se rechazan enlaces huérfanos y
  cambios de tenant incompatibles. Su eventual gestión queda fuera de #3834.

El ID interno continúa siendo `Review.id`. El ID externo no es globalmente único:
se permiten repeticiones en otros establecimientos y tenants. Una edición de
`Review.fuente` no altera ni invalida la identidad original.

## Servicio y contexto de autorización

Entrada interna:

```python
ExternalReviewPersistenceService(repository, allow_incomplete=False).persist(
    batch,
    current_user=server_authenticated_user,
    business_data_id=authorized_business_data_id,
)
```

`batch` es un `NormalizationBatchResult` de #3833, revalidado antes de escribir.
`current_user` debe provenir de autenticación del servidor. Esta firma no es un
contrato HTTP: no autoriza aceptar un objeto de usuario o tenant desde un body.

Se admiten los roles operativos existentes `usuario_negocio` y `admin_tenant`.
Se rechaza Administrador General. Se consulta además el estado vigente de usuario,
rol, tenant y su actividad en BD; no basta con confiar en un contexto obsoleto.

El tenant procede exclusivamente del contexto autenticado. Todas las consultas
de conexión e identidad incluyen ese tenant. Se valida que el negocio de cada
registro coincida con el contexto solicitado y registrado. Una conexión ajena y
una inexistente producen el mismo error público, sin filtrar pertenencias.

La conexión se consulta con bloqueo `FOR UPDATE` en PostgreSQL. En SQLite se
requieren FKs habilitadas y se inicia una transacción física `BEGIN IMMEDIATE`.
Esto serializa escritores y evita depender del comportamiento legado de SELECT.

## Propiedad de la transacción

El servicio exige una **sesión exclusiva ligada a Engine, sin transacción previa**.
Se rechazan sesiones con autobegin por lecturas de autenticación, escrituras
pendientes o ya flush, transacciones explícitas/savepoints y sesiones ligadas a
una Connection externa. El rechazo no confirma ni revierte el trabajo del llamador.

Esta regla evita anidar `Session.begin()` sobre un autobegin y evita que un
`Session.commit()` sobre una transacción externa sea interpretado como commit
definitivo. En #3835 se deberá proporcionar una sesión nueva para esta operación,
cerrando antes la sesión utilizada sólo para autenticación cuando corresponda.
No se sustituye el mecanismo transaccional de otras funcionalidades.

Dentro de la operación:

1. Validar contrato, límites y contexto de usuario.
2. Adquirir la sesión/transacción propia y verificar autorización/conexión.
3. Consultar identidades, clasificar repeticiones y crear nuevas reseñas.
4. Hacer flush de cada Review para obtener su PK y flush de su identidad.
5. Ejecutar un único commit al terminar todo el lote.
6. Devolver un DTO de contadores, sin refresh ni acceso ORM posterior al commit.

No se usa `ReviewRepository.create_many()`: su commit interno impediría componer
las dos inserciones de forma atómica. Se conservan las consultas y el comportamiento
de los métodos existentes; sólo se añade la protección temporal de logging descrita
más abajo. Los métodos externos añadidos sólo consultan o hacen flush.

## Idempotencia y política de reimportación

La unicidad en BD es la defensa final; las consultas previas sólo evitan trabajo
innecesario. Review e identidad se insertan en la misma transacción, sin huérfanos.

La huella v1 se calcula sobre una representación JSON ordenada por posición de
campos: origen, negocio, ID externo, autor, contenido, fecha UTC con microsegundos,
puntuación y procedencia `content_field`. No incluye posición de página ni campos
adicionales del proveedor. El hash no reemplaza el ID ni es una licencia de uso,
anonimización o cifrado.

| Caso | Resultado |
| --- | --- |
| Primera importación válida con texto | Crear Review e identidad |
| Huella igual a la inicialmente importada | Contabilizar repetida, sin escribir |
| Misma identidad con huella diferente | Contabilizar cambiada y posición, sin sobrescribir |
| Cambios manuales o resultados IA en Review | Conservarlos íntegramente |
| Mismo ID en otro tenant o negocio | Identidad distinta, inserción independiente |
| Duplicados idénticos de #3833 | Contabilizarlos sin insertar nuevamente |
| Grupos conflictivos de #3833 | Conservar rechazos; no guardar ninguna versión |

La comparación siempre usa la huella de la importación original, no los valores
editables actuales de Review. No hay actualización automática, cola persistente
de conflictos, análisis de IA ni reescritura de estados. Nuevas reseñas comienzan
en `nueva`, con categoría, resumen, tema y prioridad en `None`.

Las reseñas históricas sin identidad externa no se emparejan por texto o fuente:
no se inventan IDs ni se hace backfill de procedencia.

## Reseñas sin texto y adquisición incompleta

Política técnica conservadora, pendiente del PO:

- `without_text` se omite explícitamente, conserva sus advertencias en el resultado
  y no genera Review ni identidad. No se inventa texto.
- Una versión posterior con texto puede insertarse. Una versión posterior sin
  texto no borra contenido ya existente.
- `Review.contenido` sigue siendo NOT NULL; no se modifica su contrato público.
- Las adquisiciones incompletas se bloquean por defecto con `incomplete_disabled`.
- Existe la opción interna de construcción `allow_incomplete=True`, utilizada en
  pruebas controladas; no es un parámetro público ni evita el control de conexión.
  Si se habilita internamente tras decisión del PO, preserva `incomplete`, `limited`
  y `stop_reason`; no declara sincronización completa ni hace llamadas adicionales.

## Límites y revalidación

Decisiones técnicas provisionales, no límites garantizados por el proveedor:

| Límite | Implementación |
| --- | --- |
| Ocurrencias de entrada | 100, incluidas repeticiones y rechazos |
| ID externo | 512 caracteres y 1024 bytes UTF-8 |
| Negocio | 128 caracteres, formato hexadecimal `0x...:0x...` |
| Autor | Opcional, máximo 255 caracteres |
| Contenido | 64 KiB UTF-8 por registro |
| Carga textual agregada | 1 MiB |

El presupuesto agregado suma los campos de texto disponibles en reseñas aceptadas,
sin texto y versiones conflictivas: ID, origen, negocio, autor, contenido y
`content_field`; también cuenta una vez el negocio del contexto. Las ocurrencias
duplicadas sin payload propio se controlan por el límite de 100, sin inventarles
contenido. No se cuenta un JSON nativo completo: no llega a este servicio.

Se rechazan NUL, Unicode no codificable, fechas que no sean datetime UTC del
contrato normalizado, puntuaciones que no sean enteros estrictos 1–5, campos de
origen inconsistentes, posiciones, diagnósticos o contadores manipulados.
Se revalida porque los DTO dataclass pueden construirse sin el normalizador.
No se truncan datos. Un incumplimiento nuevo de la frontera de persistencia
rechaza el lote antes de escribir; los rechazos ya clasificados por #3833 se
cuentan conservando los otros registros válidos.

Estos límites mitigan el P3 en persistencia. No limitan retroactivamente memoria
consumida en la descarga o normalización, cuyos módulos no se modificaron.

## Resultado y errores

`ExternalReviewPersistenceResult` contiene contadores, flags de adquisición,
posiciones cambiadas y advertencias seguras. No retorna contenido ni autores.

```text
input_count = inserted + repeated + changed + omitted + rejected
batch_duplicates es un subconjunto de repeated; no se vuelve a sumar.
```

`rejected` incluye conflictos de #3833, sin contarlos otra vez. `repeated` incluye
repeticiones del lote y coincidencias con identidades ya guardadas.

`ExternalReviewPersistenceError` contiene un código fijo, resultado transaccional,
indicador de reejecución posible y cantidad confirmada, sin conservar excepciones
SQL originales ni sus parámetros. No hay reintentos automáticos.

| Situación | Estado comunicado |
| --- | --- |
| Contrato, contexto o habilitación inválidos | `rejected`, cero inserciones de esta operación |
| Error anterior al commit con rollback correcto | `rolled_back`, cero inserciones confirmadas |
| Colisión única | Error recuperable, rollback del lote completo |
| SQLite ocupado o PostgreSQL 40001/40P01 | Error recuperable; requiere nueva transacción |
| Error genérico durante commit | `unknown`, `committed_count=None` |
| No puede confirmarse rollback | `unknown`, sin afirmar cero guardadas |

No se trata cualquier IntegrityError como duplicado. Fallos de FK o CHECK siguen
siendo errores de integridad. La reejecución tras un resultado incierto usa las
identidades existentes y no requiere volver a consultar SerpApi.

## Migración controlada

Se reutilizan el bloqueo de inicialización de SQLite/PostgreSQL y `create_all()`.
Para tablas antiguas se comprueba primero una clave única completa padre de Review,
antes de crear las FK compuestas nuevas. Se reutiliza una restricción o índice
completo existente; si no existe, se crea `uq_reviews_id_tenant`. Se conserva la migración aditiva existente de
`resumen` y `tema`, sin modificar su definición histórica.

Se soportan BD nueva, BD antigua, índice padre ya creado, tabla de conexiones ya
creada y actualización IA parcial. Se verifica la presencia de columnas obligatorias,
PK, unicidad, FK y restricciones CHECK esperadas. Un esquema incompatible se
rechaza; no se reconstruyen tablas arbitrarias ni se reescriben filas para repararlo.

No se introdujo Alembic. No hay cambios de datos, habilitaciones ni identidades
retroactivas durante inicialización. Los índices previos y filas históricas se
conservan en las pruebas de migración.

La BD local del usuario no se migró. Conserva la diferencia previa de columnas IA.
El próximo inicio real de la aplicación en esta rama invocaría el inicializador
actualizado: ese despliegue/migración sobre datos reales debe revisarse antes de
ejecutarlo. En esta ejecución todas las migraciones apuntaron a bases efímeras.

## Seguridad y derechos de uso

El acceso técnico a SerpApi no acredita almacenamiento, retención, redistribución
ni tratamiento con IA. La habilitación futura requiere evidencia y validación del
PO para almacenamiento, visualización y usos accesibles en los servicios actuales.
Persistir una Review podría hacerla disponible para consultas, exportación y
análisis existentes; no debe activarse sólo por tener permiso de almacenamiento.

No hay bandera pública `synthetic=true`, endpoint de activación ni permisos nuevos
del Administrador General. `allow_incomplete` no evita ninguno de esos controles.
La referencia de aprobación es un control operativo, no una verificación automática
de una licencia. Las conexiones reales permanecen deshabilitadas por defecto.

Se conserva `hide_parameters=True` en el engine existente. Esa opción no oculta
las filas devueltas en DEBUG y no constituye una garantía absoluta de privacidad.
La corrección P2 siguiente protege las operaciones del repositorio incluso con
un Engine inyectado que no oculte parámetros. El servicio no encadena la excepción
SQL original en sus errores públicos.

No se guardaron reseñas reales ni se enviaron datos a Gemini. No se consumió cuota
de SerpApi. No se usaron API keys, URLs autenticadas ni datos personales en fixtures.
La rotación de la clave previamente expuesta y las cuotas de adquisiciones futuras
siguen siendo dependencias de la integración; este servicio no utiliza credenciales.

## Correcciones P2 posteriores a la auditoría

### Filas y parámetros en logs DEBUG

La auditoría reprodujo que `get_external_connection()` recuperaba la entidad
completa y SQLAlchemy registraba una fila con negocio y referencia de aprobación,
incluso con `hide_parameters=True`. La causa era la instrumentación de resultados
de SQLAlchemy, no un log explícito del servicio. Consultar Review completa también
podía registrar autor y contenido al habilitar DEBUG.

Se añadió un guard temporal por operación de `ReviewRepository`:

- No cambia consultas, resultados, contratos públicos, Engine, niveles, handlers
  ni filtros de logging. Las listas se materializan como antes.
- Sustituye sólo los emisores SQL de las Connection usadas durante la operación
  por registros técnicos fijos con nombre del método y tipo de actividad.
  No representa filas, parámetros, SQL con valores ni objetos Review.
- Cubre conexiones ya abiertas y las nuevas de `refresh()` tras un commit mediante
  un listener `after_begin` exclusivo de esa Session y de esa operación.
- Las llamadas anidadas comparten el guard. En `finally` se restauran los emisores,
  se elimina el listener y se retira el estado temporal, también ante excepciones.
- Otras conexiones, componentes y operaciones fuera de este alcance conservan
  sus logs. No es una política global para consultas directas o código ajeno.

El mecanismo utiliza los emisores internos `_log_info` y `_log_debug` de
SQLAlchemy 2.x porque `hide_parameters` no controla el registro de filas.
La versión instalada utilizada en las pruebas es SQLAlchemy **2.1.6**.
**Limitación residual:** debe revalidarse al actualizar SQLAlchemy; las pruebas
comprueban la redacción, restauración y ausencia de cambios globales. No se
introducen nuevas dependencias ni modificaciones del paquete instalado.

Regresiones nuevas con datos sintéticos y DEBUG activo comprueban autor, contenido,
ID externo, negocio, referencia de aprobación, huella, parámetros de búsquedas y
escrituras, además de resultados técnicos seguros. Se prueban lectura, filtros,
conteos, registro manual, edición, estado, guardado de un resultado IA sintético
sin proveedor y persistencia externa, con `hide_parameters` tanto True como False.
Se verifican también restauración tras éxito/error, eliminación del listener y
conservación de logs de otra conexión del mismo Engine y otro componente.

### Índice parcial aceptado como padre de una FK

La validación anterior comprobaba nombre, unicidad y columnas, pero omitía el
predicado WHERE. Así aceptaba un índice parcial y la inicialización terminaba
sin detectar que SQLite rechazaba después la FK compuesta con `foreign key mismatch`.
Inspector también omite algunos índices basados en expresiones en SQLite.

La corrección inspecciona `PRAGMA index_list` e `index_xinfo` en SQLite y la
metadata de índices/restricciones de Inspector en PostgreSQL. Exige claves únicas
completas con las columnas exactas, sin predicados, expresiones ni claves adicionales.
Se admite el orden inverso de esas mismas dos columnas: la unicidad y la FK siguen
siendo válidas, como comprueba una regresión SQLite con inserción y FK reales.
El nombre reservado `uq_reviews_id_tenant` con una definición incompatible produce
un error técnico fijo; no se borra, reemplaza ni reconstruye el índice o tabla.

Una restricción UNIQUE de tabla o un índice completo de otro nombre se reconoce
y reutiliza. Índices parciales ajenos pueden coexistir, pero nunca se seleccionan
como respaldo de la FK. Si sólo existe uno parcial ajeno se conserva y se crea el
índice completo necesario. Un índice reservado incompatible se rechaza incluso
si coexiste otra clave válida.

Tras crear las tablas, SQLite verifica la relación mediante una consulta booleana
sobre `pragma_foreign_key_check('external_review_identities')`. Esto detecta también
colaciones incompatibles sin devolver IDs de registros a los logs. La excepción
SQL original no se incorpora al diagnóstico público de esta verificación.

Las regresiones verifican índices completos, parciales, no únicos, columnas
incorrectas/adicionales, expresiones, colaciones, duplicados, coexistencia, UNIQUE
de tabla, reejecución y conservación exacta del esquema y filas al rechazar una
migración. Se insertan identidades válidas y se comprueba con SQL directo que una
reasignación de tenant es rechazada por la FK real, con `foreign_keys=ON`.

Para PostgreSQL se prueban candidatos de metadata sintética y compilación de
índices completos y parciales. Esto **no prueba reflexión, migraciones ni FK en
un servidor PostgreSQL real**; esa validación continúa pendiente.

## Validación ejecutada

Entorno virtual existente, sin nuevas dependencias, drivers ni infraestructura.
Ejecuciones con bytecode y caché de pytest deshabilitados, directorio de trabajo
aislado y bases de prueba nuevas fuera de la BD de desarrollo. Se retiraron las
credenciales del proveedor del entorno de los procesos de pruebas. Se bloquearon
conexiones y DNS externos; loopback se permite sólo para las herramientas locales
de TestClient. No se borraron temporales previos del usuario.

- Auditoría anterior a la corrección: 98 focalizadas y 1248 backend aprobadas,
  pero dos casos adversariales adicionales reprodujeron los P2 descritos arriba.
- Primera ejecución tras corregir: **122 aprobadas**, 0 fallos, 36.26 s.
- Validación focalizada final, con las 98 originales y 26 regresiones:
  **124 aprobadas**, 0 fallos, 25.98 s.
- Regresión backend completa posterior a los P2: **1274 aprobadas**, 0 fallos,
  1037.02 s. Incluye importación CSV/Excel, registro manual, consulta/detalle,
  filtros, dashboard, edición/estados, clasificación, prioridad, resumen, temas,
  respuestas sugeridas y exportación con proveedores simulados. Se utilizó
  `PYTHONTZPATH` temporal para Windows, sin modificar dependencias.
- Reejecución de los diez escenarios adversariales de la auditoría: **10 aprobados**,
  incluidos los dos que fallaban; sin marcadores de conexión en DEBUG e índice
  parcial rechazado antes de declarar válida la inicialización.
- Dos escenarios adicionales aprobados: escritores con conexiones físicas
  independientes y bloqueo real; consulta, edición, estado, dashboard, exportación
  y registro manual por FastAPI sobre reseña sintética importada, con FK activas.
- La primera ejecución general intermedia fue detenida al incorporar el caso de
  clave válida en orden inverso. No se contabiliza como suite completa aprobada;
  la ejecución final se reinició con el código y los 26 casos nuevos definitivos.
- Una advertencia existente de Starlette/TestClient por el uso de HTTPX.
- Cero intentos de conexión o DNS externo.
- La primera ejecución detectó problemas de preparación de pruebas con etiquetas
  de parámetros de gran tamaño; se asignaron identificadores cortos a esos casos.
- DDL SQLite y PostgreSQL compilado sin servidor; consulta real del repositorio
  contrastada mediante compilación para verificar ámbito y `FOR UPDATE`.
- Sintaxis de los doce archivos Python de #3834 y revisión de espacios del diff,
  incluidos los siete archivos nuevos sin seguimiento, correctas. Los cinco
  archivos modificados durante la corrección pertenecen al alcance aprobado.
- Los hashes de `.env`, la base SQLite local y los veinte archivos locales previos
  sin seguimiento permanecen iguales. `.env` continúa ignorado y sin versionar.
- Resultado técnico: ambos P2 corregidos y validación local superada; pendiente de
  revisión pre-commit. No se declara completada la Task ni validado PostgreSQL real.

Cobertura: commit único sin refresh posterior, primera inserción, reimportación,
fuente editable independiente, estados/campos manuales y resultados IA intactos,
dos tenants y dos negocios con el mismo ID, comparación opaca exacta, conflictos
de lote, reseñas sin texto, política de incompletas, contexto falso o inactivo,
activación cerrada por defecto, FKs compuestas, unicidad real, borrados/reasignación
inválidos, fallos tras flush, commits inciertos antes/después de una confirmación,
colisión de unicidad, concurrencia con dos sesiones, SQLite ocupado, límites,
Unicode/NUL, UTC, contadores manipulados, privacidad, importación aislada sin
HTTP/Gemini/engine por defecto y migraciones nuevas, antiguas, parciales y repetidas.

## PostgreSQL y decisiones pendientes

PostgreSQL es el objetivo de despliegue, pero **no está completamente verificado**.
No hay driver ni servidor PostgreSQL utilizable en este entorno. Compilar DDL y
simular SQLSTATE no prueba concurrencia, rollback, índices o migraciones en un
servidor real. Las pruebas SQLite no sustituyen esa evidencia.

Quedan pendientes ejecución PostgreSQL con BD de pruebas desechable y UTF-8,
inspección de índices/FKs reales, migración desde esquema antiguo, dos sesiones
concurrentes, locks/errores de serialización y recuperación tras fallos de commit.
No se instalaron Docker, servidores, drivers ni se modificó infraestructura.

El PO debe validar política sin texto, ausencia de actualización automática,
tratamiento de cambios externos, posibilidad de persistencia parcial, límites y
permisos de uso. #3835 deberá conectar autenticación, sesión exclusiva,
establecimiento autorizado, cliente, normalizador y persistencia; revisar los
consumidores de visualización/exportación/IA antes de habilitar datos reales.

No se realizó staging, commit, push, PR, merge ni cambio en OpenProject.
