# Acuerdo de proveedor y propuesta de contrato común de IA v1

Acuerdo general: 12 de octubre de 2026. Revisión de clasificación v1: 17 de octubre de 2026. Responsable: David Escarcega Schlemmer. Relacionado con [#3560](https://computacion.mxl.uabc.mx/openproject/work_packages/3560), [#3561](https://computacion.mxl.uabc.mx/openproject/work_packages/3561) y [#3562](https://computacion.mxl.uabc.mx/openproject/work_packages/3562).

Estado: acuerdo general aceptado por el equipo, según confirmación del Product Owner el 12 de octubre de 2026. Contrato de clasificación revisado al completar T1 el 17 de octubre. Acceso comprobado con cuatro casos el 12 y seis casos el 17, incluidos dos ambiguos. T2 incorpora configuración y transporte reutilizable en el backend, comprobados el 17 de octubre con las tres operaciones. La persistencia, servicios funcionales, endpoints e interfaz y la calidad general siguen pendientes. El cierre de T1 se registra por separado en OpenProject; este acuerdo no cierra HU-13 ni las tareas posteriores.

## Alcance del acuerdo confirmado

El PO informó: «todos dijeron que deacuerdo», en respuesta al mensaje preparado para el equipo. Se registra la aceptación de Google Gemini con `gemini-3.5-flash-lite`, inicio en nivel gratuito sujeto a cuotas, conexión común desde FastAPI, tres operaciones con salidas JSON, almacenamiento separado de categoría/resumen/tema, aislamiento por tenant, resultados sin edición manual y reparto de responsabilidades descrito en ese mensaje.

La intención principal y precedencia de categorías mixtas quedan fijadas para clasificación v1 en la revisión de T1 del 17 de octubre. Los otros detalles que no se fijaron en el mensaje enviado siguen como propuestas técnicas: longitud de resumen, catálogo o etiquetas abiertas de temas, nombres de endpoints, variables, timeout y política al editar contenido. Francisco y Diego concretan sus criterios; Gabriel confirma permisos. La confirmación del PO no se interpreta como una validación técnica o una prueba de disponibilidad del proveedor.

## Proveedor acordado

Google Gemini Developer API, acceso mediante Google AI Studio, modelo estable `gemini-3.5-flash-lite`. Usar un modelo configurable y un único adaptador de backend para HU-13, HU-14 y HU-15. El modelo admite salidas estructuradas y Google lo recomienda entre las opciones para proyectos nuevos. [Ficha del modelo](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [ciclo de modelos](https://ai.google.dev/gemini-api/docs/deprecations).

La tabla oficial ofrece entrada/salida gratuitas con límites. Si posteriormente se activa pago, Standard publica USD 0.30 por millón de tokens de entrada y USD 2.50 de salida. La propuesta inicial usa nivel gratuito; disponibilidad y cuotas de la cuenta deben comprobarse en AI Studio y no se promete un número de solicitudes. El contenido del nivel gratuito puede usarse para mejorar productos de Google; utilizar reseñas sintéticas para la demostración. [Precios](https://ai.google.dev/gemini-api/docs/pricing), [límites](https://ai.google.dev/gemini-api/docs/rate-limits).

Ejemplo orientativo en nivel de pago: 1,000 solicitudes con 500 tokens de entrada y 100 de salida cada una costarían USD 0.40 según esas tarifas (0.15 + 0.25), excluyendo tokens adicionales y otros servicios. No es una medición del proyecto ni autorización para activar facturación.

La elección busca una primera integración de análisis de texto con salida JSON. La adecuación a las reviews del producto debe verificarse con ejemplos; las capacidades publicadas no garantizan clasificación correcta.

## Acceso y configuración implementada en T2

David obtiene la credencial de la cuenta autorizada en [Google AI Studio](https://aistudio.google.com/apikey) siguiendo la [guía de claves](https://ai.google.dev/gemini-api/docs/api-key). Guardarla solo en el entorno local del backend; no incluirla en frontend, capturas, documentos, commits o conversaciones.

Variables implementadas mediante `AISettings`, cargadas solo al solicitar el adaptador, y documentadas en `backend/.env.example`:

```dotenv
AI_PROVIDER=gemini
AI_MODEL=gemini-3.5-flash-lite
GEMINI_API_KEY=
AI_TIMEOUT_SECONDS=30
AI_MAX_OUTPUT_TOKENS=1024
```

T2 implementa estas variables con configuración independiente de la configuración general de FastAPI. Una credencial ausente o inválida produce un error controlado al solicitar IA, sin impedir el inicio de la aplicación. Se usa la API REST oficial mediante `httpx`, ya instalado, como decisión de implementación de T2; no se añade el SDK `google-genai`. Los resultados se validan con Pydantic. Ver la [guía del adaptador común](../hu-13/t2-conexion-reutilizable-ia.md) y [salidas estructuradas](https://ai.google.dev/gemini-api/docs/structured-output).

## Contrato interno propuesto

Tres operaciones funcionales sobre el texto original de una review. Los nombres siguientes representan los casos de uso propuestos; el transporte compartido implementado en T2 es `generate_structured(contenido, instructions=..., response_model=...)`:

| Operación del adaptador | Salida validada | Responsable del caso de uso |
| --- | --- | --- |
| `classify(contenido)` | `{"categoria": "Queja"}` | David, HU-13 |
| `summarize(contenido)` | `{"resumen": "El cliente reporta una demora en la entrega."}` | Francisco, HU-14 |
| `detect_topic(contenido)` | `{"tema": "Entrega"}` | Diego, HU-15 |

Los valores de esta tabla son ejemplos del contrato, no evidencia. T2 documenta por separado sus tres respuestas reales de comprobación. El adaptador recibe contenido, instrucciones de la operación y su modelo Pydantic; no necesita credenciales de usuarios, correos ni identificadores de tenant. El servicio de aplicación resuelve identidad/tenant y verifica pertenencia de la review antes de invocarlo.

Solicitar JSON conforme a schema y validarlo otra vez en Pydantic. Ante una respuesta inválida o bloqueada no guardar valores ni sustituirlos por resultados aparentes. Tratar el contenido de la review como datos: instrucciones dentro del comentario no deben modificar la tarea ni los schemas.

## Criterios de clasificación

Una categoría exacta entre `Queja`, `Sugerencia`, `Felicitación`, `Consulta`, conservando los acentos del contrato. No inferir la categoría únicamente de la puntuación: clasificar por la intención del texto.

| Categoría | Criterio | Ejemplo sintético |
| --- | --- | --- |
| Queja | Insatisfacción o problema sufrido por el cliente | «Mi pedido llegó tarde y no me atendieron.» |
| Sugerencia | Propuesta de mejora sin reclamación predominante | «Sería útil ofrecer entregas los domingos.» |
| Felicitación | Reconocimiento o satisfacción predominante | «Excelente atención, muchas gracias al equipo.» |
| Consulta | Solicitud de información o aclaración | «¿Cuál es el horario de los sábados?» |

Política de clasificación v1, concretada el 17 de octubre al completar T1: elegir intención principal; solo ante empate real, usar precedencia Queja → Sugerencia → Consulta → Felicitación. Un problema sufrido prevalece sobre un elogio accesorio: «Excelente comida, pero tardaron una hora» es Queja. Una petición de mejora en forma de pregunta, «¿Podrían abrir los domingos?», es Sugerencia; una pregunta informativa del horario actual es Consulta. Ambos casos se verificaron con el modelo real el 17 de octubre. La aplicación deberá rechazar texto vacío antes de la llamada y tratar texto sin intención interpretable como no analizable, sin inventar una categoría. El [contrato revisado de T1](../hu-13/t1-definicion-clasificacion-ia.md) y su [JSON Schema](../hu-13/contrato-clasificacion-v1.schema.json) fijan el alcance de clasificación; las siguientes tareas implementarán sus reglas.

## Resumen y tema

Propuesta inicial de resumen: español, 1–2 frases, máximo 400 caracteres, conservar idea principal y no inventar causas, soluciones ni hechos. Francisco define ejemplos de fidelidad y confirma el límite en #3567. El límite técnico se valida en backend; la fidelidad requiere revisión funcional.

Propuesta inicial de tema: etiqueta breve en español, de 1–3 palabras y máximo 60 caracteres; un tema principal, independiente de la categoría. Diego confirma en #3573 si se acepta una etiqueta abierta o un catálogo. Los ejemplos Atención, Entrega, Precio y Producto son referencias, no un catálogo aprobado. No implementar restricciones de temas definitivos hasta acordarlas.

## Almacenamiento implementado en T3 y API propuesta

T3 conserva `Review.categoria` y añade `resumen: str | None` y `tema: str | None`, ambos nullable y separados. Nuevas reviews comienzan con resultados null. `ReviewRead` devuelve esos campos; ni registro manual ni `ReviewUpdate` los aceptan como entrada editable. `ClassificationResult`, `SummaryResult` y `TopicResult` definen las salidas estructuradas comunes. El método interno `ReviewRepository.save_ai_result(review_id, tenant_id, result)` guarda solo el resultado recibido y conserva los demás campos. Ver [contrato, migración y guía de integración de T3](../hu-13/t3-contrato-y-persistencia-ia.md).

| Endpoint propuesto bajo `/api/v1` | Operación | Respuesta exitosa |
| --- | --- | --- |
| `POST /reviews/{review_id}/clasificacion` | Generar y persistir categoría | 200, `ReviewRead` actualizado |
| `POST /reviews/{review_id}/resumen` | Generar y persistir resumen | 200, `ReviewRead` actualizado |
| `POST /reviews/{review_id}/tema` | Generar y persistir tema | 200, `ReviewRead` actualizado |
| `GET /reviews/{review_id}` | Consultar resultados persistidos | 200, `ReviewRead` |

El cuerpo de las operaciones de generación no solicita texto ni tenant al cliente: el backend usa el registro autorizado. Repetir una operación puede regenerar únicamente su resultado. Cada operación conserva los otros campos. No se propone un endpoint que ejecute obligatoriamente las tres operaciones juntas.

Errores propuestos: 401 sin autenticación; 403 para rol no autorizado/inactivo; 404 para review inexistente o de tenant ajeno; 422 para contenido no analizable; 502 para salida inválida del proveedor; 503 para configuración ausente/cuota/indisponibilidad; 504 para timeout. Mantener la forma existente `{"detail": "mensaje"}` y no exponer respuestas técnicas del proveedor ni secretos. Gabriel confirma autorización en #3552/#3554; `admin_general` no adquiere acceso global a reviews con esta propuesta.

La migración de almacenamiento se implementó una sola vez en #3562: `init_db` añade únicamente las columnas faltantes, conserva datos previos y admite repetición. Se comprueba con bases SQLite nuevas, existentes y parcialmente actualizadas. Francisco y Diego reutilizan esa base y añaden sus casos de uso, en vez de duplicar migraciones. La ejecución sobre PostgreSQL sigue pendiente de validación.

## División de trabajo para desbloquear al equipo

- David entrega configuración/adaptador y schemas comunes, prepara la base de persistencia y desarrolla clasificación. Comparte primero el contrato; después un PR de base común comprobada que los otros puedan integrar.
- Francisco trabaja en criterios y lógica de resumen mediante `summarize`, y su interfaz/API; confirma longitud y fidelidad.
- Diego trabaja en política y lógica de tema mediante `detect_topic`, más acción de clasificación del frontend; confirma representación de tema.
- Gabriel entrega la matriz y las dependencias de permisos que deben aplicar los tres endpoints.
- José prepara pruebas integradas y casos de aislamiento y errores usando el mismo contrato.

Los datos controlados permiten preparar código e interfaces, pero no sustituyen la aceptación con el proveedor real. Los endpoints y nombres son propuesta v1; acordarlos una vez antes de desarrollar servicios en paralelo.

## Evidencia de acceso y revisión de #3560

Proveedor/modelo aceptados: registrados por confirmación del PO. El 12 de octubre a las 17:18, hora de Tijuana, se ejecutó una llamada autenticada por categoría con reviews sintéticas: cuatro respuestas HTTP 200, JSON válido y resultados coincidentes con las expectativas de los casos claros. [Evidencia](../hu-13/evidencia-acceso-t1.md). La comprobación conserva fecha, entrada, salida y modelo sin credenciales. La política mixta de clasificación se concretó y se validó con seis casos el 17 de octubre: [reporte](../hu-13/validacion-t1-2026-10-17.md). Los criterios específicos de resumen/tema siguen a cargo de sus responsables. T2 implementa y prueba el manejo controlado de cuota, timeout y otras fallas de transporte/salida; ver [su evidencia y límites](../hu-13/t2-conexion-reutilizable-ia.md). La comprobación inicial de T1 no acredita por sí sola ese desarrollo ni la persistencia de T3. La calidad general sigue pendiente.

Antes de integrar, acordar qué ocurre al editar el contenido de una review ya analizada para evitar mostrar resultados desactualizados. No cambiar silenciosamente la política existente de edición.
