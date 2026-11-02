# HU-19 / T5 #3825 — Evidencia de codificación, contenido e integridad del CSV

Fecha: 28 de octubre de 2026. Rama: `feature/HU-19-exportacion`.

## 1. Objetivo y alcance de T5

Validar mediante pruebas automatizadas y comprobación real de apertura en **Microsoft Excel para Windows** la codificación UTF-8 con BOM, la serialización estructural CSV con caracteres especiales y saltos de línea, la neutralización de prefijos de fórmulas en todas las columnas de texto, el comportamiento ante un volumen propuesto de **1,000 reviews sintéticas** y la preservación del aislamiento multi-tenant, sin romper el contrato aprobado en T1 (`docs/hu-19/contrato-csv.md`) ni las validaciones de T2–T4.

## 2. Archivos de código y pruebas modificados

- **`backend/tests/test_review_export_api.py`** (modificado):
  - Se conservaron intactas las 48 pruebas de T2 y T4.
  - Se añadieron **4 nuevas pruebas de T5** (`test_t5_codificacion_utf8_bom_unico_y_unicode_multilingue`, `test_t5_serializacion_csv_comas_comillas_saltos_espacios_nulos_y_contenido_largo`, `test_t5_neutralizacion_formulas_cinco_columnas_texto_y_preservacion_legitimos`, `test_t5_volumen_1000_reviews_sinteticas_y_aislamiento_tenant`), alcanzando **52 pruebas en `test_review_export_api.py`**.
- **`frontend/tests/reviewExport.integration.test.mjs`** (modificado):
  - Se conservaron las 7 pruebas de integración de T3 y T4.
  - Se añadió **1 nueva prueba de integración de T5** (`preserva intactos en el Blob descargado el BOM UTF-8, caracteres Unicode, saltos de línea y fórmulas neutralizadas`), alcanzando **8 pruebas en `reviewExport.integration.test.mjs`**.
- **`docs/hu-19/evidencia-t5-codificacion-contenido.md`** (creado):
  - Presente documento de evidencia técnica de T5.
- **Código de producción (`backend/app/services/review_export_service.py`, `backend/app/api/routers/reviews.py`, `frontend/`):**
  - **Sin modificaciones.** La auditoría y las nuevas pruebas demostraron que la implementación existente cumple íntegramente el contrato sin defectos.

## 3. Casos de prueba y resultados esperados vs. obtenidos

| Área (T5) | Prueba implementada | Qué verifica | Resultado real |
| --- | --- | --- | --- |
| **A. UTF-8 y BOM** | `test_t5_codificacion_utf8_bom_unico_y_unicode_multilingue` | Bytes iniciales exactos `EF BB BF`, ausencia de BOM duplicado (`raw.count(b"\xef\xbb\xbf") == 1`), primer encabezado limpio `"id"` sin `\ufeff` al decodificar con `utf-8-sig`, acentos, `ñ`, diéresis (`Ü/ü`), símbolos monetarios (`$`, `€`, `£`, `¥`, `™`), emojis (`☕⭐🔥👍`) y caracteres asiáticos (japonés, chino, coreano). | **Aprobado** |
| **B. Serialización CSV** | `test_t5_serializacion_csv_comas_comillas_saltos_espacios_nulos_y_contenido_largo` | Comas internas, comillas dobles duplicadas según RFC 4180, saltos de línea `LF` (`\n`) y `CRLF` (`\r\n`) dentro de `contenido`, cadenas vacías `""` y `None` en `autor`/`categoria`, espacios iniciales y finales conservados, contenido largo (>2,400 caracteres) y exclusión de `tenant_id`, `prioridad`, `resumen` y `tema`. | **Aprobado** |
| **C. Neutralización de fórmulas** | `test_t5_neutralizacion_formulas_cinco_columnas_texto_y_preservacion_legitimos` | Neutralización con apóstrofo `'` en las 5 columnas de texto (`contenido`, `autor`, `fuente`, `categoria`, `estado`) ante prefijos directos (`=`, `+`, `-`, `@`) y precedidos por espacios/tabulaciones/saltos de línea/controles Unicode `Cc` y `Cf` (`\x00`, `\u200b`); preservación intacta de textos legítimos con `=`, `+`, `-`, `@` intermedios (correos, guiones, calificaciones `A+`); `id` y `puntuacion` numéricos; base de datos intacta sin escritura. | **Aprobado** |
| **D. Volumen (1,000 filas)** | `test_t5_volumen_1000_reviews_sinteticas_y_aislamiento_tenant` | Exportación de 1,000 reviews sintéticas del tenant autenticado + 50 de un segundo tenant: verifica 1,000 filas de datos + 1 fila de encabezados, 8 columnas por fila, orden `fecha DESC, id DESC`, neutralización de fórmulas intercaladas y exclusión total del tenant ajeno. *(Nota: 1,000 filas es un escenario de prueba propuesto y no un límite formal cerrado por el PO).* | **Aprobado** |
| **E. Frontend Blob Unicode** | `preserva intactos en el Blob descargado el BOM UTF-8, caracteres Unicode, saltos de línea y fórmulas neutralizadas` | Verifica en `ReviewsPage` que el `Blob` recibido y entregado al enlace de descarga conserva byte por byte el BOM `EF BB BF`, caracteres Unicode/emojis, saltos de línea entrecomillados y prefijos neutralizados con `'`. | **Aprobado** |

## 4. Comandos exactos ejecutados y resultados reales

### Backend (desde `backend/`):

```powershell
$env:DATABASE_URL='sqlite://'
.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-t5 tests/test_review_export_api.py tests/test_review_export_cors.py tests/test_reviews_api.py
Remove-Item -Recurse -Force .pytest-t5 -ErrorAction SilentlyContinue
```

- **Resultado real:** `121 passed, 65 warnings in 81.28s (0:01:21)` (`52` en `test_review_export_api.py`, `3` en `test_review_export_cors.py` y `66` en `test_reviews_api.py`; `0` fallos).

### Frontend (desde `frontend/`):

```powershell
node --test --test-concurrency=1 tests/reviewExport.integration.test.mjs
npm run lint
npm run build
```

- **Resultado real:**
  - `reviewExport.integration.test.mjs`: `8 pass, 0 fail` (6,84 s).
  - `npm run lint`: aprobado sin errores ni advertencias.
  - `npm run build`: aprobado (`built in 7.01s`).

### Formato de Git:

```powershell
git diff --check
```

- **Resultado real:** aprobado sin errores de formato ni espacios en blanco.

## 5. Alcance real de la neutralización de fórmulas CSV

- La función `_safe_text` en `backend/app/services/review_export_service.py` recorre la cadena de texto ignorando espacios iniciales (`character.isspace()`) y caracteres de categorías Unicode `Cc` (Control) y `Cf` (Format, como `\u200b` zero-width space). Si el primer carácter significativo pertenece a `=+-@`, antepone un único apóstrofo `'` al inicio del valor original completo.
- **Alcance y límites:**
  - Protege las 5 columnas de texto exportadas (`contenido`, `autor`, `fuente`, `categoria`, `estado`) sin alterar valores en la base de datos ni modificar signos `=`, `+`, `-`, `@` que aparezcan después de un carácter inicial alfanumérico o de puntuación común.
  - **No es una garantía universal para cualquier software de hoja de cálculo:** como establece `docs/hu-19/contrato-csv.md`, el apóstrofo inicial introduce un carácter adicional en la celda CSV cuando el texto está entrecomillado o cuando la aplicación lectora importa el CSV sin tratar `'` como indicador oculto de texto literal.

## 6. Validación real con Microsoft Excel para Windows

Se generó un archivo CSV sintético real desde `GET /api/v1/reviews/export` (`hu19_t5_excel_probe.csv`, 666 bytes, en directorio temporal fuera del repositorio) con 4 reviews sintéticas (IDs `501`–`504`) y se abrió directamente en **Microsoft Excel para Windows (versión 16.0, Office16)** mediante automatización COM (`New-Object -ComObject Excel.Application`, `Workbooks.Open`), inspeccionando `UsedRange`, `Rows.Count`, `Columns.Count`, `Value2`, `Text`, `Formula` y `PrefixCharacter` de cada celda:

### Resultados comprobados en Excel 16.0 (Windows):

1. **Dimensiones y separador:** Excel detectó exactamente **5 filas y 8 columnas** (`Rows: 5`, `Cols: 8`, separador de listas del sistema `,`).
2. **Fila 1 (Encabezados):** Las 8 celdas (`A1:H1`) se leyeron exactamente como `id`, `contenido`, `autor`, `fecha`, `fuente`, `puntuacion`, `categoria`, `estado` (el BOM UTF-8 `EF BB BF` fue reconocido por Excel y no contaminó la celda `A1`).
3. **Fila 2 (`id=501`, Unicode, símbolos y emojis):**
   - `B2` (`contenido`): `Café pingüino: $150.00 MXN, €120,50, £99.99, ¥2000 — ¡Excelente atención! ☕⭐🔥👍 日本語のレビュー / 中文评价 / 한국어 리뷰` conservado íntegramente sin caracteres corruptos (mojibake).
   - `C2` (`autor`): `Mónica Núñez-Gómez (Ü/ü)` conservado íntegramente.
   - `E2` (`fuente`): `Google Maps™` y `G2` (`categoria`): `Atención & Café` conservados íntegramente.
4. **Fila 3 (`id=502`, comas, comillas dobles, salto de línea y nulo):**
   - `B3` (`contenido`): `Línea 1 con "comillas", comas, y salto\nLínea 2 dentro de la misma celda.` se mantuvo dentro de una única celda (`B3`) sin desplazar columnas ni partir la fila.
   - `C3` (`autor`): `Juan "El Crítico", Jr.` y `E3` (`fuente`): `Portal, "Verificado"` conservaron comillas y comas dentro de sus celdas.
   - `G3` (`categoria` nula): importada como celda vacía (`Value2: null`, `Text: ""`).
5. **Filas 4 y 5 (`id=503` y `id=504`, neutralización de fórmulas):**
   - **Ninguna celda fue ejecutada ni evaluada como fórmula por Excel:**
     - `B4`: `Formula` y `Text` son `'=SUMA(10,20)` (texto literal, no evaluó `30`).
     - `C4`: `'+52 55 1234 5678` (texto literal).
     - `E4`: `'-FuenteRiesgo` (texto literal).
     - `G4`: `'@categoria_riesgo` (texto literal).
     - `B5`: `'   \t=1+1` (texto literal, no evaluó `2`).
   - **Observación técnica documentada:** Al abrir un CSV directamente en Excel 16.0 (especialmente cuando la celda va entrecomillada por contener comas o tabulaciones, como `"'\=SUMA(10,20)"`), Excel almacena el valor como texto literal conservando el apóstrofo `'` visible al inicio (`Text: "'=SUMA(10,20)"`, `PrefixCharacter: ""`), cumpliendo el objetivo de seguridad de impedir la ejecución de la fórmula y mostrando la diferencia visual advertida en la sección «Texto con apariencia de fórmula» de `docs/hu-19/contrato-csv.md`.
   - **Nota sobre validación visual humana:** La apertura y verificación en Excel 16.0 se realizó de forma automatizada contra la aplicación real instalada en Windows; la inspección visual interactiva por parte del usuario o Product Owner permanece disponible si el equipo desea realizar una revisión visual adicional.

## 7. Pruebas de regresión (T1–T4) y limitaciones pendientes

- **Regresión T1–T4:** Las 121 pruebas de backend ejecutadas (`test_review_export_api.py`, `test_review_export_cors.py`, `test_reviews_api.py`) y las 8 pruebas de integración de frontend (`reviewExport.integration.test.mjs`) pasaron sin fallos (`0` regresiones).
- **Limitaciones y validaciones pendientes:**
  - **PostgreSQL real:** No ejecutado localmente (se utiliza SQLite temporal en el entorno de pruebas locales).
  - **Ratificación formal del límite de volumen:** El escenario de 1,000 reviews sintéticas valida el rendimiento e integridad técnica, pero el límite máximo de negocio sigue sujeto a confirmación del Product Owner si se requiriese una cota distinta.
