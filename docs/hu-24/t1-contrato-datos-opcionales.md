# HU-24 / T1 — Contrato de registro manual y datos opcionales

Estado: propuesta funcional para revisión de Diego y David; no implementada. Base inspeccionada: `0ee39d42fa18d07b9c64abde72b6b860ac90a5b2`, rama `feature/HU-24-registro-importacion-exportacion`. Este documento no modifica contratos aprobados de otras HU ni acredita su aprobación.

## Objetivo, alcance y fuentes

Especificar registro manual y consumo de valores ausentes para orientar T2 (persistencia) y T3 (registro/edición), HU-23 (consulta/dashboard) y HU-22 (bandeja/detalle). No implementa migraciones, cambios de producto ni importación opcional. Las reglas de Sprint 4 proceden del requerimiento de HU-24/T1 entregado por el responsable; no se encontró en el repositorio un Sprint Backlog 4 independiente para contrastarlo. No se ha entregado el documento personalmente a Diego ni David.

Se inspeccionaron `backend/app/models/review.py`, schemas `review.py` y `dashboard.py`, routers `reviews.py`, `imports.py` y dependencias de autenticación, servicios de reseñas, importación, exportación, dashboard y persistencia externa, repositorio, configuración/migraciones y componentes React de captura, edición, tabla, detalle y dashboard. Se revisaron pruebas existentes `test_review_schema.py`, `test_reviews_api.py`, `test_review_edit_api.py`, `test_imports_api.py`, `test_review_export_api.py`, `test_dashboard.py`, `test_tenant_isolation.py` y las de importación externa. Se consultaron `docs/api/review-edit.md` (HU-08), `docs/testing/hu-10-pruebas-funcionales.md` (regresión HU-06/HU-08), `docs/hu-19/contrato-csv.md`, `docs/hu-12/politica-importacion-fuente.md` y documentos de mapeo/persistencia de `docs/hu-21/`. No se localizó contrato independiente HU-06 en `docs/`.

## Estado actual comprobado

- `Review`: `autor` ya admite NULL; `contenido`, `fecha`, `fuente`, `puntuacion`, `estado` y `tenant_id` son NOT NULL en el modelo. No hay CHECK de rango de puntuación declarado en este modelo; el esquema real de cada instalación debe inspeccionarse antes de migrar.
- `ReviewManualCreate` prohíbe extras, exige fecha y puntuación entre 1 y 5, acepta autor nulo y recorta texto; el registro interno impone `fuente="manual"` y `estado="nueva"`. El POST `/api/v1/reviews` responde 201 con `ReviewRead`. El formulario también exige fecha y puntuación.
- `ReviewRead`/`ReviewBase` y `DashboardReviewRead` exigen fecha y puntuación. `ReviewUpdate` distingue omitidos mediante `exclude_unset`, permite borrar autor, rechaza null en puntuación y su validador de fecha rechaza null explícito. HU-08 documenta que solo autor admite null y que recorta textos. No se modifica ese contrato aquí.
- Listado, detalle, PATCH y exportación usan tenant autenticado mediante `require_tenant_roles`, usuario activo y tenant activo; el repositorio filtra por tenant. `ReviewManualCreate` rechaza `tenant_id` como extra. Listado y recientes ordenan fecha DESC, id DESC sin definir explícitamente posición de NULL. Los filtros comparan fechas; con `fecha_hasta=9999-12-31` se omite la condición superior por desbordamiento, por lo que requerirá atención especial para excluir NULL.
- Importación CSV/XLSX exige encabezados y valores de contenido, fecha y puntuación; usa `CSV` o `Excel` cuando falta fuente y conserva la proporcionada normalizada. HU-21 inserta `row.source` y mantiene identidad externa separada; su frontera actual exige fecha y puntuación válidas. No se amplía ese contrato por este documento.
- Exportación HU-19 usa ocho columnas y `review.fecha.isoformat()`, que fallaría con fecha nula; autor nulo ya es celda vacía. Dashboard cuenta filas y nuevas, y usa SQL `AVG`, que excluye NULL; devuelve `null` si no hay valores. No se observó distribución por estrellas en el contrato actual del dashboard.
- React usa `formatDate` con «Sin fecha» en tabla/dashboard, pero el detalle construye `Date(review.fecha)` directamente; la edición hace `review.fecha.slice(...)`, requiere fecha/puntuación y convierte puntuación con `Number`. Tabla y detalle muestran «Anónimo»/«Cliente anónimo»; el dashboard muestra «Sin autor». Deben revisarse también los renderizadores de estrellas y el servicio cliente antes de aceptar null.

## Clasificación de las reglas

- **Comportamiento actual:** únicamente lo descrito en «Estado actual comprobado» y atribuido al código inspeccionado.
- **Requisito confirmado por el responsable en el encargo de T1:** contenido obligatorio no blanco; autor, fecha y puntuación opcionales; fecha ausente sin sustitución; puntuación presente entre 1 y 5, excluida de promedios y distribución si falta; fuente manual predeterminada; conservación de fuentes externas; estado inicial Nueva y aislamiento por tenant. La confirmación se refiere al texto recibido, no a una consulta independiente del Sprint Backlog 4.
- **Propuesta técnica para revisión:** representaciones `null`/NULL/celda vacía, enteros estrictos, orden de nulos, comportamiento de PATCH y distinción entre `manual` interno y `Manual` visual descritos abajo. Son especificaciones futuras, no comportamiento ya implementado ni aprobación del equipo.
- **Decisión pendiente:** ratificación de esas propuestas y las cuestiones de compatibilidad enumeradas al final. Ninguna decisión pendiente habilita cambiar silenciosamente datos existentes.

## Reglas funcionales y propuesta técnica para Sprint 4

| Campo | Entrada manual y validación | API/persistencia | Formulario y salida |
| --- | --- | --- | --- |
| `contenido` | Obligatorio, texto con al menos un carácter no blanco; rechazar `null`, vacío y solo espacios. | NOT NULL. No reescribir silenciosamente contenido existente al migrar o editar otro campo. | Mostrar texto original; decidir con el equipo si se conserva exactamente el texto nuevo o se mantiene el recorte actual. |
| `autor` | Opcional; vacío/solo espacios se interpreta como ausencia, sin inventar autor. | `null` / SQL NULL. | Campo vacío; etiqueta «Sin autor»; CSV celda vacía. |
| `fecha` | Opcional; si existe, fecha/hora ISO 8601 válida. Nunca sustituir ausencia por fecha actual. | `null` / SQL NULL; valor presente ISO 8601. No añadir zona inexistente. | Campo vacío; «Sin fecha»; CSV celda vacía. |
| `puntuacion` | Opcional; si existe, entero 1–5; rechazar 0, 6 y fracciones. No convertir ausencia en 0. | `null` / SQL NULL. | Campo vacío; «Sin puntuación»; CSV celda vacía. |
| `fuente` | Opcional en alta manual; al omitirse, mostrar `Manual` al usuario. El tratamiento de una fuente explícita requiere acuerdo. | Propuesta: guardar y devolver `manual`; conservar fuentes reales Google, CSV y Excel. | Presentar `manual` como «Manual»; CSV conserva el valor almacenado. |
| `estado` | Establecido por servidor, no por cliente. | `nueva` en alta manual; etiqueta visual «Nueva». | Mantener estados existentes. |
| `tenant_id` | No aceptado en cuerpo; se obtiene del contexto autenticado. | NOT NULL, FK de tenant; todas las operaciones restringidas a ese tenant. | No seleccionable mediante datos arbitrarios del cliente. |

**Propuesta de compatibilidad de fuente, pendiente de validación:** conservar `manual` como valor técnico en BD, JSON y CSV, y mostrar `Manual` en la interfaz. No alterar registros históricos. Esta interpretación conserva el valor técnico actual, pero debe ratificarse porque el encargo expresa el valor como `Manual`. El filtro actual compara exactamente: la interfaz debe enviar `manual` para el filtro visual «Manual»; no cambiar el significado de fuentes externas ni normalizar silenciosamente valores históricos de distinta capitalización. El tratamiento de `Manual` explícito en solicitudes y de otros valores históricos queda pendiente. El estado técnico sigue siendo `nueva`, no la etiqueta de presentación.

## Contrato propuesto de API

`POST /api/v1/reviews` con Bearer autorizado: solo `contenido` es obligatorio; `autor`, `fecha`, `puntuacion` admiten omisión o `null`, y `fuente` puede omitirse. Las cadenas vacías de fecha/puntuación son JSON válido pero no valores válidos de estos campos: la interfaz envía `null` o las omite. La admisión de `fuente` explícita, así como `null` y texto vacío, requiere decisión explícita: el POST actual rechaza cualquier campo `fuente` por ser extra. No asumir que equivalen a omisión. Rechazar campos protegidos/desconocidos, incluido `tenant_id`, con 422; sin autenticación 401, sin rol/tenant válido 403. Ejemplo:

```json
{"contenido":"Atención amable"}
```

Respuesta esperada 201 (ejemplo parcial de `ReviewRead`, los demás campos de salida existentes se conservan):

```json
{"id":42,"tenant_id":10,"contenido":"Atención amable","autor":null,"fecha":null,"puntuacion":null,"fuente":"manual","estado":"nueva"}
```

En lectura general/detalle y dashboard deben serializarse los tres valores ausentes como `null`, sin omitirlos ni usar 0 o fecha ficticia. El tenant mostrado en la respuesta actual pertenece al usuario; no autoriza elegir otro. En edición parcial, campo omitido conserva el valor; proponer `null` explícito para eliminar autor, fecha o puntuación y rechazarlo para contenido/fuente. Esto requiere acordar la evolución del contrato HU-08 antes de implementarlo. Editar otra propiedad no debe modificar contenido, fuente externa ni resultados IA. La semántica de fecha con offset seguirá la política vigente de HU-08 para edición hasta acordar una política común para alta, importación y lectura; probarla, no suponer equivalencia.

## Consultas, dashboard y CSV

En consulta sin intervalo se incluyen también fechas NULL. Si hay `fecha_desde` o `fecha_hasta`, excluir NULL, inclusive para el extremo máximo; conservar el día final inclusivo. La puntuación exacta excluye NULL. Orden propuesto: fechas conocidas DESC, después NULL, y `id DESC` como desempate en ambos grupos; debe ser explícito y coincidir en listado, recientes y exportación en ambos motores. El resultado sin fechas no equivale a fecha actual.

Las reseñas sin puntuación cuentan en total y estado, no en promedio ni distribución por estrellas; sin puntuaciones conocidas, promedio `null` y presentación «Sin puntuaciones», no 0. Cualquier futura distribución cuenta solo valores presentes. Mantener filtro de tenant en cada agregación. Verificar que «recientes» y reordenación del cliente respeten la política de NULL.

HU-19 conserva orden exacto `id,contenido,autor,fecha,fuente,puntuacion,categoria,estado`, UTF-8 con BOM, coma, CRLF, comillas y neutralización de fórmulas; exportar todas las coincidencias del tenant y mismos filtros. Su regla general de celdas nulas vacías permite representar fecha/puntuación ausentes, pero la tabla actual las describe obligatorias: acordar la extensión con responsables de HU-19 sin alterar su documento aquí. No se garantiza que un CSV exportado con ausencias pueda reimportarse: el importador actual las rechaza. Ejemplo de fila, sin mostrar BOM:

```csv
id,contenido,autor,fecha,fuente,puntuacion,categoria,estado
42,Atención amable,,,manual,,,nueva
```

## SQLite y PostgreSQL: impacto, no migración

T2 debe cambiar `reviews.fecha` y `reviews.puntuacion` para permitir NULL en modelo y esquema persistido; `autor` ya lo permite en el modelo y debe comprobarse en bases existentes. Conservar valores históricos sin reemplazarlos y validar inserción, lectura y actualización de NULL en bases aisladas. Mantener NOT NULL y FK de tenant, contenido/fuente/estado obligatorios y la identidad de la reseña. Confirmar restricciones reales y datos de cada base, no solo metadata del modelo. Si se añade CHECK de rango, debe permitir explícitamente NULL y rechazar valores presentes fuera de 1–5; definir manejo de datos históricos inválidos antes de aplicarlo. SQLite puede requerir reconstrucción controlada de tabla; preservar filas, índices, FK, triggers y relaciones, y verificar integridad con FK activas. PostgreSQL requiere revisar DDL y bloqueo transaccional en una instancia real. Las identidades externas dependen de la clave `(id, tenant_id)` y de FKs compuestas; no perderlas ni reasignar tenants. Probar migración desde esquemas existentes, reversibilidad/recuperación acordada y reinicialización en ambas bases aisladas. No se ejecutó PostgreSQL ni se afirma compatibilidad real.

### Criterios de arranque de T2

El alcance de persistencia está especificado: permitir NULL en fecha/puntuación, mantener autor nullable y las demás restricciones, preservar datos e identidades externas, y verificar esquema anterior y nuevo, integridad y migración repetida en bases aisladas. T2 puede preparar el diseño y las pruebas con esta base; la estrategia concreta de migración, tratamiento de datos inválidos y despliegue requiere revisión del equipo antes de ejecutarse. Los cambios de esquema de respuesta y consumidores deben coordinarse con T3/HU-22/HU-23 antes de habilitar registros nulos en un entorno compartido.

## Matriz de aceptación futura

Los ejemplos son sintéticos y expectativas, no resultados ejecutados. A y B son tenants distintos; solicitudes autenticadas por A salvo indicación.

| # | Entrada / preparación | Resultado esperado | Capa responsable |
| --- | --- | --- | --- |
| 1 | POST `{"contenido":"Bien"}` | 201; autor/fecha/puntuación null, fuente técnica `manual` (visual «Manual»), estado `nueva`, tenant A. | API/esquema, servicio y BD |
| 2 | POST `{"contenido":"Bien","autor":"Ana","fecha":"2026-09-27T12:30:00","puntuacion":5}` | 201; campos enviados preservados, fuente técnica `manual` (visual «Manual»), estado `nueva` y tenant A. | Formulario, esquema, servicio/BD |
| 3 | POST contenido y `autor:null` | 201; autor null, interfaz «Sin autor», CSV vacío. | Esquema/BD, interfaz y exportador |
| 4 | POST contenido y `fecha:null` | 201; fecha null, sin fecha actual; visible sin filtro. | Esquema/BD, consulta e interfaz |
| 5 | POST contenido y `puntuacion:null` | 201; null; cuenta total/estado, no promedio ni estrellas. | Esquema/BD y dashboard |
| 6 | POST contenido y `puntuacion:0` | 422, sin escritura. | Esquema API; defensa BD si se acuerda CHECK |
| 7 | POST contenido y `puntuacion:6` | 422, sin escritura. | Esquema API; defensa BD si se acuerda CHECK |
| 8 | POST contenido `"   "` o `""` | 422, sin escritura. | Formulario y esquema API |
| 9 | POST `{"contenido":"Bien"}` sin `fuente` | 201, fuente técnica `manual`; interfaz muestra «Manual». | Servicio de registro e interfaz |
| 10 | Reseña Google existente; consultar/editar otro campo/exportar | Conservar `Google` y su identidad externa; no convertir a Manual. | Servicio, repositorio, exportador e integración |
| 11 | Reseña sin fecha y GET con `fecha_desde` o `fecha_hasta`, también fecha máxima | Excluida; GET sin intervalo la incluye. | Repositorio y API, exportación con filtros |
| 12 | Exportar fila id 42 con autor/fecha/puntuación/categoría NULL | Ocho columnas; celdas vacías como ejemplo; BOM y reglas HU-19 intactos. | Exportador/API |
| 13 | A envía POST con `tenant_id` de B | 422 por campo extra, sin escritura en B; lecturas/ediciones de B no revelan datos. | Esquema, autorización y repositorio |

Añadir pruebas de omisión frente a null, valores límite 1/5, fracciones, contenido histórico con espacios, empate y orden NULL, ausencia total de puntuaciones, exportación filtrada, autor con caracteres especiales, campos no modificados y dos tenants. Probar comportamiento tanto de SQLite como PostgreSQL real; cobertura actual no demuestra estos casos nuevos.

## Dependencias y destinatarios

**T2:** `models/review.py`, `db/migrations.py`, inicialización y esquema real; restricciones, migración y preservación de índices/FK externas. Coordinar `schemas/review.py` y `schemas/dashboard.py`, repositorio y pruebas de ambos motores. No ejecutar sobre datos reales sin plan revisado.

**T3:** `schemas/review.py`, `api/routers/reviews.py`, `services/review_service.py`, `frontend/src/pages/ManualReviewPage.jsx`, `components/reviews/ReviewEditForm.jsx`, `services/reviewService.js`, pruebas de alta/edición. Preservar campos omitidos y contenido existente. Coordinar con HU-22/HU-23 `ReviewTable`, `ReviewDetail`, `DashboardPage`, `ReviewsPage`, formateadores, dashboard/repository, `review_export_service.py` y pruebas CSV. Revisar importador y HU-21 por compatibilidad, sin cambiar sus contratos por defecto.

**Para Diego — HU-23, dashboard, búsqueda y filtros:** lectura JSON con `autor`, `fecha`, `puntuacion` explícitamente `null`; inclusión en totales/estados y exclusión de puntuaciones nulas en promedio/distribución; promedio `null` sin puntuaciones; filtros de fecha excluyen NULL incluso con fecha máxima, consulta general los incluye; puntuación exacta excluye NULL; orden propuesto fecha conocida DESC, nulos al final, `id DESC`; fuente técnica `manual` y filtro exacto, con etiqueta visual «Manual»; todo limitado al tenant autenticado. Compartir matriz 1, 4–5, 9, 11–13 y verificar consumidores/CSV.

**Para David — HU-22, bandeja y detalle:** lectura/detalle del tenant con los mismos tres `null`; mostrar «Sin autor», «Sin fecha» y «Sin puntuación» sin fabricar valores; fuente técnica `manual` se muestra «Manual» y `Google`/otras fuentes conservan su valor; estado técnico `nueva` se presenta «Nueva»; soportar selección y detalle sin convertir `null` a fecha o cero. Para edición, omisión conserva datos y la limpieza explícita con `null` es propuesta sujeta a acuerdo HU-08; no modificar contenido o fuente externa al editar otros campos. Compartir matriz 1–5, 8–10 y 13. Estas entregas son propuestas: no se presume recepción ni aprobación.

## Riesgos y decisiones pendientes

1. Ratificar `manual` técnico / «Manual» visual y compatibilidad con el requisito, filtros exactos y valores históricos sin reescritura. Acordar si POST admite fuente explícita, cómo tratar `null`/vacío y si se permite editar fuente de origen externo.
2. Acordar evolución de HU-08 para limpiar fecha/puntuación, precisión y zonas; recorte de contenido nuevo y conservación de contenido histórico. Evitar modificar texto o resultados IA al cambiar otra propiedad; inspeccionar invalidación existente cuando sí cambia contenido y decidir política para datos derivados de puntuación.
3. HU-21 mantiene claves externas y huellas separadas; probar que migraciones, edición y nuevas ausencias no rompen idempotencia ni relaciones. No relajar sus validaciones de ingesta sin decisión propia.
4. Acordar alcance y responsables de soporte de ausencias en importación CSV/XLSX: hoy exportación y reimportación no son un ciclo garantizado. Coordinar extensión de HU-19 y contratos de HU-22/HU-23.
5. Decidir política de migración, restricciones, datos históricos y despliegue; medir y verificar en PostgreSQL real. Elegir tratamiento visual de puntuación ausente en todos los componentes y compatibilidad de consumidores externos de API.

## Criterios verificables para cerrar T1

- [x] Contenido, datos ausentes, fecha, puntuación, fuente, estado y tenant documentados; ejemplos y capas responsables cubren los 13 escenarios solicitados, diferenciando estado actual, requisito, propuesta y decisión pendiente.
- [x] Impactos y dependencias T2/T3, HU-19, HU-21, HU-22 y HU-23 identificados; riesgos y decisiones abiertos registrados.
- [ ] Responsables Diego y David reciben y revisan el contrato; decisiones y aceptación quedan registradas mediante el proceso acordado.
- [ ] Contrastar con Sprint Backlog 4 independiente si se facilita; este documento usa el requerimiento proporcionado.
- [ ] Ratificar compatibilidad con HU-08/HU-19 y los puntos pendientes antes de implementación. No se declara T1 cerrado administrativamente ni PostgreSQL validado.
