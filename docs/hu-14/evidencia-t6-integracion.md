# HU-14 / T6 #3572 — Evidencia de integración frontend/backend

Responsable: José Suffo. Fecha: 19 de octubre de 2026.

## Objetivo y alcance

Comprobar que el componente React solicita el resumen conforme al contrato HTTP y que
FastAPI autentica, genera con un proveedor simulado, persiste y devuelve el resultado.
No se modificaron el endpoint, el proveedor ni las funciones de HU-14.

## Casos y evidencia

- `backend/tests/test_summary_integration_t6.py`: login HTTP real, `POST {}` a
  `/api/v1/reviews/101/resumen`, respuesta 200 `ReviewRead`, consulta GET posterior,
  regeneración y verificación del contenido enviado al proveedor simulado.
- `backend/tests/test_summary.py`: se reutilizan los casos existentes de review ajena
  o inexistente (404), roles y usuarios no autorizados (401/403), salida inválida,
  errores controlados del proveedor, aislamiento por tenant, concurrencia y rollback.
- `frontend/tests/summary.integration.test.mjs`: renderiza `ReviewSummary` real con
  React y jsdom; usa `reviewService` y `apiClient` reales con un adaptador Axios de
  prueba determinista. Comprueba ruta, método, cuerpo `{}`, token, estado inicial,
  carga, bloqueo de doble envío, visualización, lectura tras recarga, regeneración,
  mensajes 401/403/404/422/503/504 y cancelación al cambiar de review.
- Las pruebas del frontend simulan respuestas HTTP; las del backend atraviesan
  FastAPI, autenticación, servicio, repositorio y SQLite temporal con
  `httpx.MockTransport`. Juntas comprueban ambos extremos del mismo contrato.

## Comandos y resultados

Desde `backend`, con `.venv` y directorios temporales aislados:

```powershell
$env:TEMP='C:\Users\joser\Documents\GestorDeReviews_Sprint2\backend\.venv\tmp-hu14-t6-suite'
$env:TMP=$env:TEMP
.\.venv\Scripts\python.exe -m pytest -q tests\test_summary_integration_t6.py tests\test_summary.py tests\test_ai_persistence.py tests\test_review_edit_api.py tests\test_review_status_api.py tests\test_reviews_api.py tests\test_classification_api.py --basetemp=.venv\pytest-hu14-t6-suite
```

Resultado: **264 aprobadas, 0 fallidas, 1 advertencia** de deprecación
Starlette/TestClient respecto a HTTPX.

Desde `frontend`:

```powershell
npm run test:integration
npm run lint
npm run build
```

Resultados: **9 pruebas frontend aprobadas, 0 fallidas**; ESLint aprobado;
build de Vite aprobado. `git diff --check`: aprobado.

Se añadió `jsdom@26.1.0` como dependencia de desarrollo con autorización del
usuario; es compatible con Node 20 y permite repetir estas pruebas sin un
navegador E2E. `npm audit` reportó 2 avisos moderados en React Router y 1 alto
en `source-map-js`, dependencias preexistentes y ajenas a jsdom; no se
actualizaron en T6.

## Limitaciones y pendientes

- No hay `GEMINI_API_KEY` local. Ninguna prueba consumió Gemini real; la calidad
  semántica de sus resúmenes sigue pendiente de una validación autorizada con
  configuración privada, sin registrar ni exponer la clave.
- Se intentó abrir Vite desde el navegador integrado mediante `localhost:5173`
  y la dirección local `192.168.1.75:5173`; ambas conexiones agotaron el tiempo.
  No se realizó ni se acredita el recorrido visual login → reviews → detalle →
  generar → visualizar → regenerar. No fue necesario iniciar una base visual de
  prueba porque el navegador no alcanzó siquiera el frontend.
- No se ejecutó una prueba E2E que conecte un navegador con FastAPI en un mismo
  proceso. Las pruebas automatizadas validan el componente y el backend por
  separado, con el contrato compartido. La prueba visual integrada queda
  pendiente en un entorno con acceso al servidor local.
- No se ejecutó la suite backend completa en T6: se seleccionaron los 264 casos
  pertinentes de resumen, persistencia y regresión de reviews/clasificación.
- PostgreSQL y la fidelidad factual general del modelo no se validaron en T6.
