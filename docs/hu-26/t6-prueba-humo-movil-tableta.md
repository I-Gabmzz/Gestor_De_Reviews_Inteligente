# HU-26 / T6 · Prueba de humo móvil y tableta

**Ejecución del 16 de noviembre de 2026, hora de Tijuana.** Se verificó el recorrido de bandeja, cambio de estado y vuelta al listado, junto con la regresión de navegación, formularios y accesibilidad. Código evaluado: `6472025ceee9542ce1d7818aa9667f9f14e260b4`, rama `feature/HU-26-movil-accesibilidad`.

## Alcance oficial

La descripción de T6 #4042 indica «Registrar evidencia de bandeja, cambio de estado y vuelta al listado». Al consultar OpenProject estaba en estado `New`, con 2 h estimadas y restantes. Sus predecesoras #4041 (teclado, foco, contraste y movimiento reducido) y #4020 (avisos, descarga y datos de la reseña) estaban cerradas. La predecesora #4025 (indicadores y enlaces a la bandeja filtrada) seguía `In progress`. [T6 #4042 en OpenProject](https://computacion.mxl.uabc.mx/openproject/projects/is20262-gestorreviews/work_packages/4042/relations)

HU-26 #4014 estaba `In progress`. T1 #4015, T2 #4038, T3 #4039, T4 #4040 y T5 #4041 figuraban cerradas. Se aplicaron los siguientes criterios de la historia al recorrido y los formularios de la demostración. [HU-26 #4014 en OpenProject](https://computacion.mxl.uabc.mx/openproject/projects/is20262-gestorreviews/work_packages/4014/relations)

- Operar búsqueda, filtros, reseñas y acciones a 320 y 390 px CSS sin desplazamiento horizontal de página. Mantener una presentación legible en tableta y escritorio.
- Conservar búsqueda, filtros, posición y foco al regresar de una reseña. Si el resultado ya no está disponible en la bandeja, conservar el contexto y devolver el foco al listado.
- Permitir el uso con teclado, con foco visible, nombres claros, estados textuales y respeto por la preferencia de movimiento reducido.
- Mantener objetivos primarios de al menos 44 px, distinguir carga, vacío, sin coincidencias, error y guardado, y evitar envíos duplicados al guardar o importar.

La [auditoría de T1](./t1-auditoria-navegacion-movil.md) se usó para seleccionar comprobaciones adicionales de formularios y dispositivos.

## Entorno y Git

- Windows y Chrome Headless 157.0.8103.51 controlado a través de Chrome DevTools Protocol. Ventanas de 320 × 800, 390 × 844, 768 × 1024 y 1280 × 900 px CSS para el recorrido funcional. La comprobación adicional de dashboard usó altura de 844 px en ambos anchos móviles. 768 px representa una tableta emulada en vertical.
- Frontend compilado con Vite 7.3.6 sobre Node v24.15.0. Para integración real se usó FastAPI con Python 3.14.4, SQLite temporal y un proxy HTTP local para servir la compilación, registrar códigos de respuesta y controlar latencias. Se usaron cuentas y reseñas sintéticas, incluidos tres roles y un negocio vacío. Servicios externos de importación e IA deshabilitados.
- A03 y B02 usan integración real con un HTTP 503 inyectado por el proxy. E01 usa una API totalmente simulada para controlar el recorrido de teclado y los estados de carga. Los demás casos ejecutados usan FastAPI y SQLite. La selección de archivos se ejercitó con archivos sintéticos mediante el navegador.
- El árbol inicial estaba limpio. Después de `git fetch origin`, HEAD, upstream y la consulta directa del remoto coincidían en el SHA evaluado. `origin/main` estaba en `0ee39d42fa18d07b9c64abde72b6b860ac90a5b2`. Respecto de ese punto, la rama de HU-26 tenía cinco commits propios y `origin/main` tenía cero commits exclusivos.

Al cierre, `origin/main` avanzó a `44c7f7bab4891424478c16d648a789118699f0c0` con la integración de HU-25. Incorporó cambios de sesión, acceso y administración. La comparación final daba cinco commits exclusivos por rama. HEAD y upstream de HU-26 siguieron en el SHA evaluado. Conviene repetir autenticación, permisos y formularios de administración al integrar ambas ramas. [Integración de HU-25 en GitHub](https://github.com/I-Gabmzz/Gestor_De_Reviews_Inteligente/pull/42)

## Matriz de humo

Cada combinación de ID y ancho ejecutado cuenta como un caso. A06 cuenta como un caso bloqueado. P01–P05 cuentan como un caso pendiente por entorno o integración. La última columna identifica capturas o registros en la carpeta de evidencias. En los nombres de archivo, `{ancho}` representa el ancho CSS.

| ID | Entorno / ancho | Precondición y pasos | Resultado esperado | Resultado obtenido y estado | Evidencia |
| --- | --- | --- | --- | --- | --- |
| A01 | SQLite · 320, 390, 768, 1280 | Cuenta de negocio con reseñas. Iniciar sesión, abrir dashboard y elegir «Ver todas». | Dashboard y bandeja operables sin desbordamiento de página. | **Aprobado ×4.** Sesión real, tarjetas hasta 768 px y tabla a 1280 px. | `A01-bandeja-{ancho}.png` |
| A02 | SQLite · 320, 390, 768 | Bandeja con texto largo. Buscar «Circuito de humo», filtrar por fuente Google, desplazar, abrir con Enter o Espacio, volver y limpiar. | Detalle visible. Al volver se conservan búsqueda, filtro, posición y foco. Limpiar restablece la consulta. | **Aprobado ×3.** Foco en el encabezado del detalle y luego en la tarjeta de origen. Scroll antes y después: 4816, 3565 y 1790 px, respectivamente. Tarjetas por encima de 44 × 44 px. | `A02-detalle-{ancho}.png`, `A02-retorno-{ancho}.png` |
| A03 | SQLite y 503 inyectado · 320, 390 | Vaciar la búsqueda, consultar una cadena sin coincidencias, forzar fallo de bandeja y elegir «Actualizar». | Carga, sin coincidencias y error distinguibles por texto. El aviso de error recibe foco y el reintento recupera el listado. | **Aprobado ×2.** Se distinguieron los tres estados y funcionó el reintento. | `A03-sin-coincidencias-{ancho}.png`, `A03-error-{ancho}.png` |
| A04 | SQLite · 1280 | Bandeja de escritorio con una reseña seleccionada. Abrir el detalle. | Tabla y detalle legibles y visibles en paralelo. | **Aprobado ×1.** Tabla de 737 px y detalle de 440 px sin desbordamiento de página. | `A04-escritorio-1280.png` |
| A05 | SQLite · 390 | Segunda cuenta en un negocio sin reseñas. Entrar en la bandeja. | El vacío del negocio se distingue de una búsqueda sin coincidencias. | **Aprobado ×1.** Apareció «Todavía no hay reviews» sin desbordamiento. | `A05-bandeja-vacia-390.png` |
| A06 | Rama HU-26 · 390 | Requiere el enlace de un indicador del dashboard de #4025 hacia la bandeja filtrada. | Entrar desde el indicador y encontrar el filtro correspondiente aplicado. | **Bloqueado ×1.** #4025 sigue abierta y el enlace de indicador queda fuera del código evaluado. El acceso general se comprobó en A01. | [Dependencia #4025](https://computacion.mxl.uabc.mx/openproject/projects/is20262-gestorreviews/work_packages/4025) |
| B01 | SQLite · 320, 390, 768 | Como administrador de negocio, filtrar por Nueva, abrir una reseña, elegir En revisión y accionar dos veces el guardado. Confirmar en el detalle y volver. | Un cambio persistido, confirmación textual y retorno al listado conservando Nueva cuando la reseña sale del filtro. | **Aprobado ×3.** Un único PATCH 200 por ejecución. Estado confirmado en el detalle recargado. El foco volvió al listado al salir la tarjeta del filtro. | `B01-estado-{ancho}.png`, `B01-retorno-filtrado-{ancho}.png` |
| B02 | SQLite y 503 inyectado · 320, 390, 768 | Reseña con estado previo conocido. Forzar fallo en el PATCH y solicitar cambio. | Error textual y conservación del estado previo. | **Aprobado ×3.** Aviso visible y valor anterior conservado. | `B02-error-estado-{ancho}.png` |
| C01 | SQLite · 320, 390 | Sesión con permiso de importar. Seleccionar extensión inválida y después un CSV con puntuación 9. | Bloquear la extensión inválida y explicar la fila rechazada por el servidor. | **Aprobado ×2.** La extensión inválida no envió POST. El servidor rechazó la fila y el formulario mostró el error asociado. | `C01-extension-{ancho}.png`, `C01-filas-{ancho}.png` |
| C02 | SQLite · 320 y 390 | Importar CSV a 320 px y XLSX a 390 px con una reseña por archivo. Repetir la acción durante el procesamiento. | Un único POST, procesamiento y resultado visibles, sin desbordamiento horizontal. | **Aprobado ×2.** Una fila guardada de una y un único POST en ambas ejecuciones. | `C02-procesamiento-{ancho}.png`, `C02-resultado-{ancho}.png` |
| D01 | SQLite · 320, 390 | Como administrador de negocio, abrir alta, enviar sin datos, completar, guardar, abrir edición y guardar cambios. | Campo inválido y mensaje asociados, confirmación y retorno del foco desde ambos diálogos. | **Aprobado ×2.** Alta y edición reales, foco restaurado a ambos disparadores y botón de cierre ≥44 × 44 px. | `D01-validacion-{ancho}.png`, `D01-confirmacion-{ancho}.png` |
| D02 | SQLite · 390 | Entrar como administrador general y probar ID de usuario vacío. Intentar abrir bandeja con ese rol y Administración de usuarios con rol usuario de negocio. | Paneles conforme a permisos, error asociado y foco en el campo inválido. | **Aprobado ×1.** Se comprobaron el panel de administración, el error de ID y las restricciones de ambas rutas. | `D02-restriccion-390.png` |
| E01 | API simulada · 320, 390 | Navegar bandeja, detalle, avisos y diálogos con Tab, Shift+Tab, Enter, Espacio y Escape. Alternar la preferencia de movimiento. Medir estilos de foco y contraste. | Orden y retorno de foco utilizables, foco visible, contraste de los elementos medidos y carga de detalle sin pulso con preferencia de reducción. | **Aprobado ×2.** Contorno de foco 7,04:1, borde y placeholder 5,07:1 y pestaña inactiva 6,77:1. El detalle desactivó el pulso al reducir movimiento y lo conservó con la preferencia normal. | `accesibilidad/chrome-mock.log`, `accesibilidad/foco-busqueda-{ancho}.png` |
| E02 | SQLite, latencia controlada · 320, 390 | Activar reducir movimiento antes de iniciar sesión. Retardar 1 s el GET del dashboard y medir el indicador mientras carga. | `animation-name: none` con `prefers-reduced-motion: reduce`. | **Fallido ×2.** Chrome confirmó la preferencia activa y `animation-name: pulse`. | `E02-{ancho}-fallo.png`, `hallazgos-dashboard.jsonl` |
| E03 | SQLite · 320, 390 | Como administrador de negocio, medir Usuarios, Importar reviews y Ver todas en el dashboard cargado. | Cada objetivo ≥44 × 44 px. | **Fallido ×2.** Alturas de 42, 40 y 42 px en ambos tamaños. Anchos de 238 y 308 px, respectivamente. | `E03-{ancho}-fallo.png`, `hallazgos-dashboard.jsonl` |
| P01 | iOS / Safari físico | Requiere iPhone. Recorrer el flujo con tacto, teclado virtual y rotación. | Acciones visibles y retorno del contexto sin interferencias del teclado, zoom o áreas seguras. | **No ejecutado ×1.** Dispositivo fuera del entorno disponible. | Pendiente |
| P02 | Android / Chrome físico | Requiere teléfono Android. Recorrer el flujo con tacto, teclado virtual y rotación. | Acciones visibles y retorno del contexto con entrada táctil y teclado. | **No ejecutado ×1.** Dispositivo fuera del entorno disponible. | Pendiente |
| P03 | Tableta física | Requiere tableta. Comprobar toque, lectura y rotación. | Flujo legible, acciones táctiles utilizables y retorno funcional. | **No ejecutado ×1.** Se comprobó solo la vista de tableta en Chrome emulado. | Pendiente |
| P04 | Lector de pantalla | Requiere lector disponible. Recorrer campos, estados dinámicos, diálogo y retorno. | Anuncios y orden comprensibles durante el recorrido. | **No ejecutado ×1.** La prueba verificó texto, foco y selectores del DOM en Chrome. Queda pendiente comprobar anuncios con tecnología asistiva. | Pendiente |
| P05 | Importación externa en vivo | Requiere una conexión de prueba autorizada. Consultar e importar desde el proveedor. | Estados de consulta, procesamiento y resultado del proveedor comprensibles. | **No ejecutado ×1.** La conexión externa se deshabilitó para la prueba de humo. CSV y XLSX se verificaron con SQLite. | Pendiente |

**Total de humo: 36 casos. 26 aprobados, 4 fallidos, 1 bloqueado y 5 no ejecutados.** Entre los aprobados hay 19 casos de integración real sin fallos inyectados, 5 con HTTP 503 controlado sobre el entorno real y 2 con API simulada. Las 4 comprobaciones fallidas se reproducen en el dashboard de la aplicación con FastAPI. Un fallo repetido en dos anchos cuenta como dos casos y un solo defecto.

## Defectos

| Ref. | Pantalla y reproducción | Severidad e impacto | Corrección mínima propuesta |
| --- | --- | --- | --- |
| T6-01 | Dashboard a 320 y 390 px. Activar «reducir movimiento», abrir el dashboard con una respuesta demorada e inspeccionar el indicador de carga. Sigue pulsando. | Media. Incumple el criterio de movimiento reducido de HU-26. El recorrido de bandeja, cambio de estado y retorno se puede ejecutar. | Limitar las dos animaciones del indicador de carga en `DashboardPage.jsx` con `motion-safe:animate-pulse` y repetir E02 en ambos anchos. |
| T6-02 | Dashboard a 320 y 390 px como administrador de negocio. Medir los enlaces Usuarios, Importar reviews y Ver todas. Resultado: 42, 40 y 42 px de alto. | Media. Incumple el mínimo táctil de HU-26 en las acciones de entrada. Los enlaces siguen siendo operables en la prueba de humo. | Aplicar una altura mínima de 44 px a los tres enlaces en `DashboardPage.jsx`, conservando el reflujo y el foco, y repetir E03. |

Se proponen correcciones puntuales para una revisión de seguimiento. El código del dashboard queda fuera de este cambio de documentación.

## Regresión frontend ejecutada

| Verificación | Resultado |
| --- | --- |
| Suite completa de `tests/*.test.mjs` | **181 aprobadas**, 0 fallidas, 0 omitidas, 0 canceladas. |
| Suite focalizada de formularios HU-26, navegación de reseñas, prioridades y avisos | **42 aprobadas**, 0 fallidas, 0 omitidas, 0 canceladas. Estas pruebas forman parte de la suite completa. |
| `npm run lint` | **Aprobado**, salida 0. |
| `npm run build` | **Aprobado**, salida 0. Compilación Vite con 1773 módulos transformados. |

Para ambas suites se usó `node --no-experimental-global-navigator --test --test-concurrency=1 --test-timeout=20000` con los archivos correspondientes. La integración FastAPI se verificó mediante los flujos de humo. La suite backend completa y PostgreSQL quedaron fuera de esta ejecución.

## Evidencias

Los archivos de ejecución quedaron fuera del repositorio, en `C:/Users/gmanj/Documents/ChatGPT/Gestor Inteligente de Reviews/output/hu26-t6`.

- `casos-sqlite.jsonl` contiene resultados por caso y viewport, capturas asociadas, métodos HTTP y códigos de respuesta. Los fallos simulados están marcados como inyectados.
- `hallazgos-dashboard.jsonl` registra las alturas medidas y el nombre de la animación. Las capturas ilustran el dashboard y el estado de carga. La animación se acredita con el valor CSS registrado.
- `accesibilidad/chrome-mock.log` contiene los resultados del control por teclado y las ratios medidas. Las capturas asociadas muestran el foco visible.
- `regresion/` contiene los dos reportes TAP, las salidas de lint y build y sus códigos de salida.

## Auditoría final

`git status --short` mostró exclusivamente este informe como archivo nuevo sin preparar. Se comprobó `git diff --check` para archivos versionados y se revisaron directamente los espacios finales del informe nuevo. La revisión del archivo no encontró credenciales ni claves. Capturas, registros y datos sintéticos se mantuvieron fuera del repositorio. El índice quedó vacío y la rama local siguió en el mismo SHA que su upstream.

## Conclusión de aceptación

La evidencia específica solicitada por T6 está reunida: bandeja operable, cambio de estado persistido y vuelta al listado con contexto en 320, 390 y 768 px emulados. El recorrido principal de T6 pasó. Para dar por cumplida la Definition of Done de cierre integral quedan #4025, los dos criterios fallidos del dashboard y la validación pendiente en dispositivos físicos y lector de pantalla. La validación en escritorio cubrió la disposición del listado y el detalle.

Se recomienda aprobar el informe para un commit documental cuando se autorice, mantener el cierre de HU-26 pendiente y repetir los casos afectados después de resolver #4025 y los defectos. La publicación y los estados de OpenProject quedan fuera de esta ejecución.


## Revalidación del 17 de noviembre de 2026

Esta sección registra una segunda ejecución. La matriz y los resultados anteriores corresponden al 16 de noviembre y se conservan como historial. La nueva ejecución usó el mismo HEAD con las dos correcciones locales, Chrome Headless 157.0.8103.79, Node v24.15.0, Vite 7.3.6 y FastAPI con Python 3.14.4 y SQLite temporal. Se usaron datos sintéticos y se separó el recorrido con API simulada de la integración real.

### Correcciones y repetición de los casos fallidos

- **D1 / T6-01.** Los dos tipos de marcador de carga usaban `animate-pulse` sin condición. Se cambió esa clase a `motion-safe:animate-pulse`. Se conservaron los cuatro marcadores, sus dimensiones y el estado accesible «Cargando dashboard».
- **D2 / T6-02.** La altura de Usuarios, Importar reviews y Ver todas dependía del texto, relleno y borde, lo que daba 40–42 px. Se añadió `min-h-11` a esos tres enlaces para darles 44 px de altura mínima, con el mismo diseño, orden y destinos.
- Se añadieron dos pruebas automatizadas a `frontend/tests/hu26Forms.integration.test.mjs`. Ambas detectaron los defectos en el código previo y pasaron tras la corrección. Comprueban los marcadores visibles y la clase condicionada, así como los tres enlaces con su altura mínima. La animación y el tamaño calculados se verificaron además en Chrome sobre la compilación de producción.

| Caso | Antes | Después | Evidencia nueva |
| --- | --- | --- | --- |
| E02 · 320 px | Fallido. Pulso activo con `reduce`. | **Aprobado.** Cuatro marcadores visibles con `animation-name: none` bajo `reduce` y `pulse` bajo `no-preference`. | `E02-320-reduce.png`, `E02-320-no-preference.png` |
| E02 · 390 px | Fallido. Pulso activo con `reduce`. | **Aprobado.** Cuatro marcadores visibles con `animation-name: none` bajo `reduce` y `pulse` bajo `no-preference`. | `E02-390-reduce.png`, `E02-390-no-preference.png` |
| E03 · 320 px | Fallido. Alturas de 42, 40 y 42 px. | **Aprobado.** Los tres enlaces miden 238 × 44 px. | `E03-320-objetivos.png` |
| E03 · 390 px | Fallido. Alturas de 42, 40 y 42 px. | **Aprobado.** Los tres enlaces miden 308 × 44 px. | `E03-390-objetivos.png` |

En los cuatro anchos, los puntos a 1 px de los bordes superior e inferior y el centro detectaron el enlace correspondiente. Las comprobaciones adicionales de E03 a **768 y 1280 px** también pasaron. En ambos anchos, Usuarios midió 128 × 44 px, Importar reviews 183 × 44 px y Ver todas 132 × 44 px. La página mantuvo `scrollWidth` igual a `clientWidth` en las cuatro mediciones. Las dos comprobaciones adicionales se registraron fuera de los 36 casos originales.

### Matriz y regresión después de la corrección

| Ejecución | Aprobados | Fallidos | Bloqueados | No ejecutados |
| --- | ---: | ---: | ---: | ---: |
| 16 de noviembre, matriz original | 26 | 4 | 1 | 5 |
| 17 de noviembre, misma matriz | 30 | 0 | 1 | 5 |

Volvieron a pasar los 26 casos ya aprobados. Se repitieron 24 casos con FastAPI y SQLite, incluidos los cinco escenarios con 503 inyectado para comprobar manejo de fallos, y los dos casos E01 con API simulada. Los cuatro casos que antes fallaban pasaron tras la corrección.

| Verificación | Resultado del 17 de noviembre |
| --- | --- |
| Suite frontend completa | **183 aprobadas**, 0 fallidas, 0 omitidas y 0 canceladas. |
| Suite focalizada de HU-26, navegación, prioridades y avisos | **44 aprobadas**, 0 fallidas, 0 omitidas y 0 canceladas. Incluye las dos pruebas nuevas y forma parte de la suite completa. |
| `npm run lint` | **Aprobado**, salida 0. |
| `npm run build` | **Aprobado**, salida 0, 1773 módulos transformados. |

Se volvió a usar `--no-experimental-global-navigator` con Node 24. Los recorridos con SQLite cubrieron la integración necesaria de FastAPI.

Las nuevas evidencias están en la subcarpeta `revalidacion-2026-11-17/` de la carpeta original. `revalidacion-dashboard.jsonl` contiene preferencias y valores CSS calculados, las dimensiones de los enlaces y las comprobaciones del área interactiva. `casos-sqlite.jsonl` contiene los 24 casos repetidos, `accesibilidad/chrome-mock.log` los dos recorridos con API simulada y `regresion/` las salidas frontend. Las capturas y registros del 16 de noviembre siguen en su ubicación original.

### Dependencia, integración y criterio de cierre

OpenProject muestra #4025 como **Closed**. La tarea integra indicadores del dashboard con enlaces al listado filtrado y pide verificar que el dashboard se actualice después de guardar un estado. El commit de los enlaces, `d422fde`, está en la rama remota de HU-23 y queda fuera de HU-26 y de `origin/main`. **A06 sigue bloqueado en la rama evaluada.** Cuando se integre, repetir a 390 px la entrada desde indicadores de estado o urgencia, comprobar que URL y bandeja reflejen el filtro y verificar los indicadores al volver al dashboard después de cambiar el estado. [Dependencia #4025 en OpenProject](https://computacion.mxl.uabc.mx/openproject/projects/is20262-gestorreviews/work_packages/4025) · [Commit de integración de indicadores](https://github.com/I-Gabmzz/Gestor_De_Reviews_Inteligente/commit/d422fde)

`origin/main` continúa en `44c7f7bab4891424478c16d648a789118699f0c0`, con la integración de HU-25. Ambas ramas tienen cinco commits exclusivos. Al integrar, repetir autenticación y salida, acceso por rol y administración. La desactivación de negocios y la invalidación de sesiones de HU-25 inciden en las precondiciones de esos recorridos. HU-23 también cambia `DashboardPage.jsx`, por lo que se deben repetir E02 y E03 al integrar los indicadores. [Integración de HU-25 en GitHub](https://github.com/I-Gabmzz/Gestor_De_Reviews_Inteligente/pull/42)

El objetivo principal de T6 está acreditado y los dos defectos de accesibilidad quedaron corregidos en la ejecución local. El cierre integral conserva A06 y los cinco casos fuera del entorno disponible (iOS, Android, tableta física, lector de pantalla e importación externa en vivo). Los cambios locales se limitan al componente del dashboard, las pruebas de HU-26 y esta ampliación del informe. El índice quedó vacío.
