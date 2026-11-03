# HU-21 — A-21F: interfaz de importación externa

## Precheck y alcance

2026-11-03: checkout inicial `feature/HU-21-importacion-externa-api`, HEAD
`36cc34f4f95ea9d4033f0e0a81215f2bd0cef4ac` (A-21B presente), staging vacío,
sin cambios versionados y con veinte archivos ajenos sin seguimiento conservados.
Se registró un manifiesto de 289 archivos no ignorados, excluyendo credenciales.
Trabajo aislado en `codex/hu-21-a21f-importacion-externa`, sin commits ni publicación.

El frontend usa React 19, Tailwind 4, Axios y la guarda de `/imports` para
`usuario_negocio` y `admin_tenant`. El cliente general tiene timeout de diez
segundos. Se conserva la importación CSV/Excel y el POST de A-21B.

## Contrato complementario propuesto antes de implementación

No existe consulta pública de conexiones. Se añadirá únicamente:

`GET /api/v1/integrations/google/reviews/connections`

Respuesta mínima:

```json
{
  "source": "Google",
  "import_enabled": false,
  "connections": [
    {"business_data_id": "0xabc:0x123", "status": "available"},
    {"business_data_id": "0xabc:0x456", "status": "disabled"}
  ]
}
```

El ejemplo es sintético. `available` significa conexión configurada con permiso
de persistencia, aprobación no vacía e identificador aceptable por el POST;
`disabled` no explica cuál de esos controles falta. La habilitación global es
independiente y siempre bloquea el botón cuando es falsa. La lista no garantiza
presupuesto ni ausencia de operaciones pendientes: la admisión autoritativa
permanece exclusivamente en A-21B.

El tenant y el rol provienen de la autenticación y se exige actor/tenant activos.
La consulta no acepta un tenant del cliente como ámbito. No expone tenant_id,
credenciales, referencias de aprobación ni filas de admisión. No crea conexiones,
no las habilita ni construye un cliente SerpApi. Errores propios sanitizados;
se conserva autenticación compartida. No se agregan migraciones ni administración.

## Decisiones y bloqueos del PO

No hace falta autorizar consumo real para esta implementación sintética. No se
habilita ninguna configuración o conexión real. Derechos de almacenamiento,
consumo, límites aprobados y reconciliación administrativa siguen pendientes.

El modelo carece de nombre comercial: el selector mostrará el identificador ya
configurado del establecimiento, sin inventar nombres ni consultar al proveedor.
Un alias legible es una posible mejora futura que requiere contrato propio; no
bloquea este selector. No se ofrece un control de habilitación o desbloqueo.

## Decisiones de interfaz y transporte

Modo Operate: extensión de la superficie existente. Se conservan su tipografía,
neutros, controles nativos, botones oscuros y feedback semántico. La sección Google
se incorpora después del flujo CSV/Excel, con título, selector etiquetado, estado
de disponibilidad y una acción explícita. No se cambia el sistema visual global.

La petición POST tendrá timeout local de 720000 ms, sin alterar Axios global:
cubre la duración nominal de hasta cinco páginas con lectura de hasta 120 s más
margen de transporte y BD. No es una garantía de duración máxima del servidor;
los timeouts por lectura no equivalen a un plazo total y la BD también puede esperar.

Antes de enviar se registra una marca de operación en sessionStorage, por usuario,
tenant y conexión, sin token ni payload. Bloquea doble envío y sobrevive a recarga
y navegación en esa pestaña. Ante timeout, desconexión, respuesta no verificable,
resultado unknown, operación pendiente o reconciliación requerida, se conserva
la marca, no se reintenta y se permite consultar reviews. El cierre de la pestaña
no cancela una operación del servidor; la exclusión y el presupuesto siguen bajo
control del backend. No se desbloquea mediante refrescar la lista de conexiones.

La protección de pestaña no sustituye la reconciliación administrativa ni coordina
dispositivos distintos. Después de una revisión administrativa confirmada puede
iniciarse una nueva sesión de pestaña; no se ofrece ese paso como repetición inmediata.
Si el navegador no permite conservar la marca, no se envía la importación externa.

## Implementación y validación

Implementación terminada el 2026-11-03. El GET propuesto quedó implementado con el
contrato anterior, limitado a `usuario_negocio` y `admin_tenant`. Se revalida el
usuario y tenant vigentes dentro de la sesión corta de consulta. La consulta no
ejecuta `commit`/`flush`; la política se lee sin activar importaciones. Los fallos
de consulta/configuración se sanitizan. El POST conserva su admisión, presupuesto,
validación de identidad, persistencia y reconciliación de A-21B.

La sección permite seleccionar exclusivamente conexiones disponibles. Presenta
carga, estado vacío, deshabilitación y errores. Un resultado confirmado muestra
obtenidas, insertadas, repetidas, cambiadas, omitidas y rechazadas, con advertencias
de adquisición incompleta/limitada o reconciliación y acceso al listado de reviews.
Los cambios detectados no se presentan como sobrescrituras de reseñas existentes.
Los formatos `detail` texto, lista y objeto se traducen a mensajes locales; no se
imprime el detalle remoto. Las respuestas se validan y se descartan campos extra.

El POST usa el cliente/interceptores existentes y envía solo `business_data_id`.
Una referencia sincrónica impide doble envío antes del siguiente render. Se
descartan respuestas tardías de otra sesión; abandonar la pantalla conserva la
marca pendiente. CSV/Excel conserva su transporte multipart y timeout general.

### Inventario de cambios

Cuatro archivos versionados modificados:

- `backend/app/api/routers/external_reviews.py`: GET y reutilización de la lectura de política.
- `backend/app/repositories/review_repository.py`: consulta Google por tenant con registro SQL privado.
- `frontend/src/pages/ImportReviewsPage.jsx`: integración y jerarquía de títulos.
- `frontend/src/services/importService.js`: GET/POST externo con validación y timeout específico.

Siete archivos nuevos:

- `backend/app/schemas/external_review_connections.py`: DTO público mínimo.
- `backend/tests/test_external_review_connections_api.py`: autorización, aislamiento y lectura segura.
- `frontend/src/components/ExternalReviewImport.jsx`: sección y resultados accesibles.
- `frontend/src/hooks/useExternalReviewImport.js`: ciclo de consulta, envío y protección de pestaña.
- `frontend/src/utils/externalReviewImport.js`: validación de contratos y errores sanitizados.
- `frontend/tests/externalReviewImport.integration.test.mjs`: integración React/Axios simulada.
- `docs/hu-21/a-21f-interfaz-importacion-externa.md`: contrato, decisiones y evidencia.

### Pruebas realizadas

| Comprobación | Resultado |
| --- | --- |
| GET nuevo: `test_external_review_connections_api.py` | 20 aprobadas |
| Suite focalizada A-21B, H1–H4, N1 y GET nuevo | 163 aprobadas |
| Regresiones backend de configuración, cliente, normalización, migraciones, persistencia e integración | 435 aprobadas |
| Integración React/Axios nueva | 28 aprobadas |
| Suite completa de frontend, incluyendo CSV/Excel | 93 aprobadas |
| `npm run lint` | Aprobado |
| `npm run build` | Aprobado |
| Detector de interfaz sobre ambos componentes de imports | Sin hallazgos (`[]`) |
| Sintaxis Python sin importar aplicaciones ni generar bytecode | 4 archivos correctos |
| `git diff --check` y comprobación de los siete archivos nuevos | Sin errores de espacios, respetando CRLF de Windows |

Los conteos de pruebas nuevas están incluidos en sus respectivas suites: no se
suman como ejecuciones de casos distintos. No se repitió la suite backend completa;
las 1525 pruebas históricas de A-21B no constituyen un resultado nuevo de A-21F.

Las pruebas backend usaron bases sintéticas temporales, sin archivos `.env` ni
bases de desarrollo, y un bloqueo de conexiones externas: cero intentos. Frontend
usó Axios con adapter simulado; el proceso bloqueó conexiones salientes y lectura
de `.env`, sin intentos de conexión. Con Node 24 se ejecutó la suite con
`--no-experimental-global-navigator --test --test-concurrency=1`: las pruebas
preexistentes asignan `navigator`, que ese runtime expone por defecto como getter.
El ajuste fue exclusivamente del runner, sin cambiar dependencias ni pruebas ajenas.
Persisten avisos preexistentes de Starlette/HTTPX y React Router; no hubo fallos.

Se revisaron visualmente escritorio (1440 px) y móvil (390 px), resultados
confirmados y resultado incierto, mediante un servidor local efímero con respuestas
en memoria. El servidor no usó el backend ni proveedores y se cerró al terminar.
No hubo desbordamiento horizontal. La pantalla incierta conserva deshabilitado el
envío y no se desbloquea al actualizar conexiones. Capturas sintéticas fuera de Git:

- `C:/Users/PC OSTRICH/.codex/visualizations/2026/11/03/01a1a147-ddaf-7723-84b3-b271ff5149b3/a21f/desktop-confirmed.png`
- `C:/Users/PC OSTRICH/.codex/visualizations/2026/11/03/01a1a147-ddaf-7723-84b3-b271ff5149b3/a21f/mobile-confirmed.png`
- `C:/Users/PC OSTRICH/.codex/visualizations/2026/11/03/01a1a147-ddaf-7723-84b3-b271ff5149b3/a21f/desktop-unknown.png`

### Límites y preparación para revisión

La demostración verifica contratos, permisos y experiencia con datos sintéticos;
no verifica latencia real, facturación, derechos de almacenamiento ni una importación
contra Google. No habilita almacenamiento ni consumo, no consulta SerpApi/Gemini,
no introduce tareas automáticas y no cambia modelos, migraciones o reconciliación.
PostgreSQL y proveedores reales permanecen como validaciones de activación.

La lista puede quedar desactualizada entre GET y POST: A-21B decide nuevamente la
admisión. La protección `sessionStorage` es de experiencia de usuario por pestaña;
no reemplaza el control del servidor y no sobrevive al cierre de esa sesión de
pestaña. Un resultado incierto requiere revisión responsable; no se agregó una
consulta pública de operaciones ni un desbloqueo. El timeout ampliado puede
terminar antes del servidor y siempre se trata como incertidumbre. Los nombres
comerciales no están disponibles en el modelo actual y se muestran IDs configurados.

Estado: lista para autoauditoría técnica de A-21F. No constituye autorización de
commit, despliegue, consumo o almacenamiento real. Staging vacío y HEAD de A-21B
conservado; los veinte archivos ajenos permanecen sin seguimiento y sin cambios.
El manifiesto final conserva 285 archivos iniciales idénticos, cuatro modificados
de A-21F y siete nuevos; no registra eliminaciones ni cambios ajenos.

## Correcciones F1/F2 posteriores a la autoauditoría NO APTO

2026-11-03. Precheck de esta corrección: rama
`codex/hu-21-a21f-importacion-externa`, HEAD
`36cc34f4f95ea9d4033f0e0a81215f2bd0cef4ac`, staging vacío. Los 296 archivos del
manifiesto coincidían con el estado auditado: cuatro versionados modificados y
siete nuevos de A-21F, más veinte archivos ajenos conservados. No existían cambios
inesperados. Esta sección conserva los resultados anteriores como antecedentes.

### F1: catálogo y resultados vinculados a la sesión vigente

Causa: el efecto limpiaba selección y operación, pero no `discovery`. Al invalidar
la sesión, `refresh()` retornaba antes de borrar el catálogo anterior. La vista
continuaba usando ese catálogo aunque la acción de importar estuviera bloqueada.

Corrección en `frontend/src/hooks/useExternalReviewImport.js`:

- Cada estado de consulta y operación queda vinculado a la sesión que lo produjo
  mediante una referencia en memoria. No se persiste ese contexto en localStorage
  ni sessionStorage.
- El render solo devuelve catálogo, errores, carga y resultados del contexto
  vigente. Un cambio de usuario, tenant, rol o token oculta los datos anteriores
  antes de los efectos y antes de que termine otro GET.
- El efecto descarta también el estado de consulta, incluso si la nueva sesión no
  está autorizada para consultar. Las solicitudes anteriores se cancelan y sus
  respuestas tardías siguen sujetas a identidad, token, señal y controlador.
- El envío comprueba el catálogo del contexto actual. La autorización real y el
  ámbito de tenant continúan a cargo del backend.
- No se vacía `sessionStorage`. Las marcas pendientes de cada usuario, tenant y
  conexión sobreviven a logout, cambio de cuenta y respuestas tardías; volver a
  la cuenta original conserva su protección.

Contraejemplo original corregido: después de cargar el catálogo, un evento de
cierre de sesión o cambio a `admin_general` elimina el selector y el identificador
anterior; no provoca consultas ni POST adicionales. Una sesión autorizada nueva
solo muestra su propia respuesta GET.

### F2: éxito coherente con el contrato real de A-21B

Causa: el parser comprobaba tipos y enumeraciones por separado, sin exigir una
combinación permitida de `outcome`, `control_status`, `stop_reason`, `incomplete`
y `limited`. Una respuesta contradictoria se consideraba confirmada y liberaba
la protección local.

Corrección en `frontend/src/utils/externalReviewImport.js`: un HTTP 200 solo se
considera verificable con `outcome=committed`, `stop_reason=no_next_token`,
`incomplete=false`, `limited=false` y control `released` o
`reconciliation_required`, además de las validaciones previas de UUID y contadores.
El segundo control mantiene el éxito de reviews pero conserva el bloqueo de envío.

Esto sigue la implementación y documentación de A-21B: el servicio rechaza toda
adquisición incompleta antes de persistir; por tanto, un `committed` con adquisición
incompleta o limitada tampoco se acepta aunque sus tres campos sean coherentes
entre sí. No se inventa una modalidad de éxito parcial ni se cambia ese contrato.
Las adquisiciones limitadas/incompletas coherentes se prueban como errores HTTP
con diagnóstico, sin contadores de persistencia confirmados.

Contraejemplo original corregido: `committed/released`, `max_pages`,
`incomplete=false`, `limited=false` produce mensaje de resultado incierto, no
muestra éxito ni los seis contadores y conserva la marca pendiente. Doble submit,
refrescar conexiones y remontar la pantalla no producen otro POST.

### Archivos afectados exclusivamente por esta corrección

- `frontend/src/hooks/useExternalReviewImport.js`.
- `frontend/src/utils/externalReviewImport.js`.
- `frontend/tests/externalReviewImport.integration.test.mjs`.
- `docs/hu-21/a-21f-interfaz-importacion-externa.md`.

No cambian el componente visual, servicios, CSV/Excel, backend, dependencias,
contrato A-21B, política de admisión, presupuesto o reconciliación.

### Regresiones y resultados posteriores a la corrección

Se añadieron 24 pruebas: siete F1 y diecisiete F2. Cubren logout, rol no autorizado,
cambio de usuario/tenant/token, GET y POST tardíos, nueva sesión, retorno a una
operación incierta, adquisición limitada/incompleta como error coherente,
combinaciones contradictorias, `unknown`/`rolled_back` por HTTP 200, control inválido
y persistencia del bloqueo tras refresh, doble envío y remontaje.

Antes de cambiar producción, la ejecución de estas 24 regresiones reprodujo los
defectos: diez aprobadas y catorce fallidas. Después de corregir:

| Comprobación | Resultado |
| --- | --- |
| Regresiones específicas F1/F2 (`--test-name-pattern=^F[12]:`) | 24 aprobadas |
| Integración completa A-21F | 52 aprobadas |
| Suite frontend completa, serial y con navegador global de Node desactivado | 117 aprobadas |
| Backend focalizado: adquisición incompleta, commit incierto y cierre de admisión tras commit confirmado | 6 aprobadas, 157 descartadas por selección |
| `npm run lint` | Aprobado |
| `npm run build`, con entorno sintético y sin leer archivos `.env` | Aprobado |
| `node --check` de hook, parser y pruebas | Aprobado |

Los subconjuntos están incluidos en las suites superiores, no son casos distintos
para sumar. No se repitió la suite backend completa: el backend permanece idéntico
y las seis comprobaciones seleccionadas corroboran el contrato usado por el parser.

Pruebas con datos sintéticos y Axios/HTTPX simulados, bloqueo de red y exclusión de
archivos de entorno: cero intentos de conexión externa. El build también usó el
bloqueo de red. Se conserva el aviso previo de React Router y el de Starlette/HTTPX.
Una primera ejecución de reproducción se interrumpió por consumo de memoria al
serializar un elemento DOM en una aserción fallida; se cambiaron las aserciones
nuevas a presencia booleana y se completaron las ejecuciones registradas arriba.
No se modificaron pruebas de otros componentes.

### Riesgos residuales y estado para revisión

La protección sigue siendo de pestaña y no sustituye el backend ni la reconciliación
administrativa. Cerrar la sesión de pestaña puede perder marcas; una respuesta
incierta requiere revisión responsable. Se mantienen el timeout específico de doce
minutos y la posibilidad de que la espera termine antes que el servidor. Consumo,
derechos de almacenamiento, proveedores y PostgreSQL reales siguen pendientes de
activación, sin habilitarlos durante estas correcciones.

Estado: preparada para nueva revisión técnica de F1/F2. No es una autorización de
commit o despliegue. No se crearon commits, push, PR ni cambios de OpenProject.
