# HU-15 / T5 #3577 — Pruebas de detección de temas y aislamiento

Fecha: 19 de octubre de 2026 (America/Tijuana). Rama: `feature/HU-15-deteccion-tema`.

Este documento registra la validación técnica de T1–T5. No ejecuta ni cierra la TASK #3578/T6 de José Suffo, no sustituye la revisión del equipo y no declara HU-15 Done.

## Alcance y componentes

- T1 registra el catálogo aprobado Atención, Servicio, Precio, Producto y Otro, con 19 ejemplos y separación de categoría.
- T2 identifica el asunto mediante `TopicService.analyze` y el adaptador Gemini existente; `TopicDecision` valida el catálogo y permite `null` solo como rechazo interno. No cambia `TopicResult`.
- T3 expone `POST /api/v1/reviews/{review_id}/tema` en el router `topics`, registrado junto al router existente de reviews. Devuelve `ReviewRead`, utiliza el contenido del servidor y no admite campos de autoridad ni resultados en el cuerpo.
- La persistencia reutiliza `ReviewRepository.save_ai_result`, `Review.tema` y `expected_content`. No se añadieron migraciones, tablas ni columnas.
- T4 muestra el resultado guardado y permite una solicitud explícita desde el detalle. La nueva detección de un tema existente fue autorizada por el usuario durante esta sesión: reemplaza solo tema tras éxito y conserva el anterior ante fallos.

## Reproducción automatizada

Entorno existente: Windows, Python 3.14.2 del entorno virtual, Pytest 8.4.2 y SQLite temporal. No se instalaron dependencias.

Desde `backend/`, en PowerShell:

```powershell
$env:DATABASE_URL='sqlite://'
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m compileall app
```

La variable se aplica solo al proceso de validación; las fixtures dirigen las operaciones HTTP y las migraciones a bases temporales. No se modificó la base de desarrollo.

Desde `frontend/`:

```powershell
npm run lint
npm run build
node --test --test-concurrency=1 tests/reviewTopic.test.mjs tests/roleAccess.test.mjs tests/roleGuard.test.mjs tests/hu04T6Navigation.test.mjs
```

También se ejecutan `git diff --check` y `git diff --cached --check` antes del commit. Los archivos de cada tarea se agregan mediante rutas explícitas.

## Resultados observados

| Comprobación | Resultado |
| --- | --- |
| T1: revisión documental, catálogo, enlaces y casos | 19 ejemplos conservados, enlaces locales existentes, diff sin errores. |
| T2: servicio nuevo, servicio de clasificación y proveedor compartido | 122 aprobadas, 0 fallos, 2 avisos. |
| T3: temas, clasificación HTTP, permisos HU-04 y persistencia común | 143 aprobadas, 0 fallos, 2 avisos. |
| T4: ESLint / Vite build / pruebas frontend pertinentes | Aprobados; 9 pruebas frontend aprobadas. |
| T5: suite completa backend | **674 aprobadas, 0 fallos, 0 omitidas**, 2 avisos, en 249.72 segundos. |
| T5: compileall | Aprobado, sin errores de compilación. |
| T5: ESLint y Vite build | Ambos aprobados. |
| T5: pruebas frontend finales | **12 aprobadas, 0 fallos, 0 omitidas**. |
| Diff del working tree y staging | Sin errores de whitespace ni marcadores de conflicto. |

Los dos avisos de backend corresponden a deprecaciones de Starlette/TestClient con httpx y del alias BlockingPortal de AnyIO. No se cambiaron dependencias para ocultarlos. Las 674 pruebas incluyen 124 casos de HU-15 en los tres archivos backend nuevos y las 550 pruebas existentes.

## Cobertura y significado de la evidencia

| Área | Evidencia | Qué comprueba |
| --- | --- | --- |
| Contrato específico | `test_topic_contracts.py`, `test_topic_service.py` | Cinco etiquetas, rechazo de valores fuera del catálogo, múltiples temas, espacios, tipos incorrectos y propiedades extra; `null` interno no persistible. El contrato compartido sigue aceptando texto libre no vacío para otros consumidores. |
| Ejemplos E01–E19 | `test_documented_example_with_simulated_decision` | Se leen los 19 casos del documento T1 y se inyecta la decisión esperada. Se valida el comportamiento posterior, incluido rechazo sin escritura. El caso vacío no llama al proveedor. |
| Transporte compartido | `test_topic_service.py`, `test_topic_api.py` | `GeminiAdapter` real con `httpx.MockTransport`: JSON inválido, respuesta fuera del catálogo, bloqueo, errores HTTP, timeout, cuota y fallo de conexión. No hay tráfico real a Gemini. |
| Autenticación y roles | `test_topic_api.py` y suites HU-04 existentes | Ausencia de token, admin_general, rol cambiado, usuario/tenant inactivos y claims inconsistentes no eluden el estado vigente en backend. |
| Multi-tenancy | `test_bidirectional_tenant_isolation_for_read_and_detection` | A no lee ni analiza B y viceversa; listados separados; un tenant de query no altera el ámbito; cuerpos con tenant se rechazan antes de IA. |
| Persistencia e independencia | `test_topic_api.py`, `test_ai_persistence.py` | Resultado leído por GET y sesión nueva; se conservan categoría, resumen, prioridad, estado, contenido, fuente, puntuación y demás campos. |
| Concurrencia y rollback | `test_topic_api.py` | Cambio de contenido, traslado de tenant o eliminación durante IA impiden guardar un resultado obsoleto. Cambios concurrentes de categoría/resumen/estado se conservan. Fallo de commit revierte sin exponer detalles internos. |
| Resultados protegidos | `test_topic_api.py` | Captura manual y edición no pueden introducir tema; error IA, no analizable o fallo de almacenamiento conserva el tema previo. |
| Frontend | `reviewTopic.test.mjs` | Presentación de solo lectura, ausencia de tema, acción según permiso, bloqueo durante guardado de estado, cliente HTTP compartido, timeout específico y propagación de fallos sin resultados ficticios ni reintentos. |
| Regresiones | Suite completa y pruebas frontend HU-04 | Se conservan autenticación, permisos, clasificación HU-13 y flujos existentes de reviews, usuarios, importación y dashboard. |

Los 19 casos con mocks **no demuestran que Gemini identifique correctamente sus temas**. Tampoco una salida estructuralmente válida demuestra fidelidad semántica. No se consumió cuota; una evaluación real requeriría autorización y un conjunto representativo revisado por el equipo.

## Comprobación del frontend en navegador durante T4

Se utilizó el navegador integrado con Vite local y FastAPI, una base SQLite temporal y un proveedor sintético. El helper de prueba permanece fuera del repositorio; no se incorporó un modo de prueba al producto. Se verificaron:

- Inicio de sesión con un usuario sintético de tenant y acceso al listado/detalle.
- Tema inicialmente ausente; indicador de carga y botón deshabilitado durante la solicitud.
- Cambio de selección mientras había una solicitud pendiente: su respuesta no se mostró en la nueva review.
- Respuesta simulada no analizable: error recuperable y conservación del resultado previo.
- Resultado persistido y visible al recargar y seleccionar de nuevo la review correspondiente.
- Detalle y controles a 375, 768 y 1280 px. La tabla existente conserva su desplazamiento horizontal interno; no se rediseñó.

La pestaña y los procesos temporales de prueba se cerraron al terminar. Esta comprobación de T4 no es la aceptación funcional completa asignada a T6.

## Límites pendientes

- PostgreSQL no fue ejecutado; se reutiliza su infraestructura existente sin cambios y falta validación operativa.
- Sin evaluación semántica real de Gemini ni garantía de precisión del catálogo.
- La edición de contenido conserva el tema previo según la conducta existente. No se implementó invalidación ni una afirmación de vigencia del análisis anterior.
- No hay filtros por tema, análisis masivo, edición manual, estadísticas ni acciones externas automáticas.
- Pendientes T6 de José, revisión, publicación e integración final según Definition of Done.
