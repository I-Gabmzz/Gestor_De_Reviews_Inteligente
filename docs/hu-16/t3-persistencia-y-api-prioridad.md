# HU-16 / T3 #3807: persistir prioridad propia

Responsable: David Escárcega Schlemmer.
[Tarea #3807](https://computacion.mxl.uabc.mx/openproject/work_packages/3807).

## Operación disponible

`POST /api/v1/reviews/{review_id}/prioridad` genera y guarda la prioridad de una
review existente del negocio autenticado. Requiere Bearer y un ID positivo. El
cuerpo puede omitirse o ser `{}`; no admite campos proporcionados por el cliente,
incluidos prioridad, contenido y tenant. El contexto siempre procede del usuario
activo consultado en base de datos, no de parámetros ni de un rol/tenant antiguo
incluido en el token.

Respuesta exitosa: HTTP 200 con `ReviewRead` y su `prioridad` exacta `Baja`, `Media`
o `Alta`. Los GET existentes de detalle y listado recuperan ese resultado desde
la base de datos. Repetir el POST vuelve a generar únicamente la prioridad y puede
consumir cuota; no hay reintento automático.

| Rol y contexto | Resultado |
| --- | --- |
| `usuario_negocio` activo, tenant activo y review propia | Permitido |
| `admin_tenant` activo, tenant activo y review propia | Permitido |
| `admin_general`, incluso enviando un tenant | 403 |
| Usuario o tenant inactivo | 403 |
| Review ajena o inexistente | 404 antes de llamar al proveedor |
| Sin autenticación válida | 401 |

La operación reutiliza los controles operativos de HU-04; no crea permisos
globales ni permite cambiar manualmente una prioridad. POST/PATCH ordinarios
rechazan cualquier campo `prioridad`, incluso junto con otros campos editables.

## Guardado y concurrencia

`PriorityResult` se incorpora a las salidas comunes de IA. Su importación desde
`app.schemas.priority` sigue disponible para el servicio de T2. El repositorio
vuelve a validar el resultado y actualiza solo la columna `prioridad`.

`PriorityService.prioritize` usa el análisis validado de T2 y condiciona el UPDATE
por ID, tenant y contenido exacto analizado. Si la review cambia de contenido,
se elimina o pasa a otro negocio durante la llamada, devuelve 409 y no guarda el
resultado obsoleto. Si cambian otros resultados o el estado de seguimiento,
conserva esos cambios y actualiza exclusivamente la prioridad. Un fallo al
confirmar la transacción hace rollback sin revelar información de base de datos.

La columna ya existe, por lo que no se requiere migración. No se normalizan ni
reescriben prioridades antiguas al iniciar la aplicación. Los resultados nuevos
de esta operación sí están restringidos al contrato v1.

## Errores y conservación

| HTTP | Situación |
| --- | --- |
| 409 | Review modificada, eliminada o movida durante el análisis |
| 422 | Petición inválida, contenido vacío/no analizable o bloqueo del proveedor |
| 500 | Fallo de lectura o persistencia |
| 502 | Respuesta inválida o solicitud rechazada por el proveedor |
| 503 | Configuración, acceso del proveedor, cuota o disponibilidad |
| 504 | Tiempo de espera agotado |

Los errores conservan la forma `{"detail": "mensaje"}` y no muestran claves ni
respuestas internas del proveedor. Un fallo no asigna Baja por defecto ni borra
la prioridad anterior. Una salida interna `null` no se guarda. La operación no
modifica categoría, resumen, tema, contenido, estado ni los otros datos originales.

## Comprobación y siguiente entrega

Las pruebas de `test_priority_api.py` ejecutan la ruta completa con autenticación,
SQLite temporal y transporte simulado del proveedor. Comprueban persistencia y
lectura posterior, roles y aislamiento en ambos sentidos, cambios en el usuario
con un token existente, rechazo de edición manual, errores, rollback y carreras
de contenido, tenant, eliminación y otros campos.

`test_ai_persistence.py` comprueba además la escritura de las tres prioridades en
sesiones nuevas, la conservación de otras reviews y resultados concurrentes, y
el rechazo de modelos construidos sin validación. Se conserva la suite de T2.

Validación local del 25 de octubre de 2026: pasaron las 129 pruebas seleccionadas
de prioridad y persistencia, y las 839 pruebas de la suite completa del backend.
Se mantiene el aviso previo de deprecación de Starlette/httpx.

Estas pruebas no envían reseñas al proveedor real ni evalúan precisión semántica;
esa evaluación corresponde a #3809. La acción de interfaz se implementa en #3808.
Este endpoint no genera los avisos de HU-20 ni cambia el estado de seguimiento.
