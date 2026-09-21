# HU-07: consulta de reviews

## Objetivo

Permitir que un usuario autenticado consulte la lista y el detalle de las reviews pertenecientes a su organización. El backend obtiene el `tenant_id` del usuario autenticado; el cliente no puede seleccionar ni enviar un tenant diferente.

## Flujo por capas

```text
React → Router FastAPI → ReviewService → ReviewRepository → Base de datos
```

- El cliente adjunta el token Bearer.
- `get_current_user` valida el token y devuelve el contexto del usuario.
- El router exige que el usuario tenga un `tenant_id`.
- El repositorio incluye el `tenant_id` en todas las consultas.
- Una review inexistente y una review de otro tenant producen la misma respuesta `404` para no revelar información.

## Endpoints

### Listar reviews

```http
GET /api/v1/reviews
Authorization: Bearer <token>
```

Las reviews se ordenan por fecha descendente y, si dos fechas coinciden, por identificador descendente.

Respuesta `200`:

```json
{
  "items": [
    {
      "tenant_id": 1,
      "autor": "Mariana",
      "contenido": "El servicio fue rápido y el personal muy amable.",
      "fecha": "2026-09-18T09:30:00",
      "fuente": "Google",
      "puntuacion": 5,
      "estado": "atendida",
      "categoria": "servicio",
      "prioridad": "baja",
      "id": 1
    }
  ],
  "total": 1
}
```

### Consultar detalle

```http
GET /api/v1/reviews/{review_id}
Authorization: Bearer <token>
```

Respuestas esperadas:

| Código | Significado |
|---|---|
| `200` | Review encontrada dentro del tenant del usuario. |
| `401` | Token ausente o inválido. |
| `403` | Usuario autenticado sin tenant asignado. |
| `404` | Review inexistente o perteneciente a otro tenant. |

## Interfaz

La ruta `/reviews` presenta una tabla con autor, resumen, fecha, fuente, calificación y estado. Al seleccionar una fila se consulta el endpoint de detalle y se muestra el contenido completo, categoría y prioridad.

El cliente busca el token en `localStorage` bajo la clave `access_token`. La pantalla de autenticación deberá guardar allí el `access_token` devuelto por `/api/v1/auth/login`.

## Verificación automatizada

```bash
cd backend
python -m pytest tests -q
```

Las pruebas cubren autenticación obligatoria, filtrado por tenant, detalle válido, identificador inexistente, intento de acceso cruzado y usuario sin tenant.
