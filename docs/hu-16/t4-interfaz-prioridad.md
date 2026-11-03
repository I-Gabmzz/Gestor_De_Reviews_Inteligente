# HU-16 / T4 #3808: mostrar prioridad y Alta

Responsable: David Escárcega Schlemmer.
[Tarea #3808](https://computacion.mxl.uabc.mx/openproject/work_packages/3808).

## Comportamiento

El detalle de la review incorpora una pestaña **Prioridad** junto a Clasificación,
Resumen y Tema. Muestra el valor guardado y una acción explícita para determinarlo
o actualizarlo. No existe un selector ni entrada editable para la prioridad.
El resultado se presenta como generado por IA y de solo lectura.

Alta se identifica mediante texto, icono y una marca de color discreta, tanto en
el detalle como junto al autor en la tabla. No se añade una columna ni un panel
vertical permanente. En pantallas estrechas las cuatro pestañas se distribuyen
en dos filas; en el resto se mantienen en una fila. La navegación con flechas,
Home y End conserva un único panel visible y sus asociaciones accesibles.

La acción solo aparece con sesión de `usuario_negocio` o `admin_tenant` y tenant
definido. El backend sigue siendo la autoridad sobre permisos. El cliente envía
POST a `/reviews/{id}/prioridad` sin contenido, tenant ni prioridad elegidos por
el usuario, con Bearer, cancelación y tiempo de espera específico de la operación.

## Carga, errores y cambios de selección

Durante la petición se muestran carga y un indicador en la pestaña. Se impiden
dobles envíos y se bloquean los otros análisis, la edición y el cambio de estado.
Cambiar de pestaña conserva la operación pendiente; cambiar de review, tenant,
contenido o desmontar el detalle cancela la espera local y descarta respuestas
tardías. Cancelar la espera no garantiza que una llamada ya recibida por el
servidor se detenga; se puede actualizar la lista para consultar el resultado.

Antes de aplicar una respuesta se comprueban ID, tenant, contenido y pertenencia
de la prioridad al contrato exacto Baja/Media/Alta. Solo se actualiza `prioridad`
en el detalle y en la fila correspondiente; se conservan cambios concurrentes de
estado, categoría y los demás campos. Al recargar se muestra el valor persistido
por la operación de T3.

Los mensajes de error traducen autenticación, permisos, conflicto, contenido,
cuota, indisponibilidad y timeout sin mostrar detalles internos. No hay reintento
automático y un error conserva la prioridad anterior.

## Verificación y límites

Validación local del 25 de octubre de 2026: pasaron las 51 pruebas frontend,
incluidas nueve nuevas de prioridad, lint y compilación de producción. Las pruebas
usan componentes, hook y cliente HTTP reales con respuestas simuladas: cubren
generación, regeneración, persistencia al recibir datos nuevamente, carga,
cancelación, respuesta tardía, bloqueo, errores, permisos, actualización de un solo
campo y marca accesible de Alta en la tabla. La navegación de las cuatro pestañas
también está cubierta por la prueba de teclado existente actualizada.

La web local se inspeccionó con una sesión de administrador de negocio: se
comprobó la presencia de la pestaña, el estado sin determinar y la acción. Esta
comprobación visual no ejecutó una generación con el proveedor externo.

El backend de T3 conserva sus 839 pruebas aprobadas. La muestra real del proveedor,
regresión integrada final y aceptación de la demo corresponden a #3809. No se
generan notificaciones de HU-20 por mostrar o actualizar esta interfaz.
