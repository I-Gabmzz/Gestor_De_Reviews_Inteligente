# Edición de reviews: paquete de trabajo #3235

## Acuerdo de campos (Task #3346)

Cisco y Gabriel acordaron que la edición de datos y el cambio de estado se
implementan por separado. La edición acepta únicamente los siguientes campos:

| Campo | Regla |
|---|---|
| `autor` | Texto de hasta 255 caracteres; `null` o texto vacío elimina el autor. |
| `contenido` | Texto obligatorio, no vacío ni compuesto únicamente por espacios. |
| `fecha` | Fecha válida en ISO 8601, por ejemplo `2026-09-27` o `2026-09-27T12:30:00`. |
| `fuente` | Texto obligatorio de 1 a 100 caracteres. |
| `puntuacion` | Número entero de 1 a 5, igual que en la importación existente. |

Se eliminan espacios al inicio y al final de los textos. Solo `autor` admite
`null`. Los campos omitidos conservan su valor anterior. Si una fecha incluye
zona horaria, se convierte a UTC antes de persistirla sin offset, de acuerdo
con el tipo `DateTime` actual; una fecha sin zona conserva su hora original.

`id`, `tenant_id`, `estado`, `categoria` y `prioridad` quedan protegidos.
También se rechazan campos desconocidos, incluidos futuros resultados de IA.
El cambio de estado corresponde a la funcionalidad de Gabriel.

