# HU-14 — Validación y guía de prueba

19 de octubre de 2026. Francisco Javier Oceguera Gutiérrez. T2–T5 #3568–#3571.

## Resultado del desarrollo

Implementados servicio, `POST /api/v1/reviews/{review_id}/resumen`, persistencia compartida e interfaz en detalle de review. Se reutiliza la base del PR #22 en `32e434c`; no se repiten migraciones ni configuración. El router de resumen es independiente para reducir conflictos con los cambios de clasificación/temas. El componente visual también está separado en `ReviewSummary.jsx`.

La interfaz muestra resultado de solo lectura, etiqueta Generado por IA, carga y errores. Bloquea peticiones repetidas mientras espera, cancela la espera al cambiar de review y solo aplica el resumen a la review y contenido correspondientes. Una respuesta de resumen no pisa cambios de estado/categoría/tema recibidos durante la espera. El timeout HTTP de esta operación deja margen al límite de 120 segundos del adaptador compartido; no cambia el timeout de las otras operaciones.

## Pruebas ejecutadas

| Verificación | Resultado |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -q tests/test_summary.py --tb=short --basetemp=.venv/pytest-summary` desde backend | **64 aprobadas**, 17.46 s |
| `.venv/Scripts/python.exe -m pytest -q --tb=short --basetemp=.venv/pytest-hu14-full` desde backend | **601 aprobadas**, 116.24 s |
| `npm run lint` desde frontend | Aprobado, código 0 |
| `npm run build` desde frontend | Aprobado, Vite 7.3.6; 1752 módulos |
| `python -m pip check` con el entorno backend | Sin requisitos rotos |
| `git diff --check` | Aprobado |
| Navegador, frontend y backend locales con SQLite de demo separada | Login, listado, detalle, acción Generar resumen y error recuperable por configuración ausente comprobados |

Entorno local: Windows, Python 3.12.14 y dependencias instaladas según `requirements.txt`; Node 24.20.0 y npm 11.19.0, con dependencias de `package-lock.json`. Los workflows del repositorio usan Python 3.13 y Node 20: su resultado corresponde al commit que GitHub evalúe, no se infiere de la ejecución local.

La suite conserva una advertencia de deprecación Starlette/TestClient sobre HTTPX. No hubo fallos. No se midió cobertura de código ni precisión estadística.

### Cobertura de los 64 casos nuevos

- Roles de negocio permitidos, tokens inválidos, usuario/tenant inactivos, rol general denegado y ámbito autenticado tomado de la base actual.
- Review ajena/inexistente sin llamada al proveedor; query y cuerpo sin capacidad para imponer otro tenant/contenido.
- Generación, regeneración y lectura posterior mediante sesiones independientes; conservación de todos los campos ajenos al resumen y del otro tenant.
- JSON, tipo y campos de salida; vacío, blanco, null no analizable y máximo de 400 caracteres Unicode tras normalizar extremos.
- Mapeo de errores, indisponibilidad/cuota/timeout y ausencia de configuración, sin filtrar cuerpos privados del proveedor.
- Cambio de contenido, tenant o eliminación durante la generación; conservación de actualizaciones concurrentes de categoría/tema; rollback ante fallo de commit.
- Revalidación de instancias del proveedor, separación entre instrucciones y contenido, protección frente a edición manual y contrato OpenAPI.

Los tests usan el adaptador real y **HTTPX MockTransport** para controlar la respuesta externa. Ejecutan autenticación, servicio, router y SQLite reales dentro de TestClient. Esto verifica el comportamiento técnico, pero no constituye una llamada real a Gemini ni demuestra la fidelidad semántica general del modelo.

## Pendiente de validación con el proveedor

El usuario confirmó que no dispone de la configuración privada. Esta copia no tiene `GEMINI_API_KEY`; no se hizo ninguna llamada a Gemini ni se fabricaron resultados de producción. El error 503 mostrado por la interfaz es el comportamiento esperado en esa situación. El resto de la aplicación continúa disponible.

Para la validación real, usar la configuración privada del backend común de HU-13 preparada por su responsable, sin publicarla en el repositorio ni enviarla en mensajes. Conservar el proveedor/modelo acordados. El archivo `.env` está ignorado por Git. No colocar la clave en `VITE_*`, JavaScript, capturas, documentos ni registros.

Una vez configurado el servicio, probar los ejemplos de [T1](contrato-resumen-v1.md), revisando hechos, matices y longitud. Registrar entradas sintéticas, salida, fecha, modelo y resultado esperado/obtenido sin secretos. La ausencia de errores estructurales no basta para afirmar fidelidad. PostgreSQL sigue pendiente de validación operativa del equipo.

## Recorrido de demostración

1. Ejecutar el backend configurado con la base compartida de HU-13 y este incremento; iniciar el frontend.
2. En una base local destinada a pruebas, `python -m scripts.seed_demo` crea `demo@example.com` / `demo123` y datos sintéticos. No usar esa cuenta como credencial de producción.
3. Entrar, abrir Reviews y seleccionar una review; solicitar Generar resumen.
4. Verificar carga, respuesta, etiqueta Generado por IA y que el resultado no es editable. Comparar la idea principal con el original.
5. Recargar y verificar que permanece asociado a la misma review. Regenerar explícitamente si se cambia después el comentario.
6. Comprobar error de configuración/servicio, entrada no analizable y aislamiento con las pruebas automatizadas y los casos integrados de T6.

No presentar el recorrido de generación como ejecutado con el proveedor real hasta completar el pendiente anterior. T6 #3572 pertenece a José Ramón Suffo Peimbert; este desarrollo no cierra su tarea ni acredita aceptación del PO o integración en main.
