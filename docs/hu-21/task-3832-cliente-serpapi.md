# HU-21 — Task #3832: cliente interno de SerpApi

## Objetivo y alcance

Responsable: Gabriel Manjarrez. Fecha de implementación: 2026-11-02.
Base: `feature/HU-21-integraciones-externas`, HEAD
`401bfdda50328d1d94583623d4ac631ab28ef3c6`.

Implementar consumo paginado acotado y gestión de errores, mediante un cliente
síncrono reutilizable desde el backend. La evidencia de acceso real permanece
en `evidencia-task-3831-acceso-serpapi.md`; no se repitió esa consulta.

Esta implementación no crea rutas HTTP, no importa repositorios o SQLAlchemy,
no modifica `Review`, no persiste reseñas y no envía información a Gemini.
Tampoco programa sincronizaciones ni integra autorización por tenant.

## Arquitectura y contrato

- `app/core/serpapi_config.py`: `SerpApiSettings`, cargada al construir el cliente.
- `app/schemas/serpapi.py`: contratos nativos internos en memoria.
- `app/services/serpapi_client.py`: transporte HTTPX, paginación y errores.
- `tests/unit/test_serpapi_config.py` y `test_serpapi_client.py`: pruebas simuladas.
- `.env.example`: nombres de variables y valores predeterminados sin credenciales.

Interfaz:

```python
with SerpApiClient(settings, transport=transport) as client:
    result = client.fetch_reviews(data_id, page_size=2, max_pages=1)
```

El ejemplo describe la interfaz; no debe ejecutarse contra el proveedor sin
autorización de consumo. En pruebas, `settings` usa un marcador sintético y
`transport` siempre es simulado. Sin configuración explícita, el constructor
carga `SerpApiSettings` de manera diferida. Importar el módulo no exige clave
ni crea conexiones; no hay cambios en el arranque de FastAPI.

`SerpApiResult` contiene:

| Campo | Significado |
|---|---|
| `pages` | Tupla de páginas válidas recibidas; número, HTTP 200, estado Success, reseñas nativas y token interno. |
| `reviews` | Propiedad que reúne las reseñas de las páginas, sin normalización ni deduplicación. |
| `place_info` | Información del negocio de la primera página, si existe. |
| `first_page_metadata` | Sólo id, status, created_at, processed_at y total_time_taken disponibles de la primera página. |
| `request_count` | Intentos de solicitud de esta operación, incluido el intento fallido. No equivale a créditos. |
| `record_count` | Registros de páginas válidas, incluidos registros sin texto. |
| `stop_reason` | Motivo estable de detención. |
| `incomplete` | Recorrido interrumpido por límite, anomalía o error. |
| `limited` | Se alcanzó el máximo de páginas con continuación pendiente. |

Cada `SerpApiReview.data` conserva el diccionario nativo, sin completar texto
ausente ni convertirlo al modelo ORM. Las páginas posteriores pueden omitir
`place_info`; los metadatos originales no se reemplazan. Los diccionarios
siguen siendo mutables y sensibles aunque sus contenedores sean dataclasses
congeladas; son contratos internos, no esquemas para publicar como respuesta.

## Configuración

| Variable | Valor inicial / validación |
|---|---|
| `SERPAPI_API_KEY` | Requerida al construir el cliente; `SecretStr`, no vacía, ASCII imprimible sin espacios internos. |
| `SERPAPI_PAGE_SIZE` | 5; rango 1–20. |
| `SERPAPI_MAX_PAGES` | 3; rango 1–5. |
| `SERPAPI_TIMEOUT_SECONDS` | Lectura: 30 segundos; positivo, finito, máximo 120. |

Conexión, escritura y pool: 5 segundos cada uno. Reintentos automáticos: cero.
La ruta de `.env` se resuelve desde el módulo hasta `backend/.env`, con
independencia del directorio actual. El entorno del proceso tiene la prioridad
habitual de Pydantic Settings. Las pruebas deshabilitan ese archivo y eliminan
las variables SerpApi heredadas para no cargar credenciales reales.

## Peticiones, paginación y consumo

Método GET contra `https://serpapi.com/search.json`, sin redirecciones ni
proxies heredados del entorno. No hay host, motor ni autenticación controlables
desde `fetch_reviews`.

Parámetros fijos: `engine=google_maps_reviews`, `sort_by=newestFirst`, `hl=es`,
`output=json`, `async=false`, `no_cache=false`. Se agregan el `data_id` validado
en formato hexadecimal `0x...:0x...`, `num` y la credencial de configuración.
Cada continuación agrega exclusivamente `next_page_token`, conservando todos
los demás parámetros. No se usa `start` ni se sigue la URL `next` del proveedor.

Los argumentos por operación sólo pueden reducir los límites configurados.
Se rechazan identificadores inválidos y límites fuera de rango antes de enviar
solicitudes. Una respuesta con más registros que `num` se rechaza como inválida.

| `stop_reason` | Comportamiento |
|---|---|
| `no_next_token` | Recorrido terminado según la respuesta, incluso si la página está vacía. `incomplete=False`. |
| `empty_with_token` | Se recibió una página vacía con continuación; detener sin otra solicitud. |
| `repeated_token` | Se repitió un token visto en esta operación; detener antes de reutilizarlo. |
| `max_pages` | Quedó continuación al alcanzar el límite. `limited=True`. |
| `error` | Se lanzó una excepción sanitizada; el resultado interno es parcial. |

Los últimos cuatro motivos producen `incomplete=True`. Ninguno de los motivos,
incluido `no_next_token`, garantiza recuperar todas las reseñas públicas.

Presupuesto predeterminado por operación: hasta 3 intentos / 15 registros.
Máximo configurable: 5 intentos / 100 registros. Estos son límites de la
operación, no del saldo mensual ni de llamadas acumuladas. La caché puede influir
en el débito del proveedor: no se infieren créditos gastados de `request_count`.
Un timeout puede ocurrir después de que el proveedor haya procesado la solicitud;
por eso no se reintenta. No hay consultas auxiliares a la API de cuenta.

## Errores y resultado parcial

`SerpApiError` expone `code`, `http_status` si se conoce y `partial_result`.
Los mensajes son constantes y no incluyen cuerpos, URLs, parámetros ni textos
del proveedor. Los errores de transporte y JSON se elevan sin mostrar la cadena
original de excepciones. No se usa `raise_for_status()` con una URL autenticada.

| Condición | Código |
|---|---|
| Configuración ausente o inválida | `configuration` |
| Identificador o límites inválidos | `input` |
| Cliente cerrado | `closed` |
| HTTP 400 y otros HTTP no admitidos | `request` |
| HTTP 401 / 403 / 429 | `credentials` / `forbidden` / `quota` |
| HTTP 500, 503 y otros 5xx | `unavailable` |
| HTTP 3xx | `redirect` |
| Timeout / error de conexión o protocolo | `timeout` / `network` |
| JSON o estructura inválidos; estado desconocido | `invalid_response` |
| Token de continuación no codificable en UTF-8 | `invalid_response` |
| HTTP 200 con estado Error o campo error no vacío | `provider_error` |
| Processing, Queued o Pending | `pending`, sin sondeo |

Una respuesta con error se trata conservadoramente como fallo, aunque también
declare Success; no se interpreta el texto libre del proveedor para deducir
que una búsqueda vacía terminó bien. Las búsquedas pendientes tampoco se
consultan por segunda vez automáticamente.

Después de una página válida, cualquier fallo conserva sólo las páginas ya
validadas en `partial_result`, con `stop_reason=error`, `incomplete=True` y el
intento fallido contado. Se lanza la excepción: no se devuelve un éxito completo.
Antes de la primera página válida, el parcial tiene cero registros. Los errores
de entrada y configuración ocurren antes de iniciar una operación y no tienen
parcial. Cada respuesta y el cliente se cierran; usar `with` o `close()`.

## Hallazgo P2 y corrección

La auditoría final reprodujo una continuación con un sustituto Unicode aislado.
El token era una cadena no vacía, pero HTTPX no podía codificarla para construir
la siguiente petición. Se escapaba `UnicodeEncodeError`, sin `partial_result`,
y `repr` podía incluir el token e incluso una credencial sintética reflejada
por el proveedor. No se utilizaron credenciales ni reseñas reales al reproducirlo.

La corrección está localizada en `_validate_body`: comprobar
`token.encode("utf-8")` y convertir `UnicodeEncodeError` en
`SerpApiError("invalid_response", http_status=200)`, con mensaje fijo y sin
mostrar la excepción original. La validación ocurre antes de agregar la página
al resultado y antes de construir otra petición. No se cambia el token válido.

La página que contiene el token inválido se rechaza completa. Si fue la primera,
el parcial tiene cero páginas y una solicitud; no hay segunda petición. Si fue
la segunda tras una primera válida, el parcial conserva sólo esa primera página,
con dos solicitudes y sin tercera petición. En ambos casos: `stop_reason=error`,
`incomplete=True`, `limited=False`. El contador no incluye una continuación que
nunca se intentó y no se introducen reintentos.

Se añadieron seis casos de regresión con `MockTransport`: cuatro combinaciones
de sustituto alto/bajo y página inválida primera/segunda; dos continuaciones
UTF-8 válidas con caracteres multibyte. Las aserciones comprueban código y HTTP,
parcial, metadatos, exclusión de registros de la página rechazada, conteo exacto,
ausencia de peticiones adicionales, parámetros conservados y ausencia del token
o credencial sintética en `str`, `repr`, traceback y registros INFO/DEBUG.

## Seguridad

- La credencial se excluye de `repr` y de la serialización de configuración.
- Reseñas, negocio, metadatos y tokens se excluyen de las representaciones de
  los contratos. No se conserva `search_parameters`, `json_endpoint` ni la URL
  de continuación como metadatos del resultado.
- HTTPX registra URLs autenticadas a nivel INFO; HTTPCore puede registrar
  excepciones y detalles a nivel DEBUG. Un filtro permanente se instala en los
  emisores `httpx`, `httpcore`, `httpcore.connection`, `httpcore.http11`,
  `httpcore.http2`, `httpcore.proxy`, `httpcore.socks` y sus descendientes ya
  registrados. Los filtros del padre no bastan para sus hijos.
- Un `ContextVar` descarta esos registros antes de llegar a los handlers durante
  cada petición y el cierre del cliente. No se formatea el mensaje, no se
  almacenan claves en el filtro y no se alteran niveles globales por petición.
  Las solicitudes ajenas en otros hilos conservan sus logs. Se verificó con
  HTTPX 0.28.1 / HTTPCore 1.0.9 y captura INFO/DEBUG, incluidas excepciones.
- El transporte predeterminado usa TLS con certificados del sistema y
  verificación de nombre/certificado. Un `SSLContext` explícito evita que
  `create_default_context()` active key logging al heredar `SSLKEYLOGFILE`.
  No cambia la variable global ni crea archivos de claves TLS.
- Los transportes inyectados son componentes internos de confianza. No agregar
  hooks de trazado, instrumentación de URLs ni logs de variables locales/cuerpos;
  cualquier nueva instrumentación o actualización de emisores del transporte
  requiere repetir la revisión de privacidad.
- No serializar ni registrar explícitamente `review.data`, `place_info` o tokens:
  excluirlos de `repr` no convierte su contenido en información pública segura.

### P3: riesgo residual de emisores de logging creados posteriormente

P3 permanece abierto. Un logger hijo creado después de instalar los filtros,
incluso dentro de un transporte inyectado, no hereda el filtro de su padre.
La auditoría lo reprodujo con un emisor sintético. Los emisores incorporados de
HTTPX 0.28.1 / HTTPCore 1.0.9 sí están cubiertos; las pruebas comprueban que los
logs ajenos fuera del contexto y en otro hilo se conservan.

No se amplió el mecanismo de logging: reinstalar filtros antes de cada petición
no cubriría hijos creados durante ella. Interceptar globalmente creación/emisión
de registros o modificar handlers/fábrica de registros requiere una revisión
de diseño y efectos sobre otras funcionalidades. Esa ampliación queda fuera de
esta corrección. No se cambiaron niveles, handlers ni la fábrica global.

Recomendación: mantener el transporte inyectado como componente interno de
confianza, revisar instrumentación y emisores al actualizar dependencias y
evaluar una solución de logging independiente antes de admitir nuevos emisores
durante las peticiones. No se declara protección para loggers arbitrarios ni
se declara P3 resuelto.

La clave anteriormente expuesta no fue modificada ni utilizada para estas
pruebas. Su rotación continúa pendiente. El cliente no consulta plan/saldo ni
garantiza ausencia de cargos en una futura ejecución; ésta necesita autorización
y verificación operativa independientes.

## Validación local

Se preparó únicamente el entorno virtual ignorado `backend/.venv`, que carecía
de pip y dependencias: `python -m ensurepip --upgrade` dentro del venv, seguido
de `python -m pip install -r backend/requirements.txt`. No se cambiaron manifiestos
ni se agregaron dependencias al proyecto. La descarga de paquetes no consultó
SerpApi. Se usó Python 3.13.9 y pytest 8.4.2.

Desde `backend`, comandos de selección:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --confcutdir=tests/unit tests/unit/test_serpapi_config.py tests/unit/test_serpapi_client.py
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --confcutdir=tests/unit tests/unit/test_serpapi_client.py -k "unencodable_pagination_token or utf8_pagination_token"
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/test_priority_verification.py
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
```

`--confcutdir=tests/unit` evita cargar el conftest general y FastAPI/DB en la
ejecución focalizada. La suite general usa sus fixtures SQLite temporales.
Para la ejecución de esta Task, ambos comandos se invocaron mediante
`pytest.main` en procesos aislados con plugins externos desactivados. Se quitó
`SSLKEYLOGFILE` sólo del entorno del proceso de prueba; su configuración global
no cambió. En focalizadas se bloquearon DNS y conexiones; en regresión se
bloqueó la red externa y sólo se permitió loopback para infraestructura local.
La regresión final se inició desde un directorio temporal fuera del proyecto
para evitar que la configuración general del backend leyera su `.env` local;
el motor global se configuró como SQLite en memoria sólo para ese proceso.
Todas las llamadas SerpApi fueron `MockTransport`, sin lectura de clave real,
acceso al proveedor, PostgreSQL ni consumo de cuota.

Para reproducir el aislamiento de la suite general desde `backend`, asignar
`$directorioIana` a la ruta absoluta del directorio temporal `zoneinfo` validado,
que contiene `America/Tijuana`. El procedimiento recibe esa ruta como argumento
y establece `PYTHONTZPATH` sólo en el proceso hijo; no cambia configuración global
ni instala paquetes en el venv del proyecto. Se reutilizaron los datos temporales
de tzdata 2026.6 preparados en la auditoría, sin modificar sus archivos.

```powershell
@'
import os, pathlib, socket, sys, tempfile
os.environ.pop("SSLKEYLOGFILE", None)
os.environ.pop("SERPAPI_API_KEY", None)
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
timezone_data = pathlib.Path(sys.argv[1])
if not timezone_data.is_absolute() or not (timezone_data / "America/Tijuana").is_file():
    raise ValueError("Se requiere un directorio temporal IANA absoluto y validado")
os.environ["PYTHONTZPATH"] = str(timezone_data)
backend = pathlib.Path.cwd()
sys.path.insert(0, str(backend))
connect = socket.socket.connect
resolve = socket.getaddrinfo
def offline_connect(sock, address):
    if isinstance(address, tuple) and str(address[0]) in ("localhost", "127.0.0.1", "::1"):
        return connect(sock, address)
    raise AssertionError("External network disabled")
def offline_resolve(host, *args, **kwargs):
    if host in ("localhost", "127.0.0.1", "::1", None):
        return resolve(host, *args, **kwargs)
    raise AssertionError("External DNS disabled")
socket.socket.connect = offline_connect
socket.getaddrinfo = offline_resolve
import pytest
with tempfile.TemporaryDirectory(prefix="hu21-regression-") as isolated_cwd:
    try:
        os.chdir(isolated_cwd)
        code = pytest.main(["-q", "--tb=short", "-p", "no:cacheprovider",
                            "-c", str(backend / "pyproject.toml"), str(backend / "tests")])
    finally:
        os.chdir(backend)
sys.exit(code)
'@ | .\.venv\Scripts\python.exe -B - "$directorioIana"
```

El `finally` restaura el directorio antes de limpiar el temporal: en Windows,
mantenerlo como directorio actual impide eliminarlo. Esta incidencia se detectó
en los envoltorios de recopilación y regresión; no en el cliente SerpApi. Tras
la suite completa, el envoltorio emitió `PermissionError [WinError 32]` durante
la limpieza, después de imprimir todos los resultados de pytest. El comando
anterior incorpora la corrección; se comprobó la restauración del directorio
en la ejecución aislada del módulo de prioridad. Quedaron carpetas temporales
fuera del repositorio; la revisión automática rechazó la limpieza manual de
la carpeta de recopilación con el motivo `blocked by policy` y no se forzó.

Resultados focalizados iniciales: **87 passed in 4.82s**, sin warnings ni acceso
a red. Incluyen límites configurados de cinco páginas / veinte registros,
operaciones independientes, errores del proveedor sin metadatos, aislamiento
de logs entre hilos y logs DEBUG que contienen excepciones simuladas.

La comprobación aislada del módulo existente `test_priority_verification.py`
dio **3 failed, 1 warning in 1.11s**. Los tres casos fallaron antes de evaluar
su comportamiento por `ZoneInfoNotFoundError: America/Tijuana`, causado por
`ModuleNotFoundError: tzdata` en este Python Windows. `tzdata` no figura en los
requisitos declarados y no se añadió para esta Task. Casos afectados:

- `test_verification_records_mismatches_without_hiding_them_or_exposing_credentials[Alta-0]`.
- `test_verification_records_mismatches_without_hiding_them_or_exposing_credentials[Media-1]`.
- `test_verification_rejects_empty_content_without_provider_and_never_overwrites_report`.

El warning procede de Starlette TestClient: uso de `httpx` deprecado en la
versión resuelta por los requisitos actuales. No afecta a las focalizadas.
No se instaló `httpx2` ni se cambió código ajeno al alcance para suprimirlo.

Resultado inicial de la suite general: **3 failed, 981 passed, 1 warning in
419.22s (0:06:59)**. Los 984 casos se ejecutaron, incluidas las 87 pruebas de
SerpApi. Los únicos fallos fueron los tres casos de prioridad descritos arriba.
Una primera ejecución general se interrumpió para validar la versión final
con aislamiento del directorio; no se contabiliza como resultado completo.

`git diff --check` pasó. La revisión final confirmó seis archivos nuevos y
sólo `.env.example` modificado entre los archivos versionados; índice sin
cambios. Los veinte archivos personales/de auditoría/métricas/temporales
preexistentes y `.env` conservaron sus hashes. La credencial local no figura
en ninguno de los siete archivos autorizados; `.env` sigue ignorado y sin
versionar. No hay imports de SQLAlchemy, repositorios, routers ni Gemini en
los módulos nuevos.

La auditoría posterior reprodujo los tres fallos en una copia del HEAD original
sin archivos ni imports de #3832: **3 failed, 1 warning in 0.98s**. Con datos IANA
temporales y `PYTHONTZPATH`, prioridad pasó y la suite previa a esta corrección
dio **984 passed, 1 warning in 357.13s**. Esto identifica una limitación del
entorno Windows, no una regresión de SerpApi. `tzdata` continúa sin declararse
en los manifiestos y sin instalarse en el venv del proyecto; no se afirma que
el entorno haya quedado resuelto de forma permanente.

### Validación de la corrección P2

Antes de aplicar la corrección, los casos nuevos dieron **4 failed, 2 passed,
87 deselected in 0.91s**. Los cuatro fallos reprodujeron el defecto original;
las dos continuaciones válidas ya funcionaban.

Después de aplicar la corrección:

| Comprobación | Resultado real |
|---|---|
| Regresiones nuevas P2 y tokens UTF-8 válidos | 6 passed, 87 deselected in 1.35s |
| Suite focalizada completa de #3832 | 93 passed in 2.27s |
| Tres pruebas de prioridad con `PYTHONTZPATH` temporal | 3 passed, 1 warning in 2.31s |
| Suite general con `PYTHONTZPATH` temporal | 990 passed, 1 warning in 354.13s (0:05:54) |
| Sintaxis de cliente y pruebas | Aprobada, sin escribir bytecode. |
| Dependencias: `pip check` | No broken requirements found. |
| `git diff --check` y espacios de los tres archivos editados | Aprobados. |

Los procesos de prueba bloquearon red externa y DNS; focalizadas sin conexiones
permitidas y suite general sólo con loopback para su infraestructura local.
Se usó un directorio de trabajo aislado para no leer el `.env` local desde la
configuración general. No se utilizó la clave real ni se realizaron solicitudes
reales a SerpApi. Los datos horarios se configuraron sólo en los procesos de
prioridad y regresión, manteniendo la configuración global sin cambios.

Las ejecuciones focalizadas, de prioridad y general registraron cero intentos de
conexión o DNS externos. Permanece una advertencia de Starlette/TestClient por
uso de HTTPX deprecado; no se modificaron dependencias para suprimirla.

La revisión de integridad confirmó cambios sólo en el cliente, su archivo de
pruebas y este documento durante la corrección. Configuración, contratos,
pruebas de configuración, `.env.example`, `.env` y archivos locales ajenos
conservaron sus hashes. La clave real no aparece en ninguno de los siete
archivos de #3832; `.env` continúa ignorado y sin versionar. Se mantiene la rama
y el HEAD originales, con índice vacío.

Veredicto posterior a P2: **LISTA PARA COMMIT** dentro del alcance autorizado,
con P3 abierto como riesgo residual documentado. No se hicieron staging, commit,
push, PR, merge ni cambios en OpenProject. No se declara resuelta la exposición
previa de la credencial ni los bloqueos de integración de las Tasks siguientes.

No se ejecutaron pruebas reales de SerpApi, pruebas contra PostgreSQL ni de
frontend: no están autorizadas o no corresponden al cambio. No hay nuevas
reseñas reales persistidas ni solicitudes a servicios de IA.

## Dependencias y bloqueos que permanecen abiertos

- #3833: normalización y política para reseñas sin texto; no inventar contenido.
- #3834: persistencia e idempotencia, condicionadas a derechos de almacenamiento
  y retención confirmados; el cliente no realiza deduplicación entre páginas.
- #3835: flujo de integración/sincronización y manejo operativo de errores,
  según criterios aprobados para esa Task.
- Confirmar derechos de almacenamiento, retención, visualización y tratamiento
  mediante IA. El acceso técnico de #3831 no los acredita.
- Rotar la credencial expuesta y revisar sus accesos.
- Diseñar control agregado de cuota, concurrencia y facturación antes de
  habilitar consumo automático o accesible a usuarios.
- Implementar aislamiento multi-tenant de configuración, autorización,
  operaciones y datos en la futura integración. Este cliente de bajo nivel no
  recibe usuarios ni tenants y no demuestra ese aislamiento.

El resultado de #3832 se entrega para revisión pre-commit. No se modificó
OpenProject ni se hicieron staging, commit, push, PR o merge.
