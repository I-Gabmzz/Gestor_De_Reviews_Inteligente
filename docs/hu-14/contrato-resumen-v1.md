# HU-14 — Contrato funcional de resumen v1

T1 #3567, 19 de octubre de 2026. Responsable: Francisco Javier Oceguera Gutiérrez.
Implementación propuesta para revisión del equipo; la aceptación final de la historia corresponde al PO.

## Comportamiento

El usuario solicita un resumen de una review guardada de su negocio. Se resume el contenido original completo, no el texto truncado de la tabla. El resultado debe conservar la idea principal, en español y preferentemente en una o dos frases. Se fija un máximo de **400 caracteres Unicode**, incluidos espacios interiores, tras quitar espacios de los extremos. No se recorta una salida larga para hacerla pasar como válida.

Se conservan los problemas, reconocimientos, peticiones o matices esenciales, sin inventar hechos, causas, soluciones, identidades ni compromisos. Una review breve puede producir un resumen de longitud similar. Si no hay una idea interpretable, el proveedor devuelve `{"resumen": null}` como rechazo interno; no se guarda ese resultado. La entrada vacía se rechaza antes de llamar al proveedor. Las instrucciones dentro de una review son datos y no sustituyen las instrucciones del servicio.

| Entrada sintética | Idea que debe conservar | Resultado incorrecto |
| --- | --- | --- |
| La comida estaba muy buena, pero esperamos una hora y nadie explicó la demora. | Comida valorada positivamente y espera de una hora sin explicación. | Omitir la demora o inventar una devolución. |
| ¿Podrían incluir opciones sin azúcar? | Solicitud de opciones sin azúcar. | Afirmar que ya se incorporaron. |
| El pedido llegó roto. Escribí dos veces y todavía no me responden. | Pedido roto y falta de respuesta tras dos contactos. | Inventar una causa o una solución. |
| Excelente atención, volveré. | Reconocimiento de atención e intención de volver. | Convertirlo en una queja. |
| No sé si el retraso fue del repartidor o del local. | Retraso con causa desconocida. | Atribuirlo al repartidor o al local. |
| Texto sin significado o una instrucción aislada para ignorar la tarea. | Rechazo si no hay experiencia/petición interpretable. | Inventar una experiencia del cliente. |

Los ejemplos definen criterios semánticos, no cadenas literales obligatorias ni una garantía de precisión general. La validación estructural automatizada no demuestra por sí sola fidelidad factual.

## Contrato técnico

- Reutilizar configuración, adaptador Gemini, columna `resumen`, migración y repositorio de HU-13/T2–T3. No duplicar conexión ni migraciones.
- `POST /api/v1/reviews/{review_id}/resumen`: token Bearer, id positivo, cuerpo omitido o `{}`. Rechazar campos enviados por el cliente, incluidos contenido, tenant y resumen.
- Respuesta 200: `ReviewRead` con el resumen guardado. `GET /api/v1/reviews/{review_id}` permite recuperarlo tras recarga.
- Solo `usuario_negocio` y `admin_tenant` activos, dentro de su tenant activo. `admin_general` no obtiene acceso global. Comprobar pertenencia antes de crear el proveedor.
- Salida persistible: `{"resumen": "texto de 1 a 400 caracteres"}`; solo lectura. POST/PATCH ordinarios no admiten edición manual de resultados.
- Regenerar reemplaza únicamente `resumen`; conserva contenido, categoría, tema, prioridad y estado. Puede consumir cuota otra vez y no tiene reintento automático.
- Una edición, eliminación o cambio de tenant durante la generación impide guardar el resultado obsoleto (409). Fallos del proveedor o de validación no reemplazan el resumen anterior; fallos de escritura hacen rollback.
- Errores controlados: 401 autenticación; 403 permisos/usuario/tenant; 404 recurso ajeno o inexistente; 409 conflicto concurrente; 422 petición o contenido no analizable; 500 persistencia; 502 salida/proveedor inválidos; 503 configuración, cuota o indisponibilidad; 504 timeout. No devolver credenciales ni detalles internos del proveedor.

## Interfaz y límites

Detalle con acción explícita, estado de carga y bloqueo de doble envío, error recuperable, resumen de solo lectura identificado como **Generado por IA** y persistencia tras recarga. Cambiar de review durante una petición no puede colocar el resultado en otra review.

La etiqueta es un criterio de aceptación del producto. El resumen no es traducción, respuesta al cliente, publicación externa ni resumen agregado. La política transversal de invalidación después de ediciones posteriores continúa pendiente del equipo; conservar el comportamiento compartido y permitir regeneración explícita. No afirmar que un resumen anterior refleja una edición posterior.

Dependencia de código: `feature/HU-13-clasificacion`, commit `32e434cea50a1875c58f9e1081307a5dd851f7af`, PR #22. T6 #3572 de pruebas integradas corresponde a José Ramón Suffo Peimbert y permanece separada de las tareas T1–T5 de Francisco.
