# HU-21 — Task #3833: mapeo y normalización de campos externos

## Alcance y estado

Implementación de un normalizador puro, síncrono y exclusivamente en memoria
para el resultado del cliente SerpApi de #3832. No modifica ese cliente ni la
evidencia histórica de #3831. Pendiente de revisión pre-commit.

Base de implementación: `5198116449d1d99d21c827eef2dfd51f7bf063d1`, rama
`feature/HU-21-integraciones-externas`. Validación: 2026-11-02.

No incorpora endpoints, persistencia, modelos SQLAlchemy, migraciones,
configuración, cambios de dependencias ni ejecución de IA. No realiza llamadas
HTTP ni lee credenciales. #3834 y #3835 permanecen fuera de este cambio.

## Archivos

- `backend/app/schemas/external_review.py`: DTO internos inmutables.
- `backend/app/services/serpapi_normalizer.py`: validación y normalización pura.
- `backend/tests/unit/test_serpapi_normalizer.py`: datos completamente sintéticos.
- Este documento.

## Contrato interno

```python
normalize_serpapi_result(
    result: SerpApiResult, *, business_data_id: str
) -> NormalizationBatchResult
```

El contexto del establecimiento es obligatorio y explícito. Debe corresponder al
`data_id` usado por el llamador en #3832; se valida la misma forma hexadecimal
`0x...:0x...`. No es un Place ID. No se infiere de títulos, URLs, metadatos ni de
`place_info`. Esta validación sintáctica no acredita la identidad del negocio ni
su pertenencia a un tenant. El llamador deberá verificar ambas en la integración.

`NormalizedExternalReview` contiene:

| Campo | Tipo / significado |
| --- | --- |
| `external_review_id` | Cadena opaca validada, conservada exactamente |
| `source` | `Literal["Google"]`; plataforma original |
| `author` | `str` o `None`, máximo 255 caracteres tras recorte exterior |
| `content` | `str` o `None`, sin texto inventado |
| `review_date` | `datetime` consciente de zona, normalizado a UTC |
| `rating` | Entero entre 1 y 5 |
| `business_data_id` | Contexto explícito, sin transformaciones |
| `content_field` | `extracted_snippet.original`, `snippet` o `None` |
| `position` | Página del cliente, índice en página y ordinal del lote desde 1 |

Los DTO son `dataclass(frozen=True, slots=True)`. La función es la frontera de
validación; construir directamente estos DTO no sustituye sus validaciones.
No son esquemas públicos ni instrucciones de inserción en `Review`.

## Mapeo y documentación del proveedor

Rutas contrastadas el 2026-11-02 con la documentación oficial de
[Google Maps Reviews API de SerpApi](https://serpapi.com/google-maps-reviews-api).
No se copiaron respuestas ni datos personales de sus ejemplos.

| Entrada nativa | Salida | Regla |
| --- | --- | --- |
| `review_id` | `external_review_id` | Obligatorio, cadena no vacía, UTF-8 válido; sin generar otro ID |
| `source` | `source` | Se admite exclusivamente el valor exacto `Google` |
| `user.name` | `author` | Opcional, recorte exterior y límite 255 |
| `extracted_snippet.original` | `content` | Preferente cuando no está vacío |
| `snippet` | `content` | Alternativa si falta o está vacío el texto original |
| `iso_date` | `review_date` | ISO con zona explícita, convertido a UTC |
| `rating` | `rating` | Entero o flotante integral finito dentro de 1–5 |
| Argumento `business_data_id` | `business_data_id` | No procede de metadatos de la respuesta |

SerpApi es el intermediario técnico. La documentación también muestra reseñas
agregadas de otras plataformas: no se las reclasifica como Google.
La política de aceptar únicamente `Google` queda pendiente de validación final
del PO. No se aceptan alias ni cambios de mayúsculas de manera implícita.

`snippet` puede mezclar texto original y traducido; `content_field` conserva
esta distinción de procedencia. No se utiliza `extracted_snippet.translated`,
la respuesta del propietario, la fecha relativa ni la fecha de última edición.
La estructura documentada no equivale a una nueva observación real: no se
recuperaron reseñas para validar este cambio. La verificación integrada queda
para #3835, con autorización independiente cuando requiera una consulta.

## Validación y rechazo por registro

- Identificador: requerido, no vacío ni compuesto únicamente por espacios;
  únicamente cadena con Unicode codificable en UTF-8. La comprobación de vacío
  no altera espacios, mayúsculas ni caracteres del identificador opaco original.
- Autor: falta, `None` o blanco se representan como `None`, con advertencia.
  `user` presente debe ser objeto, y `name` presente debe ser cadena o `None`.
  Tipos incorrectos, Unicode inválido y longitud superior a 255 se rechazan.
- Contenido: original preferente, alternativa documentada y recorte exterior.
  Ausencia, `None` o blanco no generan rechazo. Se validan ambos campos usados
  si están presentes: un original válido no oculta un `snippet` de tipo incorrecto,
  y un original malformado no se sustituye silenciosamente por la alternativa.
  `extracted_snippet` debe ser objeto o `None`. No se convierten listas,
  diccionarios, números o booleanos a texto.
- Fecha: requerida; se acepta el subconjunto ISO extendido
  `YYYY-MM-DDTHH:MM:SS[.ffffff](Z|±HH:MM)` con 1–6 decimales opcionales.
  Se comprueba el calendario y se normaliza a UTC con zona conservada.
  Fechas sin zona, relativas, ambiguas, inválidas, offsets malformados, offset
  desconocido `-00:00`, pérdida de precisión y desbordamiento UTC se rechazan.
  No se usa la hora actual como sustituto.
- Puntuación: sólo `int` o `float` integral finito entre 1 y 5. Se rechazan
  booleanos, cadenas, fracciones, NaN e infinitos; no hay redondeo.
- Fuente: todo valor distinto del literal `Google`, incluso ausente, se rechaza
  con `unsupported_source`. No se incluye el valor rechazado en el diagnóstico.
- Campos adicionales: se ignoran; no se conservan fotografías, perfiles, URLs,
  metadatos ni respuestas del propietario. Los diccionarios originales no cambian.

Un registro rechazado informa su posición, el primer campo inválido y un código
estable. No pierde los registros válidos de otras posiciones. Los códigos son:

| Clase | Códigos |
| --- | --- |
| Validación de campo | `required`, `invalid_type`, `invalid_unicode`, `too_long`, `invalid_date`, `timezone_required`, `invalid_rating`, `unsupported_source` |
| Estructura de registro | `invalid_record` |
| Conflicto | `conflicting_duplicate` |
| Advertencias opcionales | `missing_author`, `missing_content` |
| Error de lote | `invalid_business_context`, `invalid_result` |

Los avisos opcionales corresponden a ocurrencias que superaron la validación
individual, aunque posteriormente resulten duplicadas o conflictivas. No son
contadores de registros adicionales. Un registro inválido no aporta una versión
normalizada al agrupamiento de duplicados.

El contrato de #3832 usa dataclasses sin validación en runtime: por eso se
verifican tipo de resultado, contenedores de páginas/reseñas, números de página,
flags y motivo de detención antes de recorrerlos. Una estructura de lote inválida
produce `invalid_result`, sin excepción con datos nativos. Los tipos JSON nativos
malformados de una fila producen un rechazo individual; no se soporta la ejecución
de objetos personalizados con métodos arbitrarios en lugar de esos contratos.

## Política efectiva de reseñas sin texto

Una reseña con ID, fuente, fecha y puntuación válidos puede estar en
`without_text`, con `content=None`, `content_field=None` y aviso `missing_content`.
Se conservan el autor disponible y los otros campos validados. No se completa
texto mediante IA ni se inventa una reseña sustitutiva.

La prueba histórica de #3831 recuperó cinco reseñas y sólo dos tenían texto.
No se reutilizaron sus contenidos ni sus autores en fixtures de #3833.

`Review.contenido` exige actualmente un valor no nulo. Este cambio no intenta
insertar los registros sin texto. #3834 y el PO deben decidir su tratamiento de
persistencia, visualización y elegibilidad de análisis antes de integrar el flujo.

## Duplicados dentro de un lote

Clave: `(source, business_data_id, external_review_id)`. No hay estado global,
índices de base de datos ni deduplicación entre ejecuciones.

1. Se validan las filas y se agrupan por identidad en memoria, entre páginas.
2. La igualdad compara todos los campos normalizados salvo `position`, incluida
   la procedencia `content_field`. Ignora campos nativos adicionales y diferencias
   que desaparecen al normalizar, por ejemplo `4`/`4.0` o offsets equivalentes.
3. Si todas las versiones son iguales, se conserva la primera ocurrencia; cada
   repetición figura en `duplicates` con su posición y la posición conservada.
4. Si alguna difiere, TODAS las ocurrencias del grupo van a `conflicts` y a
   `rejected` con `conflicting_duplicate`, incluso repeticiones previas idénticas.
   Ninguna se acepta ni se cuenta como duplicado idéntico. No se elige ganadora.
5. Los grupos ajenos al conflicto se conservan. El mismo ID en dos negocios tiene
   identidades distintas.

El normalizador procesa únicamente los registros y el identificador de
establecimiento recibidos. No realiza comprobaciones de pertenencia a un tenant;
estas deberán implementarse en la capa de integración y persistencia de la
Task #3834.

Las versiones conflictivas permanecen disponibles sólo en memoria para revisión
explícita; están ocultas en `repr`. No se guardan en este cambio.

## Resultado, contadores y recuperación parcial

`NormalizationBatchResult` entrega tuplas inmutables `with_text`, `without_text`,
`rejected`, `duplicates`, `conflicts`, `warnings` y `batch_error` opcional.
Sus contadores se derivan de las colecciones, sin incrementar totales paralelos:

```text
total = with_text + without_text + rejected + duplicates
conflicting es un subconjunto de rejected; no vuelve a sumarse a total.
```

`total` cuenta las ocurrencias realmente recorridas, no confía en el
`record_count` declarado por el proveedor. Cada posición aparece en exactamente
una de las cuatro categorías principales. Un registro puede tener varios avisos.
`conflicts` agrupa versiones; su tamaño no se confunde con el número de filas.

Se preservan `incomplete`, `limited` y `stop_reason` del resultado de #3832.
Estos flags describen la adquisición, no la calidad de las filas. Por eso un
resultado con adquisición completa puede incluir rechazos de normalización.
Un resultado parcial por error, límite de páginas o token repetido conserva sus
filas disponibles y su estado incompleto. No implica haber obtenido todas las
reseñas públicas del establecimiento.

Un contexto inválido produce `batch_error=invalid_business_context`, conserva
los flags válidos de adquisición y no normaliza filas. En cualquier error de lote
`input_count=0` significa **entradas no procesadas**, no ausencia de reseñas en el
resultado original: el llamador debe comprobar `batch_error` antes de interpretar
los contadores. Si el contenedor es inválido, se informa `incomplete=True`,
`limited=False`, `stop_reason=None`, sin copiar flags no confiables.

## Seguridad y ausencia de efectos secundarios

- El normalizador y sus DTO importan sólo biblioteca estándar y contratos
  internos de esquemas. No importan el cliente HTTP, FastAPI, repositorios,
  modelos ORM, configuración, servicios de IA ni adaptadores de persistencia.
- No leen `.env`, no reciben API keys y no emiten logs ni cambian logging global.
- Errores y advertencias contienen exclusivamente códigos, campos fijos y
  posiciones. No contienen valores originales ni mensajes de excepciones nativas.
- `repr` de reseñas y resultados oculta campos sensibles y versiones conflictivas.
  Acceder a atributos o serializar mediante `asdict` sigue exponiendo datos:
  ocultar `repr` no es anonimización, autorización de almacenamiento ni cifrado.
- Fixtures y ejemplos son sintéticos, sin autores, reseñas, tokens ni URLs
  autenticadas reales. No se consumió cuota de SerpApi.
- La revisión comprueba que los archivos previos y `.env` no cambiaron y que
  `.env` permanece ignorado, fuera del índice y sin versionar.

## Validación automatizada

Ejecución con Python del entorno virtual existente, bytecode y caché de pytest
deshabilitados. No se instalaron dependencias. Para las suites focalizadas se
usó `--confcutdir=tests/unit`, evitando cargar el `conftest.py` general, que
importa aplicación y base de datos. La clave real se eliminó del entorno del
proceso de pruebas; no se leyó el `.env` local.

Resultados finales:

- #3833: **160 aprobadas**, 0 fallos, 0 advertencias, 0.63 s.
- Compatibilidad #3832: **93 aprobadas**, 0 fallos, 0 advertencias, 2.63 s.
- Ambas ejecuciones: **0 intentos de conexión o DNS externo**.
- Regresión backend general: **1150 aprobadas**, 0 fallos, **1 advertencia**,
  664.84 s (11 min 04 s), con `PYTHONTZPATH` temporal. Incluye las suites
  focalizadas; los totales no se suman entre ejecuciones.
- Regresión general: **0 intentos de conexión o DNS externo**.
- Advertencia existente: `StarletteDeprecationWarning` por el uso de HTTPX con
  `starlette.testclient`. No se instalaron paquetes ni se alteró esa integración.
- Sintaxis: compilación en memoria y AST correctos de los tres archivos Python
  nuevos, sin generar bytecode.
- `git diff --check`: correcto. Comprobación adicional de los cuatro archivos
  sin seguimiento mediante `git diff --no-index --check`: sin diagnósticos de
  espacios. Se deshabilitó `core.autocrlf` sólo en esas invocaciones para evitar
  avisos de conversión LF/CRLF, sin cambiar la configuración del repositorio.
- Seguridad: la clave local no aparece en ninguno de los archivos nuevos y no
  se encontraron URLs autenticadas. `.env` continúa ignorado y sin versionar.
- Integridad: los 248 archivos previos conservan sus hashes; únicamente se
  añadieron los cuatro archivos autorizados, sin cambios preparados en el índice.

La suite de #3833 comprueba mapeo, texto ausente, autor opcional, límites,
Unicode inválido, preferencias y tipos de contenido, fechas UTC y offsets,
rechazos temporales y de puntuación, fuente explícita, metadatos ignorados,
errores por posición, contenedores malformados, duplicados idénticos y conflictivos
entre páginas, identidades por negocio, flags de adquisición, conciliación de
contadores, determinismo e inmutabilidad de entradas, DTO inmutables y privacidad
de diagnósticos, representaciones y logs.

Además de comprobar mediante AST la lista permitida de importaciones, una prueba
en proceso aislado bloquea importaciones HTTP/DB/IA, eventos de socket/SQLite y
aperturas de archivos para escritura. Importa y ejecuta el normalizador con una
reseña sintética sin texto. No requiere PostgreSQL, SQLite, Internet ni Gemini.

La regresión general usa las bases temporales que ya gestionan las pruebas
existentes, nunca la base de desarrollo. Sólo se permite loopback para el
transporte local de TestClient; conexiones y DNS externos se bloquean. En Windows
se reutilizan datos horarios temporales mediante `PYTHONTZPATH` únicamente en el
proceso de pruebas. No se alteran manifiestos, paquetes globales ni pruebas previas.

## Decisiones pendientes y dependencias

### PO y derechos

- Validación final del alcance de fuente exacta `Google`, política de alternativa
  `snippet`, comparación de procedencia en conflictos y tratamiento de rechazos.
- Tratamiento de reseñas sin texto: persistencia, interfaz y exclusión/inclusión
  en análisis; el esquema actual no admite contenido nulo.
- Confirmar derechos y condiciones para almacenamiento, retención, visualización
  y procesamiento con IA. El acceso técnico no acredita esos permisos.
- Seguridad de la clave previamente expuesta: rotación y manejo de secretos
  pendientes. El normalizador no necesita ni resuelve esa credencial.
- Control de cuotas y facturación de futuras adquisiciones. #3833 no hace llamadas
  ni demuestra un consumo exacto de créditos de la prueba histórica.
- Riesgo residual P3: el normalizador no establece límites explícitos para el
  tamaño de contenido, identificadores o cantidad de registros del lote. Deben
  definirse límites antes de aceptar lotes externos sin las restricciones del
  cliente #3832. Las pruebas con entradas grandes no garantizan protección frente
  al agotamiento de memoria.

### #3834 — integración y persistencia

Debe resolver pertenencia del negocio al tenant y contexto autenticado; modelo
de identificadores externos y unicidad por tenant/negocio/fuente; idempotencia
entre ejecuciones; transacciones y política de grupos conflictivos; registros sin
texto; adaptación explícita de UTC consciente al `DateTime` actual; y decisiones
sobre estado inicial y restantes campos requeridos por `Review`.

Validar la forma de un `data_id` no implementa aislamiento multi-tenant. Tampoco
hay escritura, migración ni unicidad nueva en este cambio.

### #3835 — verificación integrada

Validar cliente-normalizador-persistencia con dobles controlados, errores y
resultados parciales, idempotencia, aislamiento de tenants, seguridad y decisiones
aprobadas del PO. Toda nueva consulta real o uso de IA requiere autorización y
comprobación de derechos/cuotas; no forma parte de #3833.

No se realizó staging, commit, push, PR, merge ni cambio en OpenProject.
