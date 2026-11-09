# HU-24 / T3 — Registro y edición con datos opcionales

Estado: implementación local para revisión, sin commit, push ni despliegue. Rama `feature/HU-24-registro-importacion-exportacion`, base inicial `77e07223726fc97bfb2ab5dc70818a0b0b133a84`. T1 y T2 permanecen sin modificar en su implementación y documentación; se actualizó una prueba de T2 cuya expectativa de entrada obligatoria fue sustituida expresamente por T3. No se modificó OpenProject.

## Contrato implementado

`POST /api/v1/reviews` requiere `contenido` no vacío ni compuesto por espacios. `autor`, `fecha` y `puntuacion` se pueden omitir o enviar como `null`; fecha presente es datetime aceptado por Pydantic y puntuación presente es un entero estricto de 1 a 5. No se inventan fechas ni puntuaciones. El servidor continúa asignando `fuente="manual"`, `estado="nueva"` y el tenant autenticado; rechaza campos adicionales como `tenant_id`, `fuente`, `estado` y resultados de IA. Las fuentes históricas no se migran. Autor se normaliza a `null` si está vacío y contenido mantiene la normalización de espacios preexistente en alta.

```json
{"contenido":"Atención amable"}
```

El alta anterior debe responder 201 con `autor`, `fecha` y `puntuacion` en `null`. Un alta completa puede enviar `{"contenido":"Bien","autor":"Ana","fecha":"2026-09-24T10:30:00","puntuacion":5}`. Son inválidos contenido `"   "`, puntuaciones `0`, `6`, fracciones, booleanos o texto numérico, así como identificadores de tenant enviados por el cliente.

`PATCH /api/v1/reviews/{id}` conserva campos omitidos y admite `{"fecha":null,"puntuacion":null,"autor":null}` para limpiarlos. `contenido` y `fuente` no admiten `null`; campos protegidos, desconocidos y de IA se rechazan. La edición de fecha con zona continúa normalizándose a UTC según HU-08. Se conserva el comportamiento previo para invalidar resultados derivados cuando se edita expresamente el contenido; editar otro campo no debe reescribir contenido histórico ni fuente externa. Los roles siguen siendo `usuario_negocio` y `admin_tenant`; el identificador del tenant se resuelve del usuario autenticado y la búsqueda de la reseña se limita a ese tenant. La reseña ajena devuelve 404 en lectura/edición.

## Interfaz y alcance

El formulario manual muestra fecha y puntuación como opcionales y envía `null` cuando están vacías. El formulario de edición acepta y permite limpiar los tres campos opcionales, y construye el PATCH comparando valores ingresados con los originales: cambiar otro campo no recorta contenido histórico ni sustituye fuente. Tabla y detalle compartidos con HU-22 muestran «Sin fecha» y «Sin puntuación» para que una reseña recién guardada pueda abrirse y editarse. Son ajustes mínimos del flujo; no se rediseñó bandeja ni se modificaron dashboard, filtros o exportación.

## Evidencia de pruebas

Desde `backend/`, con entorno Python existente del Sprint 3, `DATABASE_URL=sqlite://`, bases temporales nuevas, bytecode y caché de pytest deshabilitados y sin credenciales de proveedor, se ejecutó:

```text
python -m pytest tests/test_hu24_t3_http.py tests/test_hu24_t3_optional_reviews.py tests/test_reviews_api.py tests/test_review_edit_api.py tests/test_review_status_api.py tests/test_imports_api.py tests/test_dashboard.py tests/test_review_export_api.py tests/test_tenant_isolation.py tests/test_hu24_nullable_migration.py tests/test_review_service.py -q -p no:cacheprovider --basetemp ..\.hu24-t3-regression
374 passed, 95 warnings in 159.85s
```

La ejecución HTTP usó FastAPI/TestClient en proceso y SQLite temporal; no es una prueba de red o navegador contra un servidor desplegado. Cubre crear → leer → completar → limpiar, persistencia, roles de usuario y administrador de tenant, 401/403, aislamiento de otro tenant y entradas inválidas. Los módulos de regresión de HU-19 y dashboard pasan para sus fixtures existentes con valores completos; eso **no demuestra** compatibilidad con valores ausentes.

Posteriormente se añadió la comprobación de edición de una reseña histórica Google conservando estado, contenido y resumen; `python -m pytest tests/test_hu24_t3_optional_reviews.py -q -p no:cacheprovider --basetemp ..\.hu24-t3-persist` dio **16 passed**, incluida esa prueba. Una primera ejecución HTTP dentro del aislamiento quedó detenida y se interrumpió; la regresión anterior terminó al ejecutar las pruebas fuera de ese aislamiento, con bases temporales y sin claves de proveedores. No se cuenta la ejecución interrumpida como aprobada.

Desde `frontend/`: `npm run lint` y `npm run build` finalizaron correctamente; `node --test --test-concurrency=1 tests/hu24OptionalReviews.integration.test.mjs tests/reviewExport.integration.test.mjs` produjo **12 passed**. Las pruebas de interfaz usan React, JSDOM, Vite y respuestas simuladas: comprueban payloads, rechazos, limpieza y apertura en tabla/detalle, además de la regresión existente de exportación con datos completos. Para ejecutar se copió temporalmente el `node_modules` existente del Sprint 3; Vite y React coincidían con el lockfile local. No se instalaron dependencias ni se conservan artefactos de prueba.

## Bloqueos y dependencias

- **Dashboard HU-23:** `DashboardReviewRead` sigue exigiendo fecha y puntuación; con una reseña reciente que tenga nulos se comprobó que el schema rechaza ambos. HU-23 debe acordar el comportamiento de visualización y métricas antes de habilitar este flujo en un entorno compartido.
- **Exportación HU-19/T4:** `serialize_reviews_csv` sigue llamando `fecha.isoformat()`; se reprodujo `AttributeError` con fecha nula. No se implementó exportación opcional por estar expresamente fuera de T3. Sin fecha, una exportación que incluya esa reseña falla.
- **Filtros y orden HU-23:** el caso `fecha_hasta=9999-12-31` y el orden entre NULL y fechas aún requieren tratamiento explícito y pruebas por motor. No se modificaron filtros.
- **HU-22:** tabla/detalle recibieron solo el ajuste necesario para reabrir valores ausentes; coordinar con su responsable los cambios compartidos y las etiquetas visuales. La fuente técnica se sigue mostrando según la interfaz existente; la decisión de presentación «Manual» sigue pendiente.
- **PostgreSQL:** no se ejecutaron pruebas en servidor PostgreSQL real; la validación T2 y el flujo T3 en ese motor siguen pendientes. Respaldos/restauración y habilitación explícita de migración siguen sujetos al procedimiento de T2.

**No habilitar en entornos compartidos ni declarar compatibilidad completa con HU-19/HU-23** hasta resolver los bloqueos anteriores. No se implementaron T4, T5 ni T6.

## Archivos

- Backend: `backend/app/schemas/review.py`, `backend/tests/test_hu24_t3_optional_reviews.py`, `backend/tests/test_hu24_t3_http.py`, `backend/tests/test_review_edit_api.py`, `backend/tests/test_hu24_nullable_migration.py` (ajuste de expectativas antiguas que exigían fecha/puntuación).
- Frontend: `frontend/src/pages/ManualReviewPage.jsx`, `frontend/src/components/reviews/ReviewEditForm.jsx`, `ReviewTable.jsx`, `ReviewDetail.jsx`, `frontend/tests/hu24OptionalReviews.integration.test.mjs`.
- Evidencia: este documento.
