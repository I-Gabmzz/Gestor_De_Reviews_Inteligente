# HU-18 / T5 #3820 — Validación de tono, privacidad y casos límite

Estado: pruebas locales y revisión técnica finalizadas; **aprobación de T5 comunicada por el responsable de HU-18**, sujeta a ausencia de bloqueantes en la revisión final. HU-18 no se declara Done ni integrada en main. No hay autorización para Gemini real, publicación ni PR.

Responsable: Diego Erik Alfonso Montoya. PO: David Escárcega. Base: `62df1cd7d2337c3fcba3521bc4d042cef9c3fcd8`, rama `feature/HU-18-respuesta-sugerida`. Referencia: [contrato aprobado de T1](contrato-respuesta-sugerida.md). Las evidencias de [T2](t2-servicio-respuesta-sugerida.md), [T3](t3-api-persistencia.md) y [T4](t4-interfaz-respuesta-sugerida.md) se reutilizan como cobertura, no como aceptación de T5.

## Estado de aceptación de T5

- Product Owner: David Escárcega.
- Responsable: Diego Erik Alfonso Montoya.
- TASK: #3820 — Validar tono y casos límite.
- Estado: aprobación comunicada por el responsable de HU-18 después de entregar los resultados técnicos y la documentación, condicionada a que la revisión final no encuentre correcciones bloqueantes.
- Evidencia externa formal: no adjuntada; no se atribuyen firma, acta, correo, enlace ni registro en OpenProject.
- Alcance aprobado comunicado: validación técnica, pruebas y documentación de T5. La aprobación humana no sustituye evidencia técnica ni convierte criterios parciales en verificados completamente.
- No consta una aceptación individual de cada riesgo ni una evaluación de generaciones reales por David. Se mantienen los límites de privacidad, falsos positivos y las validaciones externas pendientes indicadas más adelante.

## Alcance y entorno

Solo se añaden este documento y `backend/tests/test_suggested_response_t5.py`. No se modifica producción, configuración, frontend ni pruebas previas. Python 3.14 y dependencias locales existentes; React/JSDOM y Node 24 con opción de compatibilidad. SQLite en fixtures temporales o memoria; no se inicia servidor contra la base personal. No se inspeccionan credenciales ni se ejecuta Gemini o SerpApi real.

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
| 9 | Privacidad | S contactos/alto riesgo/salidas; T5 contactos combinados, siete rechazos, cinco salidas y falsos positivos | Minimización y rechazo de patrones concretos, mensajes controlados y caplog | Datos no reconocidos y ofuscaciones no cubiertos universalmente: **Parcial** |
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

Se añaden **48 casos**: 17 contextos, 10 ataques, 3 contactos, 7 entradas de alto riesgo, 5 fechas/valoraciones/cantidades/referencias normales, 1 caracterización de pedido numérico y 5 salidas privadas reconocibles. No se duplican las pruebas completas de seguridad, persistencia y navegación ya existentes. No se añaden pruebas frontend porque T4 cubre esos escenarios mediante el hook y componentes reales con peticiones simuladas.

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

## Resultados de ejecución

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

Dictamen de la revisión técnica: no se identificaron nuevos defectos de producción, regresiones ni bloqueantes técnicos en las rutas evaluadas. Se revisaron controles de acceso, escritura atómica, invalidación, límites de privacidad, pruebas y documentación además del resultado del runner. Los límites de detección de T2 no se presentan como corregidos ni como aceptados individualmente por el PO. La aprobación comunicada habilita el cierre técnico de T5 si la repetición de validaciones sigue siendo satisfactoria; las validaciones externas pendientes impiden presentar la evidencia como una verificación integral con servicios reales.

Estado Git de la entrega previa a la autorización de cierre: HEAD local/remoto conservado, sin staging ni modificaciones rastreadas; únicamente los dos archivos nuevos de T5. T1–T4 y el merge técnico intactos. El cierre autorizado debe crear un único commit con estos dos archivos, sin cambios productivos, PR, cambios en main u OpenProject.

## Pendientes y aceptación

- **Pendiente externo:** calidad semántica con Gemini real, incluidos español, tono, fidelidad, privacidad no reconocida y resistencia a ataques. No autorizado ni realizado.
- **Pendiente externo:** PostgreSQL real operativo. Se reutiliza compilación de SQL PostgreSQL y pruebas SQLite; no equivale a ejecución real.
- **Pendiente externo:** validación visual en navegador real/responsive. JSDOM no la sustituye; no se inició un backend contra la base personal.
- **Aprobación comunicada:** T5 aprobada por David según confirmación del responsable. No consta aceptación individual de cada riesgo ni evaluación de muestras generadas realmente; se conserva esa distinción.
- **No bloqueante para pruebas locales:** incompatibilidad del navigator global de Node 24 y advertencia de puerto WebSocket; se usa la opción temporal aprobada sin cambiar configuración.

Con la aprobación específica comunicada, el staging, commit y push de T5 quedan condicionados a repetir satisfactoriamente las pruebas y la auditoría final, sin bloqueantes. No se marca HU-18 Done, no se crea PR, no se fusiona a main ni se actualiza OpenProject.
