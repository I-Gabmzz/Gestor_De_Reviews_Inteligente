# HU-19 / T4 #3824 — Evidencia de comparación entre listado y exportación CSV

Fecha: 28 de octubre de 2026. Rama: `feature/HU-19-exportacion`.

## 1. Objetivo de T4

Verificar mediante pruebas automatizadas que el CSV exportado por `GET /api/v1/reviews/export` contiene exactamente los mismos registros, en el mismo orden y con los mismos valores representados en las ocho columnas del contrato aprobado (`id,contenido,autor,fecha,fuente,puntuacion,categoria,estado`), que el endpoint de listado `GET /api/v1/reviews` cuando ambos reciben los mismos filtros y el mismo contexto de usuario/tenant. Asimismo, comprobar que la acción de exportación en la interfaz React depende de los filtros aplicados al listado y no de la review seleccionada individualmente.

## 2. Alcance de las pruebas

- **Backend (`backend/tests/test_review_export_api.py`):**
  - Se conservaron intactas las pruebas de T2 (21 ejecuciones parametrizadas) y de T3 (`test_review_export_cors.py`, 3 casos).
  - Se añadieron **27 nuevos casos parametrizados** en dos funciones de prueba (`test_comparacion_exhaustiva_listado_y_csv_ocho_columnas_orden_y_nulos` con 24 escenarios y `test_aislamiento_multitenant_comparado_con_mismos_filtros` con 3 escenarios) apoyados en la fixture sintética `seed_t4_comparison_reviews` y el verificador `_expected_csv_row_from_item` (alcanzando **48 pruebas en `test_review_export_api.py`** y **51 en las dos suites de exportación**).
- **Frontend (`frontend/tests/reviewExport.integration.test.mjs`):**
  - Se conservaron los 6 casos de integración existentes de T3.
  - Se añadió 1 caso de integración específico (`la exportación depende de los filtros aplicados al listado y no de la review seleccionada`) que carga múltiples reviews en `ReviewsPage`, cambia explícitamente la fila seleccionada (`aria-selected="true"` pasa de la review `101` a la `102`) y verifica que la petición a `/reviews/export` no envía identificadores de selección (`review_id` ni `id`), descargando el CSV completo del listado filtrado sin alterar la selección activa en pantalla.
- **No se modificó código de producción**, esquemas de base de datos, dependencias ni el contrato `docs/hu-19/contrato-csv.md`.

## 3. Comandos ejecutados

### Verificación de línea base y suite de backend (desde `backend/`):

```powershell
$env:DATABASE_URL='sqlite://'
.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-t4 tests/test_review_export_api.py tests/test_review_export_cors.py tests/test_reviews_api.py
Remove-Item -Recurse -Force .pytest-t4 -ErrorAction SilentlyContinue
```

### Suite de integración frontend, linter y build (desde `frontend/`):

```powershell
node --test --test-concurrency=1 tests/reviewExport.integration.test.mjs
npm run lint
npm run build
```

### Verificación de formato y estado Git:

```powershell
git diff --check
git status -sb
```

## 4. Casos de prueba y resultados reales

| Suite / Comando | Antes de T4 (Línea base) | Con cambios de T4 | Estado |
| --- | ---: | ---: | --- |
| `backend/tests/test_review_export_api.py` | 21 aprobadas | **48 aprobadas** (+27 casos T4) | Aprobado (0 fallos) |
| `backend/tests/test_review_export_cors.py` | 3 aprobadas | **3 aprobadas** | Aprobado (0 fallos) |
| `backend/tests/test_reviews_api.py` | 66 aprobadas | **66 aprobadas** | Aprobado (0 fallos) |
| **Total Backend ejecutado (3 archivos)** | **90 aprobadas** (60,21 s) | **117 aprobadas** (78,32 s) | **Aprobado (0 fallos)** |
| **Suites de exportación (`export_api` + `export_cors`)** | 24 aprobadas | **51 aprobadas** (35,85 s) | **Aprobado (0 fallos)** |
| `frontend/tests/reviewExport.integration.test.mjs` | 6 aprobadas (7,00 s) | **7 aprobadas** (+1 caso T4, 6,47 s) | **Aprobado (0 fallos)** |
| `npm run lint` (ESLint) | — | Sin errores ni advertencias | **Aprobado** |
| `npm run build` (Vite) | — | Compilación exitosa en 8,06 s | **Aprobado** |
| `git diff --check` | — | Sin errores de espacios/formato | **Aprobado** |

## 5. Comparación entre listado y exportación

Para cada combinación de filtros probada en `test_comparacion_exhaustiva_listado_y_csv_ocho_columnas_orden_y_nulos`:

1. Se invoca `GET /api/v1/reviews` y `GET /api/v1/reviews/export` con idénticos parámetros `params` y cabeceras de autorización.
2. Se comprueba que ambos devuelven HTTP `200`, que el archivo CSV inicia con el BOM UTF-8 (`\xef\xbb\xbf`), que la fila `0` coincide exactamente con `["id", "contenido", "autor", "fecha", "fuente", "puntuacion", "categoria", "estado"]` y que el número de filas de datos del CSV es igual a `len(items)` y a `total` del listado.
3. Para cada par `(item, csv_row)` en orden estricto (`zip(items, data_rows, strict=True)`), se valida que `csv_row` tenga exactamente 8 columnas y coincida celda por celda con la transformación contractual de `item` (sin invocar funciones internas de producción):
   - `id`: `str(item["id"])`
   - `contenido`: `str(item["contenido"])` (conservando saltos de línea, comas y comillas dobles)
   - `autor`: `""` cuando `item["autor"] is None`, o `str(item["autor"])`
   - `fecha`: `str(item["fecha"])` en formato ISO 8601 exacto
   - `fuente`: `str(item["fuente"])`
   - `puntuacion`: `str(item["puntuacion"])`
   - `categoria`: `""` cuando `item["categoria"] is None`, o `str(item["categoria"])`
   - `estado`: `str(item["estado"])`
4. Se confirma además que campos internos del modelo como `tenant_id`, `prioridad`, `resumen` y `tema` (presentes en el JSON de listado, p. ej. en la review sintética `301`) no se filtran como columnas adicionales en el CSV.

## 6. Validación de orden, filtros, fechas, búsqueda, valores nulos y aislamiento

- **Orden (`fecha DESC, id DESC`):**
  - Las reviews sintéticas `304` y `305` comparten exactamente el mismo instante `2026-09-27T23:59:59.999999`. Tanto el listado como el CSV devuelven `[305, 304]` de forma consistente.
- **Seis filtros individuales y combinados:**
  - `busqueda`: coincidencia parcial insensible a mayúsculas/minúsculas y recorte de espacios (`"servicio"`, `"  SERVICIO NOCTURNO  "`), escape literal de comodines SQL (`"100%"` → `[306]`, `"servicio_especial"` → `[306]`), cadenas vacías o de solo espacios tratadas como ausencia de filtro (`""`, `"   "`).
  - `fecha_desde` y `fecha_hasta`: validación de bordes horarios exactos:
    - `301` (`2026-09-26T23:59:59.999999`) queda fuera de `fecha_desde=2026-09-27`.
    - `302` (`2026-09-27T00:00:00`) y `304`/`305` (`2026-09-27T23:59:59.999999`) entran en el rango `2026-09-27` a `2026-09-27`.
    - `306` (`2026-09-28T00:00:00`) queda fuera de `fecha_hasta=2026-09-27` y entra cuando `fecha_hasta=2026-09-28`.
  - `puntuacion`: igualdad exacta numérica (`5` → `[305, 304, 302, 301]`, `3` → `[306]`).
  - `estado`: igualdad exacta (`nueva`, `en_revision`, `atendida`).
  - `fuente`: igualdad exacta sensible a mayúsculas tras `strip()` (`"Google"` y `"  Google  "` devuelven `[305, 304, 302, 301]`; `"google"` devuelve `[307]`; `"GOOGLE"` devuelve `[]`).
  - Combinación simultánea de los 6 filtros: devuelve `[305, 304, 302]` con coincidencia total de las 8 columnas.
- **Resultados vacíos:**
  - Con `{"busqueda": "no-existe-coincidencia"}`, `{"fuente": "GOOGLE"}` y `{"estado": "atendida", "fuente": "Facebook"}`, el listado devuelve `items: [], total: 0` y la exportación devuelve únicamente el BOM y la fila de encabezados (`rows == [HEADERS]`, `data_rows == []`).
- **Valores nulos:**
  - Las reviews `302` (`autor=None, categoria=None`), `303` (`autor="Carlos Ruiz", categoria=None`), `304` (`autor=None, categoria="Servicio"`) y `307` (`autor=None, categoria="Otro"`) verifican todas las combinaciones de nulidad, serializándose siempre como cadena vacía `""` en las posiciones de columna `2` (`autor`) y `6` (`categoria`), sin emitir `"null"`, `"None"` ni `"Anónimo"`.
- **Aislamiento multi-tenant:**
  - En `test_aislamiento_multitenant_comparado_con_mismos_filtros`, bajo el mismo conjunto de 6 filtros activos (`busqueda="servicio"`, `fecha_desde="2026-09-27"`, `fecha_hasta="2026-09-27"`, `puntuacion=5`, `estado="nueva"`, `fuente="Google"`), los usuarios del tenant `10` (`usuario@example.com` y `tenant@example.com`) obtienen exactamente `[305, 304, 302]` tanto en listado como en CSV, mientras que el usuario del tenant `20` (`usuario-b@example.com`) obtiene exclusivamente `[401]`, coincidiendo las 8 columnas de cada tenant sin filtración cruzada.
- **Validación de filtros inválidos:**
  - Cubierta en `test_filtros_invalidos_tienen_el_mismo_error_que_el_listado`, verificando respuesta `422` y cuerpo JSON idéntico entre `/api/v1/reviews` y `/api/v1/reviews/export`.

## 7. Incidencias encontradas y resolución

- **Incidencia de entorno:** Al ejecutar `pytest` dentro del sandbox de Windows, la creación del directorio temporal de Pytest bloqueó el proceso sin terminar (mismo comportamiento del entorno documentado previamente en `docs/hu-15/evidencia-pruebas-t6.md`).
- **Resolución:** Se canceló la tarea bloqueada y se ejecutó Pytest fuera del sandbox utilizando `--basetemp .pytest-t4` dentro de `backend/`, eliminando el directorio temporal tras completar la ejecución. No hubo fallos en ninguna prueba del producto.

## 8. Pruebas que no pudieron ejecutarse y su motivo

- **PostgreSQL real:** Las pruebas se ejecutaron contra bases de datos SQLite temporales conforme a la configuración de desarrollo y pruebas locales del proyecto; no hay una instancia PostgreSQL configurada en el entorno local.
- **Pruebas de volumen, apertura en hojas de cálculo y batería exhaustiva de codificación/fórmulas de T5:** No se ejecutaron por pertenecer al alcance exclusivo de la tarea **T5 #3825**, la cual aún no se ha iniciado por instrucción explícita.
