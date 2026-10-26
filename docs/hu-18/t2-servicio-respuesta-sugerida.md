# HU-18 / T2 #3817 — Servicio de respuesta sugerida

**Estado: implementado y probado con proveedor simulado; pendiente de revisión puntual de David y de autorización para commit.** No hay aprobación de T2 implícita en la aprobación de T1.

Responsable: Diego Erik Alfonso Montoya. Product Owner: David Escárcega. Base: `7290c5abb5b82bb92101ee8e4d2bd24c82559073`. Se conserva sin cambios el [contrato funcional aprobado de T1](contrato-respuesta-sugerida.md).

## Implementación y límites de la entrega

- [SuggestedResponseResult](../../backend/app/schemas/suggested_response.py): un único campo obligatorio `respuesta_sugerida`, string estricto, no vacío después de trim exterior; rechaza `null`, tipos incorrectos y propiedades adicionales. No se impone máximo de caracteres ni un número obligatorio de oraciones.
- `SuggestedResponseDecision`, en el mismo módulo, permite `null` exclusivamente como rechazo interno de contenido no analizable o no respondible con seguridad, siguiendo los patrones de HU-13 a HU-15. No es el resultado exitoso: el servicio lo traduce a `SuggestedResponseContentError`. Un resultado válido se convierte en `SuggestedResponseResult`.
- [SuggestedResponseService.generate(contenido: str) -> SuggestedResponseResult](../../backend/app/services/suggested_response_service.py): recibe contenido que el llamador ya haya autorizado. Normaliza espacios exteriores, minimiza información privada reconocible, valida la entrada, solicita una decisión al proveedor y revalida su contrato antes de devolver el resultado.
- La fábrica opcional `provider_factory` sigue las convenciones existentes: context manager de `StructuredAIProvider`, por defecto `create_ai_provider`. Se reutilizan `AISettings`, `GeminiAdapter` y `generate_structured`; no se cambia configuración, modelo ni transporte compartido. Cada generación hace un solo intento y cierra su proveedor.
- Las instrucciones exigen español, tono profesional/cordial/empático, preferentemente dos a cuatro oraciones, adaptación a comentarios positivos, negativos, consultas, sugerencias y mixtos, fidelidad y ausencia de compensaciones, contactos, políticas o acciones inventadas. La review se mantiene separada de las instrucciones de sistema.

El servicio no recibe Review, sesión de base de datos, tenant ni repositorio. No consulta ni persiste datos, no cambia estado y no ejecuta clasificación, resumen, tema, prioridad o solución. No publica, envía mensajes ni invoca herramientas. Su único contacto externo en uso futuro sería la generación mediante el proveedor compartido. No hay endpoint ni UI nuevos. T3 deberá autorizar, obtener la review desde servidor, preservar el ámbito del tenant, guardar el resultado y proteger su vigencia; esta entrega no declara esas operaciones implementadas.

## Privacidad implementada y límites

No se encontró una utilidad previa de anonimización en `backend/app`. Se implementaron funciones privadas pequeñas en el propio servicio, sin dependencias nuevas ni una plataforma de anonimización.

| Patrón reconocido | Tratamiento antes del proveedor | Comprobación |
| --- | --- | --- |
| Correos con formato habitual, incluidos los ejemplos con letras acentuadas | Sustituir por `[CORREO_OCULTO]` | El request simulado no contiene el correo original y conserva la experiencia. |
| Grupos numéricos de 7 a 12 dígitos separados por espacios, paréntesis, puntos o guiones, con prefijo `+` opcional | Sustituir por `[TELEFONO_OCULTO]` | Casos de teléfono local, nacional y formato internacional de ejemplo. |
| Fechas con formato `YYYY-MM-DD` | Conservar el texto | Caso con fecha, espacios interiores y varios contactos. |
| Grupos de 13 o más dígitos | Rechazar antes de crear el proveedor | Caso de número de tarjeta sintético; la regla es conservadora y también puede rechazar teléfonos largos. |
| Etiquetas reconocidas de contraseña, PIN, CVV/CVC, token, claves, identificadores, datos bancarios o domicilio, seguidas de `:`, `=` o `es`; patrón Bearer | Rechazar antes de crear el proveedor | Casos parametrizados, con mensajes sin el contenido de entrada. |

Se repite la comprobación de privacidad en la salida: correos, grupos numéricos de contacto, patrones de alto riesgo o marcadores de enmascaramiento no se devuelven al llamador. Un texto de solo puntuación tampoco es un resultado utilizable. La entrada vacía, de tipo incorrecto, sin letras o formada solo por contactos/fechas se rechaza localmente; el resto de casos no interpretables depende de la decisión validada del proveedor.

**No es una garantía de anonimización ni un detector universal de datos personales.** No identifica todos los nombres, domicilios en texto libre, identificadores alfanuméricos sin etiqueta, formatos no previstos, números escritos con palabras u ofuscaciones. Puede confundir un número de pedido con un teléfono y rechazar etiquetas o números que no sean sensibles. La fecha se reconoce por forma, no se valida como fecha de negocio. Deben revisarse estos límites y falsos positivos con David antes de usar datos reales; las expresiones regulares no sustituyen la evaluación semántica ni la política del proveedor.

No se añaden logs de reviews ni se incluyen valores privados en los mensajes propios del servicio. Las instrucciones piden omitir también información privada que la regla local no haya reconocido, pero los mocks no demuestran que Gemini real lo cumpla.

## Errores y contratos anteriores

Se conservan los errores de configuración, credenciales, cuota, timeout, red/indisponibilidad, bloqueo, petición y respuesta inválida del proveedor. No se convierten todos en un genérico ni se genera una respuesta de respaldo aparente. Un tipo de decisión inesperado o un modelo construido sin validación se rechaza o revalida como en los servicios existentes.

HU-18 añade `SuggestedResponseContentError` (`not_analyzable`) para contenido o respuesta no utilizables y `SuggestedResponsePrivacyError` (`privacy`) para datos detectados que no se pueden tratar de forma segura. Ambos heredan `AIError` y tienen mensajes fijos. No hay mapeo HTTP en T2; se resolverá en T3. `AIResult`, `save_ai_result()`, Review y las otras HUs permanecen sin cambios.

## Pruebas y evidencia simulada para David

[test_suggested_response_service.py](../../backend/tests/test_suggested_response_service.py) usa `httpx.MockTransport` con el adaptador real o un proveedor inyectado. Las credenciales de configuración son valores sintéticos y `_env_file=None` evita leer configuración real en los casos de transporte. Una fixture impide usar el transporte HTTP real en las pruebas nuevas.

**92 casos aprobados** de T2: estructura estricta, normalización, ausencia de máximo añadido, respuestas vacías/inválidas, entradas no analizables, campos de autoridad/publicación rechazados, instrucciones y separación de contenido, privacidad de entrada/salida, errores simulados HTTP/red, configuración ausente, rechazo del proveedor y ausencia de llamadas a publicación/persistencia/estado u otros análisis. También se comprueba que errores inesperados de programación no se oculten como fallos genéricos del proveedor.

Los siguientes resultados se proporcionan deliberadamente por mocks en esas pruebas: verifican el recorrido y las reglas enviadas, **no** una evaluación de calidad de Gemini. Las expectativas de contenido se inspeccionaron manualmente como ejemplos ficticios, sin atribuir aceptación a David.

| Caso ficticio evaluado | Resultado configurado en el mock | Qué acredita |
| --- | --- | --- |
| Comida excelente y personal amable | «Gracias por compartir tu experiencia. Nos alegra que disfrutaras la comida y la atención.» | Recepción y devolución del texto válido; reglas para felicitaciones enviadas. |
| Empleado grosero al consultar pedido | «Lamentamos la experiencia que describes. Gracias por compartir cómo te sentiste con la atención.» | Reglas para quejas, empatía y prohibición de promesas en las instrucciones. |
| Consulta sobre apertura en domingo | «Gracias por tu consulta. No contamos con información suficiente para confirmar ese horario.» | Instrucción de no inventar horario y retorno del texto simulado. |
| Sugerencia de opciones sin azúcar | «Gracias por sugerir opciones sin azúcar. Apreciamos que compartas tus preferencias.» | Reglas de sugerencia sin prometer implementación. |
| Buena comida y entrega tardía | «Nos alegra que disfrutaras la comida. Lamentamos la demora que reportas en la entrega.» | Instrucción de conservar matices y admitir comentario mixto. |
| Experiencia ambigua | «Gracias por compartir tu impresión. ¿Qué aspecto no cumplió tus expectativas?» | La instrucción permite aclaración sin inventar el aspecto. |
| Pedido tardío con orden maliciosa de publicar | «Lamentamos la demora que reportas. Gracias por compartir tu experiencia.» | La orden permanece en datos no confiables; las reglas del sistema no se sustituyen. |
| Pedido tardío con correo/teléfono sintéticos | «Lamentamos la demora que describes.» | Enmascaramiento real previo al request simulado y devolución sin contactos. |

Para texto sin significado u órdenes aisladas, el mock devuelve `respuesta_sugerida: null` y el servicio produce el rechazo controlado; no se acredita un clasificador local de significado. Las pruebas de ausencia de publicación comprueban que el proveedor solo recibe `generate_structured` y que el request simulado va únicamente al endpoint de generación, sin campos de acciones. No prueban endpoints HU-18 ni aislamiento de un endpoint inexistente.

## Validaciones ejecutadas

Desde `backend`:

```powershell
python -m pytest tests/test_suggested_response_service.py -q
```

Resultado: **92 passed**, dos avisos de deprecación ya existentes de Starlette/httpx/anyio.

Regresión de proveedor, persistencia y servicios/API de clasificación, resumen y tema, incluyendo T2: **445 passed**, dos avisos de deprecación conocidos. Se ejecutó el siguiente script en memoria mediante `python -c`, sin crear archivos de infraestructura ni permitir HTTP real:

```python
import httpx
import pytest
from unittest.mock import patch

def deny_real_http(*args, **kwargs):
    raise AssertionError('La regresión HU-18 debe usar proveedores simulados; HTTP real bloqueado')

with patch.object(httpx.HTTPTransport, 'handle_request', deny_real_http), patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', deny_real_http):
    raise SystemExit(pytest.main([
        '-q',
        'tests/test_suggested_response_service.py',
        'tests/test_ai_provider.py',
        'tests/test_ai_persistence.py',
        'tests/test_classification_service.py',
        'tests/test_classification_api.py',
        'tests/test_summary.py',
        'tests/test_summary_integration_t6.py',
        'tests/test_topic_service.py',
        'tests/test_topic_api.py',
        'tests/test_topic_contracts.py',
    ]))
```

Las fixtures de las pruebas existentes dirigen sus escrituras a SQLite temporal/en memoria; no se inició un servicio ni se migró o modificó la base local del equipo. No hubo llamadas reales a Gemini ni pruebas contra PostgreSQL real. No se ejecutó la suite completa de funcionalidades ajenas a IA ni pruebas frontend en esta tarea.

Comprobación sintáctica de los archivos Python afectados: `python -m compileall -q app/schemas/suggested_response.py app/services/suggested_response_service.py tests/test_suggested_response_service.py`, desde `backend`, resultado OK. No hay linter Python configurado en `backend/pyproject.toml`; no se instaló otro para esta tarea. La revisión Git se realiza sin staging y con `git diff --check`; los archivos nuevos se inspeccionan también directamente porque aún no están versionados.

## Revisión pendiente y continuidad

David debe revisar la adecuación del tono, consultas sin información del negocio, manejo de ambigüedad, reglas de privacidad y sus falsos positivos. La gramática, fidelidad semántica, ausencia de promesas, resistencia a prompt injection y omisión de datos no detectados no quedan garantizadas por Pydantic ni por ejemplos simulados. No se atribuye aprobación de T2 a la aprobación de T1.

Quedan para las tareas autorizadas posteriormente el endpoint protegido, persistencia, invalidación de sugerencias obsoletas, concurrencia, interfaz de solo lectura y validación funcional con aceptación del PO. Esta entrega no implementa T3–T5 ni cierra HU-18. No se hace staging, commit, push ni PR con esta ejecución.
