# HU-13 / T1: validación del contrato v1 — 17 de octubre de 2026

Ejecución real: `2026-10-17T10:59:29.081846-07:00` (America/Tijuana). Proveedor: Google Gemini Developer API. Modelo solicitado y devuelto en los seis casos: `gemini-3.5-flash-lite`.

## Resultados

| Caso sintético | Esperada | Obtenida | HTTP | Tiempo |
| --- | --- | --- | --- | --- |
| Mi pedido llegó tarde y nadie resolvió el problema. | Queja | Queja | 200 | 0.690 s |
| Sería útil ofrecer entregas los domingos. | Sugerencia | Sugerencia | 200 | 1.386 s |
| Excelente atención, gracias al equipo por su ayuda. | Felicitación | Felicitación | 200 | 1.345 s |
| ¿Cuál es el horario de los sábados? | Consulta | Consulta | 200 | 0.673 s |
| Excelente comida, pero tardaron una hora. | Queja | Queja | 200 | 0.659 s |
| ¿Podrían abrir los domingos? | Sugerencia | Sugerencia | 200 | 0.654 s |

**6/6 casos aprobados** con JSON válido y una única categoría del catálogo. Los cuatro casos claros se volvieron a ejecutar y se añadieron dos ambiguos. Las expectativas se conservan en el reporte de comprobación; no se enviaron etiquetas esperadas en las solicitudes al modelo. El prompt comunica las reglas generales del contrato.

La comprobación usa reseñas ficticias, no modifica la base de datos ni demuestra integración funcional. Es una muestra de aceptación pequeña y no una medida de precisión general. El script detuvo un intento inicial por restricción de red del entorno; esta tabla corresponde exclusivamente a la ejecución autenticada posterior que completó los seis casos. No se inspeccionó ni cambió la facturación de la cuenta.

La [evidencia JSON](evidencia-validacion-t1-2026-10-17.json) conserva las instrucciones utilizadas, fecha, entradas, schema, respuestas y tiempos. Se mantiene intacta la [primera comprobación del 12 de octubre](evidencia-acceso-t1.json).

## Reproducir sin sobrescribir evidencias

```bash
backend/.venv/bin/python backend/scripts/verify_gemini_t1.py --include-mixed
```

Requiere el entorno backend y `GEMINI_API_KEY` en el entorno o `backend/.env`. Se crea un archivo nuevo; no se muestra la clave ni se sustituyen evidencias previas. Consume cuota de Gemini.
