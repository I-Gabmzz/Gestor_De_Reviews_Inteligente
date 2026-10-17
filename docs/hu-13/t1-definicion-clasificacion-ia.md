# HU-13 / T1 #3560: definición de clasificación y selección de IA

Responsable: David Escárcega Schlemmer, Product Owner y desarrollador asignado. [Tarea #3560](https://computacion.mxl.uabc.mx/openproject/work_packages/3560). Selección y primera comprobación: 12 de octubre de 2026. Revisión final del contrato y nueva validación: 17 de octubre de 2026, America/Tijuana.

## Alcance y resultado de T1

T1 define proveedor, modelo, acceso, categorías, contrato y fallos previstos. Se revisó el contrato contra los criterios oficiales y se fijó una regla v1 para casos mixtos. La disponibilidad real se comprobó el 12 de octubre con cuatro casos y se volvió a verificar el 17 con seis casos, incluidos dos ambiguos: todos devolvieron HTTP 200, JSON válido y la categoría esperada. Las evidencias conservan sus fechas reales.

Estos entregables completan el alcance documental y la comprobación de T1. La conexión reutilizable de la aplicación, persistencia, servicio y endpoint corresponden a #3561-#3564; no quedan implementados por este documento ni por el script aislado.

## Necesidad y proveedor seleccionado

El producto necesita clasificar reseñas y compartir infraestructura de IA con resumen (HU-14) y tema (HU-15), respetando el tenant. El equipo aceptó Google Gemini Developer API con `gemini-3.5-flash-lite`, según la confirmación del PO del 12 de octubre. El [acuerdo común](../ia/proveedor-y-contrato-v1.md) conserva el alcance aceptado y separa propuestas de otras tareas.

La elección cubre análisis breve de texto, salida estructurada y acceso desde Python/FastAPI. La [ficha oficial](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) confirma salida de texto y soporte de structured outputs. La [guía de salidas estructuradas](https://ai.google.dev/gemini-api/docs/structured-output) permite definir JSON Schema y validar resultados en Python. Estas capacidades documentadas justifican la selección; la calidad debe comprobarse con reseñas del producto.

Inicio previsto en nivel gratuito sujeto a cuotas, sin activar facturación. Como referencia de pago Standard, las [tarifas](https://ai.google.dev/gemini-api/docs/pricing) consultadas el 17 de octubre son USD 0.30 por millón de tokens de entrada y USD 2.50 de salida. El escenario del equipo de 10,000 reseñas, tres solicitudes por reseña y 300/60 tokens de entrada/salida da 9 millones de entrada y 1.8 millones de salida: USD 7.20 estimados, sin caché, impuestos ni tokens adicionales. No es una factura ni costo observado. La API aceptó la clave local; las pruebas no inspeccionan la configuración de facturación de la cuenta.

El equipo contrastó costos y capacidades de seis candidatos durante el avance: Gemini 3.5 Flash-Lite, Gemini 3.1 Flash-Lite, GPT-5 nano, GPT-5 mini, Mistral Small 4 y Claude Haiku 4.5. Las pruebas reales documentadas aquí corresponden exclusivamente al modelo seleccionado, no a un benchmark entre proveedores.

## Categorías y criterios v1

La clasificación depende de la intención del texto, no de su puntuación. Devuelve exactamente una categoría, con acentos y mayúsculas del contrato.

| Categoría | Criterio | Ejemplo sintético | Resultado |
| --- | --- | --- | --- |
| Queja | Problema sufrido o insatisfacción predominante | Mi pedido llegó tarde y nadie resolvió el problema. | Queja |
| Sugerencia | Propuesta de mejora predominante | Sería útil ofrecer entregas los domingos. | Sugerencia |
| Felicitación | Reconocimiento o satisfacción predominante | Excelente atención, gracias al equipo por su ayuda. | Felicitación |
| Consulta | Solicitud de información o aclaración predominante | ¿Cuál es el horario de los sábados? | Consulta |

### Casos mixtos

1. Elegir la intención principal del comentario.
2. Un problema real reportado prevalece sobre un elogio accesorio: «Excelente comida, pero tardaron una hora» se clasifica como Queja.
3. Una petición de mejora formulada como pregunta sigue siendo Sugerencia: «¿Podrían abrir los domingos?» se clasifica como Sugerencia. Una pregunta informativa sobre el horario actual es Consulta.
4. Solo si existe un empate entre intenciones, aplicar Queja > Sugerencia > Consulta > Felicitación.
5. Una categoría válida en JSON no garantiza que su interpretación sea correcta; los ejemplos funcionales deben revisarse durante las pruebas de HU-13.

La regla v1 se concreta en esta revisión del 17 de octubre para completar T1, después de la propuesta presentada al PO. No se atribuye esta regla a una reunión del equipo del 12 ni se modifica retrospectivamente la primera evidencia. Las dos reseñas ambiguas se probaron realmente con Gemini el 17 de octubre.

## Contrato de clasificación revisado

Versión: `hu13-t1-2026-10-17`. Entrada interna: `contenido`, texto original no vacío de una review autorizada. La aplicación comprobará identidad y pertenencia al tenant antes de enviar el contenido. La review se trata como datos; las instrucciones incluidas en su texto no cambian la tarea ni la salida permitida.

Salida exitosa:

```json
{"categoria":"Queja"}
```

El [JSON Schema](contrato-clasificacion-v1.schema.json) exige un objeto con un único campo obligatorio `categoria`, restringido a `Queja`, `Sugerencia`, `Felicitación` y `Consulta`; rechaza campos adicionales. El backend deberá validar la salida de nuevo antes de persistirla. Texto vacío, una respuesta bloqueada o contenido sin intención interpretable producen un error controlado, sin inventar una quinta categoría.

Los errores no devuelven una clasificación aparente, no borran resultados previos ni modifican estado, prioridad, resumen o tema. El contrato no acepta categoría desde una edición manual. La definición de estas reglas pertenece a T1; su implementación y pruebas de aplicación se realizarán en las siguientes tareas.

## Fallos previstos y tratamiento acordado para implementar

| Situación | Comportamiento previsto |
| --- | --- |
| Clave ausente/rechazada o modelo sin acceso | Error controlado; no registrar clave ni respuesta técnica sensible. |
| Cuota agotada o servicio indisponible | Informar indisponibilidad; conservar resultados previos; sin bucles de reintento ilimitados. |
| Timeout o fallo de red | Interrumpir la operación y devolver error controlado, sin cambios parciales. |
| Respuesta bloqueada, vacía, JSON inválido o categoría fuera del catálogo | Rechazar salida; no guardar ni sustituir la clasificación anterior. |
| Texto vacío o sin intención interpretable | Rechazar como no analizable; no inventar una categoría. |
| Usuario sin permiso o review de tenant ajeno | Rechazar antes de llamar a IA o modificar datos. |

El mapeo final de errores HTTP pertenece a T2/T5. Los fallos se prevén aquí; no se declara implementado o probado su manejo dentro de la aplicación. Acceso y cuotas dependen de la cuenta; consultar [límites de Gemini](https://ai.google.dev/gemini-api/docs/rate-limits).

## Evidencia y reproducción

- [Primera ejecución, 12 de octubre](evidencia-acceso-t1.md): cuatro casos claros, 4/4. Su [JSON original](evidencia-acceso-t1.json) se conserva sin cambios.
- [Validación del contrato, 17 de octubre](validacion-t1-2026-10-17.md): seis casos, 6/6, incluidos los dos ambiguos. Su [JSON](evidencia-validacion-t1-2026-10-17.json) registra instrucciones efectivas, modelo, entradas, salidas y tiempos.
- [Script independiente](../../backend/scripts/verify_gemini_t1.py): ejecuta las comprobaciones con reseñas sintéticas; no integra endpoints ni escribe en la base de datos.

Con el entorno backend y sus dependencias instalados, guardar `GEMINI_API_KEY` en el entorno o `backend/.env` y ejecutar desde la raíz:

```bash
backend/.venv/bin/python backend/scripts/verify_gemini_t1.py --include-mixed
```

El script genera un archivo nuevo de evidencia y rechaza sobrescribir registros existentes. Cada ejecución consume cuota. No enviar la clave por chat ni incluirla en frontend, capturas o commits. El archivo `.env` está ignorado. La [guía oficial de claves](https://ai.google.dev/gemini-api/docs/api-key) documenta el acceso. Se usaron datos ficticios; el nivel gratuito puede usar contenido para mejorar productos de Google según sus condiciones.

## Criterios de finalización de T1

| Criterio oficial | Evidencia de cumplimiento |
| --- | --- |
| Proveedor, modelo y acceso definidos | Acuerdo de equipo informado por el PO el 12; modelo solicitado y devuelto confirmado en ambas ejecuciones. |
| Contrato revisado | Entrada, schema exacto, regla de intención principal/casos mixtos, protección por tenant y comportamiento ante fallos revisados contra HU-13. |
| Cuatro categorías definidas | Catálogo y ejemplos de este documento; seis casos comprobados con la regla v1 el 17. |
| Disponibilidad real comprobada | Llamadas autenticadas HTTP 200; 4/4 el 12 y 6/6 el 17, con JSON válido y modelo confirmado. |
| Fallos previstos | Tabla de escenarios y comportamiento esperado; implementación asignada a las tareas posteriores. |

## Límites y continuación

Las muestras pequeñas acreditan disponibilidad y comportamiento inicial, no precisión general. Resumen y tema no fueron probados en estas ejecuciones. Francisco y Diego deben concretar sus criterios propios; HU-04/T4 sigue siendo dependencia del endpoint autorizado. No se cierra HU-13 al completar T1.

Siguiente entrega: T2 #3561 implementa configuración y adaptador compartidos; T3 #3562 prepara lectura y persistencia compatibles. Las fechas del trabajo y del cierre deben registrarse cuando ocurren; publicar hoy la evidencia del 12 no cambia su fecha de ejecución.
