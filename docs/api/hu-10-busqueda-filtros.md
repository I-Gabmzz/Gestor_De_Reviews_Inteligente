# HU-10: búsqueda y filtrado de reviews

## Objetivo

Como usuario de negocio, quiero buscar y filtrar reviews para localizar rápidamente la retroalimentación que necesito revisar.

- Historia de Usuario en OpenProject: **#3237**.
- Actor principal: usuario de negocio.
- Prioridad: High.
- Trabajo total estimado de la HU: 26h.
- TASK de este documento: **#3331 - Definir criterios de búsqueda y filtrado**, estimada en 3h.

Los criterios de aceptación oficiales son buscar por texto o palabras clave, filtrar por fecha, puntuación, estado y fuente, y operar exclusivamente sobre reviews visibles para el tenant del usuario.

Este documento registra el contrato aprobado para la implementación posterior. TASK #3331 es exclusivamente documental: todavía no incorpora búsqueda, filtros ni nuevos parámetros ejecutables a la API.

## Relación con HU-07

HU-10 extiende el listado existente de [HU-07: consulta de reviews](hu-07-consulta-reviews.md). No crea otro listado, página, repository ni endpoint paralelo.

Se conserva la arquitectura y el stack existentes: React 19, JavaScript, JSX y Tailwind CSS 4; API REST con Python y FastAPI; SQLAlchemy con SQLite local y PostgreSQL como objetivo.

```text
Query parameters -> Router -> ReviewService -> ReviewRepository -> Database
```

El router recibirá y validará los parámetros; el servicio coordinará los criterios y sus reglas; el repository aplicará el tenant y los predicados en la consulta a la base de datos. No se cargarán todas las reviews para filtrarlas en memoria o en React.

Sin parámetros, el comportamiento debe permanecer idéntico a HU-07, incluyendo los campos de respuesta y el orden. Las rutas existentes de detalle e importación no cambian.

## Endpoint y autenticación

```http
GET /api/v1/reviews
Authorization: Bearer <token>
```

Se reutilizan la autenticación oficial de HU-01, `get_current_user`, `AuthenticatedUser`, `get_current_tenant_id` y `get_db`. El frontend seguirá utilizando el `apiClient` existente, cuyo `baseURL` incluye `/api/v1`.

## Contrato existente de respuesta

La respuesta continúa utilizando `ReviewList`:

```json
{
  "items": [],
  "total": 0
}
```

- `items`: reviews del tenant autorizado que coinciden con todos los criterios presentes.
- `total`: cantidad de resultados coincidentes, no el total global del tenant cuando hay filtros activos.
- Cada item conserva el contrato de `ReviewRead`: `id`, `tenant_id`, `autor`, `contenido`, `fecha`, `fuente`, `puntuacion`, `estado`, `categoria` y `prioridad`.
- `autor`, `categoria` y `prioridad` pueden ser `null`; `fecha` se representa como datetime ISO 8601.
- Sin criterios, `items` y `total` son equivalentes al listado actual de HU-07.
- No se agrega paginación.

## Parámetros opcionales aprobados

| Parámetro | Tipo/formato | Significado |
|---|---|---|
| `busqueda` | Texto | Coincidencia parcial sobre `Review.contenido`. |
| `fecha_desde` | Fecha `YYYY-MM-DD` | Inicio inclusivo del primer día. |
| `fecha_hasta` | Fecha `YYYY-MM-DD` | Incluye el último día completo. |
| `puntuacion` | Integer, de 1 a 5 | Coincidencia exacta de puntuación. |
| `estado` | `nueva`, `en_revision`, `atendida` | Coincidencia exacta del estado técnico. |
| `fuente` | Texto libre | Coincidencia exacta con la fuente almacenada. |

Todos los parámetros son opcionales e independientes, salvo la validación del rango cuando se proporcionan ambas fechas. Únicamente se aplican los criterios proporcionados que no se normalicen a ausencia de búsqueda o filtro.

`tenant_id` no forma parte de estos parámetros.

## Búsqueda textual

El parámetro `busqueda` opera exclusivamente sobre **`Review.contenido`**, según la descripción oficial de TASK #3357.

- La coincidencia es parcial e ignora diferencias entre mayúsculas y minúsculas.
- Se eliminan los espacios exteriores y se conserva el contenido interior del texto.
- El valor completo se interpreta como una sola cadena de búsqueda.
- `busqueda=servicio lento` busca la cadena parcial `servicio lento`; no se divide en `servicio AND lento` ni en `servicio OR lento`.
- Una cadena vacía o compuesta únicamente por espacios se trata como ausencia de búsqueda.
- Los caracteres especiales de LIKE, incluidos `%` y `_`, se tratan como texto literal, no como comodines controlados por el usuario. La implementación posterior deberá escapar el patrón y usar parámetros vinculados, sin concatenar SQL con la entrada del cliente.
- No se establece una longitud máxima adicional para la búsqueda.
- No se garantiza equivalencia especial de tildes: no debe prometerse que `atencion` encuentre `atención`.

No se busca sobre autor, fuente, categoría, prioridad o tenant. Tampoco se incorpora búsqueda semántica, fuzzy search ni ranking de relevancia.

## Filtros

### Fecha

`fecha_desde` y `fecha_hasta` aceptan exclusivamente fechas con formato `YYYY-MM-DD`. Es válido enviar solo el inicio, solo el final o ambos límites.

La semántica de comparación preferida es:

```text
fecha >= inicio de fecha_desde
AND
fecha < inicio del día siguiente a fecha_hasta
```

Solo se utiliza cada condición cuando su parámetro está presente. El límite superior exclusivo incluye todo el día final, sin depender de una hora máxima artificial como `23:59:59`.

Si ambas fechas son iguales, el filtro representa ese día completo. Por ejemplo, `fecha_desde=2026-09-27&fecha_hasta=2026-09-27` comprende desde el inicio del 27 de septiembre hasta antes del inicio del 28.

Un formato inválido o un rango con `fecha_desde > fecha_hasta` produce **HTTP 422**.

Se mantiene la semántica actual de `Review.fecha`, almacenada como `DateTime`. HU-10 no introduce una política de zonas horarias ni conversiones nuevas a UTC.

### Puntuación

`puntuacion` debe ser un entero entre **1 y 5**, inclusive. La coincidencia es exacta: `puntuacion=5` solo devuelve reviews con puntuación 5.

Un valor no entero o fuera de `1..5` produce **HTTP 422**. No se incorporan filtros de puntuación mínima, máxima ni rangos.

### Estado

Los valores técnicos vigentes son **`nueva`**, **`en_revision`** y **`atendida`**. El filtro utiliza coincidencia exacta y no modifica la representación almacenada.

No se aceptan aliases como `Nueva`, `En revisión` o `Atendida`. Cualquier valor fuera de los tres permitidos produce **HTTP 422**. La interfaz podrá presentar etiquetas amigables en las tareas frontend posteriores.

### Fuente

`fuente` utiliza el texto libre existente en el modelo; no se agrega enum, tabla Fuente ni catálogo cerrado.

- Se eliminan los espacios exteriores del parámetro.
- Se compara exactamente con el valor almacenado, conservando su capitalización; no se agrega búsqueda parcial ni equivalencia de mayúsculas para este filtro.
- Una cadena vacía después de trim se trata como ausencia de filtro.
- No se limita el contrato a ejemplos como Google, Facebook, CSV o Excel.
- Una fuente no vacía pero inexistente en los registros devuelve **200 OK**, con `items: []` y `total: 0`; no es un error de validación.

La importación existente puede conservar una fuente proporcionada o asignar CSV/Excel cuando falta. HU-10 no cambia esa persistencia.

## Combinación de criterios

Todos los criterios presentes se combinan mediante **AND**:

```text
tenant autorizado
AND busqueda
AND fecha_desde
AND fecha_hasta
AND puntuacion
AND estado
AND fuente
```

Por ejemplo, `busqueda=servicio&estado=nueva&puntuacion=5` devuelve únicamente reviews del tenant autorizado cuyo contenido contenga `servicio`, cuyo estado sea `nueva` y cuya puntuación sea 5.

Los predicados se ejecutarán en la consulta del repository, manteniendo compatibilidad con SQLite y PostgreSQL. Limpiar todos los criterios desde el frontend posteriormente equivaldrá a solicitar la colección sin esos parámetros.

## Aislamiento multi-tenant

```text
JWT -> usuario autenticado -> get_current_tenant_id -> tenant autorizado -> consulta
```

Toda consulta debe partir de la restricción obligatoria `Review.tenant_id == tenant_id autorizado` y agregar posteriormente los demás criterios. Estos nunca pueden sustituir o retirar la restricción de tenant.

`tenant_id` enviado manualmente por el cliente no forma parte del contrato y no debe utilizarse para determinar el negocio ni permitir consultas cruzadas. Tampoco se acepta un tenant seleccionable mediante body o headers personalizados.

No se incorpora selector de tenant para el usuario de negocio, una autenticación paralela ni un mecanismo nuevo de token. Un usuario autenticado sin contexto de tenant permitido, incluido `admin_general`, conserva la respuesta 403 del mecanismo oficial.

## Ordenamiento

Se mantiene el orden de HU-07:

```text
fecha DESC
id DESC
```

Los filtros únicamente reducen el conjunto de resultados. El identificador descendente conserva el desempate cuando dos fechas coinciden. No hay orden configurable ni ranking.

## Respuestas y errores

| Código | Situación |
|---|---|
| `200 OK` | Consulta válida, con o sin resultados. |
| `401 Unauthorized` | Usuario sin autenticación válida. |
| `403 Forbidden` | Usuario autenticado sin contexto de tenant permitido. |
| `422 Unprocessable Entity` | Formato inválido de fecha, rango invertido, puntuación no entera o fuera de 1..5, estado no permitido u otros errores de validación de query parameters. |

Las respuestas no deben exponer SQL, stack traces, tokens ni información interna. HU-10 no cambia los mecanismos oficiales de autenticación y autorización.

## Ejemplos documentales

Estos ejemplos describen el contrato aprobado para las siguientes TASK; no implican que los filtros ya estén implementados. Todas las solicitudes requieren el Bearer token oficial.

### Sin criterios y con criterios combinados

```http
GET /api/v1/reviews
GET /api/v1/reviews?busqueda=servicio&puntuacion=5&estado=nueva
GET /api/v1/reviews?busqueda=servicio%20lento
GET /api/v1/reviews?busqueda=servicio&fecha_desde=2026-09-01&fecha_hasta=2026-09-27&puntuacion=5&estado=nueva&fuente=Google
```

`servicio%20lento` representa una sola cadena con un espacio interior.

### Fechas y fuente

```http
GET /api/v1/reviews?fecha_desde=2026-09-01
GET /api/v1/reviews?fecha_hasta=2026-09-27
GET /api/v1/reviews?fecha_desde=2026-09-27&fecha_hasta=2026-09-27
GET /api/v1/reviews?fuente=Formulario%20web
```

### Caracteres literales y ausencia de criterios

```http
GET /api/v1/reviews?busqueda=100%25
GET /api/v1/reviews?busqueda=servicio_lento
GET /api/v1/reviews?busqueda=%20%20&fuente=%20%20
```

En el primer caso se busca el texto literal `100%`; en el segundo, el guion bajo es literal. En el tercero, búsqueda y fuente se normalizan a ausencia de criterios, conservando el listado sin filtros.

### Respuesta con resultados

Ejemplo ficticio que conserva los campos actuales de HU-07:

```json
{
  "items": [
    {
      "id": 101,
      "tenant_id": 10,
      "autor": "Ana",
      "contenido": "El servicio fue excelente.",
      "fecha": "2026-09-27T18:30:00",
      "fuente": "Google",
      "puntuacion": 5,
      "estado": "nueva",
      "categoria": null,
      "prioridad": null
    }
  ],
  "total": 1
}
```

El `tenant_id` presente en `ReviewRead` es un dato de salida del contrato existente, no un parámetro para seleccionar el tenant.

### Sin resultados

Una búsqueda sin coincidencias o una fuente inexistente produce **200 OK**:

```json
{
  "items": [],
  "total": 0
}
```

### Consultas inválidas

Cada solicitud siguiente debe producir **HTTP 422**:

```http
GET /api/v1/reviews?fecha_desde=27-09-2026
GET /api/v1/reviews?fecha_desde=2026-09-28&fecha_hasta=2026-09-27
GET /api/v1/reviews?puntuacion=4.5
GET /api/v1/reviews?puntuacion=6
GET /api/v1/reviews?estado=Nueva
```

## Fuera de alcance

- Búsqueda por autor o por campos distintos de contenido.
- Filtros de categoría, prioridad o criterios adicionales no aprobados.
- IA, búsqueda semántica, fuzzy search y ranking de relevancia.
- Elasticsearch, motores externos, microservicios y tecnologías nuevas.
- Paginación, orden configurable y filtros avanzados adicionales.
- Cambios en dashboard o funcionalidades ajenas a HU-10.
- Cambios visuales, campo de búsqueda, controles y conexión frontend durante TASK #3331.

## Relación con las siguientes TASK

La HU se desarrolla en una sola rama: `feature/HU-10-busqueda-filtros`.

| TASK | Nombre oficial | Alcance | Estimación |
|---|---|---|---|
| #3331 | Definir criterios de búsqueda y filtrado | Documentar este contrato; sin comportamiento ejecutable. | 3h |
| #3357 | Implementar búsqueda de reviews en backend | Implementar búsqueda sobre `Review.contenido`, aislada por tenant. | 4h |
| #3358 | Implementar filtros de reviews en backend | Implementar fecha, puntuación, estado y fuente, combinables. | 3h |
| #3359 | Integrar parámetros de búsqueda y filtros | Exponer, validar e integrar los parámetros en `GET /api/v1/reviews`. | 2h |
| #3360 | Implementar campo de búsqueda | Incorporar el campo de búsqueda frontend. | 3h |
| #3361 | Implementar controles de filtrado | Incorporar controles de fecha, puntuación, estado y fuente, con limpieza. | 5h |
| #3334 | Integrar filtros del frontend con API | Enviar criterios mediante el cliente existente y actualizar la tabla. | 3h |
| #3335 | Probar búsqueda y filtrado de reviews | Validar resultados, ausencia de coincidencias, combinaciones, limpieza y aislamiento mediante pruebas funcionales completas. | 3h |

Este documento no inicia ninguna de las siguientes TASK. La implementación posterior debe conservar el comportamiento sin filtros de HU-07 y comprobar el contrato, las validaciones y el aislamiento definidos aquí.
