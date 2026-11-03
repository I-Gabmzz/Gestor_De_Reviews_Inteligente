# HU-21 / Task #3835 — Integración y fuente real

## Alcance y estado

Fecha de validación: 2026-11-02. Base de trabajo:
`feature/HU-21-integraciones-externas`, HEAD
`162addf3818b3a8572ddf692e7d0579e5a1a0cf2`.

La Task busca probar el recorrido de adquisición, normalización y persistencia.
Esta entrega implementa exclusivamente la fase A autorizada: pruebas completas
con HTTP y datos sintéticos. No añade endpoints, orquestadores de producción,
modelos, migraciones, configuración ni mecanismos públicos de activación.

| Nivel | Evidencia | Estado |
| --- | --- | --- |
| A | Cliente real de código + HTTP simulado + normalizador + persistencia en SQLite temporal | Implementado y validado con pruebas sintéticas |
| B | Lectura limitada del proveedor real con el cliente actual | Procedimiento preparado; sin ejecutar y pendiente de autorización específica |
| C | Persistencia de reseñas reales | Bloqueada por derechos pendientes |

La fase A no demuestra B ni C. La prueba histórica de #3831 acredita acceso
técnico anterior, no saldo actual ni compatibilidad real del recorrido actual.
No se declara completada #3835 únicamente con mocks.

## Componentes y contratos existentes

Las pruebas llaman directamente a los componentes de producción publicados:

```python
SerpApiClient(config=None, *, transport=None)
client.fetch_reviews(data_id, *, page_size=None, max_pages=None)  # SerpApiResult
normalize_serpapi_result(result, *, business_data_id=...)  # NormalizationBatchResult
ExternalReviewPersistenceService(repository, *, allow_incomplete=False)
service.persist(batch, *, current_user=..., business_data_id=...)  # ExternalReviewPersistenceResult
```

`ReviewRepository` recibe una `Session` de SQLAlchemy. El resultado persistido
se comprueba mediante consultas directas a `Review` y `ExternalReviewIdentity`.
No se reemplazan el cliente, el normalizador ni el servicio por mocks. Se simulan
el transporte HTTP y un fallo de repositorio para comprobar rollback.

## Entorno y flujo probado

Archivo: `backend/tests/test_external_review_integration.py`.

- `httpx.MockTransport`, con transporte instrumentado para contar solicitudes y
  comprobar su cierre. Las solicitudes registradas en memoria excluyen la clave.
- `SerpApiSettings` explícita con credencial ficticia y `_env_file=None`;
  las variables SerpApi heredadas se eliminan temporalmente mediante `monkeypatch`.
- Respuestas construidas en código, sin recuperar fixtures de #3831.
- SQLite en el directorio temporal exclusivo de cada test, con FK habilitadas;
  inicialización mediante `init_db(engine)` dirigido expresamente a esa base.
- Usuarios, correos `example.com`, tenants, establecimientos y reseñas ficticios.
  La habilitación con referencia `synthetic-test-only` existe exclusivamente en
  esas bases efímeras. No se activa almacenamiento real.

El flujo principal adquiere una página simulada, comprueba el identificador del
establecimiento cuando está presente, normaliza y verifica fuente, texto, autor,
puntuación y fecha UTC. Sólo después abre una sesión exclusiva de persistencia.
Consulta ambas tablas y repite una adquisición/importación idéntica: permanece
una sola reseña con una sola identidad externa.

Los eventos `checkout`/`checkin` comprueban que no hay conexiones de base de datos
retenidas durante HTTP ni al finalizar los tests. Cada persistencia utiliza una
sesión nueva ligada al engine, sin transacción anterior; el servicio conserva la
propiedad de su commit/rollback. El transporte se cierra incluso ante errores.

## Escenarios y aserciones

| Grupo | Comprobaciones efectivas |
| --- | --- |
| Adquisición | Una página y varias páginas; token sólo desde `next_page_token`; cantidad exacta de intentos; no se sigue la URL de continuación |
| Recorridos incompletos | Límite de páginas, página vacía con token y token repetido; indicadores y motivo conservados; persistencia rechazada por defecto |
| Errores | HTTP 401, 429 y 503; error del proveedor, estado pendiente y timeout; todos antes y después de una página válida; sin reintentos ni escrituras parciales |
| Mapeo | Fuente Google, origen del texto, texto/autor ausentes, fecha con offset convertida a UTC, puntuaciones enteras y flotantes integrales válidas; rechazo de booleanos, texto, fracciones y valores fuera de rango |
| Duplicados | Idénticos contabilizados; todas las versiones conflictivas rechazadas; conciliación de contadores |
| Persistencia | Inserción de Review y su identidad; reimportación sin duplicados; reseñas sin texto omitidas sin crear identidad |
| Cambios posteriores | Cambio externo reportado sin sustituir texto, autor, fuente, estado o resultados de IA sintéticos editados localmente; fingerprint original conservado |
| Transacciones | Fallo después de insertar el segundo registro; rollback de ambas tablas; cero huérfanos; reejecución posterior correcta |
| Tenants | Mismo ID externo en dos tenants produce dos reseñas independientes; claims de tenant en JSON no controlan el contexto; conexión ajena rechazada |
| Límites | Cinco páginas de veinte registros; límites por operación fuera de rango sin HTTP; página de 21 registros rechazada; límites de identificador, contenido UTF-8, establecimiento y presupuesto textual agregado |
| Seguridad | Logs DEBUG ejercitados, repr y excepciones sin marcadores privados; transportes y sesiones liberados; niveles, handlers y propagación conservados |

Los límites probados incluyen ID externo de 512 caracteres/1024 bytes, contenido
de 64 KiB, establecimiento de 128 caracteres y presupuesto textual agregado de
1 MiB. Las cinco páginas de veinte registros alcanzan las 100 ocurrencias
admitidas por persistencia. Los límites se prueban en sus fronteras y con excesos.
Los IDs de parametrización son cortos para no incorporar grandes payloads al
nombre de directorio temporal en Windows.

`request_count` representa intentos HTTP, incluidos los fallidos. No representa
créditos facturados. No se comprueba saldo real ni se implementa un presupuesto
agregado entre operaciones, cuentas o tenants.

## Identidad de establecimiento y autorización

La composición de pruebas compara `place_info.data_id`, cuando existe, con el
identificador solicitado. Un valor diferente detiene esa composición antes de
normalizar/persistir. Esta comprobación pertenece al helper de pruebas: **el
cliente de producción conserva `place_info`, pero no verifica automáticamente
la identidad comercial**. No se añadió un orquestador que lo haga.

Si no hay identificador verificable, se documenta esa ausencia. No se infiere
equivalencia desde el nombre. La prueba sintética correspondiente usa únicamente
el establecimiento confiable solicitado y configurado en su fixture; no acredita
una identidad externa que la respuesta no contiene.

El contexto del normalizador debe coincidir con el de persistencia. El servicio
rechaza registros de otro establecimiento, comprueba usuario/tenant activos y
consulta la conexión por tenant, fuente y establecimiento. La identidad utiliza
unicidad compuesta por esos campos y el ID externo. Los `tenant_id` recibidos en
JSON son ignorados: se utiliza `AuthenticatedUser` preparado del lado del servidor.

Una integración operativa futura deberá autorizar también la lectura antes de
consumir cuota, cerrar la sesión de comprobación y revalidar al persistir con una
sesión exclusiva. Esta entrega no crea un disparador operativo ni reutiliza la
sesión de autenticación para escribir.

## Seguridad y ausencia de tráfico externo

El fixture automático intercepta `socket.getaddrinfo`, `socket.gethostbyname`,
`socket.gethostbyname_ex` y `socket.gethostbyaddr`; también `socket.create_connection`,
`socket.socket.connect`, `connect_ex` y `sendto`, los métodos de envío de los
transportes HTTPX reales síncrono/asíncrono y la inicialización de `GeminiAdapter`.
La interceptación usa `monkeypatch` y se restaura al terminar cada ámbito de prueba.
Adicionalmente,
`httpx.Client.send` acepta sólo GET de Google Maps Reviews con el transporte
simulado instrumentado de este módulo. Cualquier otro HTTP, incluido un envío de
publicación, falla el test. El contador de intentos inesperados debe quedar vacío.

Se añaden seis casos para los tres resolutores heredados, con salida normal y
con excepción: una función centinela sustituye al resolver subyacente antes de
instalar la protección. Las sondas deben fallar en el bloqueo sin alcanzar el
centinela, y las referencias deben restaurarse en ambos tipos de salida. Sólo se
retira del contador la sonda deliberada tras comprobar que es el único intento.
No se realiza resolución DNS real. Esto corrige el P3 detectado en la auditoría.

Estas barreras cubren las operaciones enumeradas y los componentes ejercitados;
no son un aislamiento universal del sistema operativo ni una garantía frente a
cualquier biblioteca, subproceso o mecanismo posible de acceso a red.

El ejecutor de validación añade una barrera de sockets/DNS antes de importar
pytest. Usa `DATABASE_URL=sqlite:///:memory:`, elimina del proceso la clave
SerpApi y `SSLKEYLOGFILE`, deshabilita plugins automáticos, bytecode y caché pytest,
y utiliza directorios nuevos fuera del repositorio. La regresión general permite
loopback para las herramientas de pruebas, pero bloquea destinos externos.

Los logs HTTPX/HTTPCore reciben deliberadamente URL y marcadores ficticios durante
la solicitud; se comprueba su supresión. Los logs SQLAlchemy DEBUG se ejercitan
durante persistencia y deben contener actividad redactada sin texto, autor ni ID
privado. El test verifica que los niveles, handlers y propagación se restauran.
Los filtros de privacidad HTTP permanentes del cliente son comportamiento previo;
no se afirma que no exista ninguna modificación de filtros.

Los resultados de IA usados para probar conservación son cadenas insertadas
manualmente en SQLite temporal. No se invoca un modelo ni se publican respuestas.
No se utiliza ninguna clave real, review real o nombre de cliente real.

## Antecedentes de validación anteriores a la corrección P3

| Ejecución | Resultado |
| --- | --- |
| Suite nueva #3835 | 48 aprobadas, 2 advertencias, 2.34 s; cero intentos externos |
| Pruebas relacionadas #3832, #3833 y #3834 | 377 aprobadas, 2 advertencias, 12.13 s; cero intentos externos |
| Regresión backend completa | 1322 aprobadas, 2 advertencias, 382.89 s; cero intentos externos; `PYTHONTZPATH` temporal |
| Sintaxis Python | Compilación en memoria correcta, sin generar bytecode |
| Archivos existentes | 260 hashes previos conservados, incluidos `.env`, SQLite y 20 archivos sin seguimiento; índice vacío; `.env` ignorado y sin versionar |

Las dos advertencias de las tres ejecuciones proceden de Starlette/TestClient:
deprecación de su uso de HTTPX y del alias `anyio.abc.BlockingPortal`.
Estos resultados son antecedentes de la implementación inicial, no ejecuciones
nuevas de la corrección P3. La suite backend completa de 1322 casos no se repite:
no cambió código de producción. La validación actual se registra por separado.

## Validación actual de la corrección P3

| Ejecución | Resultado |
| --- | --- |
| Integración #3835, incluidos los seis casos nuevos | 54 aprobadas, 2 advertencias, 2.38 s |
| Pruebas relacionadas #3832–#3834 | 377 aprobadas, 2 advertencias, 7.45 s |
| Escenarios adversariales adicionales ejecutados en memoria | 10 aprobados; 12 sondas deliberadas bloqueadas antes de alcanzar la red |
| Conexiones y consultas DNS externas reales durante las pruebas | 0; sin SerpApi real, Gemini ni publicaciones automáticas |

Los escenarios adicionales verifican FK compuestas entre tenants y conexiones,
unicidad con rollback, contexto autenticado falsificado, usuario revocado tras
HTTP, sesión de autenticación ocupada, dos sesiones concurrentes, barreras DNS y
HTTP/IA/publicación, bloqueo de resolutores heredados y privacidad ante errores.
No crean archivos de pruebas adicionales dentro del repositorio.

Las seis sondas de la suite integrada y las doce del ejecutor adversarial son
operaciones negativas deliberadas y bloqueadas, no tráfico DNS/HTTP real. Los
contadores de intentos inesperados quedan en cero. Las dos advertencias de pytest
son las de Starlette/TestClient ya descritas. Los recuentos de ejecuciones
independientes no se suman como casos únicos adicionales.

Para repetir la suite nueva desde backend, usando una base por defecto en memoria
y un directorio temporal nuevo fuera del repositorio:

```powershell
$hu21TestTemp = Join-Path ([IO.Path]::GetTempPath()) ("hu21-3835-" + [guid]::NewGuid().ToString("N"))
$env:DATABASE_URL = "sqlite:///:memory:"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
python -B -m pytest -q -p no:cacheprovider --basetemp "$hu21TestTemp" tests/test_external_review_integration.py
```

Ejecutar en una sesión de consola destinada a pruebas: las variables sólo afectan
ese proceso y sus hijos, no el archivo `.env`. Para la regresión general, utilizar `PYTHONTZPATH` temporal
con datos horarios válidos de `America/Tijuana` si Windows no los proporciona;
no modificar dependencias del proyecto ni instalar paquetes globales.

## Fase B: procedimiento preparado, no ejecutado

1. Obtener autorización específica de Gabriel para una solicitud, máximo cinco
   reseñas y máximo un crédito gratuito, sin cargos, paginación ni reintentos.
2. Gabriel comprueba saldo gratuito actual y ausencia de condiciones que puedan
   generar cargos en el panel. El saldo histórico no sirve como prueba actual.
   Si no se puede garantizar la condición sin cargos, detenerse.
3. Resolver la seguridad de la clave anteriormente expuesta; preferir su rotación.
   Verificar `.env` ignorado y cargarla sin mostrar valor ni URL autenticada.
4. Usar Metro Café – UABC y el identificador ya probado:
   `0x80d7714666b3fca7:0x995967454b24c05e`. No buscar otro establecimiento.
5. Abrir un único `SerpApiClient` y ejecutar una sola vez
   `fetch_reviews(data_id, page_size=5, max_pages=1)`. No invocar persistencia ni
   abrir la base de desarrollo. No llamar APIs de cuenta para medir el consumo.
6. Verificar `place_info` sin suponer identidad única por nombre. Si falta una
   identificación suficiente o hay contradicción, informar la limitación y no
   interpretar la muestra como perteneciente al negocio confirmado.
7. Normalizar sólo en memoria y comprobar presencia y compatibilidad de
   `review_id`, `source`, `iso_date`, `rating`, `user.name`, `snippet` y
   `extracted_snippet.original`, sin imprimir valores privados. Informar conteos
   de aceptadas, sin texto y rechazadas por códigos; no presuponer los 2/5 textos
   de la muestra histórica.
8. Si aparece continuación, conservar `incomplete=True`, `limited=True` y
   `stop_reason=max_pages`; no usar el token ni declarar sincronización completa.
   Ante error, registrar el código anonimizado y detenerse sin segunda solicitud.
9. Registrar fecha, HTTP, estado de búsqueda, negocio identificado, cantidad,
   presencia de campos, intentos y motivo de terminación. Gabriel podrá comprobar
   consumo en el panel; si no se verifica el débito, indicarlo expresamente.
10. Cerrar el cliente y descartar datos en memoria. No guardar respuesta, autores,
    textos, IDs de reseñas, token, clave o URL autenticada; no usar Gemini.

## Derechos pendientes y fase C

La lectura técnica y su normalización en memoria no autorizan insertar reseñas reales en Review ni habilitar su visualización, retención o procesamiento mediante IA.

El acceso técnico de SerpApi no prueba derechos de almacenamiento, visualización,
retención, transferencia ni procesamiento mediante IA. Cada uso sigue pendiente
de evidencia aplicable. Insertar en Review podría exponer datos a funcionalidades
existentes; la autorización de lectura no habilita esos usos.

Mantener el almacenamiento real deshabilitado. Ninguna configuración persistente
se modifica por esta entrega. La habilitación sintética del fixture no constituye
un mecanismo ni una autorización para habilitar conexiones reales.

## Riesgos residuales y PostgreSQL

- Continúan pendientes migraciones, restricciones e índices compuestos,
  collations, bloqueos, concurrencia y recuperación transaccional en PostgreSQL
  real. SQLite y compilación SQL no equivalen a esa validación. No se instalan
  drivers, PostgreSQL o Docker.
- La protección SQLAlchemy usa emisores internos; requiere regresiones ante
  actualizaciones y no protege automáticamente SQL ejecutado fuera del repositorio.
- Continúa el P3 de loggers HTTP creados posteriormente sin filtro equivalente.
- Los límites de persistencia no limitan retroactivamente bytes descargados o
  memoria durante JSON/normalización. No aceptar lotes arbitrarios sin límites.
- No hay control agregado de cuota o facturación. Las pruebas no acreditan saldo.
- Falta evidencia real del cliente/normalizador actuales, permisos de uso y
  seguridad resuelta de la clave expuesta. La fase B requiere autorización nueva.

## Criterios de aceptación de esta entrega

- El flujo completo utiliza los cinco componentes existentes y verifica las dos
  tablas, con aserciones de mapeo, contadores, idempotencia y rollback.
- Las pruebas de errores, aislamiento, permisos deshabilitados y límites pasan
  con transporte exclusivamente simulado y sesiones exclusivas.
- Tras corregir P3 pasan las 54 pruebas de integración y las 377 relacionadas;
  la regresión completa de 1322 casos permanece como antecedente aprobado.
- No hay tráfico externo, datos reales, modificaciones de producción ni cambios
  en los archivos previos. Sólo se crean los dos archivos autorizados.
- Las fases B y C conservan sus bloqueos; PostgreSQL real sigue sin validarse.

La autorización de publicación se limita a los dos archivos de fase A. No incluye
fase B, PR, merge ni cambios en OpenProject. #3835 permanece abierta; la evidencia
sintética no demuestra acceso real actual ni habilita la persistencia real.
