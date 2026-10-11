# HU-12 · T2 #3558 — Política de fuente en importación

Decisión funcional aprobada para CSV y Excel `.xlsx`:

- Una columna `fuente` ausente o una celda `None`, vacía o compuesta solo por espacios usa `CSV` o `Excel`, según el formato.
- Una fuente proporcionada conserva sus letras y mayúsculas/minúsculas; se eliminan solo espacios exteriores. Se acepta si su longitud normalizada es de 1 a 100 caracteres.
- Una fuente de más de 100 caracteres genera un error de validación con fila y campo `fuente`. Si cualquier fila es inválida, no se guarda ninguna review del archivo.

`backend/tests/test_imports_api.py` cubre ambos formatos, valores automáticos, fuente normalizada, límites de 100/101 caracteres, atomicidad, puntuación existente, aislamiento por tenant y los dos endpoints públicos de importación. No cambian el registro manual, la edición, la puntuación, los filtros ni el formato de respuesta. La auditoría previa se conserva en `auditoria-fuente-puntuacion.md` como estado anterior a T2.
