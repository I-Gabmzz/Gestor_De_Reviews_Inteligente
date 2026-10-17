# Validación de T3 — 17 de octubre de 2026

Tarea #3562, HU-13. Rama `feature/HU-13-clasificacion`, [PR #22](https://github.com/I-Gabmzz/Gestor_De_Reviews_Inteligente/pull/22). [Contrato y guía de integración](t3-contrato-y-persistencia-ia.md).

## Resultado local

Suite completa iniciada el 17 de octubre a las 12:27:28, hora de Tijuana, con Python 3.13:

```bash
cd backend
.venv/bin/python -m pytest -q --junitxml=/private/tmp/hu13-t3-pytest.xml
```

**459 pruebas aprobadas, 0 fallos, 0 errores, 0 omitidas**, en 44.19 segundos. Incluye 29 casos nuevos en `test_ai_persistence.py`, un caso adicional de protección de `tema` en la edición manual y la actualización de expectativas de lectura/cambio de estado. Se conserva un aviso de deprecación de Starlette/TestClient ya presente en T2.

También se comprobaron importación de FastAPI, sintaxis, schemas comunes, enlaces locales y diff sin errores. No se hicieron llamadas adicionales al proveedor para T3.

| Criterio de T3 | Evidencia comprobada |
| --- | --- |
| Contrato común sin duplicación | Tres modelos compartidos, reutilizados por el script de comprobación; una columna por resultado y un único método interno de escritura. |
| Datos previos conservados | Base anterior a T3 con todas las columnas originales, categorías antiguas, índice y clave foránea; comparación antes/después y lectura ORM. |
| Base nueva y existente | Inicialización limpia, actualización parcial conservando resumen previo, repetición e inicio simultáneo SQLite. |
| Resultados independientes | Guardar/regenerar cada operación conserva otros campos; sesión nueva confirma persistencia; sesiones con lecturas anteriores no borran otros resultados. |
| Aislamiento | Una review ajena y una inexistente devuelven `None`; ninguna se modifica. El `UPDATE` filtra por review y tenant. |
| Validación y fallos | Categorías oficiales, rechazo de valores inválidos/extras y modelos sin validar; error de commit revierte los cambios y permite reutilizar la sesión. |
| Lectura y protección manual | GET de detalle/listado expone los resultados guardados. POST manual y PATCH rechazan los tres campos de IA con 422 y sin cambios parciales; edición/estado conservan resultados previos. |

## Copia de la base local existente

Se creó una copia temporal consistente mediante la API de backup de SQLite, leyendo la base original sin permiso de escritura. Esa base aún no contenía `resumen` ni `tema`.

La actualización se ejecutó **dos veces sobre la copia**. La comparación de todas las columnas previas de todas las filas confirmó conservación exacta:

| Tabla | Filas conservadas |
| --- | ---: |
| `reviews` | 5 |
| `users` | 3 |
| `tenants` | 1 |

Las columnas nuevas quedaron presentes, `PRAGMA integrity_check` devolvió `ok` y `PRAGMA foreign_key_check` no detectó inconsistencias. La copia temporal se eliminó al terminar la comprobación; la base original no se modificó. Al iniciar la aplicación con esta versión, `init_db` aplicará la misma actualización a la base configurada.

## Límites de esta evidencia

Se ejecutó SQLite; no se validó una instancia PostgreSQL. Las entradas de las pruebas son sintéticas y no acreditan calidad semántica del modelo. T3 prepara contrato y almacenamiento; servicios, endpoints de generación, interfaz y aceptación integrada pertenecen a las tareas posteriores. El PR requiere revisión y permanece sin fusionar.
