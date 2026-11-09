# HU-23 #4011 / T1 #4022 — Contrato de urgencia, búsqueda y métricas

Sprint 4 · Responsable: Diego Erik Alfonso Montoya · Estimación: 2 horas.
Base inspeccionada: `0ee39d42fa18d07b9c64abde72b6b860ac90a5b2`.

**Estado: documento preparatorio para revisión del equipo.** Las reglas funcionales se toman del encargo de T1 y de `sprint-backlog-4.md` adjunto, que es un plan local. Se contrastó `t1-contrato-datos-opcionales.md` de HU-24/T1 como propuesta. Los adjuntos se usaron como referencias de requisitos; no acreditan implementación, entrega, aprobación ni cierre en OpenProject.

## Objetivo y límites

El usuario de negocio puede consultar su avance desde el dashboard y abrir la bandeja con un conjunto de filtros visible. Los indicadores, la lista y el CSV se calculan sobre el negocio autenticado. T1 solo define el contrato: T2 amplía la consulta; T3 agrega métricas; T4 integra la navegación; T5 valida el recorrido, la paridad CSV y el volumen.

## Base existente comprobada

| Área | Estado en la base inspeccionada |
| --- | --- |
| Dashboard | [Router](../../backend/app/api/routers/dashboard.py), [servicio](../../backend/app/services/dashboard_service.py) y [schema](../../backend/app/schemas/dashboard.py) de `GET /api/v1/dashboard`: `nombre_negocio`, `total_reviews`, `promedio_puntuacion`, `reviews_nuevas` y `reviews_recientes` (hasta cinco). El [repositorio](../../backend/app/repositories/review_repository.py) usa conteo de filas, SQL AVG, conteo de nuevas y orden por fecha e ID descendentes. |
| Consulta | [Router de reseñas](../../backend/app/api/routers/reviews.py) y [ReviewService](../../backend/app/services/review_service.py) reciben `busqueda`, `fecha_desde`, `fecha_hasta`, `puntuacion`, `estado` y `fuente`. El [contrato HU-10](../api/hu-10-busqueda-filtros.md) y el código buscan solo en contenido, con `icontains(..., autoescape=True)`; autor, tema y Urgente son ampliaciones. |
| CSV | `GET /api/v1/reviews/export` usa la misma consulta de listado y [serialize_reviews_csv](../../backend/app/services/review_export_service.py). Conserva el formato de [HU-19](../hu-19/contrato-csv.md). |
| Interfaz | [DashboardPage](../../frontend/src/pages/DashboardPage.jsx) consulta `getDashboard` por el cliente HTTP común y enlaza a la bandeja general. [ReviewsPage](../../frontend/src/pages/ReviewsPage.jsx) contiene los controles de búsqueda y filtros; `useSearchParams` lee `?review=` para el detalle y hoy reinicia los filtros al procesar ese acceso directo. Los criterios de búsqueda/filtros viven en estado local. [La API cliente](../../frontend/src/api/reviews.js) usa `reviewParams` tanto para listado como CSV; la exportación recibe `listedCriteria`, los criterios del último listado cargado correctamente. |
| IA y autorización | [Review](../../backend/app/models/review.py) guarda `tema` y `prioridad`, ambos anulables. [Los resultados de IA](../../backend/app/schemas/ai.py) usan `Baja`, `Media` y `Alta`. Dashboard, lista y CSV usan [require_tenant_roles](../../backend/app/api/dependencies.py) para `usuario_negocio` y `admin_tenant` en un negocio activo. El tenant se resuelve en el servidor; un valor enviado por el cliente no cambia ese ámbito. |

La cobertura existente incluye [dashboard](../../backend/tests/test_dashboard.py), [listado](../../backend/tests/test_reviews_api.py), [CSV](../../backend/tests/test_review_export_api.py) y [exportación desde React](../../frontend/tests/reviewExport.integration.test.mjs). No demuestra el comportamiento nuevo de HU-23.

## Urgencia y consulta

**Regla confirmada:** una reseña del tenant autenticado es Urgente si `prioridad == "Alta"` **y** `estado` pertenece a `{"nueva", "en_revision"}`. Urgente es un criterio derivado, no un cuarto estado ni un dato persistido. Alta + Atendida, Media + Nueva y prioridad ausente no son urgentes. La bandeja, el contador, el CSV y el enlace del dashboard aplican la misma regla. Al confirmar un estado y volver al dashboard, se vuelven a consultar las métricas: una urgente atendida deja de contarse como urgente.

**Búsqueda confirmada:** consultar contenido, autor y tema detectado dentro del negocio autenticado. **Propuesta de T1:** ampliar `busqueda` para encontrar el término completo como subcadena en **cualquiera** de los tres campos (OR); aplicar los demás filtros y el tenant como **intersección** (AND). Una fila coincidente en varios campos se cuenta y exporta una sola vez.

- Conservar el recorte de espacios exteriores, el texto interno y la coincidencia parcial sin distinguir mayúsculas según las reglas actuales. Una cadena vacía o solo espacios equivale a omitir el filtro. Autor y tema NULL no aportan coincidencia, pero no impiden que otro campo coincida.
- Escapar `%` y `_` como literales, con parámetros vinculados. Codificar en URL los caracteres reservados; por ejemplo, el literal `%` se transmite como `%25`. No añadir búsqueda semántica, tokenización, ranking ni equivalencia entre letras con y sin tilde. Comprobar las variantes de mayúsculas Unicode en ambos motores antes de comprometer una equivalencia uniforme.
- El OR amplía deliberadamente la cobertura de HU-10 y, por tanto, puede devolver más filas con el mismo término. Validar esta ampliación y la compatibilidad de los consumidores con el equipo; no reinterpretar los otros filtros.

| Criterio | Contrato |
| --- | --- |
| Texto | `busqueda` conserva las reglas anteriores y amplía los campos según la propuesta. |
| Fecha | `fecha_desde` y `fecha_hasta` aceptan `YYYY-MM-DD`, con límites por día inclusivos y cualquiera de los extremos opcional. Fechas inválidas o rango invertido: HTTP 422. |
| Puntuación | `puntuacion`: entero de 1 a 5, igualdad exacta. Fracciones y valores fuera del rango: HTTP 422. |
| Estado | `estado`: `nueva`, `en_revision` o `atendida`. Etiquetas visuales: Nueva, En revisión y Atendida. Otro valor: HTTP 422. |
| Fuente | `fuente`: texto recortado e igualdad exacta, incluida capitalización; vacío equivale a omitir. Una fuente válida sin coincidencias no es error. |
| Prioridad pendiente / Urgente | **Propuesta HTTP sin implementar:** `urgente=true` activa el criterio. Omitido o `false` no restringe; `false` no significa «solo no urgentes». Aceptar únicamente los literales `true` y `false`; vacío u otro valor explícito: HTTP 422. El cliente omite el parámetro cuando el control está inactivo. No se propone un filtro general de prioridad en T1. |

Con la intersección propuesta, Urgente + Nueva conserva solo urgentes nuevas, Urgente + En revisión conserva solo urgentes en revisión y Urgente + Atendida devuelve cero resultados. Puntuación, fuente y texto reducen ese mismo conjunto. No se cambia ni se borra un filtro por seleccionar otro. Una consulta válida sin coincidencias devuelve HTTP 200 con `items: []`, `total: 0`; el CSV conserva encabezados sin filas. Mantener HTTP 401 sin autenticación válida, HTTP 403 sin rol o tenant autorizado y HTTP 422 para criterios inválidos.

## Métricas y navegación

Las métricas del dashboard se calculan sobre **todo el tenant autenticado**, independientemente de los filtros de la bandeja. El total y los conteos Nueva, En revisión y Atendida incluyen reseñas sin puntuación. El promedio divide la suma de puntuaciones presentes entre el número de reseñas puntuadas; si no hay ninguna, es `null` y se muestra «Sin puntuaciones». La distribución devuelve cinco casillas ordenadas del 1 al 5 y cuenta solo puntuaciones presentes. Urgentes cuenta filas que cumplen la regla, con o sin puntuación. Un negocio vacío tiene total, estados, urgentes y las cinco casillas en cero, con promedio nulo. Una puntuación ausente no se convierte en cero.

**Propuesta de salida para T3:** conservar el endpoint y los campos vigentes, y agregar `reviews_en_revision`, `reviews_atendidas`, `reviews_urgentes` (enteros), y `distribucion_puntuaciones` como lista de cinco objetos con `puntuacion` y `total` enteros. Los nombres y la forma quedan para revisión; no son campos disponibles hoy. El promedio numérico no se redondea para calcular otros indicadores; el dashboard puede conservar su presentación a un decimal.

| Indicador | URL propuesta desde el dashboard | Filtro visible al abrir |
| --- | --- | --- |
| Total | `/reviews` | Ninguno |
| Nueva | `/reviews?estado=nueva` | Nueva |
| En revisión | `/reviews?estado=en_revision` | En revisión |
| Atendida | `/reviews?estado=atendida` | Atendida |
| Urgentes | `/reviews?urgente=true` | Urgente, sin estado adicional |

**Propuesta para T4/HU-22:** reutilizar `useSearchParams` con los nombres de consulta aprobados, para hidratar controles y listado al abrir, recargar o volver. Los enlaces del dashboard parten del criterio del indicador, sin heredar filtros previos. Limpiar todos los criterios quita texto y filtros de la URL y muestra el listado completo del negocio; no equivale a cambiar el tenant. Un criterio explícito inválido no debe convertirse silenciosamente en una consulta amplia.

`review` queda reservado al acceso directo al detalle, no es un filtro de listado ni de CSV. El acceso desde avisos con `?review=` debe seguir funcionando con autorización del servidor. Si la URL combina filtros y `review`, la propuesta es respetar los filtros y abrir el detalle autorizado sin agregar artificialmente esa fila al conjunto listado/exportado. Un detalle ajeno o inexistente conserva el rechazo existente. Coordinar el cambio con HU-22: hoy procesar `review` limpia criterios; la coexistencia propuesta aún no existe. Limpiar criterios no necesita borrar la selección explícita de detalle.

## CSV y compatibilidad con HU-24

El CSV debe contener todas las coincidencias de los criterios aplicados al listado, con el mismo orden y alcance por tenant. Compartir normalización, validación y consulta para búsqueda, fechas, puntuación, estado, fuente y Urgente; no depender de la fila abierta. Mantener encabezados `id,contenido,autor,fecha,fuente,puntuacion,categoria,estado`, UTF-8 con BOM, coma, CRLF, escapado y neutralización de fórmulas de HU-19. No añadir columnas de prioridad, tema ni tenant para filtrar por ellos.

| Tema | Requisito Sprint 4 y efecto futuro | Estado actual / decisión pendiente |
| --- | --- | --- |
| Autor ausente | Sigue en el conjunto; no inventar un nombre para buscar. «Sin autor» es una etiqueta visual, no texto indexado; CSV vacío. | El modelo ya admite NULL. |
| Fecha ausente | Sin intervalo se incluye; con cualquier extremo se excluye. No sustituir por fecha actual. | Modelo y lectura todavía exigen fecha. Revisar `fecha_hasta=9999-12-31`: hoy se omite la cota superior y habrá que excluir NULL explícitamente aun en ese caso. La propuesta HU-24 de fechas conocidas DESC, nulos al final e `id DESC` como desempate requiere ratificación y paridad lista/recientes/CSV en ambos motores. |
| Puntuación ausente | Cuenta en total, estados y urgencia; no en promedio, estrellas ni filtro de puntuación exacta. CSV vacío. | Modelo y lectura todavía exigen puntuación. SQL AVG ya ignora NULL y puede devolver nulo, pero esto no habilita persistencia opcional. Revisar presentación: el dashboard hoy puede convertir ausencia en `0/5`. |
| Fuente manual | La ausencia de fuente en alta manual se representa como Manual según el requisito. Conservar fuentes externas e históricas. | El alta actual fija `manual` y el filtro es exacto. HU-24 propone `manual` técnico y «Manual» visual; ratificarlo, incluido el tratamiento de fuente explícita, antes de normalizar valores. |

HU-24 propone SQL NULL, JSON `null`, celdas CSV vacías y etiquetas «Sin fecha» y «Sin puntuación» para los valores ausentes. La persistencia y lectura de fecha/puntuación NULL requieren HU-24. Coordinar celdas vacías con HU-19: el exportador llama hoy a `fecha.isoformat()` y el detalle/edición también presuponen fecha en algunos puntos. No ampliar las reglas de ingesta CSV/XLSX ni prometer reimportación de un CSV con ausencias. Los ejemplos con fecha o puntuación ausentes se validarán sobre datos persistidos solo cuando el esquema y los consumidores correspondientes los soporten.

## Matriz sintética para David y José

Expectativas contractuales, **no resultados de pruebas ejecutadas**. `—` indica ausencia, no un valor literal. Las fechas representan días de noviembre de 2026. Comparar membresía por ID y, en cada consulta, comprobar que el CSV sigue el orden efectivo del listado. Ninguna fila de B participa al consultar A.

| ID | Tenant | Autor | Contenido | Tema | Fecha | Puntuación | Prioridad | Estado | Fuente |
| --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| 101 | A | Ana | Entrega puntual | Envío | 2026-11-09 | 5 | Alta | nueva | Google |
| 102 | A | Bruno | Servicio lento | Atención | 2026-11-08 | 3 | Alta | en_revision | manual |
| 103 | A | Carla | Gracias | Envío | 2026-11-07 | 4 | Alta | atendida | Google |
| 104 | A | — | Empaque del envío 100% | — | 2026-11-06 | 2 | Media | nueva | CSV |
| 105 | A | Ana | Consulta | Atención | — | — | Baja | en_revision | manual |
| 106 | A | Eva | Demora en atención | — | 2026-11-05 | 1 | — | atendida | Google |
| 201 | B | Ana | Entrega puntual | Envío | 2026-11-09 | 4 | Alta | nueva | Google |
| 202 | B | — | Atención lenta | — | — | — | Alta | en_revision | manual |
| 203 | B | Luis | Revisión | Atención | 2026-11-08 | — | Media | atendida | CSV |

| Conjunto del dashboard | Total | Nueva | En revisión | Atendida | Urgentes | Promedio | Distribución 1, 2, 3, 4, 5 |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| A | 6 | 2 | 2 | 2 | 2 (101, 102) | (5+3+4+2+1)/5 = 3 | 1, 1, 1, 1, 1 |
| B | 3 | 1 | 1 | 1 | 2 (201, 202) | 4/1 = 4 | 0, 0, 0, 1, 0 |
| Negocio vacío, escenario independiente | 0 | 0 | 0 | 0 | 0 | null | 0, 0, 0, 0, 0 |
| Negocio sin puntuaciones, escenario independiente con solo las filas 202 y 203 | 2 | 0 | 1 | 1 | 1 (202) | null | 0, 0, 0, 0, 0 |

| Tenant autenticado | Criterios | IDs del listado | Filas CSV sin encabezado |
| --- | --- | --- | ---: |
| A | Sin filtros o después de limpiar todos | 101, 102, 103, 104, 105, 106 | 6 |
| A | `busqueda=ana` (autor) | 101, 105 | 2 |
| A | `busqueda=envío` (tema o contenido) | 101, 103, 104 | 3 |
| A | `busqueda=ATENCIÓN` (tema o contenido) | 102, 105, 106 | 3 |
| A | `busqueda=%25` en URL (literal %) | 104 | 1 |
| A | `urgente=true` | 101, 102 | 2 |
| A | `urgente=true&estado=nueva` | 101 | 1 |
| A | `urgente=true&estado=en_revision` | 102 | 1 |
| A | `urgente=true&estado=atendida` | Ninguno | 0 |
| A | `urgente=true&puntuacion=3` | 102 | 1 |
| A | `urgente=true&fuente=Google` | 101 | 1 |
| A | `urgente=true&busqueda=ENVÍO` | 101 | 1 |
| A | `fecha_desde=2026-11-07&fecha_hasta=2026-11-08` | 102, 103 | 2 |
| A | `fecha_hasta=9999-12-31` | 101, 102, 103, 104, 106 | 5 |
| B | `urgente=true` | 201, 202 | 2 |
| B | `busqueda=ana` | 201 | 1 |

Al guardar 101 como Atendida y volver al dashboard de A: total 6, Nueva 1, En revisión 2, Atendida 3, una urgente (102), promedio 3 y las cinco casillas sin cambios. El enlace Urgentes y el CSV con ese filtro deben mostrar solo 102; B conserva sus cifras.

## Dependencias y entregables para otras HUs

- **David Escárcega · HU-22:** revisar etiquetas visibles, URLs propuestas, combinación por intersección, limpieza y coexistencia con el acceso desde avisos. Usar los ejemplos de indicadores de A y el cambio de 101 para validar la bandeja. HU-22/22.3 consume T2 de HU-23; T4 de HU-23 consume esa bandeja y las métricas de T3. La bandeja actual existe, pero su adaptación de Sprint 4 no se presume disponible.
- **José Suffo · HU-24:** revisar el OR de los tres campos, urgencia, filtros compartidos y paridad de IDs, orden y filas CSV. Confirmar nulos, fuente y orden con HU-24/T1 y HU-19; usar 104, 105 y 202 como casos de ausencias. T3 de HU-23 depende de T1 y HU-24/24.1; la verificación con nulos persistidos requiere su implementación. T5 depende de T4 y la comprobación de paridad HU-24/24.4.
- **Gabriel Manjarrez · HU-26:** necesitará los criterios visibles, su representación en URL, los enlaces del dashboard y la acción de limpieza. Al volver de un detalle móvil conservar búsqueda, filtros, posición y foco cuando la fila siga visible; si salió de Urgentes tras el guardado, devolver el foco al listado o al control del filtro. Coordinar con David sobre la misma bandeja.

**Pendientes para revisión:** ratificar OR, literal `urgente`, forma de métricas y navegación combinada con `review`; acordar orden de NULL, representación de fuente y compatibilidad de lectura/exportación con HU-24. Para T5, medir y registrar la respuesta del listado con 500 reseñas por negocio, búsqueda más filtro combinado y entorno identificado; el plan no fija un umbral ni exige implementar paginación en T1.

La matriz y los ejemplos quedan preparados para compartir. No se acredita recepción, aprobación ni cierre administrativo. En T1 no se ejecutan pruebas de producto ni mediciones porque no cambia código.
