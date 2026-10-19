# HU-13 / T2 #3561: configuración y conexión reutilizable con IA

Responsable: David Escárcega Schlemmer. Desarrollo y comprobación real: 17 de octubre de 2026, America/Tijuana. [Tarea #3561](https://computacion.mxl.uabc.mx/openproject/work_packages/3561). Rama: `feature/HU-13-clasificacion`. Continúa el contrato de [T1](t1-definicion-clasificacion-ia.md).

## Resultado y límites del alcance

Se implementó un adaptador común de Gemini dentro del backend para las tres historias de IA. Recibe texto, instrucciones y un modelo Pydantic de salida; devuelve una instancia validada o una excepción controlada. Una misma instancia reutiliza el cliente HTTP entre solicitudes y se cierra con un bloque `with`.

La implementación no accede a usuarios, tenants, reviews ni base de datos. Los servicios de HU-13/HU-14/HU-15 deben comprobar autorización y tenant antes de invocarlo. La persistencia pertenece a T3; servicio de clasificación y endpoint pertenecen a T4/T5. No se añadieron rutas ni componentes frontend y no se declara terminada ninguna de las tres historias de IA.

## Archivos de aplicación

| Archivo | Responsabilidad |
| --- | --- |
| `backend/app/core/ai_config.py` | `AISettings`: configuración validada y clave privada en `SecretStr`. |
| `backend/app/schemas/ai.py` | `AIResponse`: base estricta que rechaza propiedades adicionales. Cada HU define sus campos y validaciones. |
| `backend/app/services/ai_provider.py` | Protocolo `StructuredAIProvider`, fábrica `create_ai_provider`, adaptador `GeminiAdapter` y errores de infraestructura. |
| `backend/.env.example` | Nombres y valores iniciales sin credenciales. |

Se usa la [API REST oficial de generación](https://ai.google.dev/api/generate-content) mediante `httpx`, ya presente en las dependencias del proyecto. Esta decisión concreta la propuesta inicial de usar un SDK: evita añadir otra dependencia y mantiene aislado el transporte del proveedor. No se instala `google-genai` en esta tarea. Se solicitan [salidas estructuradas](https://ai.google.dev/gemini-api/docs/structured-output) con JSON Schema y se validan otra vez con Pydantic.

## Configuración

Ejecutar el backend desde `backend/`, como indica el README, y mantener la clave en su entorno o en `backend/.env`:

```dotenv
AI_PROVIDER=gemini
AI_MODEL=gemini-3.5-flash-lite
GEMINI_API_KEY=
AI_TIMEOUT_SECONDS=30
AI_MAX_OUTPUT_TOKENS=1024
```

La clave vacía del ejemplo es deliberada. `AISettings` se crea al pedir el proveedor, nunca al importar la aplicación; configuración ausente o inválida genera `AIConfigurationError` al solicitar IA. Login, health y consulta de reseñas no requieren una clave de Gemini.

Solo se admite el proveedor `gemini`. El identificador de modelo no acepta rutas, parámetros ni caracteres de control. La clave no se muestra en representaciones de configuración y se envía en la cabecera `x-goog-api-key`, nunca en la URL. El timeout debe ser mayor que cero y como máximo 120 segundos; se aplica a las fases de la solicitud HTTP. El máximo de tokens de salida admite 64-8192, con 1024 como valor inicial.

No hay reintentos automáticos ni seguimiento de redirecciones. Las excepciones públicas contienen mensajes fijos y códigos internos, sin cuerpos del proveedor, clave ni texto completo de la reseña. No se registra ese contenido en logs del adaptador.

## Uso común desde los servicios

Ejemplo de consumo de la infraestructura; los prompts y modelos funcionales definitivos pertenecen a cada historia:

```python
from typing import Literal

from app.schemas.ai import AIResponse
from app.services.ai_provider import create_ai_provider


class ClassificationResult(AIResponse):
    categoria: Literal["Queja", "Sugerencia", "Felicitación", "Consulta"]


# Antes de este punto, el servicio debe resolver la review y su tenant autorizado.
with create_ai_provider() as provider:
    result = provider.generate_structured(
        contenido,
        instructions=instrucciones_clasificacion_v1,
        response_model=ClassificationResult,
    )
```

La misma interfaz recibe un modelo con `resumen` o `tema` y las instrucciones que acuerden Francisco y Diego. No deben duplicar el cliente ni manejar la clave en frontend. El proveedor síncrono debe utilizarse desde funciones síncronas de FastAPI o mediante su threadpool si se integra en una ruta asíncrona. El llamador gestiona su ciclo de vida con `with`; no debe crear un cliente global abierto al importar módulos.

La validación estructural verifica campos, tipos y restricciones del modelo proporcionado. No prueba por sí sola fidelidad de un resumen o corrección de un tema. Las reseñas se envían como contenido de usuario y las instrucciones funcionales permanecen separadas en `systemInstruction`.

## Errores controlados

| Excepción | Código interno | Situación |
| --- | --- | --- |
| `AIConfigurationError` | `configuration` | Configuración inválida o modelo sin acceso (404). |
| `AICredentialsError` | `credentials` | Acceso rechazado (401/403 o `API_KEY_INVALID` en 400). |
| `AIQuotaError` | `quota` | Cuota agotada (429). |
| `AITimeoutError` | `timeout` | Timeout de transporte o 408/504. |
| `AIUnavailableError` | `unavailable` | Red, otros errores 5xx o redirección inesperada. |
| `AIRequestError` | `request` | Otras solicitudes rechazadas por el proveedor. |
| `AIBlockedResponseError` | `blocked` | Bloqueo explícito o finalización por seguridad/recitación. |
| `AIInvalidResponseError` | `invalid_response` | Cuerpo, finalización, JSON o schema de salida inválidos. |
| `AIInputError` | `input` | Contenido o instrucciones vacíos; no se llama al proveedor. |

El mapeo de estas excepciones a respuestas HTTP de los endpoints se realiza en las tareas de API. No se usan resultados ficticios como fallback ni se guarda ninguna salida desde el adaptador.

## Validación de T2

Las pruebas de `backend/tests/test_ai_provider.py` usan `httpx.MockTransport` y credenciales ficticias, sin consumo de cuota. Cubren reutilización para los tres esquemas, separación de instrucciones/datos, clave fuera de URL, errores de acceso/cuota/red/timeout, redirecciones rechazadas, respuestas bloqueadas/truncadas/malformadas, propiedades adicionales, tipos estrictos y ausencia de secretos en excepciones. También comprueban que sin credenciales de IA siguen funcionando health, login y consulta.

Validación final desde `backend/`: `.venv/bin/python -m pytest -q` completó **429 pruebas aprobadas**, incluidas 57 de la infraestructura nueva. Se observó un aviso de deprecación de Starlette/TestClient, sin fallos. La importación de FastAPI y `git diff --cached --check` también finalizaron correctamente.

La [evidencia real del adaptador](evidencia-adaptador-t2-2026-10-17.json) se ejecutó el 17 de octubre a las 11:17 hora de Tijuana. Una misma instancia completó tres operaciones sobre la reseña sintética «Mi pedido llegó una hora tarde y la comida estaba fría»:

| Operación | Salida real validada | Tiempo observado |
| --- | --- | --- |
| Clasificación | `{"categoria":"Queja"}` | 0.849 s |
| Resumen | `{"resumen":"El pedido llegó una hora tarde y la comida estaba fría."}` | 0.711 s |
| Tema | `{"tema":"Servicio de entrega"}` | 0.717 s |

**3/3 operaciones completadas con respuesta válida.** El resumen conserva los dos hechos del ejemplo y el tema corresponde a la entrega. Estos casos comprueban reutilización del transporte; no constituyen aceptación de HU-14/HU-15 ni una evaluación representativa de calidad. Los tiempos no son una garantía de latencia. El reporte conserva el modelo solicitado; no registra metadatos de versión devueltos porque la interfaz del adaptador expone únicamente el resultado validado.

Reproducción desde la raíz, con el entorno backend instalado:

```bash
backend/.venv/bin/python backend/scripts/verify_gemini_t2.py
```

El script utiliza el adaptador de aplicación y carga `backend/.env` explícitamente. Crea un archivo nuevo por ejecución y no reemplaza evidencias. Una nueva ejecución consume cuota. Los modelos de resumen/tema del script son ejemplos técnicos de salida, no contratos funcionales aprobados para esas historias.

## Criterios oficiales y evidencia

| Criterio de #3561 | Cumplimiento |
| --- | --- |
| Configuración y adaptador compartidos | `AISettings`, `create_ai_provider` y `GeminiAdapter`; interfaz común para cada schema. |
| Conexión real utilizable por las tres operaciones | Tres llamadas reales realizadas mediante la misma instancia, con resultados publicados en la evidencia de T2. |
| Configuración válida | Validación aislada de proveedor, modelo, credencial, timeout y límite de salida; errores de IA no bloquean funciones existentes. |
| Errores de acceso/respuesta controlados | Excepciones sanitizadas y pruebas de credenciales, cuota, red, bloqueo, formato y schema. |

La siguiente tarea es T3 #3562: preparar contrato y almacenamiento de resultados conservando datos existentes. El adaptador queda disponible para que Francisco y Diego desarrollen sus servicios con reglas propias.
