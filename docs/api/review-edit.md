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

## Contrato del endpoint (Task #3347)

```http
PATCH /api/v1/reviews/{review_id}
Authorization: Bearer <token>
Content-Type: application/json
```

Ejemplo de actualización parcial:

```json
{
  "contenido": "El servicio fue rápido y el personal muy amable.",
  "puntuacion": 5
}
```

La petición debe incluir al menos un campo editable. No se envía `tenant_id`:
el backend lo obtiene del usuario autenticado. Se reutiliza el flujo
`Router → ReviewService → ReviewRepository → Base de datos`.

La respuesta `200` utiliza el mismo JSON `ReviewRead` del endpoint de detalle
y devuelve todos los datos de la review después de guardar los cambios. El
frontend puede actualizar la tabla y el detalle con esa respuesta.

| Código | Significado |
|---|---|
| `200` | Edición guardada dentro del tenant del usuario. |
| `401` | Token ausente o inválido. |
| `403` | Usuario inactivo o sin tenant autorizado. |
| `404` | Review inexistente o de otro tenant; ambas usan la misma respuesta. |
| `422` | Datos inválidos, cuerpo vacío, campos protegidos o desconocidos. |

Una petición inválida no guarda cambios parciales. La categoría, prioridad,
estado y asociación al tenant mantienen su valor. No se modifica el modelo
de datos ni se requiere una migración.

## Comprobación

```bash
cd backend
python -m pytest tests/test_review_edit_api.py -q
```

Las pruebas verifican edición completa y parcial, persistencia en otra sesión,
campos protegidos, validaciones, autenticación, aislamiento entre tenants y
actualización de las métricas que dependen de la puntuación.

