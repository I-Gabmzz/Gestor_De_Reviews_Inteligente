# HU-23 #4011 / T2 #4023 — Búsqueda, urgencia y paridad CSV

Base: [contrato T1](./t1-contrato-urgencia-busqueda-metricas.md), commit `1eb82eb41918503859847c567740778f3dbec732`. La implementación de T2 sigue la propuesta solicitada; `urgente` aún requiere ratificación externa antes de publicar la rama. No consta aprobación del PO.

## Contrato implementado

- `GET /api/v1/reviews` y `GET /api/v1/reviews/export` usan la misma consulta. `busqueda` aplica coincidencia parcial **OR** en contenido, autor y tema IA, después de recortar espacios exteriores. Una cadena vacía no restringe; un campo NULL no coincide por sí solo. Cada coincidencia devuelve una sola fila. Se conservan `icontains`, parámetros vinculados y escape literal de `%` y `_`. Se conserva el comportamiento de mayúsculas del motor; no se garantiza equivalencia uniforme de mayúsculas acentuadas entre SQLite y PostgreSQL.
- `urgente=true` exige prioridad `Alta` y estado `nueva` o `en_revision`. Omitirlo o enviar `false` no restringe. Otro literal explícito, incluso vacío, devuelve HTTP 422. No se agrega estado ni columna. El tenant autenticado y los demás filtros se aplican con **AND**. Por ejemplo, Urgente + Atendida devuelve lista vacía y CSV solo con encabezados.
- CSV conserva las ocho columnas HU-19 (`id,contenido,autor,fecha,fuente,puntuacion,categoria,estado`), BOM, separador, CRLF y neutralización de fórmulas. Conserva el mismo orden del listado, fecha DESC e ID DESC. El serializador, roles, modelos, migraciones e importaciones no cambian.
- El cliente comparte `reviewParams`: admite `urgente` booleano o literal de URL y omite `false` como criterio inactivo. No incorpora `tenant_id` ni cambia los controles, el dashboard o la navegación.

## Evidencia y auditoría

La matriz de T1 se adaptó al esquema actual con fechas y puntuaciones presentes, dos tenants, autor/tema/prioridad NULL cuando ya son válidos y un empate de fechas. Se verificaron IDs, total, orden, paridad CSV, literales y permisos con datos ficticios. Las expectativas históricas de búsqueda solo por contenido y de seis parámetros OpenAPI se actualizaron por el contrato T2; se mantiene el rechazo de coincidencias en metadatos fuera de los tres campos. El ejemplo de T1 con `ENVÍO` se probó como `envío` en SQLite; la insensibilidad a mayúsculas se verificó por separado con letras ASCII, sin cambiar la colación existente.

| Validación | Resultado |
| --- | --- |
| Backend: `tests/test_review_query_hu23.py` | **32 aprobadas** |
| Backend: listado, servicio, CSV, CORS de exportación, tenant y dashboard | **260 aprobadas** |
| Backend: `tests/test_database_connection.py` | **5 aprobadas**, incluidos los tres casos antes fallidos |
| Backend completo | **2074 aprobadas**, 0 fallidas y **30 omitidas** |
| Frontend: `node --no-experimental-global-navigator --test tests/*.test.mjs` | **155 aprobadas**, 0 fallidas y 0 omitidas |
| Frontend: `node node_modules/eslint/bin/eslint.js .` y `node node_modules/vite/bin/vite.js build` | Código 0 en ambos |

El backend se ejecutó con `pytest.main` desde un proceso aislado: HTTPX real y sockets no locales bloqueados, conexión de la aplicación bloqueada, SQLite solo en memoria o bajo el directorio temporal de pruebas, y `TEST_POSTGRES_URL` ausente en ese proceso. No se usaron bases personales ni proveedores. La compilación SQL sin conexión en ambos dialectos comprobó el grupo OR bajo el AND del tenant, el escape de patrones, los valores vinculados, el orden y la ausencia de joins. No equivale a una prueba contra PostgreSQL real.

La validación final se ejecutó con Python 3.14.4 y pytest 8.4.2 desde un entorno virtual temporal fuera del repositorio. Se reutilizaron las dependencias locales de prueba y se instaló `psycopg[binary]` 3.3.9 solo en el entorno virtual. Los tres casos anteriormente fallidos ahora pasan. Las 30 omisiones preexistentes requieren `TEST_POSTGRES_URL`. La instancia real de PostgreSQL sigue sin verificarse. Frontend, ESLint y build se repitieron con Node 24.22.1.

## Archivos y coordinación

- Backend: [router](../../backend/app/api/routers/reviews.py), [servicio](../../backend/app/services/review_service.py), [repositorio](../../backend/app/repositories/review_repository.py) y pruebas `test_review_query_hu23.py`, `test_review_service.py`, `test_reviews_api.py`, `test_review_export_api.py`.
- Frontend: [cliente HTTP de reseñas](../../frontend/src/api/reviews.js) y `reviewExport.integration.test.mjs`.
- David (HU-22): integrar el control visual con `urgente=true`, conservar los filtros activos y el criterio de la lista cargada al exportar. La apertura desde indicadores sigue para T4.
- José (HU-24): revisar paridad con `busqueda` y `urgente` en ambas rutas, y conservar fuente exacta y formato HU-19. Fecha y puntuación opcionales, representación de ausencias y orden con nulos requieren su coordinación; T2 no los habilita.

La evidencia queda preparada para compartir; no se presume recepción ni aprobación.
