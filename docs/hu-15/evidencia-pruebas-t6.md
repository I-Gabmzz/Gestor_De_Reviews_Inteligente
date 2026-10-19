# HU-15 / T6 #3578 — Pruebas funcionales y de integración

Fecha: 19 de octubre de 2026. Responsable: José Suffo. Rama: `feature/HU-15-deteccion-tema`.

## Objetivo y alcance

Verificar la detección de temas desde el componente React y el contrato HTTP, y reutilizar las pruebas FastAPI/SQLite existentes para persistencia, permisos, aislamiento y errores del proveedor. No se cambiaron contratos, servicios de IA, permisos ni código funcional.

## Casos y resultados

| Nivel | Casos ejecutados | Resultado |
| --- | --- | --- |
| React DOM con jsdom y Vite SSR | POST autenticado sin cuerpo; tema existente y recarga de datos; clic, carga, resultado y regeneración; errores 401, 403, 404, 409, 422, 502, 503 y 504; cambio de review durante una petición y descarte de respuesta tardía | 4 pruebas nuevas aprobadas |
| Frontend existente | Presentación estática de tema, cliente HTTP, permiso visible y guardas de rol | 12 pruebas aprobadas |
| Backend FastAPI/SQLite con `httpx.MockTransport` | HU-15 (contrato, servicio y API), HU-13 (clasificación), persistencia común, reviews, edición y estado | 360 aprobadas, 0 fallidas, 1 advertencia de deprecación; 114,46 s |
| ESLint | `npm run lint` | Aprobado |
| Vite | `npm run build` | Aprobado |
| Whitespace | `git diff --check` | Aprobado |

Las pruebas backend existentes de `test_topic_api.py` comprueban login y roles, POST 200 y `ReviewRead.tema`, GET posterior, regeneración, review inexistente o ajena, aislamiento entre tenants, rechazo del catálogo inválido, fallos del proveedor y conservación de datos ante errores. T6 las ejecuta sin copiar sus casos. Los casos nuevos montan `ReviewDetail` y ejercitan el hook real; sustituyen únicamente la respuesta del transporte HTTP para controlar tiempos y errores. Un caso deja actuar al interceptor real de autenticación de Axios y comprueba método, URL, cuerpo y token.

## Reproducción

Desde `frontend/`:

```powershell
$files = Get-ChildItem -LiteralPath tests -Filter '*.test.mjs' | ForEach-Object { $_.FullName }
node --test --test-concurrency=1 $files
npm run lint
npm run build
```

Desde `backend/`, con `backend/.venv` y dependencias del proyecto:

```powershell
$env:DATABASE_URL='sqlite://'
.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-t6 tests/test_topic_api.py tests/test_topic_service.py tests/test_topic_contracts.py tests/test_classification_api.py tests/test_classification_service.py tests/test_ai_persistence.py tests/test_reviews_api.py tests/test_review_edit_api.py tests/test_review_status_api.py tests/test_review_edit_status_integration.py
```

Después de la suite se elimina el directorio temporal `.pytest-t6`. Los tests HTTP emplean bases SQLite temporales y un proveedor simulado determinista; no utilizan datos de desarrollo ni consumen Gemini.

El primer intento dentro del entorno aislado no pudo crear el directorio temporal predeterminado de Pytest. Se interrumpió y se repitió la suite con `--basetemp` dentro del proyecto en una ejecución autorizada. Esta repetición terminó con los 360 casos aprobados; el error inicial fue del entorno de ejecución, no de una aserción del producto. La advertencia restante es de Starlette/TestClient y httpx.

## Nivel de integración y límites

La cobertura automatizada combina un componente React montado en DOM simulado, el cliente Axios y pruebas FastAPI con base temporal y proveedor simulado. **No es una prueba E2E React → FastAPI en navegador**: la respuesta HTTP del test React y la llamada al proveedor del test backend se simulan por separado. La validación visual interactiva de T6 no se ejecutó; T4 documentó una comprobación anterior con navegador y servidor locales, que no sustituye esta aceptación. No había `GEMINI_API_KEY` local, por lo que no se evaluó Gemini real ni la precisión semántica de los temas.

HU-14 no está en esta rama. La compatibilidad conjunta HU-14/HU-15 requiere una verificación posterior cuando ambos cambios compartan una base; no se intentó integrarlos en T6.
