# HU-17 — Posible solución para una review

Historia #3255, Sprint 3. Responsable: Francisco Javier Oceguera Gutiérrez.
Rama: `feature/HU-17-solucion`. Base: `187e770` de `main`.

## Requisitos registrados en OpenProject

Generar una recomendación basada en el contenido de la review; identificarla
como sugerencia de IA; asociarla a la review; permitir su consulta sin edición;
y conservar su estado de seguimiento. La recomendación orienta al negocio,
mientras que HU-18 prepara una respuesta dirigida al cliente.

## Propuesta para revisión del Product Owner

T1 #3810 exige acordar formato, límites y retención. No se dispone todavía de
esa aprobación. La implementación de esta rama permite revisar esta propuesta:

- Español, texto breve y máximo 1000 caracteres Unicode tras quitar espacios exteriores.
- Pasos prudentes que el negocio pueda evaluar, sin afirmar acciones realizadas,
  causas, compensaciones ni promesas que no estén sustentadas.
- Conservar únicamente la última solución válida en `Review.solucion`, sin historial.
- Generar o regenerar solo por solicitud explícita; reemplazar únicamente tras éxito.
- Invalidar la solución cuando se modifica el contenido; no invalidarla por cambios
  en fuente, puntuación o seguimiento. No modificar las otras salidas de análisis.
- Rechazar contenido no interpretable mediante un resultado interno `null`, sin
  persistirlo ni sustituir una solución anterior válida.

Estas decisiones son una propuesta técnica revisable. El PR se mantiene en
borrador; no acredita aceptación de T1 ni cierre de la historia. La retención por
el proveedor y los respaldos no se definen mediante este cambio.

## Contrato técnico implementado

`POST /api/v1/reviews/{review_id}/solucion`, cuerpo omitido o `{}`.
Devuelve `ReviewRead`, incluyendo `solucion`, y permite recuperar el resultado
mediante el GET existente. No acepta contenido, tenant ni resultados elegidos
por el cliente. El JSON del proveedor contiene solo `solucion`.

Roles: `usuario_negocio` y `admin_tenant`, con usuario/tenant activos comprobados
en backend. `admin_general` no puede analizar reviews de otro negocio. Una review
ajena y una inexistente devuelven 404 antes de consultar al proveedor.

Errores: 401 autenticación; 403 autorización; 404 recurso no disponible; 409
comentario cambiado durante el análisis; 422 entrada no analizable; 500 escritura;
502 salida inválida; 503 configuración, credenciales, cuota o indisponibilidad;
504 espera agotada. Los mensajes no incluyen cuerpos privados del proveedor.

Se reutiliza `GeminiAdapter`, sin publicar claves ni crear otro transporte. El
contenido se envía como datos, separado de las instrucciones. El prompt requiere
fidelidad, ausencia de promesas y exclusión de datos personales; esto no constituye
una garantía semántica ni un mecanismo de anonimización. Usar muestras sintéticas
para evaluación. No se han enviado reviews reales durante este desarrollo.

La migración `add_solution_column` es aditiva y se ejecuta dentro del bloqueo de
inicio existente. Conserva datos anteriores y admite ejecuciones repetidas.
La escritura comprueba el contenido esperado para descartar una generación que
ya no corresponda a la review. Las regeneraciones simultáneas entre sesiones se
resuelven por último guardado válido; no se garantiza orden por inicio de petición.

La interfaz presenta texto escapado de solo lectura, carga y errores recuperables.
Impide doble envío en el componente, cancela su espera al cambiar review/contenido
y actualiza únicamente la solución de la review coincidente. No publica respuestas,
no envía mensajes al cliente ni cambia automáticamente el estado de seguimiento.

## Trazabilidad de tareas

| Tarea | Evidencia de esta rama | Condición restante |
| --- | --- | --- |
| #3810 Definir solución sugerida | Este contrato propuesto | Revisión y aprobación del PO |
| #3811 Generar solución estructurada | SolutionService, esquemas y tests | Ratificar política funcional y probar proveedor real |
| #3812 Asociar solución a review propia | API, migración y escritura aislada | Confirmar conservación propuesta |
| #3813 Mostrar solución de solo lectura | Pestaña Solución y tests React | Recorrido con proveedor real |
| #3814 Probar errores y regresión | Tests API/UI y suite de regresión | Checks del PR y revisión |
| #3815 Evaluar muestra y demo | Casos propuestos en validacion-y-demo.md | Evaluación real y aceptación del PO |
