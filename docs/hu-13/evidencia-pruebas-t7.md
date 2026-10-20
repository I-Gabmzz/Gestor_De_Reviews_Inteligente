# HU-13 / T7 #3566 — Clasificación, errores y aislamiento

Fecha: 19 de octubre de 2026. Responsable: José Suffo. Rama: `feature/HU-13-clasificacion`. Base T1–T6: `f7b65dc980bae818f9172016ec7ab6d9e86154aa`.

## Objetivo y alcance

Verificar la clasificación de reviews, su persistencia, los errores controlados y el aislamiento multi-tenant. Se reutilizan las pruebas existentes de FastAPI, SQLite y el proveedor simulado. Las pruebas nuevas ejercitan interacciones reales del componente React en un DOM simulado. No se cambian contrato, modelo, permisos, servicios de IA ni código funcional.

## Entorno y reproducción

- Windows; Python 3.13.5 en `backend/.venv`; SQLite temporal; Pytest 8.4.2.
- Node 20.20.2; npm 10.8.2; React 19; Vite 7. `jsdom` 26.1.0 se declara como dependencia de desarrollo con autorización del usuario para reproducir las pruebas interactivas.
- Sin `GEMINI_API_KEY` local. Los tests backend usan `httpx.MockTransport`; no hacen llamadas reales a Gemini.

Desde `backend/`:

```powershell
$env:DATABASE_URL='sqlite://'
.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-t7
```

Desde `frontend/`:

```powershell
$files = Get-ChildItem -LiteralPath tests -Filter '*.test.mjs' | ForEach-Object { $_.FullName }
node --test --test-concurrency=1 $files
npm run lint
npm run build
```

Desde la raíz: `git diff --check`.

## Casos ejecutados

| Nivel | Pruebas y alcance | Resultado |
| --- | --- | --- |
| Backend existente | Suite completa: clasificación, cuatro categorías, persistencia y GET, regeneración, autenticación, roles, tenant ajeno e inexistente, salidas inválidas, fallos de red/cuota, concurrencia; además reviews, edición y autenticación | 537 aprobadas, 0 fallidas, 0 omitidas; 1 advertencia; 137,81 s |
| Frontend existente | Contrato POST autenticado y sin cuerpo/tenant, respuesta, presentación estática, permisos visuales, errores y mezcla exclusiva de categoría | 10 aprobadas, 0 fallidas, 0 omitidas |
| Frontend nuevo | Clic, carga, resultado, datos conservados, regeneración y nueva carga; nueve errores HTTP y recuperación; selección de otra review durante la petición; rechazo de respuesta de otra review, tenant, contenido o categoría | 4 aprobadas, 0 fallidas, 0 omitidas |
| ESLint | `npm run lint` | Aprobado |
| Build | `npm run build` | Aprobado |
| Whitespace | `git diff --check` | Aprobado |

Las pruebas nuevas montan `ReviewDetail` y ejecutan `useReviewClassification` en jsdom; sustituyen únicamente la respuesta de `apiClient.post` para controlar el tiempo, las categorías y los errores. El test existente del cliente deja actuar al interceptor Axios y comprueba `POST /reviews/{id}/clasificacion`, Bearer y cuerpo omitido. Las pruebas backend existentes usan el endpoint FastAPI real, autenticación, repositorio y SQLite temporal, y sustituyen el proveedor externo. En conjunto validan el contrato por ambos lados, **pero no son un E2E automatizado React → FastAPI en navegador**.

La advertencia backend es `StarletteDeprecationWarning` por el uso de `httpx` con `starlette.testclient`; no indica un fallo de T7. No se cambiaron dependencias backend para suprimirla.

## Limitaciones y pendientes

No se ejecutó una prueba nueva en navegador para T7. [La evidencia T6](t6-frontend-clasificacion.md) documenta un recorrido previo con FastAPI y proveedor simulado; no se presenta como resultado nuevo de T7. No se probó Gemini real ni la precisión semántica de sus clasificaciones. No se probó PostgreSQL en esta ejecución.

La rama HU-13 no contiene las implementaciones posteriores de HU-04, HU-14 y HU-15. Cuando se integren, habrá que comprobar conjuntamente los controles añadidos a `ReviewDetail.jsx`, `ReviewsPage.jsx` y `reviewService.js`. T7 no integra esas ramas.
