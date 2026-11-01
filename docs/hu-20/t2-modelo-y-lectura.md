# HU-20 / T2 #3827: aviso del tenant

[Tarea #3827](https://computacion.mxl.uabc.mx/openproject/work_packages/3827).
Responsable: David Escárcega Schlemmer.

Se incorpora `review_notifications` mediante la creación aditiva de tablas de
`init_db`. Conserva reviews y resultados existentes; repetir el inicio no crea
avisos para prioridades antiguas ni reemplaza datos. El evento referencia review
y tenant, tiene fecha UTC y restricción única por ambos identificadores. Las
claves foráneas eliminan el evento al eliminar la review cuando el motor aplica
esas restricciones; la lectura también excluye referencias que ya no existen.

`GET /api/v1/notificaciones` requiere Bearer, usuario de negocio o administrador
de tenant activos y negocio activo. El ámbito procede de la cuenta consultada
en base de datos. El administrador general no obtiene acceso global. Un parámetro
`tenant_id` no amplía el ámbito.

La respuesta contiene `items` y `total`. Cada elemento expone ID, review, fecha de
creación UTC, autor, extracto de hasta 180 caracteres y prioridad Alta. La consulta
une el evento con la review actual y verifica que ambos pertenezcan al negocio
autenticado y que la prioridad siga en Alta. No devuelve copias antiguas de texto
ni avisos de reviews ajenas, eliminadas o que hayan bajado de prioridad.

La paginación admite `limit` de 1 a 100, por defecto 20, y `offset` no negativo.
El total se calcula sobre todos los avisos vigentes del negocio. El orden es fecha
de creación descendente y después ID descendente, de forma determinista. Los
fallos de lectura producen 500 con un mensaje controlado, sin detalles internos.

El repositorio incorpora creación interna únicamente para una review Alta propia,
sin confirmar la transacción del llamador. No existe POST público para crear
avisos. T3 #3828 conecta esa operación con el guardado de prioridad y añade el
tratamiento idempotente de reintentos y concurrencia.

Validación local del 1 de noviembre de 2026: pasaron 27 pruebas de lectura y
almacenamiento de avisos. Cubren roles, tokens, cuenta/tenant actuales, aislamiento
en ambos sentidos, paginación, fechas, conservación de datos y transacciones,
ausencia de backfill, restricción única y eliminación en cascada en SQLite.
