# HU-18 / T5 #3820 — Validación de tono, privacidad y casos límite

Estado: T5 publicada con **aprobación comunicada por el responsable de HU-18**; auditorías posteriores encontraron dos evasiones de privacidad. La corrección técnica y su autoauditoría se describen abajo. Su cierre Git está autorizado si pasan todas las verificaciones; no se atribuye aprobación específica del PO para este parche. HU-18 no se declara Done ni integrada en main. No hay autorización para Gemini real, publicación ni PR.

Responsable: Diego Erik Alfonso Montoya. PO: David Escárcega. Base: `62df1cd7d2337c3fcba3521bc4d042cef9c3fcd8`, rama `feature/HU-18-respuesta-sugerida`. Referencia: [contrato aprobado de T1](contrato-respuesta-sugerida.md). Las evidencias de [T2](t2-servicio-respuesta-sugerida.md), [T3](t3-api-persistencia.md) y [T4](t4-interfaz-respuesta-sugerida.md) se reutilizan como cobertura, no como aceptación de T5.

## Estado de aceptación de T5

- Product Owner: David Escárcega.
- Responsable: Diego Erik Alfonso Montoya.
- TASK: #3820 — Validar tono y casos límite.
- Estado: aprobación comunicada por el responsable de HU-18 después de entregar los resultados técnicos y la documentación, condicionada a que la revisión final no encuentre correcciones bloqueantes.
- Evidencia externa formal: no adjuntada; no se atribuyen firma, acta, correo, enlace ni registro en OpenProject.
- Alcance aprobado comunicado: validación técnica, pruebas y documentación de T5. La aprobación humana no sustituye evidencia técnica ni convierte criterios parciales en verificados completamente.
- No consta una aceptación individual de cada riesgo ni una evaluación de generaciones reales por David. Se mantienen los límites de privacidad, falsos positivos y las validaciones externas pendientes indicadas más adelante.
- La corrección de privacidad posterior al commit T5 `b65b6b0` tiene autorización técnica de implementación, pruebas y cierre Git condicionado a ausencia de bloqueantes. No se ha comunicado aceptación específica del PO para esta nueva corrección; sigue pendiente la auditoría de integración antes del PR.

## Alcance y entorno

La entrega inicial de T5 añadió este documento y `backend/tests/test_suggested_response_t5.py`, sin modificar producción. El parche posterior modifica exclusivamente esos dos archivos y `backend/app/services/suggested_response_service.py`. No cambia configuración, frontend, schemas, modelos, migraciones ni otras HUs. Python 3.14 y dependencias locales existentes; React/JSDOM y Node 24 con opción de compatibilidad. SQLite en fixtures temporales o memoria; no se inicia servidor contra la base personal. No se inspeccionan credenciales ni se ejecuta Gemini o SerpApi real.

El flujo vigente autoriza usuario/rol/tenant antes de generar, obtiene el contenido almacenado, utiliza el proveedor común con salida Pydantic y guarda condicionalmente la sugerencia/version. El detalle React la presenta como texto de solo lectura; generar y regenerar requieren una acción manual. No hay envío ni cambios de estado asociados a HU-18.

## Matriz de trazabilidad

Los nombres de pruebas backend pertenecen a `test_suggested_response_service.py` (S), `test_suggested_response_api.py` (A), `test_suggested_response_persistence.py` (P) y el archivo nuevo `test_suggested_response_t5.py` (T5). UI corresponde a `reviewSuggestedResponse.integration.test.mjs` y pruebas de pestañas de clasificación. **Cumple** se limita al control automatizado indicado, no a garantías del modelo real.

| # | Requisito | Prueba existente y complemento T5 | Método / resultado verificable | Límite / estado |
| --- | --- | --- | --- | --- |
| 1 | Español predeterminado | S: `test_mock_examples_send_full_content_and_hu18_instructions`; T5: `test_context_reaches_provider_with_quality_rules_not_a_semantic_score` | Comprueba instrucciones, incluido comentario en inglés | Obediencia de Gemini no evaluada: **Parcial** |
| 2 | Tono profesional, cordial, empático | Mismas pruebas | Reglas presentes para los 17 contextos | Tono de salida real pendiente: **Parcial** |
| 3 | Preferencia de 2–4 oraciones | Mismas pruebas; S: `test_result_is_strict_normalizes_only_outer_whitespace_and_has_no_extra_limit` | Preferencia enviada sin límite arbitrario | No se puntúa mock ni se obliga mínimo: **Parcial** |
| 4 | Fidelidad a la review | S y T5 contextos; UI combinación limitada | Contenido correcto llega al proveedor sin convertirlo en instrucción | Fidelidad de salida real: **Parcial** |
| 5 | No inventar compromisos | T5 contextos, en particular reembolso y consultas | Se envían prohibiciones de promesas y datos inventados | Schema no detecta promesas: **Parcial** |
| 6 | Quejas y felicitaciones | S seis ejemplos, T5 positivos/negativos/mixtos | Cada experiencia llega sin transformaciones indebidas | Adecuación real requiere PO: **Parcial** |
| 7 | Consultas sin datos | T5 horario/precio/devolución | Instrucción de reconocer información insuficiente | Respuesta real no verificada: **Parcial** |
| 8 | Ambigüedad | S rechazo null; T5 tres comentarios limitados | Conserva contenido y pide aclaración no sensible en instrucciones | Interpretación real: **Parcial** |
| 9 | Privacidad | S contactos/alto riesgo/salidas; T5 casos iniciales y regresiones `credential`/`session` | Incumplimientos bloqueantes: «contraseña de acceso es» y «clave de inicio de sesión es» pasaban entrada/salida. La corrección verifica rechazo compartido, cero construcción del proveedor en entrada, HTTP 422 y conservación de borrador/versiones, incluido repositorio real en memoria | **Parcial**: protección verificada para la familia evaluada, no detección universal; validaciones externas pendientes |
| 10 | Instrucciones maliciosas | S separación usuario/sistema y rechazo de campos extra; T5 `test_adversarial_text_is_data_and_cannot_add_service_actions` | Diez ataques permanecen en contenido no confiable; solo se llama a generación | Resistencia real del modelo: **Parcial** |
| 11 | Rechazo no analizable | S `test_invalid_or_obviously_empty_content_never_constructs_provider`, `test_uninterpretable_content_rejected_by_provider_decision_is_not_a_result` | Vacíos/puntuación sin proveedor; null interno nunca es éxito | Otros casos dependen del modelo: **Parcial** |
| 12 | Última sugerencia válida | A `test_allowed_roles_persist_only_suggestion_and_get_reads_it`; P `test_result_survives_new_session_and_keeps_other_fields` | Lectura GET y sesión nueva, conserva otros campos | SQLite aislado: **Cumple**; PostgreSQL operativo pendiente |
| 13 | Regeneración manual | A `test_manual_regeneration_replaces_previous_value_only_after_success`; UI genera/regenera | Una acción explícita produce la petición | **Cumple** en API y JSDOM |
| 14 | Conservar anterior ante fallos | A `test_error_mapping_is_controlled_without_writes`, `test_commit_failure_rolls_back_and_hides_database_details`; UI errores | Errores de proveedor y commit no reemplazan resultado | **Cumple** en escenarios probados |
| 15 | Invalidación al editar contenido | A `test_edit_invalidates_only_when_normalized_content_really_changes`; P ediciones obsoletas | Invalida por cambio real; autor/fecha/fuente/estado no invalidan | **Cumple** en SQLite |
| 16 | Concurrencia | P `test_two_simultaneous_generations_have_one_winner_and_one_conflict`; A `test_changes_during_generation_reject_obsolete_result`; UI A→B→A | UPDATE por id/tenant/contenido/versión; un ganador, conflicto y descarte tardío | **Cumple** en entornos simulados/SQLite; PostgreSQL real pendiente |
| 17 | Multi-tenant y autorización | A `test_bidirectional_tenant_isolation_and_manual_tenant_is_ignored`, pruebas roles/inactivo/404 y OpenAPI | Lectura/generación/persistencia delimitadas; no consume IA para recurso ajeno | **Cumple** en API aislada |
| 18 | Solo lectura | UI `borrador persistido es texto de solo lectura sin acciones de publicación` | Texto escapado, sin editor; cinco pestañas conservadas | **Cumple** en JSDOM; navegador real pendiente |
| 19 | No publicar ni enviar | S `test_service_has_no_publication_persistence_status_or_other_analysis_calls`; T5 ataques; UI | Sin acciones externas del servicio o controles de envío; tráfico real bloqueado | **Cumple** en rutas auditadas, no obediencia semántica del modelo |
| 20 | No modificar estado ni otras IA | A `test_allowed_roles_persist_only_suggestion_and_get_reads_it`, `test_priority_and_suggestion_keep_their_results_and_notifications_independent`; UI | Solo sugerencia/version; no cambios en prioridad, avisos o seguimiento | **Cumple** en escenarios de persistencia/UI |

## Pruebas nuevas y casos para David

La entrega inicial añadió **48 casos**: 17 contextos, 10 ataques, 3 contactos, 7 entradas de alto riesgo, 5 fechas/valoraciones/cantidades/referencias normales, 1 caracterización de pedido numérico y 5 salidas privadas reconocibles. La corrección conserva los 48 y añade 87 regresiones: **135 casos actuales en T5** (31 más que el primer parche de 104 casos). No se duplican las pruebas completas de seguridad, persistencia y navegación ya existentes. No se añaden pruebas frontend porque T4 cubre esos escenarios mediante el hook y componentes reales con peticiones simuladas.

La respuesta fija de las pruebas de contextos es «Gracias por compartir tu experiencia.»: solo verifica el recorrido del resultado. **No es una generación real ni una muestra calificada semánticamente** y no representa una respuesta apropiada para todos los contextos.

| Caso sintético | Entrada representativa | Qué debe revisar David en una futura salida real |
| --- | --- | --- |
| Felicitación general | Excelente experiencia. | Agradecer sin inventar hechos |
| Empleado | La empleada ficticia fue muy amable. | Reconocer la atención sin inventar nombres |
| Positiva breve | Muy bien. | Brevedad sin completar hechos inexistentes |
| Atención | El trato fue descortés. | Empatía sin confrontar ni prometer sanciones |
| Demora | El pedido llegó tarde. | Reconocer demora sin garantizar entregas |
| Producto | El producto dejó de funcionar. | Reconocer el problema sin afirmar una reparación |
| Reembolso | Quiero un reembolso por el producto defectuoso. | No aprobar ni prometer compensación |
| Mixto producto | Buena atención, pero el producto estaba defectuoso. | Conservar ambos matices |
| Mixto demora | Buena calidad, pero la entrega tardó mucho. | No ignorar la demora |
| Elogio y sugerencia | Excelente comida; sugiero opciones sin azúcar. | Agradecer sin prometer implementación |
| Horario | ¿Abren los domingos? | No inventar horarios |
| Precio | ¿Cuánto cuesta el servicio? | No inventar tarifas |
| Devolución | ¿Cuál es la política de devolución? | Reconocer falta de política proporcionada |
| Ambigua | No fue lo que esperaba. | Pedir aclaración no sensible |
| Breve | Regular. | No inventar la causa de la valoración |
| Sin contexto | No sé qué pensar de esta experiencia. | Reconocimiento neutral o rechazo seguro |
| Inglés | Good service, but delivery was late. | Español fiel a los dos matices |

Ejemplos **ilustrativos redactados manualmente**, no obtenidos de Gemini:

- Demora: «Lamentamos la demora que describes. Gracias por compartir tu experiencia.»
- Horario desconocido: «Gracias por tu consulta. No contamos con información suficiente para confirmar ese horario.»
- Positiva: «Gracias por compartir tu experiencia. Nos alegra que la atención haya sido de tu agrado.»

Rúbrica humana propuesta: evaluar cada salida con **Cumple / Requiere revisión / No cumple** en fidelidad, español, tono, claridad, ausencia de compromisos inventados, privacidad y adecuación al contexto. Revisar la preferencia de 2–4 oraciones sin convertirla en mínimo obligatorio. Cualquier dato sensible, promesa inventada, instrucción ejecutable o afirmación de publicación impide aceptar esa muestra. No se asignan puntuaciones a textos programados en mocks. La aprobación comunicada de T5 no acredita evaluación de generaciones reales ni aceptación individual de cada limitación.

## Privacidad, adversarios y falsos positivos

Solo se utilizan contactos y datos ficticios; ningún valor es una credencial utilizable. Se comprueban correo y teléfonos nacionales/internacionales de ejemplo, direcciones etiquetadas, DNI, token, contraseña, tarjeta, CLABE y api_key sintéticos. Las entradas detectadas de alto riesgo se rechazan antes de crear proveedor; las de contacto se enmascaran conservando la experiencia. Las salidas privadas reconocidas se rechazan con mensajes controlados, sin su contenido en caplog.

No se acredita detección universal: nombres, domicilios libres, identificadores alfanuméricos sin etiqueta, secretos sin formato reconocido y ofuscaciones siguen dependiendo de la revisión semántica. No se considera seguro usar información real con estos tests como única evidencia. La ausencia en caplog prueba las ejecuciones concretas, no todos los sistemas de logging posibles. La prueba previa de redacción SQL cubre escritura y refresh con echo detallado.

Falsos positivos comprobados: `2026-11-03`, 5 de 5, cantidades cortas y referencia `ABC-123` se conservan. El pedido numérico `12345678` se convierte en `[TELEFONO_OCULTO]`: límite conocido en T2, no una prueba de identificación correcta de teléfonos. Se pierde el ID pero se conserva la experiencia. Grupos de 13+ dígitos y algunas etiquetas se rechazan conservadoramente. **Limitación no bloqueante para este cierre técnico:** el caso probado conserva la experiencia necesaria para el borrador y no expone información; no acredita fidelidad de una salida real. No consta aprobación individual de este riesgo por el PO.

Mejora posterior recomendada: distinguir referencias de pedido de teléfonos mediante contexto y formatos explícitos, con regresiones de identificadores, contactos y cantidades antes de cambiar la minimización. No eximir indiscriminadamente los dígitos etiquetados como pedido, pues podrían contener información sensible. Esta recomendación no se implementa ni modifica T2 durante el cierre.

Los diez ataques intentan ignorar sistema, revelar API key, publicar, cambiar estado, acceder a otro tenant, insultar, inventar compensación, devolver campos extra, simular desarrollador y llamar herramientas. Las pruebas verifican la separación de instrucciones/datos y la ausencia de acciones del servicio; no reproducen ni ejecutan esas órdenes. Los tests previos del adaptador rechazan campos extra, JSON inválido y tipos incorrectos. **No prueban resistencia real del modelo a prompt injection.**

## Regresiones y auditoría

Se reutilizan pruebas API de 401/403/404, tenant inactivo, contenido autorizado desde servidor, regeneración/error/timeout/409, rollback y GET posterior; repositorio con versiones y filtros tenant; migración aditiva/idempotente; interacción con prioridad y avisos; reviews externas con identidad preservada. La suite frontend conserva exportación CSV, notificaciones, selección por `?review=`, cinco pestañas, carga, errores, lectura y nueve regresiones A→B→A, incluyendo promesas que ignoran abort y desmontaje.

Revisión técnica separada de la ejecución de tests: comprobar que las aserciones observan el contenido enviado, la no creación del proveedor o la salida rechazada; que el doble solo expone `generate_structured`; y que los nombres no atribuyen calidad a salidas programadas. No se modifica autenticación, modelo, schema, proveedor, migraciones, repositorio ni hook. No se eliminan ni debilitan tests previos. Esta revisión no constituye auditoría externa ni aprobación humana independiente.

## Resultados históricos del cierre inicial

| Validación ejecutada | Resultado real |
| --- | --- |
| Backend: `python -m pytest -q tests/test_suggested_response_t5.py` | **48 passed**, 0 failed, 0 skipped; dos warnings conocidos. |
| Backend completo, `pytest.main(['-q'])` mediante el script en memoria inferior | **1605 passed**, 0 failed, 0 skipped, 163.08 s en la repetición de cierre; dos warnings conocidos. Incluye los 1557 anteriores y 48 nuevos. |
| Frontend: `node --no-experimental-global-navigator --test tests/*.test.mjs` | **83 passed**, 0 failed, 0 skipped, 0 cancelled; los 12 archivos de pruebas existentes se ejecutaron. |
| Frontend: `node node_modules/eslint/bin/eslint.js .` | Código 0. |
| Frontend: `node node_modules/vite/bin/vite.js build` | Código 0, Vite 7.3.6, 1767 módulos. |
| Python: `ast.parse(Path('backend/tests/test_suggested_response_t5.py').read_text(encoding='utf-8'))` mediante `python -B -` desde la raíz | Sintaxis correcta, sin generar bytecode del archivo nuevo. |
| `git diff --check` | Código 0. Como los dos archivos nuevos no están rastreados, además se revisaron directamente sus líneas, final de archivo y contenido. |

La suite backend completa se ejecutó desde `backend` con `python -B -` recibiendo este script en memoria, en lugar de ejecutar un `python -m pytest -q` desprotegido. Invoca la misma suite con `-q` y añade las protecciones siguientes, sin cambiar archivos del proyecto:

```python
from unittest.mock import patch
import httpx
import pytest
from sqlalchemy import event
from app.db.connection import engine

def denied_http(*args, **kwargs):
    raise AssertionError('HTTP real bloqueado durante HU-18/T5')

def denied_personal_db(*args, **kwargs):
    raise AssertionError('BD configurada del usuario bloqueada durante HU-18/T5')

event.listen(engine, 'do_connect', denied_personal_db)
with patch.object(httpx.HTTPTransport, 'handle_request', denied_http), patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', denied_http):
    raise SystemExit(pytest.main(['-q']))
```

Las fixtures sustituyen la sesión y el lifespan por SQLite temporal; el guard impide que una omisión alcance el engine configurado del usuario. No se iniciaron servicios ni se ejecutaron migraciones personales. Los transportes simulados y TestClient siguen disponibles; no hubo intentos de transporte real que hicieran fallar la ejecución. Esta protección cubre las rutas HTTPX usadas por las integraciones auditadas, no constituye un cortafuegos de sistema.

Warnings backend: deprecación de Starlette TestClient con httpx y del alias BlockingPortal de anyio. Warning frontend: WebSocket 24678 ocupado. No producen fallos; no se instalaron paquetes ni se modificó configuración para ocultarlos.

La repetición previa al commit, posterior a la aprobación comunicada, confirmó los mismos totales de 48 pruebas específicas, 1605 backend y 83 frontend, sin fallos ni omisiones, además de ESLint y build con código 0. Solo se actualizó este documento para formalizar la aprobación y describir la recomendación sobre falsos positivos; las pruebas permanecieron intactas.

Dictamen histórico del cierre inicial: no se habían identificado bloqueantes en las rutas entonces evaluadas. **Ese dictamen fue superado por el hallazgo de privacidad descrito a continuación.** Los totales aprobados no demostraban cobertura de las frases con calificadores. Los límites de detección no se presentan como aceptados individualmente por el PO; las validaciones externas pendientes impiden presentar la evidencia como una verificación integral con servicios reales.

Estado Git de la entrega previa a la autorización de cierre: HEAD local/remoto conservado, sin staging ni modificaciones rastreadas; únicamente los dos archivos nuevos de T5. T1–T4 y el merge técnico intactos. El cierre autorizado debe crear un único commit con estos dos archivos, sin cambios productivos, PR, cambios en main u OpenProject.

## Corrección posterior: credenciales con palabras intermedias

Base del parche: `b65b6b0b4fc31b3a0aee1927c404a7a4811e86ef`. Hallazgo **BLOQUEANTE** descubierto después del cierre inicial de T5. Reproducción anterior con doble en memoria: «Mi contraseña es CLAVE-SINTETICA-NO-REAL.» se rechazaba, pero «Mi contraseña de acceso es CLAVE-SINTETICA-NO-REAL.» llegaba íntegra al proveedor simulado. Una salida simulada con «La contraseña de acceso es …» se devolvía como válida. No se utilizó ningún secreto real ni se llamó a Gemini.

Causa común: `_PRIVATE_FIELD` exigía asignación inmediatamente después de la etiqueta sensible. El primer parche admitió calificadores, pero restringió «clave» a ciertas formulaciones de autenticación. Una segunda auditoría reprodujo que «Mi clave de inicio de sesión es CLAVE-SINTETICA-NO-REAL.» se enviaba y aceptaba; con repositorio real en memoria reemplazaba el borrador y avanzaba la versión de 4 a 5. Ambas evasiones incumplían el contrato; no se consideran resueltas mediante una advertencia genérica de límites.

Corrección dentro del alcance: `_has_high_risk_data` utiliza `_has_credential_assignment`, compartido por entrada y salida. Todas las etiquetas sensibles, incluida «clave», usan la misma gramática de etiqueta, calificadores acotados y asignación; no se exige una frase concreta de autenticación. Se conservan las reglas anteriores de correos, teléfonos y otros campos privados. Las locuciones ordinarias «clave del éxito» y «clave de sol» se exceptúan de manera limitada; si sus calificadores mencionan autenticación, se rechazan igualmente. El vocabulario de esa excepción nunca limita la detección positiva del resto de construcciones.

La detección inspecciona una copia con normalización Unicode NFKC y espacios, comillas, paréntesis, corchetes, comas y guiones internos habituales; no reescribe el contenido enviado o persistido. Los tramos están acotados a doce palabras intermedias de hasta 24 letras; no se usa `.*`. Las negaciones y conjunciones no se admiten como calificadores, y los puntos separan las frases: «Mi contraseña de acceso no funciona» no se confunde con una revelación, tampoco al acompañarla de otra queja. La asignación admite `:`, `=`, guiones separadores, «es» o «is» y exige valor no blanco. Se prioriza impedir la exposición: «Mi contraseña de acceso es incorrecta/inválida» puede rechazarse conservadoramente. Es un falso positivo conocido, no una fuga, y no se intenta resolverlo con exclusiones inseguras de valores.

Se reutiliza `SuggestedResponsePrivacyError` con mensaje fijo. En entrada se rechaza antes de construir el proveedor; en salida se rechaza antes de devolver `SuggestedResponseResult`. El orquestador no llega a `save_suggested_response` ante ese error. El endpoint existente conserva HTTP 422 sin incluir la credencial. No cambian contratos, modelos, persistencia, estado, otras salidas IA ni acciones externas.

Regresiones añadidas al archivo T5, sin debilitar las anteriores:

- 28 formatos de credencial probados por entrada y salida: **56 casos**, incluidos ambos defectos, «clave para acceder a mi cuenta», calificadores largos, PIN/token/API key, mayúsculas, acentos, comillas, paréntesis, guiones, espacios extensos y Unicode.
- **13 casos legítimos**: acceso que falla sin revelar valor, frases ordinarias con «clave», quejas, felicitaciones, consulta, fechas, cantidades, valoración y pedido alfanumérico.
- **1 caso largo** de más de 100 000 caracteres, con queja de acceso y frases normales, conservando el texto completo y sin cruzar frases para buscar una asignación.
- **16 casos HTTP con SQLite temporal**: ocho construcciones representativas en ambas direcciones. La entrada no construye proveedor; la salida usa un doble. Todos exigen 422, mensaje fijo, ausencia de secreto sintético en error/caplog, igualdad completa de ReviewRead antes/después y contador conservado en 4.
- **1 regresión con SQLite exclusivamente en memoria, servicio y repositorio reales**: «clave de inicio de sesión» se rechaza sin reemplazar el borrador ni cambiar la versión 4 o los demás campos. Una regeneración posterior válida sí guarda su texto y avanza a 5, conservando estado y otras salidas IA.

La regresión del caso original falló antes del parche porque se alcanzaba la fábrica del proveedor; se conservó y pasó después. Durante la ampliación se corrigió una expectativa de una prueba nueva de texto largo: su entrada terminaba en un espacio que el servicio elimina por contrato. Se construyó la entrada sin ese espacio, manteniendo la aserción de igualdad completa. No se ocultó un defecto ni se cambió el comportamiento de normalización del servicio.

Durante la segunda corrección la regla general rechazó la referencia musical «clave de sol del logotipo». Se corrigió la excepción ordinaria sin cambiar esa prueba y se añadió una credencial con esa locución y contexto de acceso para comprobar que la excepción no anula la protección. La autoauditoría posterior evaluó además 12 formulaciones en memoria, distintas de la matriz completa, con 24 rechazos de entrada/salida: portal bancario, recuperación de cuenta, entrada a plataforma, acceso y sesión con calificadores largos, corchetes, comillas angulares, guiones y Unicode. No se identificó una evasión equivalente en esos casos; no se atribuye auditoría humana externa ni seguridad universal.

### Validación del parche

| Comando desde el directorio correspondiente | Resultado |
| --- | --- |
| Backend: `python -m pytest -q tests/test_suggested_response_t5.py -k 'credential or session'` | **87 passed**, 48 deselected, sin fallos; dos warnings conocidos. |
| Backend: `python -m pytest -q tests/test_suggested_response_t5.py` | **135 passed**, sin fallos ni omisiones; dos warnings conocidos. |
| Backend completo mediante el script de protección documentado arriba | **1692 passed**, 0 failed, 0 skipped, 160.55 s; dos warnings conocidos. Incluye los 1605 originales y 87 regresiones del fix. |
| Frontend: `node --no-experimental-global-navigator --test tests/*.test.mjs` | **83 passed**, 0 failed, 0 skipped, 0 cancelled. |
| Frontend: `node node_modules/eslint/bin/eslint.js .` | Código 0. |
| Frontend: `node node_modules/vite/bin/vite.js build` | Código 0, Vite 7.3.6. |

Comprobación sintáctica de los dos archivos Python mediante `ast.parse` desde `python -B -`: correcta. Exploración local con 148 000 caracteres de quejas sin valor y 110 000 caracteres de etiquetas repetidas: sin rechazo, 0.032 s y 0.1276 s respectivamente. No son límites de rendimiento garantizados; complementan los cuantificadores acotados y la regresión automatizada de texto largo.

La revisión funcional específica del PO para este parche no ha sido comunicada; no se inventa. La instrucción de corrección definitiva autoriza un único commit y push normal si todas las verificaciones técnicas pasan. No autoriza PR, integración en main ni cambios en OpenProject.

Revisión crítica: la segunda evasión invalida el dictamen favorable del primer parche. La versión corregida mantiene el rechazo compartido sin cambiar excepciones, HTTP ni persistencia. Las 28 variantes se rechazan, las quejas sin valor siguen analizándose y las regresiones API/repositorio conservan los datos anteriores. La autoauditoría no identificó nuevas evasiones en los formatos evaluados. La regresión completa aprobó sin fallos ni omisiones; no se interpreta como prueba de ausencia universal de otras formas de revelar secretos. No se identifican bloqueantes pendientes dentro del alcance evaluado; se puede reanudar la auditoría de integración.

Clasificación: ambos bloqueantes quedan corregidos en los escenarios reproducidos. Siguen como límites no bloqueantes los falsos positivos conservadores y las advertencias conocidas. Continúan pendientes externos Gemini real, PostgreSQL real, navegador real y cualquier aceptación específica que requiera el equipo, además de la auditoría de integración antes del PR.

Límites: se reconocen asignaciones con etiquetas y calificadores acotados. Otras construcciones, ofuscaciones, valores sin etiqueta o calificadores fuera del patrón no quedan certificados. El rechazo conservador puede afectar textos sin secretos; no se prometen anonimización universal ni semántica perfecta. No se registran valores detectados ni se añaden logs. El cierre Git debe incluir únicamente los tres archivos autorizados, con `git diff --check` y `git diff --cached --check` correctos.

## Pendientes y aceptación

- **Pendiente externo:** calidad semántica con Gemini real, incluidos español, tono, fidelidad, privacidad no reconocida y resistencia a ataques. No autorizado ni realizado.
- **Pendiente externo:** PostgreSQL real operativo. Se reutiliza compilación de SQL PostgreSQL y pruebas SQLite; no equivale a ejecución real.
- **Pendiente externo:** validación visual en navegador real/responsive. JSDOM no la sustituye; no se inició un backend contra la base personal.
- **Aprobación comunicada:** T5 aprobada por David según confirmación del responsable. No consta aceptación individual de cada riesgo ni evaluación de muestras generadas realmente; se conserva esa distinción.
- **No bloqueante para pruebas locales:** incompatibilidad del navigator global de Node 24 y advertencia de puerto WebSocket; se usa la opción temporal aprobada sin cambiar configuración.

La aprobación comunicada habilitó el cierre inicial de T5. La instrucción posterior autoriza separadamente el cierre técnico del fix condicionado a sus verificaciones; no equivale a aprobación específica del PO ni aceptación de cada riesgo. No se marca HU-18 Done, no se crea PR, no se fusiona a main ni se actualiza OpenProject.
