# HU-12 · T1 #3557 — Auditoría de fuente y puntuación

Fecha: 10 de octubre de 2026. Rama: `feature/HU-12-fuente-valoracion`. Base revisada: `1f67d7e8d0eded1ee7190260d1847503c91ca12a`, idéntica a `origin/main` al iniciar T1.

## Objetivo y alcance

Identificar el comportamiento actual de `fuente` y `puntuacion` antes de proponer correcciones para T2 #3558. Se revisaron registro manual, importación CSV/XLSX, edición, listado, detalle, búsqueda y filtros, contratos de API, modelo y persistencia, componentes React y pruebas backend. Esta tarea no cambia código funcional ni pruebas versionadas.

Esta auditoría vive en `docs/hu-12/` porque reúne varios flujos de la historia, no documenta un único endpoint (`docs/api/`) ni es solo un acta de ejecución (`docs/testing/`).

## Matriz de escritura

| Flujo | Entrada y obligatoriedad | Validación y normalización | Persistencia y respuesta | Frontend y cobertura existente |
| --- | --- | --- | --- | --- |
| Registro manual, `POST /api/v1/reviews` | `contenido`, `fecha` y `puntuacion` requeridos; `autor` opcional. El cliente no puede enviar `fuente` porque el esquema prohíbe campos extra. | El formulario ofrece puntuaciones 1–5 y envía un número. `ReviewManualCreate` aplica rango 1–5, pero su `int` no es estricto: acepta, por ejemplo, el JSON string `"3"`. | El servidor fija `fuente="manual"`, `estado="nueva"` y el tenant autenticado; responde **201** con `ReviewRead`, incluidos `fuente` y `puntuacion`. | `ManualReviewPage` no ofrece campo de fuente. `test_reviews_api.py` comprueba la fuente fija, la puntuación, autenticación y rechazo de 6. |
| Importación, `POST /api/v1/reviews/import` y `/api/v1/imports/upload` | Archivo `.csv` o `.xlsx`; encabezados obligatorios `contenido`, `fecha`, `puntuacion`. `autor` y `fuente` son opcionales. Existen alias para el encabezado de puntuación. | Cada puntuación se convierte a `float`, se exige valor entero entre 1 y 5 y se guarda como `int`; acepta `3.0`. La fuente suministrada se recorta en extremos, sin comprobar vacío ni longitud. Si falta la columna o la celda es `None`, usa `CSV` o `Excel`. Un archivo con errores de fila no guarda ninguna fila. | Persiste el tenant autenticado y `estado="nueva"`. Responde **200** con resumen de filas/errores, sin devolver las reviews creadas ni sus fuentes; también devuelve **200** cuando la validación de filas falla, con `es_valido=false`. | `ImportReviewsPage` sube el archivo y muestra el resumen, sin controles individuales de fuente o puntuación. `test_imports_api.py` cubre importación válida, contenido inválido, autenticación y tenant; no cubre fuente vacía, longitud ni representaciones decimales de puntuación. |
| Edición, `PATCH /api/v1/reviews/{id}` | Campos opcionales de actualización parcial; se admiten `fuente` y `puntuacion`. Un `null` explícito para cualquiera se rechaza. | `ReviewUpdate` recorta la fuente, exige 1–100 caracteres y puntuación `int` estricta de 1 a 5; rechaza `"3"`, `3.5`, booleanos y valores fuera de rango. El formulario valida lo mismo y envía solo campos cambiados. | El servicio busca la review del tenant, el repositorio actualiza y responde **200** con `ReviewRead`; los campos omitidos permanecen. | `ReviewEditForm` muestra y edita ambos campos. `test_review_edit_api.py` cubre actualización, límites, valores inválidos, conservación de campos, tenant y efecto de la puntuación en dashboard. |

## Lectura, visualización y filtros

- `GET /api/v1/reviews` devuelve `items` y `total`; `GET /api/v1/reviews/{id}` devuelve `ReviewRead`. Ambos incluyen el texto almacenado de `fuente` y el entero `puntuacion`; las consultas se acotan al tenant autenticado. La tabla muestra la fuente literal y una estrella con el número; el detalle muestra la puntuación y la fuente. Si `fuente` es `""`, la tabla queda visualmente en blanco y el detalle dice **Sin información** por el fallback de `DetailItem`. La API, en cambio, devuelve `""`.
- El filtro `puntuacion` acepta enteros 1–5 y compara por igualdad. El filtro `fuente` recorta espacios exteriores; un texto vacío equivale a no filtrar. Una fuente no vacía se compara por igualdad exacta en SQL: `Google` y `google` son distintos en las pruebas SQLite existentes. No hay catálogo cerrado. Los filtros se combinan con AND y el repositorio aplica primero `tenant_id`. La búsqueda libre solo examina `contenido`, no `fuente`.
- `ReviewsPage` ofrece selector 1–5 y entrada de fuente con espera de 400 ms; `getReviews` omite criterios vacíos. Después de editar, la página recarga el listado, por lo que una review puede salir del filtro activo al cambiar fuente o puntuación. `test_reviews_api.py` y `test_review_service.py` comprueban respuestas, combinaciones, normalización, distinción de mayúsculas y aislamiento; no hay prueba automatizada frontend en el repositorio.

## Modelo y reglas de persistencia

`Review.fuente` es `String(100), nullable=False` y `Review.puntuacion` es `Integer, nullable=False`; la tabla no declara restricciones SQL para fuente no vacía ni rango 1–5. La API de registro y edición aplica reglas más fuertes, pero la ruta de importación crea objetos `Review` directamente. SQLite permite aquí un texto de 101 caracteres en la columna declarada `String(100)`; la compatibilidad efectiva con PostgreSQL para ese caso no se ha probado. El promedio del dashboard se calcula sobre la puntuación por tenant.

## Hallazgos clasificados

| ID | Clasificación | Evidencia y consecuencia |
| --- | --- | --- |
| H1 | **Defecto confirmado** | CSV con columna `fuente` y celda vacía pasó la validación y guardó `fuente=""`. Una fuente vacía no cumple la regla de edición y produce tabla vacía frente a **Sin información** en detalle. El filtro de fuente vacía significa “sin filtro”, así que no permite seleccionar solo esas reviews. |
| H2 | **Defecto confirmado de validación; riesgo PostgreSQL potencial** | Una fuente de 101 caracteres se validó y persistió en SQLite pese a `String(100)` y al límite de edición. PostgreSQL podría rechazar ese valor; no se ejecutó PostgreSQL ni se afirma un fallo observado allí. |
| H3 | **Pendiente de validación con Product Owner** | Registro manual acepta `"3"`, importación acepta `3.0` y edición exige entero JSON estricto. Los tres almacenan el entero `3` cuando aceptan esos ejemplos. No se identificó puntuación fuera de 1–5 persistida por estos flujos; falta decidir si deben aceptar las mismas representaciones de entrada. |
| H4 | **Comportamiento válido** | El filtro de fuente distingue mayúsculas/minúsculas y hace coincidencia exacta, de acuerdo con el contrato documentado de HU-10 y las pruebas actuales. Cambiar esa semántica requeriría un requisito nuevo. |
| H5 | **Pendiente de validación con Product Owner** | La ausencia de fuente importada produce `CSV`/`Excel`, mientras una celda explícitamente vacía produce `""`. Debe decidirse si una celda vacía se rechaza o usa el valor automático. También conviene confirmar si una fuente inicialmente `manual` debe poder cambiarse en edición, como permite hoy el código. |
| H6 | **Riesgo potencial** | La base de datos solo impone no-null e integer; escrituras fuera de los esquemas de API podrían introducir una fuente vacía o puntuación fuera de rango. No se observó esa ruta en la aplicación actual. |

## Evidencia ejecutada en T1

- Suite existente enfocada: `test_imports_api.py`, `test_reviews_api.py`, `test_review_edit_api.py`, `test_review_service.py` y `test_review_edit_status_integration.py`: **229 aprobadas, 0 fallidas, 1 advertencia**, con Python 3.13.5 y `backend/.venv`. La advertencia es `StarletteDeprecationWarning` de `fastapi.testclient` por uso de `httpx`.
- Comprobaciones temporales sin archivos versionados, usando SQLite en memoria: CSV con fuente vacía guardó `""`; CSV con 101 caracteres guardó longitud 101; CSV sin columna fuente guardó `"CSV"`; CSV con puntuación `3.0` guardó `3`; XLSX sin columna fuente guardó `"Excel"`. Una validación directa de esquemas confirmó que `ReviewManualCreate` acepta `"3"` y `ReviewUpdate` lo rechaza.
- Las pruebas existentes verifican fuente `Google` frente a `google`, filtros exactos y tenant. No se ejecutó una base PostgreSQL ni pruebas automatizadas de interacción visual; la descripción del frontend procede de inspección de sus componentes. La suite completa de 352 pruebas, ESLint y build se habían ejecutado durante la preparación del entorno sobre el mismo SHA, antes de T1.

## Archivos involucrados

- Backend: `backend/app/schemas/review.py`, `backend/app/models/review.py`, `backend/app/services/import_service.py`, `backend/app/services/review_service.py`, `backend/app/repositories/review_repository.py`, `backend/app/api/routers/reviews.py`, `backend/app/api/routers/imports.py`, `backend/app/api/dependencies.py`.
- Frontend: `frontend/src/pages/ManualReviewPage.jsx`, `frontend/src/pages/ImportReviewsPage.jsx`, `frontend/src/pages/ReviewsPage.jsx`, `frontend/src/components/reviews/ReviewEditForm.jsx`, `frontend/src/components/reviews/ReviewTable.jsx`, `frontend/src/components/reviews/ReviewDetail.jsx`, `frontend/src/services/importService.js`, `frontend/src/services/reviewService.js`, `frontend/src/api/reviews.js`.
- Pruebas y contrato: los cinco archivos de pruebas citados arriba y `docs/api/hu-10-busqueda-filtros.md`.

## Riesgos de integración y propuesta mínima para T2

La importación toma el `tenant_id` de la autenticación y las lecturas/ediciones lo restringen en el repositorio; las pruebas actuales de importación y reviews cubren ese aislamiento. Cualquier ajuste de validación en T2 debe conservarlo. La futura HU-04 puede cambiar permisos y acciones visibles; HU-13 a HU-15 pueden ampliar respuesta y detalle, por lo que conviene evitar cambios no requeridos al contrato `ReviewRead`.

Para T2 se recomienda: (1) resolver con Product Owner la política de celda de fuente vacía; (2) aplicar en importación una validación coherente de fuente no vacía y máximo 100 caracteres, o el valor automático acordado; (3) añadir pruebas de límites y valor automático en CSV/XLSX, visualización, filtros y tenant; (4) alinear representaciones aceptadas de puntuación solo después de decidir el contrato. Conservar la comparación exacta y sensible a mayúsculas del filtro mientras no cambie HU-10. No se implementó ninguna de estas correcciones en T1.
