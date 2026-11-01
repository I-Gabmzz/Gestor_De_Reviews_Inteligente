# HU-20 / T1 #3826: regla de aviso

Responsable: David Escárcega Schlemmer, Product Owner y desarrollador asignado.
[Historia #3234](https://computacion.mxl.uabc.mx/openproject/work_packages/3234),
[tarea #3826](https://computacion.mxl.uabc.mx/openproject/work_packages/3826).
Definición: 1 de noviembre de 2026, America/Tijuana.

## Alcance de la primera versión

Se adopta la propuesta de aviso interno indicada al continuar HU-20: al guardar
una prioridad Alta válida de HU-16, mostrar un aviso a usuarios de negocio y
administradores del mismo tenant, sin duplicarlo al regenerar y sin cambiar el
estado de seguimiento. Los criterios vigentes de OpenProject admiten que esta
primera versión funcione únicamente dentro de la plataforma.

El aviso pertenece al negocio y es compartido por sus usuarios autorizados. No
es una bandeja individual de mensajes no leídos; el contador identifica reviews
con un aviso de prioridad Alta vigente. No incluye correo, notificaciones push,
envíos externos ni cambios en permisos o estado de la review.

## Matriz de eventos y destinatarios

| Situación | Comportamiento |
| --- | --- |
| HU-16 guarda Alta válida para una review propia | Guardar prioridad y aviso en una misma transacción. |
| El proveedor propone Alta pero falla el guardado o hay conflicto de contenido | No crear aviso ni sustituir la prioridad anterior. |
| Prioridad Media, Baja, rechazo, timeout o salida inválida | No crear aviso. |
| Regenerar Alta varias veces, incluso con solicitudes concurrentes | Conservar un único aviso y su fecha original por review y negocio. |
| Alta pasa a Media/Baja | Conservar el registro del evento, ocultarlo de los avisos vigentes. |
| La misma review vuelve a Alta | Mostrar el mismo aviso, sin crear otro ni cambiar su fecha. |
| Review eliminada o movida a otro tenant | No mostrar sus datos en el negocio anterior. Resolver siempre el ámbito actual al consultar. |
| Alta anterior a HU-20, sin evento nuevo de guardado | No fabricar avisos retroactivos al iniciar ni durante una consulta GET. |
| Usuario de negocio o administrador de tenant activos | Consultar únicamente avisos y reviews de su tenant activo. |
| Administrador general, usuario inactivo o tenant inactivo | Acceso denegado. |
| Visitar un aviso | Abrir la review correspondiente; no cambiar su estado. |

## Contrato y conservación

- La aplicación crea los avisos internamente; el navegador no envía tenant,
  destinatarios, prioridad ni texto del aviso para crear uno.
- Cada evento contiene ID, review, tenant y fecha de creación UTC. La restricción
  de unicidad se aplica en la base de datos a `(tenant_id, review_id)`.
- La lista consulta también la review actual, exige pertenencia al mismo tenant
  y prioridad Alta y muestra autor y un extracto breve. No conserva copias de
  comentarios que puedan quedar obsoletas ni devuelve reviews ajenas.
- La lectura es paginada y devuelve el total vigente para el contador. El enlace
  solo transporta el ID de review; el backend vuelve a comprobar autorización
  al abrir el detalle. No se confía en un tenant enviado por URL.
- No se eliminan avisos al regenerar, no se registra una hora nueva para simular
  otro evento y no se sustituyen resultados de categoría, resumen o tema.
- Si falla la creación del aviso, se revierte también el nuevo guardado de Alta;
  así no se confirma al usuario una actualización parcial.

## Casos de aceptación

1. Alta persistida genera exactamente un aviso propio; el GET lo recupera.
2. Baja/Media y errores del proveedor no crean avisos ni alteran seguimiento.
3. Un reintento y dos solicitudes simultáneas conservan un solo ID y fecha.
4. Un fallo de escritura revierte prioridad y aviso, conservando datos previos.
5. Aislamiento de lectura, contador y enlace en ambos sentidos entre negocios.
6. Alta → Media → Alta reutiliza el evento y refleja solo avisos vigentes.
7. Un usuario autorizado ve el indicador, abre la review exacta y conserva el
   resultado al recargar; carga, error y ausencia de avisos tienen estados claros.
8. Cambiar de cuenta o selección descarta respuestas anteriores y no mezcla datos.

T2 #3827 implementa modelo y lectura; T3 #3828 conecta el guardado transaccional
y la idempotencia; T4 #3829 incorpora indicador y navegación; T5 #3830 verifica
el flujo, regresión, CI y demostración para aceptación final del PO.
