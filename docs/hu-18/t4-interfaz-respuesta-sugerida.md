# HU-18 / T4 #3819 — Borrador de respuesta sugerida en React

Estado: implementada y probada con solicitudes simuladas; pendiente de revisión y autorización de commit. No se inicia T5.

Base de trabajo: `72c916fedcd6933c15fc93991555527f79c47ef6`, rama `feature/HU-18-respuesta-sugerida`. Se respeta el [contrato aprobado](contrato-respuesta-sugerida.md) y la [API de T3](t3-api-persistencia.md), sin modificar backend.

## Archivos y arquitectura

- `frontend/src/components/reviews/ReviewDetail.jsx`: quinta pestaña, «Respuesta sugerida», conservando clasificación, resumen, tema y prioridad; navegación por teclado y un panel visible a la vez. Integra los estados de generación con el bloqueo de las otras operaciones IA, edición y seguimiento.
- `frontend/src/hooks/useSuggestedResponse.js`: solicitud explícita, bloqueo de duplicados, cancelación y descarte de resultados obsoletos; errores y reinicio tras recarga.
- `frontend/src/utils/reviewSuggestedResponse.js`: validación de identidad y resultado textual no vacío, combinación limitada a `respuesta_sugerida` y mensajes controlados.
- `frontend/src/services/reviewService.js`: única operación nueva de consumo HTTP, reutilizando `apiClient`.
- `frontend/src/pages/ReviewsPage.jsx`: propaga permisos operativos existentes y combina el resultado en detalle y listado sin sobrescribir otros campos. La recarga explícita vuelve a consultar el detalle además del listado.
- `frontend/tests/reviewSuggestedResponse.integration.test.mjs`: dieciocho pruebas de T4 con React, JSDOM, Vite SSR y cliente HTTP simulado, incluidas nueve regresiones del ciclo de selección.
- `frontend/tests/reviewClassification.integration.test.mjs`: expectativa de pestañas y navegación End/Home ampliada a la quinta pestaña, conservando las comprobaciones anteriores.

No se añaden bibliotecas, configuración global ni una segunda capa de API. Las pestañas se distribuyen en dos columnas, tres desde el breakpoint sm, para acomodar los cinco controles.

## Flujo y contrato HTTP

El GET existente carga `respuesta_sugerida` persistida. La pestaña muestra «Borrador sugerido por IA — no enviado», texto de solo lectura y una aclaración de que no publica, envía ni modifica el seguimiento. Si no existe resultado, presenta un estado vacío.

Los roles operativos autorizados por la política frontend existente pueden pulsar «Generar sugerencia» o «Regenerar sugerencia». Un usuario sin ese permiso ve solamente el texto; el backend mantiene la autoridad de autenticación, roles y tenant.

`generateSuggestedResponse(reviewId, { signal })` realiza `POST /reviews/{reviewId}/respuesta-sugerida` mediante el cliente configurado bajo `/api/v1`. No envía body, query parameters, contenido, tenant, resultado IA ni estado. El token procede del interceptor existente. El timeout de esta operación es 150000 ms, siguiendo el patrón de prioridad y clasificación.

La respuesta ReviewRead se valida por id, tenant, contenido original y sugerencia textual no vacía. Se copia únicamente `respuesta_sugerida` a las entidades que coinciden. Estado, categoría, resumen, tema y prioridad de una respuesta antigua no sobrescriben los valores de la vista.

## Carga, errores y selección

La generación no se dispara al abrir la pestaña. Mientras hay una petición, muestra feedback accesible y bloquea duplicados y operaciones concurrentes de la misma vista. Cambiar de pestaña conserva la operación. Cambiar de review, tenant o contenido, cargar otra selección o desmontar el detalle cancela la petición; una respuesta tardía se ignora incluso si el adaptador simulado no respeta la cancelación.

La regeneración conserva el borrador visible hasta recibir un resultado válido. Los errores 401, 403, 404, 409, 422, 500, 502, 503 y 504 tienen mensajes comprensibles; errores de red y respuestas incompatibles muestran un mensaje de resultado no confirmado. No se muestran detalles internos ni se inventa un éxito.

Un 409 bloquea temporalmente la regeneración y ofrece «Recargar información». La acción reinicia el estado temporal e incrementa la clave de recarga de la página; se consulta de nuevo el listado con sus criterios y el detalle seleccionado. No hay regeneración automática. Se conserva la navegación por `?review=` y no se altera el callback de prioridad ni el evento de avisos. La exportación CSV mantiene su implementación.

## Evidencia de pruebas

Solo datos y tokens ficticios. Las peticiones se simulan mediante el adaptador Axios o dobles del cliente. No se inició backend ni se consumió Gemini o SerpApi reales.

Las nueve pruebas nuevas cubren:

1. Método y ruta, autenticación, ausencia de body/tenant/contenido y propagación de AbortSignal.
2. Texto persistido, escape de HTML, ausencia de editor y acciones de publicación/envío.
3. Primera generación y regeneración, conservando las otras salidas IA y el estado aunque el servidor simulado devuelva valores antiguos.
4. Loading, bloqueo de duplicados y de operaciones concurrentes.
5. Nueve errores HTTP, conservación del resultado y recarga controlada por conflicto.
6. Cancelación y descarte de respuestas tardías al cambiar id, tenant o contenido.
7. Rechazo de resultados ajenos, vacíos o estructuralmente incompatibles.
8. Lectura sin permiso de generación.
9. ReviewsPage real dentro de MemoryRouter con `?review=101`, consulta del detalle, generación, conservación de prioridad/estado/exportación y recuperación del resultado vigente tras 409.

Validación final desde `frontend`:

| Comando | Resultado |
| --- | --- |
| `node --no-experimental-global-navigator --test tests/*.test.mjs` | **83 passed, 0 failed**, sin canceladas ni omitidas; 18 pruebas de T4 (nueve originales y nueve regresiones) y 65 anteriores. |
| `node node_modules/eslint/bin/eslint.js .` | OK. |
| `node node_modules/vite/bin/vite.js build` | OK, Vite 7.3.6. |

La primera ejecución detectó dos problemas en expectativas de pruebas: el harness nuevo no habilitaba prioridad y la prueba anterior enumeraba cuatro pestañas. Se corrigieron el harness y la enumeración/navegación de cinco pestañas sin eliminar aserciones ni modificar reglas funcionales. La ejecución final pasa completa.

Permanece un aviso de WebSocket 24678 ocupado en la suite conjunta; no provoca fallos ni se cambió configuración Vite para ocultarlo. La opción de compatibilidad sigue siendo necesaria con Node 24; esta tarea no modifica el setup general.

## Corrección del ciclo de selección A → B → A

La auditoría posterior a la primera entrega reprodujo un defecto bloqueante: el hook cancelaba la petición y limpiaba su referencia, pero conservaba `operation`. Volver a una identidad anterior reactivaba su carga, conflicto o feedback antiguo. Una solicitud cancelada podía dejar controles bloqueados sin petición activa; un 409 podía reaparecer tras consultar datos vigentes.

La corrección queda limitada a `useSuggestedResponse.js`, sus pruebas y esta evidencia. El estado inicial de operación conserva la identidad del ciclo. Cuando cambia la identidad (id, tenant, contenido, incluida la ausencia de selección mientras carga), el hook sustituye condicionalmente el estado temporal por una operación vacía de la nueva selección. Es un ajuste durante render condicionado por el estado anterior: converge en el siguiente render y no depende de un efecto posterior para ocultar la carga antigua. Pasar por B descarta el estado de A; regresar a A inicia otro estado vacío aunque los valores originales coincidan.

Se mantiene un único mecanismo de descarte del estado de selección junto con la cancelación existente: el efecto sigue abortando y liberando la referencia al cambiar identidad o desmontar. Las respuestas solo se procesan si su controlador no está abortado y continúa siendo la solicitud activa. Una promesa antigua no puede reemplazar ni limpiar la referencia de una operación nueva. `reset()` conserva el mismo formato de estado vacío para la recarga explícita tras un 409 vigente.

La respuesta persistida no forma parte de este estado temporal: se sigue leyendo de `review.respuesta_sugerida` y no se borra al ajustar el hook. No se cambian servicios, contratos HTTP, otros hooks IA ni backend.

Nueve regresiones adicionales verifican:

1. A → B → A con generación pendiente: señal abortada, ausencia de carga fantasma, controles utilizables y nueva generación exitosa; el resultado viejo se descarta.
2. Rechazo tardío de la petición original mientras otra generación de A está activa: no introduce error ni cancela/oculta la carga nueva; solo se notifica el resultado nuevo.
3. 409 en A → B → A: no reaparece conflicto ni bloqueo y se permite regenerar conservando el borrador recuperado.
4. Error 503 en A → B → A: no reaparece el error y una nueva generación funciona.
5. Éxito anterior: al regresar se muestra el dato persistido vigente, sin recuperar el texto ni el feedback temporal de la visita anterior.
6. Cambio de contenido y retorno al original: cancela y descarta el resultado antiguo sin reactivar estados.
7. Cambio de tenant y retorno: misma protección, sin callbacks con el resultado viejo.
8. Doble clic de regeneración: una sola petición y conservación del borrador durante la espera.
9. Desmontaje con una promesa que ignora abort: señal cancelada y ningún callback de resultado tras resolverla.

Los casos directos del hook usan un harness React bajo StrictMode; los casos de controles usan ReviewDetail real. No se modifica el setup general de pruebas. La suite conjunta posterior pasó con **83 pruebas aprobadas y cero fallos**; ESLint y build también pasaron con los comandos de la tabla anterior. No se detectaron regresiones en las pruebas previas. Continúa el aviso de puerto WebSocket ocupado, sin fallo de tests.

Esta evidencia no representa aprobación del PO ni una validación semántica de Gemini. La corrección forma parte de T4 aún sin commit; no inicia T5 y no añade envío ni publicación.

## Límites y revisión

La validación UI fue automatizada con JSDOM; no acredita una inspección visual en navegador real ni la calidad semántica de Gemini. La autorización efectiva y persistencia pertenecen al backend de T3, sin cambios en esta tarea. No se repitió su suite backend porque no se modificó código backend.

No existe editor de borrador, botón de publicación, envío, mensajería ni cambio automático de estado. Los únicos controles nuevos generan/regeneran o recargan información. El resultado se presenta como referencia de IA y no como respuesta publicada.

T5 queda pendiente: tono, contenido adverso, privacidad y casos límite, revisión del PO y validaciones externas que correspondan. No se atribuye aprobación de T4 al PO. No se crea commit, push, PR ni se modifica OpenProject durante esta entrega.
