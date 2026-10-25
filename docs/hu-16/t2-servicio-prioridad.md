# HU-16 / T2 #3806: generar prioridad validada

Responsable: David Escárcega Schlemmer.
[Tarea #3806](https://computacion.mxl.uabc.mx/openproject/work_packages/3806).

## Implementación

`PriorityService.analyze(review_id, tenant_id)` consulta exclusivamente la review
del tenant recibido del contexto autorizado y devuelve `PriorityAnalysis` con el
contenido original y un `PriorityResult` validado. Reutiliza `create_ai_provider`,
la configuración existente y el transporte de salidas estructuradas. No añade
dependencias, migraciones, rutas HTTP ni escrituras en base de datos.

El prompt incorpora la [rúbrica v1 y sus casos](t1-definicion-prioridad.md).
`PriorityDecision` exige el campo `prioridad` y permite los tres valores exactos o
`null` como rechazo interno. El servicio vuelve a validar la decisión aunque se
sustituya el proveedor. Solo devuelve un `PriorityResult` de Baja, Media o Alta;
el resultado incluye el contenido analizado para que #3807 pueda evitar guardar
una respuesta obsoleta si la review cambia durante la llamada.

Una review ajena o inexistente y el contenido vacío se rechazan antes de crear el
proveedor. Un fallo de lectura se convierte en `PriorityReadError`, sin mostrar
detalles de base de datos. El contenido no interpretable produce
`PriorityContentError`. Las salidas mal formadas se rechazan y los errores de
cuota, timeout o indisponibilidad conservan el tratamiento común. No hay prioridad
por defecto ni reintento automático.

## Comprobación y límites

`backend/tests/test_priority_service.py` comprueba los tres valores, la consulta
por tenant, el contenido completo separado de las instrucciones, el rechazo de
salidas inválidas, la revalidación de proveedores sustituidos, fallos de lectura
y transporte, y la ausencia de escrituras y reintentos.

Las respuestas de estas pruebas son simuladas mediante el transporte de pruebas
del adaptador común; no se usa una clave real ni se consume cuota. Comprobar que
una respuesta cumple el esquema no demuestra que su prioridad sea semánticamente
correcta. La evaluación con una muestra real del proveedor queda en #3809.

Validación local del 25 de octubre de 2026: las 34 pruebas del servicio y las
773 pruebas de la suite completa del backend pasaron. El JSON Schema documental
coincide con el modelo `PriorityResult` en valores permitidos, campo obligatorio
y rechazo de propiedades adicionales. La suite conserva un aviso de deprecación
de Starlette/httpx ya presente en la configuración de pruebas.

Al completar T2 no existía una acción pública para priorizar. #3807 incorpora
después la [operación autorizada y su persistencia](t3-persistencia-y-api-prioridad.md);
#3808 cubre la interfaz. Este análisis no genera notificaciones de HU-20 ni cambia
el estado de seguimiento.
