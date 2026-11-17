# HU-24 / T4 — Importación y exportación con datos opcionales

Contexto histórico de implementación: revisión local sobre la base `74149d6b5ee546d6cbff2e3686f275325fd5599b`. Posteriormente T4 se publicó y HU-22 y HU-23 se integraron. La evidencia integrada está en el [informe de Sprint 4](validacion-funcional-integracion-sprint4.md).

## Alcance y comportamiento

Antes, CSV y XLSX exigían valor de fecha y puntuación en cada fila y el exportador fallaba al llamar `isoformat()` sobre fecha nula. Ahora sus celdas pueden estar vacías o contener solo espacios y se guardan como SQL NULL; el autor ausente o blanco también es NULL. Si se proporcionan, fecha y puntuación se validan; la puntuación debe ser un entero de 1 a 5 y se rechazan booleanos. La comparación decimal evita aceptar una fracción por redondeo binario y conserva entradas históricas como `3.0`. El comentario sigue siendo obligatorio. No se inventa fecha, autor ni puntuación.

**Encabezados:** se mantienen obligatorios `contenido`, `fecha` y `puntuacion` y sus alias existentes; la columna `autor` es opcional. El responsable confirmó para T4 que fecha y puntuación deben conservar sus encabezados aunque sus celdas puedan estar vacías. Una fila sin alguna de esas cabeceras invalida el archivo. Las fuentes proporcionadas se conservan con el recorte existente; si falta o está en blanco, se usa `CSV` o `Excel` según extensión. El tenant se obtiene del contexto autenticado, nunca de una columna o parámetro del archivo.

La auditoría identificó que dos encabezados idénticos o equivalentes, por ejemplo `fecha` y `date`, podían sobrescribir un dato antes de validarlo. Ahora CSV y XLSX rechazan las colisiones después de normalizar los encabezados y antes de construir diccionarios por fila; se informa un error global y no se guarda el lote. Se conservan los alias existentes. También se valida que el autor normalizado tenga hasta 255 caracteres, sin truncarlo. Las puntuaciones se validan y convierten mediante una sola interpretación decimal: acepta `1`, `5`, `3.0` y `3e0`, rechaza `1_`, fracciones, valores fuera de rango y booleanos.

**Decisión del Product Owner:** se mantiene la importación atómica para CSV/XLSX y se sustituye el criterio anterior de conservar filas válidas ante filas inválidas. Si una fila es inválida, se rechaza el lote completo, no se persiste ninguna fila y se informa el motivo del rechazo. No existe importación parcial. Esta decisión no elimina el riesgo de resultado incierto durante el propio commit descrito a continuación.

La auditoría también reprodujo que `create_many` podía confirmar el lote y fallar después al refrescar filas, comunicando un error pese a haber guardado datos. El importador utiliza ahora una operación específica del repositorio que devuelve únicamente el conteo y no ejecuta refrescos posteriores al commit; el contrato anterior de `create_many` permanece intacto para otros consumidores. Los errores de inserción probados revierten el lote. **Un error durante el propio commit puede tener resultado incierto**, incluido el caso en que el servidor confirmó antes de perder la respuesta; rollback no demuestra que el lote no se guardó. La importación no incorpora idempotencia general: antes de reintentar un resultado incierto se requiere comprobar los datos y acordar la recuperación. No se afirma atomicidad absoluta ante pérdida de conexión o caída del sistema.

```csv
contenido,autor,fecha,puntuacion,fuente
Atención amable,,,,Google
Servicio rápido,Ana,2026-09-24,5,
```

El exportador mantiene el orden recibido, las ocho columnas y el contrato HU-19 (`id,contenido,autor,fecha,fuente,puntuacion,categoria,estado`), UTF-8 con BOM, comas, CRLF, escapado CSV y neutralización de texto con apariencia de fórmula. Autor, fecha y puntuación ausentes son celdas vacías. Ejemplo sin representar el BOM:

```csv
id,contenido,autor,fecha,fuente,puntuacion,categoria,estado
42,Atención amable,,,Google,,,nueva
```

Las rutas de listado y exportación siguen usando `ReviewService.list_by_tenant` y los filtros y autorización existentes; no se agregó una segunda consulta ni filtros de HU-23. La exportación permanece aislada por tenant.

## Dependencias y pendientes en el momento de la implementación

- HU-23 no está integrada en esta rama. Búsqueda por contenido/autor/tema, urgencia, combinación AND y paridad con esos nuevos filtros necesitan pruebas una vez disponible su rama. El orden de fechas NULL y el caso `fecha_hasta=9999-12-31` siguen pendientes; T4 no cambia esos filtros ni el dashboard.
- La rama HU-22 `abd86502a3e6770c0240ee31f98fdd2e83144c5a` tiene conflictos conocidos en `ReviewDetail.jsx` y `ReviewTable.jsx`, y cambios compartidos en `ReviewEditForm.jsx`. No se modificaron esos componentes ni se integró HU-22. Su resolución corresponde a integración posterior.
- En ese momento estaba pendiente la decisión del PO sobre importación parcial; posteriormente se aprobó mantener la política atómica descrita arriba. No se altera la procedencia ni la integración Google.
- La implementación se verificó solo con SQLite sintético. PostgreSQL real y sus migraciones, respaldo/restauración de una base representativa, y paridad con HU-23 permanecen pendientes. Las pruebas de datos completos no prueban el dashboard con valores ausentes.

## Archivos

- `backend/app/services/import_service.py`: campos opcionales y validación de valores presentes.
- `backend/app/services/review_export_service.py`: serialización vacía de fecha y puntuación nulas.
- `backend/app/repositories/review_repository.py`: operación específica de importación sin refrescos después del commit; no modifica `create_many`.
- `backend/tests/test_hu24_t4_import_export.py`: regresiones sintéticas de importación, exportación y aislamiento.
- `docs/hu-24/t4-importacion-exportacion-opcionales.md`: esta evidencia.

## Verificación

Las pruebas se ejecutaron desde `backend/` con el entorno virtual existente del Sprint 3, `DATABASE_URL=sqlite://`, SQLite temporal, bytecode y caché de pytest deshabilitados, variables de credenciales de proveedor eliminadas del proceso y sin llamadas a APIs externas:

```text
python -m pytest tests/test_hu24_t4_import_export.py tests/test_imports_api.py tests/test_review_export_api.py tests/test_reviews_api.py tests/test_hu24_t3_http.py -q -p no:cacheprovider --basetemp ..\.hu24-t4-final-regression
177 passed, 95 warnings in 113.11s
```

Se usó `C:\Users\joser\Documents\GestorDeReviews_Sprint3\backend\.venv\Scripts\python.exe`; FastAPI/TestClient se ejecutó en proceso fuera del aislamiento que previamente bloqueó sus pruebas, sobre bases temporales. Las advertencias corresponden a deprecaciones de FastAPI y a metadata de Pydantic. Los casos de T4 verifican CSV/XLSX, encabezados, ausencia de autor/fecha/puntuación, puntuaciones inválidas y de precisión límite, atomicidad, fuente, caracteres especiales, fórmulas, formato y paridad de los filtros actuales. La prueba HTTP importa y exporta reseñas similares de dos tenants con parámetros y columnas de tenant manipulados, y compara los identificadores permitidos con el listado.

Posteriormente se añadieron tres casos de paridad con filtros de fecha y filtros combinados. La ejecución completa de `tests/test_hu24_t4_import_export.py` dio **35 passed, 95 warnings** sobre SQLite temporal; incluye la prueba HTTP con dos tenants. Esta suite específica se ejecutó después de la regresión de 177 pruebas.

Tras las correcciones de auditoría se ejecutó, en el mismo entorno aislado:

```text
python -m pytest tests/test_hu24_t4_import_export.py tests/test_imports_api.py tests/test_review_export_api.py tests/test_reviews_api.py tests/test_hu24_t3_http.py tests/test_external_review_persistence.py -q -p no:cacheprovider --basetemp ..\.hu24-t4-fix-regression
322 passed, 95 warnings in 122.31s
```

Se agregaron pruebas de encabezados idénticos y equivalentes CSV/XLSX con valores vacíos en ambas posiciones, encabezados sin filas, errores HTTP controlados, límites de autor, puntuaciones límite y ambiguas, fallo SQL durante la inserción y fallo simulado después de una confirmación. También se comprueba que el flujo de importación no invoque `refresh` tras el commit. El caso de commit incierto muestra que el lote puede existir aun cuando se recibe una excepción; no acredita recuperación automática ni idempotencia.

La sintaxis de los archivos Python fue comprobada con `ast.parse`; `git diff --check` no informó errores. No se ejecutaron lint ni build de frontend porque T4 no modifica código de frontend. No se ejecutaron PostgreSQL real, APIs externas ni la suite backend completa.
