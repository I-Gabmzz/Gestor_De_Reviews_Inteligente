# HU-20 / T3 #3828: evitar duplicados

[Tarea #3828](https://computacion.mxl.uabc.mx/openproject/work_packages/3828).
Responsable: David Escárcega Schlemmer.

El guardado común de resultados de HU-16 incorpora la creación de aviso solamente
cuando recibe un `PriorityResult` validado cuyo valor exacto es Alta. La operación
actualiza condicionalmente la prioridad por ID, tenant y contenido analizado,
inserta o recupera el aviso y después confirma la transacción. No se crea un aviso
a partir de una respuesta del proveedor que no haya llegado al guardado válido.

La inserción usa `INSERT … SELECT` condicionado por la review Alta propia y
`ON CONFLICT (tenant_id, review_id) DO NOTHING`. La restricción única de T2 es la
última garantía ante concurrencia. Un reintento conserva el ID y la fecha original;
no se captura indiscriminadamente cualquier error de integridad como si fuera
un duplicado. Los errores reales se propagan al rollback de la transacción.

Si cambia el contenido, desaparece la review o deja de pertenecer al tenant antes
del UPDATE, no se guarda prioridad ni aviso. Si la creación del aviso no puede
confirmarse, se revierte la prioridad nueva. Los análisis de categoría, resumen
y tema, y las prioridades Baja/Media, no crean eventos. El estado de seguimiento
y los datos originales se conservan.

Cuando la prioridad deja de ser Alta, el evento se conserva pero la consulta de
avisos vigentes lo excluye. Si vuelve a Alta, reaparece el mismo evento. Las
consultas GET y el inicio de la aplicación no generan avisos retroactivos.

Validación local del 1 de noviembre de 2026: pasaron 130 pruebas seleccionadas de
avisos, prioridad y persistencia. Se verificaron escrituras concurrentes reales
con cuatro sesiones SQLite, reintentos, ciclo Alta/Media/Alta, rollback de inserción
y commit, ausencia de cambios de seguimiento y conservación de datos anteriores.
La sentencia PostgreSQL se comprobó mediante compilación del dialecto; no se
afirma una ejecución integrada contra un servidor PostgreSQL.
