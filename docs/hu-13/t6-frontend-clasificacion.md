# HU-13 / T6 #3565 — Clasificación en el detalle de reviews

Fecha: 19 de octubre de 2026 (America/Tijuana). Responsable: Diego Erik Alfonso Montoya. Accountable: Ángel Gabriel Manjarrez Moreno.

Rama: `feature/HU-13-clasificacion`. Base auditada: `32e434cea50a1875c58f9e1081307a5dd851f7af`. T1–T5 de David permanecen intactas. Esta entrega corresponde exclusivamente a frontend T6; no declara HU-13 Done ni reemplaza aceptación o revisión.

## Auditoría previa

Se confirmaron los commits `788ec10`, `69e1a23`, `f45eaeb`, `626251e` y `32e434c`. El [contrato real de T5](t5-api-clasificacion.md) expone `POST /api/v1/reviews/{review_id}/clasificacion`, con Bearer, cuerpo opcional sin campos y respuesta `ReviewRead` completa con la categoría persistida. `GET /api/v1/reviews/{id}` recupera ese valor.

La clasificación autoriza `usuario_negocio` y `admin_tenant` con usuario/tenant vigentes, consulta por ID y tenant antes de IA y guarda solo categoría con `expected_content`. `admin_general` no obtiene acceso operativo global. Las categorías admitidas son Queja, Sugerencia, Felicitación y Consulta. Se mantienen los errores 401/403/404/409/422/500/502/503/504 existentes.

El frontend previo mostraba categoría de solo lectura en `ReviewDetail`, cargaba detalle/listado por `reviewService`, editaba mediante `ReviewEditForm` y gestionaba seguimiento con `ReviewStatusControl`. La selección se conserva por ID al recargar el listado. `apiClient` ya añade el token de localStorage. No existían pruebas frontend versionadas ni script de test en esta rama; se utiliza Node test runner, Vite y React ya disponibles, sin agregar paquetes ni modificar `package.json`.

Esta rama contiene autorización backend reutilizable de HU-04/T3, pero no la navegación de HU-04/T5 ni los controles frontend de HU-14/HU-15. No se integraron ni copiaron esas ramas. La futura combinación del componente compartido requiere revisar ambos controles; no se afirma que ese merge esté validado.

## Implementación

- [reviewService.js](../../frontend/src/services/reviewService.js): `classifyReview(reviewId, options)` usa el cliente existente, omite el cuerpo, acepta señal de cancelación y amplía únicamente el timeout de esta operación a 150 s. Devuelve datos del backend y propaga errores.
- [useReviewClassification.js](../../frontend/src/hooks/useReviewClassification.js): bloquea solicitudes duplicadas incluso antes del siguiente render, gestiona carga/éxito/error y cancela la espera al cambiar de review, tenant o contenido y al desmontar. Cancelar la espera no revierte un análisis ya iniciado en backend.
- [reviewClassification.js](../../frontend/src/utils/reviewClassification.js): verifica identidad, tenant, contenido y categoría de la respuesta; mezcla exclusivamente `categoria`. Traduce errores a mensajes fijos sin mostrar cuerpos técnicos. La autorización visual usa la sesión existente; la seguridad definitiva sigue en backend.
- [ReviewClassification.jsx](../../frontend/src/components/reviews/ReviewClassification.jsx): acción inicial y repetición explícita, indicador de procesamiento, confirmación y error recuperable. No genera ni permite editar categorías.
- [ReviewDetail.jsx](../../frontend/src/components/reviews/ReviewDetail.jsx): conserva la categoría de solo lectura e inserta el control de clasificación. Impide edición/seguimiento mientras se procesa clasificación, y no inicia clasificación durante un guardado de estado. No modifica el contrato de edición.
- [ReviewsPage.jsx](../../frontend/src/pages/ReviewsPage.jsx): aplica solo la categoría al detalle y al elemento correspondiente del listado si coinciden ID, tenant y contenido. No reemplaza estado, tema, resumen, prioridad ni otros datos con una respuesta potencialmente anterior.
- [reviewClassification.test.mjs](../../frontend/tests/reviewClassification.test.mjs): pruebas de transporte, contratos visuales, permisos, mezcla de respuesta, errores y estados de presentación.

No se modificó backend, modelos, persistencia, adaptador Gemini, configuración HTTP global, búsqueda, filtros, dashboard, importación ni `ReviewStatusControl`.

## Validación automatizada

Desde `backend/` con el entorno virtual existente, aislando el proceso de la base de desarrollo:

```powershell
$env:DATABASE_URL='sqlite://'
.\.venv\Scripts\python.exe -m pytest
```

Resultado: **537 aprobadas, 0 fallidas, 0 omitidas**, en 119.31 segundos. Dos avisos de deprecación existentes de Starlette/TestClient con httpx y BlockingPortal de AnyIO. Las fixtures HTTP dirigen el arranque y las sesiones a SQLite temporal. No se realizaron llamadas reales a Gemini.

Desde `frontend/`:

```powershell
npm run lint
npm run build
node --test --test-concurrency=1 tests/reviewClassification.test.mjs
```

Resultado: ESLint y Vite build aprobados; **10 pruebas frontend aprobadas, 0 fallidas**. Se comprueban solicitud autenticada sin tenant/cuerpo editable, respuesta real propagada, ausencia de reintentos automáticos, cuatro categorías, actualización exclusiva del campo, rechazo de otra review/tenant/contenido, permisos visuales, categoría de solo lectura, presentación de carga/error y conservación de edición/seguimiento.

Las pruebas de renderizado estático no ejecutan interacciones ni efectos de React. El ciclo asíncrono del hook y la persistencia se comprobaron en navegador según el recorrido siguiente; no se presenta el renderizado estático como E2E.

## Recorrido de navegador con backend real y proveedor simulado

Se levantaron Vite y FastAPI localmente con un helper fuera del repositorio, base SQLite temporal y usuarios/reviews sintéticos. El helper usa `ClassificationService`, autenticación, repositorio y endpoint reales; sustituye únicamente la fábrica del proveedor por `GeminiAdapter` con `httpx.MockTransport`, con demora intencional y respuestas predeterminadas.

Comprobaciones observadas:

1. Login y apertura del listado/detalle.
2. Review sin categoría: acción Clasificar con IA, carga visible, botón deshabilitado y una única solicitud por ejecución.
3. POST devuelve Queja, la interfaz la muestra y el GET posterior tras recargar y seleccionar la misma review conserva Queja.
4. Cambio de seguimiento a En revisión y edición del autor guardados sin perder categoría.
5. Repetición explícita y cambio a otra review mientras esperaba: la nueva selección continúa sin categoría; el resultado anterior no se aplica allí.
6. Contenido no analizable simulado: HTTP 422, mensaje comprensible y categoría Consulta previa conservada.
7. Cuota simulada: HTTP 503, mensaje recuperable y categoría Sugerencia previa conservada, sin exponer el cuerpo técnico del proveedor.
8. Consulta SQLite en modo de solo lectura confirma categoría, edición/estado, campos restantes y reviews ajenas a esas operaciones conservados.

El análisis semántico fue simulado: esto prueba integración frontend/backend y persistencia, no precisión real de Gemini. No se consumió cuota ni se modificaron bases del equipo.

## Límites y coordinación

PostgreSQL no fue ejecutado. No se cambió la política existente de conservación de categoría tras editar contenido. Los errores de red y restantes estados HTTP tienen pruebas deterministas de mensajes; no todos fueron inducidos en navegador. La integración futura con HU-14/HU-15 debe combinar las adiciones en `ReviewDetail` y `ReviewsPage`, conservando cada operación y sus permisos, sin reemplazar archivos completos.

Pendientes revisión, publicación autorizada, pruebas de aceptación e integración final según Definition of Done.
