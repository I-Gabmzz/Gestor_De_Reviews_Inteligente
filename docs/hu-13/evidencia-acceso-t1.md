# HU-13/T1 #3560: comprobación real de acceso a Gemini

Ejecutada el 12 de octubre de 2026, 17:18, America/Tijuana. Proveedor: Google Gemini Developer API. Modelo solicitado y confirmado en las cuatro respuestas: `gemini-3.5-flash-lite`.

## Resultado

| Reseña sintética | Categoría esperada | Respuesta real | HTTP | Tiempo observado |
| --- | --- | --- | --- | --- |
| Mi pedido llegó tarde y nadie resolvió el problema. | Queja | `{"categoria":"Queja"}` | 200 | 0.892 s |
| Sería útil ofrecer entregas los domingos. | Sugerencia | `{"categoria":"Sugerencia"}` | 200 | 0.674 s |
| Excelente atención, gracias al equipo por su ayuda. | Felicitación | `{"categoria":"Felicitación"}` | 200 | 0.705 s |
| ¿Cuál es el horario de los sábados? | Consulta | `{"categoria":"Consulta"}` | 200 | 0.667 s |

**4/4 casos aprobados.** Cada respuesta contiene exclusivamente `categoria` y un valor exacto del catálogo. Se envió un schema JSON al proveedor y también se validó la salida localmente. Las expectativas no se incluyeron en los mensajes enviados al modelo.

Los tiempos son mediciones de esta ejecución y no una garantía de latencia. Los cuatro ejemplos claros verifican acceso y comportamiento básico; no son una evaluación representativa de precisión, casos mixtos, resumen o temas.

## Reproducción

Desde la raíz del repositorio, con `GEMINI_API_KEY` en el entorno o `backend/.env`:

```bash
backend/.venv/bin/python backend/scripts/verify_gemini_t1.py
```

El script realiza hasta cuatro llamadas de generación con reseñas sintéticas y detiene la prueba ante error del proveedor, red, timeout o respuesta no válida. Desde la revisión del 17 de octubre el script genera un archivo nuevo por ejecución y rechaza sobrescribir evidencias existentes. Una nueva ejecución consume cuota. Este JSON histórico del 12 de octubre se conserva intacto. La versión actual del script incorpora la política mixta v1; las reglas y los dos casos ambiguos se comprobaron por separado el 17 de octubre.

La configuración de la clave está excluida de Git. Se comprobó que la credencial no aparezca en el script ni en los entregables de esta tarea. Se omiten mensajes técnicos sin validar para evitar registrar credenciales o contenido arbitrario.

El [JSON de ejecución](evidencia-acceso-t1.json) conserva fecha, instrucciones del schema de salida, entradas, expectativas, resultados, códigos HTTP, modelo confirmado y tiempos. El [documento de T1](t1-definicion-clasificacion-ia.md) contiene la selección, criterios y registro para el avance.

## Alcance técnico

Esta comprobación es un script independiente. No modifica configuración de producción, endpoints, modelos de datos, repositorios, permisos ni componentes frontend. No persiste resultados en la base de datos de la aplicación. Por tanto, acredita acceso real como parte de #3560, mientras #3561–#3564 siguen pendientes de implementación.

## Revisión posterior

El [reporte del 17 de octubre](validacion-t1-2026-10-17.md) documenta seis casos reales con el contrato v1, incluidos dos ambiguos. No cambia ni amplía retrospectivamente los resultados de esta primera ejecución.
