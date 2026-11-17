# HU-22 · T1 · Bandeja de reseñas

Abre [el prototipo](t1-bandeja.html) en un navegador y usa el selector **Caso de prueba** al pie de la pantalla. Las reseñas son ficticias y las respuestas de carga y guardado se simulan en el navegador.

## Jerarquía y componentes

| Área | Contenido y comportamiento |
| --- | --- |
| Encabezado | Identidad del producto, negocio activo y título «Reseñas». La búsqueda y los filtros aparecen antes de la lista y se mantienen visibles cuando cambia el resultado. |
| Bandeja | Una fila por reseña con autor, extracto de hasta dos líneas, fuente, fecha, puntuación y estado. Usar texto para identificar la urgencia y borde y fondo para distinguir la selección. |
| Detalle | En escritorio, se abre junto al listado. Muestra autor, datos y etiquetas, seguidos por el comentario original completo. El análisis se puede desplegar debajo. Las acciones de seguimiento se agrupan al final. |
| Seguimiento | El estado confirmado aparece junto a los datos de la reseña. Al elegir otro estado, el cambio se confirma con «Guardar estado». La lista y el detalle se actualizan cuando el servidor confirma. |

La tipografía de sistema y las superficies claras mantienen la lectura continua. El botón principal usa azul. El foco de teclado se distingue de la selección de una fila. En espacio estrecho los paneles se apilan. La interacción de regreso desde el detalle móvil se coordina con HU-26.

## Estados

| Caso | Mensaje y acción |
| --- | --- |
| Carga inicial o consulta | «Cargando reseñas…» en la bandeja. Conservar los criterios de consulta. Si carga solo el detalle, conservar el listado y la selección. |
| Negocio vacío | «Aún no hay reseñas». Mantener la estructura y dejar visible el acceso al registro o importación según el rol. |
| Consulta sin resultados | «No encontramos reseñas». Mostrar los criterios usados y ofrecer «Limpiar búsqueda y filtros». Devolver el foco a la búsqueda al limpiar. |
| Error de consulta | «No pudimos cargar las reseñas». Ofrecer «Reintentar» con los mismos criterios. Si falla solo el detalle, el reintento se ofrece ahí. |
| Guardando | «Guardando estado…». Impedir envíos repetidos durante la espera y conservar la etiqueta confirmada. |
| Error de guardado | Explicar que se conserva el estado anterior y permitir reintentar con la opción elegida. Mantener abierto el detalle. |
| Éxito de guardado | «Estado guardado». Anunciarlo junto a la acción y mostrar el estado confirmado en ambos paneles. Mantener el detalle abierto si la reseña queda fuera del filtro tras el cambio. |

## Contratos para la integración

- **HU-23.** «Urgente» se deriva de prioridad alta y estado Nueva o En revisión. La búsqueda cubre comentario, autor y tema. Los controles de consulta deberán compartir criterios con el CSV y coexistir con la apertura directa desde avisos.
- **HU-24.** Mostrar «Sin autor», «Sin fecha» y «Sin puntuación» cuando el dato esté ausente. Mostrar la valoración disponible como «2/5» y la fuente técnica `manual` como «Manual».

## Verificación del prototipo

- En escritorio se comprobó la vista de dos columnas con una reseña de 886 caracteres y tres párrafos completos. El extracto ocupa dos líneas. A 390 px se comprobó que los paneles se apilan y el contenido cabe sin desplazamiento horizontal.
- Se recorrieron los ejemplos de carga, negocio vacío, consulta sin resultados, fallo de lista y detalle, y confirmación.
- El reintento de la lista conservó la búsqueda y el filtro. Al limpiar, reaparecieron las dos reseñas de ejemplo y el foco volvió a la búsqueda. El reintento del detalle recuperó la reseña y llevó el foco a su título.
- Se simuló un fallo al pasar de «En revisión» a «Atendida». La etiqueta anterior se conservó. El segundo intento confirmó «Atendida» y retiró la etiqueta «Urgente».
- Se abrió por teclado una reseña sin datos opcionales y se comprobaron las etiquetas de ausencia.
