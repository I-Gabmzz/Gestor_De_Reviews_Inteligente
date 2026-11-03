# HU-21 — Evidencia de Task #3831: acceso real a SerpApi

## Identificación y alcance

- Historia: HU-21 — Integración con APIs externas (#3232).
- Task: #3831 — Comprobar fuente autorizada.
- Responsable: Gabriel Manjarrez.
- Descripción: «Proyecto/cuenta/permisos y lectura controlada sin secretos».
- Evidencia esperada: acceso real autorizado o bloqueo preciso.

Este documento registra una comprobación técnica de acceso.
No implementa consumo paginado, normalización, persistencia,
sincronización ni las Tasks #3832–#3835.

## Proveedor y autorización de la prueba

- Proveedor de acceso: SerpApi.
- Fuente original: Google Maps.
- Tipo: API comercial de terceros basada en extracción de información
  pública; no es una API oficial de Google.
- Cuenta Free, acceso API y 250 solicitudes disponibles:
  confirmados por Gabriel antes de ejecutar.
- Autorización: una solicitud, máximo cinco reseñas, hasta un crédito
  gratuito, sin cargos monetarios, paginación ni reintentos.

Outscraper no se utilizó. Gabriel confirmó que su cuenta exigía añadir
créditos para habilitar la generación del token API.

## Configuración y seguridad

Antes de la solicitud se comprobó que:

- El archivo local `backend/.env` existía.
- Contenía una asignación no vacía y sintácticamente válida de
  `SERPAPI_API_KEY`.
- El archivo estaba excluido de Git y no estaba versionado.
- La credencial no se imprimió ni se incorporó al código.

La clave había aparecido anteriormente en una captura. Gabriel decidió
conservarla para esta prueba. La exposición no se considera resuelta;
permanece recomendada su rotación.

## Solicitud realizada

- Método: GET.
- Endpoint sin credencial: https://serpapi.com/search.json
- Motor: `google_maps_reviews`.
- Identificador: `data_id` correspondiente al negocio seleccionado.
- Límite: `num=5`.
- Orden: `sort_by=newestFirst`.
- Idioma: `hl=es`.
- Formato: `output=json`.
- Modo: `async=false`.
- Caché permitida: `no_cache=false`.
- Autenticación: parámetro `api_key`, cargado localmente y omitido
  de esta evidencia.
- Cliente: HTTPX.
- Solicitudes: 1.
- Reintentos: 0.
- Solicitudes de paginación: 0.

No se registra la URL autenticada ni el identificador de la búsqueda.

## Resultado observado

- Fecha local: 2026-11-02, 06:01:32, America/Tijuana (UTC−08:00).
- Fecha UTC: 2026-11-02, 14:01:32.
- Estado HTTP: 200.
- Estado de búsqueda: Success.
- Error del proveedor: no observado.
- Negocio identificado: Metro Café – UABC, Mexicali.
- Identidad corroborada mediante nombre, dirección en Mexicali
  y coincidencia del `data_id` devuelto.
- Reseñas recuperadas: 5.
- Límite solicitado: respetado.
- Token de paginación: no presente.

La ausencia de token no demuestra cobertura completa de las reseñas
del establecimiento.

| Campo | Presencia observada |
|---|---:|
| Autor | 5/5 |
| Texto | 2/5 |
| Fecha ISO | 5/5 |
| Puntuación | 5/5 |
| Fuente | 5/5 |
| ID externo | 5/5 |

En tres reseñas no se detectó texto en los campos inspeccionados.
Esta condición deberá contemplarse en #3833 sin inventar contenido.

## Consumo y corroboración

Se realizó una única petición. El débito exacto de cuota y el saldo
posterior no se consultaron mediante solicitudes adicionales.

Gabriel comprobó posteriormente que la solicitud aparece registrada
en el panel de SerpApi. Esta corroboración no se interpreta como
confirmación de un débito exacto ni de un saldo restante de 249.

La ejecución utilizó el plan Free confirmado por Gabriel.
No se activaron pagos ni suscripciones durante la prueba.
No se obtuvo una comprobación independiente de facturación.

## Tratamiento de la respuesta

La respuesta se inspeccionó exclusivamente en memoria.

No se guardaron reseñas en archivos o base de datos, no se enviaron
a Gemini ni a otro modelo de IA y no se mostraron nombres de autores,
textos, perfiles, credenciales o el JSON completo.

La evidencia conserva únicamente resultados técnicos y cantidades.
La retención que aplique el proveedor es independiente de la ausencia
de persistencia local.

## Resultado de #3831

CUMPLE la comprobación técnica de acceso real autorizado:
autenticación válida, lectura exitosa y correspondencia del negocio.

Este resultado no acredita derechos generales de almacenamiento,
redistribución, visualización o procesamiento con IA. Tampoco implica
que HU-21 esté integrada u operativa.

La revisión y aceptación formal de la Task corresponden al proceso
del equipo. Esta ejecución no cambió su estado en OpenProject.

## Bloqueos y requisitos pendientes

| Tema | Estado y acción necesaria |
|---|---|
| Almacenamiento y retención | Acreditar condiciones aplicables antes de persistir reseñas. Responsable: PO y titular/proveedor correspondiente. |
| Visualización y procesamiento con IA | Confirmar derechos y condiciones para mostrar o transferir contenido. Responsable: PO y titular/proveedor correspondiente. |
| Credencial expuesta | Rotación recomendada; no se declara resuelta. Responsable: Gabriel o administrador de cuenta. |
| Cuotas y facturación | Verificar consumo, renovación y límites antes de nuevas ejecuciones. Responsable: administrador de cuenta y Gabriel. |
| Multi-tenancy | Implementar y probar aislamiento de configuración, operaciones y datos por tenant. Responsable: desarrollo de HU-21. |
| Integración completa | #3832–#3835 permanecen pendientes; esta lectura no las sustituye. |

## Referencias oficiales

- Endpoint y parámetros:
  https://serpapi.com/google-maps-reviews-api
- Planes y reglas de consumo:
  https://serpapi.com/pricing
- Estados y errores:
  https://serpapi.com/api-status-and-error-codes
- Condiciones y privacidad:
  https://serpapi.com/legal

Las referencias describen el servicio; la evidencia de acceso procede
de la ejecución real registrada arriba. No se repitió la consulta
para preparar este documento.
