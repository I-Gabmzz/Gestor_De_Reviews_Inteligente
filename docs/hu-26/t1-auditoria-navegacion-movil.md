# HU-26 / T1 #4015 — Auditoría de navegación móvil y accesibilidad

Fecha: 2026-11-09. Alcance: inspección estática del frontend para dejar criterios
verificables a T2–T6. No se implementaron cambios de interfaz ni se ejecutó una
validación visual o en navegador en esta tarea.

## Estado al preparar T1 para commit independiente

- Rama: `feature/HU-26-movil-accesibilidad`, creada desde `origin/main` actualizado.
- SHA base y `HEAD`: `0ee39d42fa18d07b9c64abde72b6b860ac90a5b2`.
- Se ejecutó `git fetch origin --prune`; no existía rama HU-26 local ni remota.
- Los archivos sin seguimiento preexistentes (`Herramientas_de_software_Gabriel.*`,
  `docs/auditoria-sprint-3/`, `docs/metricas/`, `tmp/`) se conservaron intactos.
  Este documento es el único archivo propio de HU-26; no se hizo commit, push,
  PR ni cambio en OpenProject.

## Inventario y comportamiento actual

| Área | Archivos principales | Lo que hace el código hoy |
|---|---|---|
| Rutas, sesión y administración general | `frontend/src/App.jsx`, `frontend/src/components/AdminBusinessPanel.jsx` | Define rutas protegidas e indicador de sesión. `/admin` incluye alta de cuentas de negocio, asignación/pausa de conexión Google Maps y cambio de rol. El panel administrativo usa formularios etiquetados, feedback de estado/error y campos de 48 px; las acciones secundarias declaran mínimo de 44 px. |
| Bandeja, búsqueda, filtros, detalle y edición | `frontend/src/pages/ReviewsPage.jsx`, `frontend/src/components/reviews/ReviewTable.jsx`, `ReviewDetail.jsx`, `ReviewEditForm.jsx`, `ReviewStatusControl.jsx`, `frontend/src/styles/controls.css` | Búsqueda con debounce de 400 ms, filtros de fecha/puntuación/estado/fuente, exportación y detalle en una columna junto a la tabla desde `xl`; por debajo de `xl` el detalle queda después del listado. La fila enfocable abre el detalle con Enter/Espacio o clic. Editar abre un `<dialog>`. |
| Importación CSV/Excel y externa | `frontend/src/pages/ImportReviewsPage.jsx`, `frontend/src/components/ExternalReviewImport.jsx`, `frontend/src/hooks/useExternalReviewImport.js` | CSV/Excel muestra errores y resultado de validación/importación. La sección externa expone carga, indisponibilidad, envío, resultado confirmado e incertidumbre protegida; su operación puede durar varios minutos. |
| Administración de usuarios | `frontend/src/pages/UsersPage.jsx`, `frontend/src/components/users/CreateUserForm.jsx`, `EditUserForm.jsx` | Tabla desplazable en móvil; alta/edición usan diálogos nativos, enfocan el primer campo y restauran el foco al botón que abrió el diálogo. Estados de carga, error, vacío, guardado y cambio de estado están presentes. |
| Estilos compartidos y viewport | `frontend/src/index.css`, `frontend/src/styles/controls.css`, `frontend/index.html` | `body` tiene mínimo de 320 px; controles de formulario pasan a 16 px hasta 639 px; estilo de tablas común. El viewport no declara `viewport-fit=cover`. |

### Hallazgos comprobados en código

1. `ReviewTable` tiene `min-width: 44rem` (704 px) y `UsersPage` fija la tabla a
   `min-w-[50rem]` (800 px), ambas dentro de `overflow-x-auto`. A 320/390 px se
   requiere desplazamiento horizontal dentro de la tabla; las seis columnas de
   reseñas no se reordenan ni colapsan en el código inspeccionado.
2. Las filas de reseña son `<tr tabIndex={0}>` con manejadores de Enter/Espacio y
   `aria-selected`, pero no declaran rol interactivo ni instrucción visible para
   teclado. La activación no desplaza el foco al detalle. El detalle no muestra
   una acción explícita “Volver al listado”.
3. El estado de búsqueda/filtros/selección vive en `ReviewsPage`. Al seleccionar
   una fila permanece en esa página y se conservan los valores; si se abandona la
   ruta y se vuelve, el componente se crea de nuevo y los filtros empiezan vacíos.
   No se conserva el `scrollY` ni la fila enfocada. El parámetro `?review=ID`
   carga un detalle, desplaza y enfoca el panel, pero el efecto asociado limpia
   búsqueda y filtros.
4. El panel de detalle con selección de fila no mueve foco ni scroll. El efecto de
   deep link sí enfoca el `aside` del detalle (`tabIndex=-1`) y usa
   `scrollIntoView`; no hay flujo de retorno equivalente.
5. Objetivos menores de 44 × 44 px visibles por clases: limpiar búsqueda
   (`size-9`, 36 × 36); tabs de análisis (`py-2`, sin altura mínima); cerrar
   diálogos de usuario (`size-9`); acciones Editar/Activar/Desactivar en usuarios
   (`px-2 py-1.5`, sin altura mínima). Varias acciones del detalle usan `py-2`
   sin altura mínima. Los tamaños finales de controles nativos/estilos
   sobrepuestos se deben medir en navegador.
6. Los formularios compartidos fijan font-size móvil a 16 px, pero el selector de
   filtros se define localmente a 14 px y la regla compartida se aplica a los
   controles que no son checkbox/radio/range/submit/button. Verificar en Safari
   si algún control concreto dispara zoom al recibir foco.
7. Los formularios de edición de reseña y usuarios usan `<dialog>` y enfoque
   inicial/restauración nativa o explícita. Debe verificarse con teclado y lector
   de pantalla que Tab queda contenido y Escape/completado restaura el foco
   correcto en los navegadores objetivo.
8. Los estados de carga, vacío/sin coincidencias, error y guardado están
   representados en la bandeja; importación externa diferencia consulta,
   importación, confirmación e incertidumbre. CSV/Excel muestra “Importando…”,
   pero el formulario no declara `aria-busy` ni el mensaje de progreso un rol
   vivo. La consulta de listado tiene texto `aria-live="polite"`; se debe
   comprobar que cambios de carga/resultados se anuncian con claridad.
9. `frontend/index.html` declara `width=device-width, initial-scale=1.0`, no
   restringe zoom y no declara `viewport-fit=cover`. No se encontraron reglas
   globales de foco o tamaño táctil en CSS que subsanen por completo los puntos
   anteriores.

### A validar visualmente/en navegador

- Si el scroll interno de tablas es descubrible con tacto y teclado, y cómo se
  ven columnas, contenido largo y controles a 320/390 px con texto real.
- Contraste y visibilidad del anillo de foco en todos los botones, enlaces,
  selects, diálogos y foco programático del detalle; orden con lector de pantalla.
- Tamaño renderizado de controles, especialmente tabs, botones compactos,
  selector de archivo y controles nativos de fecha/select.
- Comportamiento de diálogo y teclado virtual, safe areas, scroll/retorno, zoom de
  inputs, rotación y navegación atrás en Safari iOS y Chrome Android. El viewport
  no puede declararse correcto para notch/PWA solo por inspección estática.
- El registro previo de HU-21 describe inspección visual del flujo externo a
  390 px con datos sintéticos; no es una comprobación de esta auditoría ni cubre
  el listado, administración, 320 px o dispositivos reales.

## Reglas objetivo verificables

### Vista y retorno listado ↔ detalle

1. En 320 y 390 px, mostrar el listado como vista inicial y el detalle como una
   vista móvil de una sola columna. Al abrir una reseña, el encabezado enfocable
   del detalle recibe foco y queda visible bajo el borde superior; incluir una
   acción “Volver a resultados” antes del contenido del detalle.
2. Al regresar, restaurar exactamente búsqueda, filtros, selección/listado y
   posición vertical del listado. Enfocar la fila que abrió el detalle sin
   desplazarla fuera de pantalla. Si ya no está en resultados, enfocar el
   encabezado del listado y conservar criterios; nunca dejar foco en `body`.
3. Un cambio de datos que quite la fila seleccionada conserva criterios y anuncia
   el nuevo conteo; mover foco al encabezado del listado solo si la pantalla
   activa queda sin destino. En escritorio se puede conservar el panel paralelo.
4. El estado de retorno se mantiene para navegación interna de la misma tarea; una
   recarga o URL compartible debe reconstruir criterios mediante URL o un estado
   documentado. No limpiar criterios al abrir `?review=ID` sin una decisión
   explícita de producto.

### Orden de foco

- Orden de documento, sin `tabIndex` positivo: **notificaciones → Cambiar cuenta
  → enlace principal → Registrar review → Actualizar → búsqueda → Limpiar
  búsqueda (si aparece) →
  Limpiar filtros → Exportar CSV → Desde → Hasta → Puntuación → Estado → Fuente
  → filas en orden visual → control de estado del detalle → pestañas (una sola
  parada; flechas cambian pestaña) → acciones de la pestaña activa → Editar
  review**.
- La fila seleccionada debe exponer nombre/autor, resumen y estado de selección
  a tecnologías asistivas y ser una acción identificable; Enter y Espacio abren
  el mismo detalle que el toque/clic. Flechas entre filas son opcionales solo si
  se implementa un patrón de lista compuesto completo; no mezclarlo con tab-stop
  independiente por fila.
- Al abrir editor: foco inicial en el título o primer campo según patrón
  consistente; Tab permanece en el diálogo, Escape cierra si no hay guardado en
  curso, errores enfocan el primer campo inválido; al cerrar/guardar devolver
  foco al botón “Editar review”. Mantener el comportamiento equivalente para
  alta/edición de usuario y devolver al disparador exacto.
- Anuncios de carga/resultado/guardado/error no deben robar foco. Al producirse
  un error de validación, asociarlo con el campo (`aria-describedby` e
  `aria-invalid`) y enfocar el primer inválido; confirmaciones con `role=status`,
  errores con `role=alert`, y progreso con `aria-busy` más anuncio textual.

### Estados requeridos

| Área | Estados que deben seguir distinguibles y anunciables |
|---|---|
| Listado | Cargando/actualizando; resultados; vacío sin registros; sin coincidencias con criterios; error de consulta con reintento; exportación en progreso, éxito de descarga o error. |
| Detalle | Cargando; sin selección; detalle cargado; error de detalle; guardado de cambios; guardado de estado; éxito/error sin perder contexto del listado. |
| CSV/Excel | Archivo seleccionado; validación; importando; resumen con aceptadas/rechazadas; éxito, parcial/invalidación y error recuperable. |
| Importación externa | Consultando conexiones; sin conexiones/disponibilidad desactivada/no autorizada; importando con acción bloqueada y mensaje de duración; confirmada con conteos; fallo; incierta/reconciliación requerida con reintento bloqueado. |
| Administración | Cargando; lista vacía; error al cargar; diálogo abierto; validación; guardando/actualizando; éxito; error recuperable. |

## Objetivos táctiles ≥ 44 × 44 px

Usar el área de activación completa, no solo el ícono o texto. Confirmar la
medida renderizada de botones compactos y controles nativos en los dos anchos.

| Control | Hallazgo/criterio |
|---|---|
| Filas/acciones de reseña | Activación por fila completa; botones dentro de detalle con área mínima 44 × 44. |
| Limpiar búsqueda | Actual 36 × 36; aumentar hit area a 44 × 44 sin estrechar el campo. |
| Tabs de análisis | Actualmente sin altura mínima; cada tab debe alcanzar 44 px de alto. |
| Actualizar, limpiar filtros, exportar, registrar | Garantizar mínimo 44 × 44 aunque el texto se parta en 320 px. |
| Selector y botones de importación, volver a reviews | Botones externos ya usan `min-h-11`; confirmar ancho mínimo, wrap y separación. Extender mínimo a CSV/Excel y enlaces de navegación. |
| Usuarios: nuevo, editar, activar/desactivar | Alta tiene `min-h-11`; acciones de fila no. Llevar las acciones al menos a 44 × 44 y etiquetar cada control con usuario y acción. |
| Cerrar/cancelar/guardar diálogos | Cerrar de usuario es 36 × 36; garantizar 44 × 44 para cerrar, cancelar y confirmar. |
| Cambiar cuenta/notificaciones/navegación y administración general | Medir controles de cabecera/notificaciones; el panel de administración declara mínimo de 44 px para acciones secundarias y 48 px para acciones principales. Conservar esas áreas al reflujo. |

## Problemas y responsabilidad propuesta

La asignación T2–T6 es una propuesta por área funcional para coordinar el
desarrollo; contrastarla con el desglose de tickets antes de planificar. T1 deja
reglas base y no adelanta implementación.

| Problema | Evidencia | Impacto en móvil/accesibilidad | Task responsable propuesta |
|---|---|---|---|
| Tabla de reseñas de 704 px y tabla de usuarios de 800 px | Clases `min-width`/`min-w` y `overflow-x-auto` | A 320/390 px exige scroll horizontal y reduce descubribilidad de contenido/acciones. | T2: bandeja, lista y filtros; T5: usuarios/administración. |
| Detalle permanece después de la lista; sin retorno/foco en selección de fila | Grid `xl` y ausencia de navegación/handler de foco en selección normal | En teléfono obliga a desplazarse a detalle; contexto y teclado quedan lejos. | T3: detalle y transición/retorno; T6: integración y foco. |
| Filtros/scroll/fila no sobreviven al desmontaje de la ruta; deep link limpia filtros | Estado local de `ReviewsPage`; efecto de `requestedReviewId` | Regresar desde importación/administración pierde continuidad; historial no expresa el estado. | T2: serialización/restauración de bandeja; T3: detalle y retorno. |
| Controles por debajo de 44 px | `size-9`, tabs `py-2`, acciones de usuario `py-1.5` | Toques precisos difíciles y riesgo de activar el objetivo vecino. | T2: controles de listado; T3: detalle; T5: acciones y diálogos admin. |
| Tabla de usuarios solo es desplazable en móvil | Tabla `min-w-[50rem]`; acciones al final | Administración requiere scroll lateral para descubrir acciones. | T5. |
| CSV muestra progreso visual pero sin `aria-busy`/anuncio vivo explícito | Formulario sin `aria-busy`; etiqueta cambia a “Importando…” | Estado puede no anunciarse a lector de pantalla durante espera. | T4: importaciones. |
| Criterios responsive, foco y lector no tienen evidencia en 320 px ni dispositivo | Solo inspección de fuente en T1 | Layout, teclado virtual, safe area y dimensiones CSS reales no quedan confirmados. | T6: matriz y validación de navegador/dispositivo. |

## Matriz de validación

La matriz especifica aceptación futura; **no** indica pruebas ejecutadas en esta
tarea. Revisar en viewport CSS de 320 y 390 px, zoom 100 %, teclado táctil y
teclado físico. Añadir Safari iOS y Chrome Android para cierre de T6.

| Escenario | 320 px | 390 px | Evidencia esperada |
|---|---|---|---|
| Bandeja con datos y texto largo | Sin scroll horizontal de página; navegación/lista entendible; texto parte sin ocultar acciones | Igual; distribución aprovecha ancho y conserva jerarquía | Captura y medida de `scrollWidth` vs `clientWidth`; recorrido touch/teclado. |
| Búsqueda + cinco filtros activos | Campos apilados, etiquetas legibles, ningún botón solapado; limpiar se alcanza con ≥44 px | Igual, sin cortes ni tap targets menores | Captura con búsqueda larga y filtros; estados persistentes. |
| Abrir y volver del detalle | Detalle en vista única; foco/encabezado visible; regreso restaura filtros, scroll y fila | Igual, contenido refluye sin salto inesperado | Grabar foco activo, `scrollY`, valores y fila antes/después. |
| Carga, vacío, sin coincidencias y error de listado | Mensajes completos, reintento táctil accesible y anuncio sin mover foco | Igual | Capturas por estado, árbol accesible/anuncio de lector. |
| Cambiar estado, editar y guardar/error | Diálogo cabe con teclado virtual y scroll interno; botones ≥44 px; foco atrapado/restaurado | Igual; sin zoom inesperado en inputs | Video de apertura, validación, guardar, error y cierre con teclado/lector. |
| Import CSV/Excel | Selector y botón refluye; progreso y resultado no desbordan | Igual | Capturas idle/progreso/éxito/error y anuncio de progreso. |
| Importación externa | Select, refresh e importación son utilizables; texto de varios minutos/estado incierto completo | Igual | Capturas consulta/disponible/en curso/confirmada/incierta/error; no doble envío. |
| Usuarios/administración | Lista y acciones usables sin perder la relación nombre-acción; modal scrollable y controles ≥44 px | Igual | Capturas carga/vacío/error/diálogo/guardado; foco al disparador. |
| Teclado, lector, notch y rotación | Recorrido lógico, foco visible, zoom permitido, sin contenido tras teclado o áreas seguras | Igual | Safari iOS/Chrome Android en dispositivo; portrait, landscape y teclado visible. |

## Archivos y validación de T1

- Creado: `docs/hu-26/t1-auditoria-navegacion-movil.md`.
- Inspección estática de rutas, componentes, clases responsive, estados y
  manejadores de foco en el frontend; verificación de rama, `HEAD`, estado de
  Git y referencia local `origin/main`.
- No se ejecutaron pruebas, build, emulación, navegador, lector de pantalla ni
  dispositivo físico. No se modificó código de producto; los archivos sin
  seguimiento ajenos a T1 se conservaron intactos.
