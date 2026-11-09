# HU-25 · Administración de negocios y acceso

## Cuentas y negocios de prueba (#4033)

La prueba usa dos negocios, una reseña por negocio y una conexión de Google habilitada para el negocio A. Los datos son ficticios y se cargan en una base aislada.

| Rol | Negocio | Acceso esperado |
| --- | --- | --- |
| Administrador general | Sin negocio asignado | Consulta y modifica el nombre y estado de ambos negocios. |
| Administrador de negocio | A | Accede a sus reseñas y administra sus cuentas. La API de administración general devuelve 403. |
| Usuario de negocio | A y una cuenta distinta en B | Cada cuenta ve las reseñas de su negocio. La API de administración general devuelve 403. |

El panel reutiliza `GET /api/v1/tenants` y `PATCH /api/v1/tenants/{id}`. El cambio de estado conserva las reseñas, las cuentas y las conexiones del negocio. Al reactivar, las cuentas habilitadas deben iniciar sesión de nuevo.

## Matriz de resultados (#4034–#4037)

Comprobación local del 9 de noviembre de 2026 con el frontend compilado, FastAPI y SQLite. Las pruebas de API emplean su propia base temporal.

| Caso | Comprobación | Resultado local |
| --- | --- | --- |
| Edición y estado | Editar A, desactivarlo, recargar el panel y reactivarlo. | El nombre y el estado persistieron. La conexión de Google conservó su estado. |
| Sesiones anteriores | Consultar las reseñas de A con la sesión anterior durante la desactivación y tras reactivar. | 403 mientras está inactivo y 401 tras reactivar. Chrome volvió al inicio de sesión con un aviso. |
| Nuevo acceso | Iniciar sesión en una cuenta habilitada después de reactivar A. | Las reseñas de A volvieron a estar disponibles. Una cuenta deshabilitada siguió recibiendo 403. |
| Roles | Intentar abrir el panel y enviar un PATCH como administrador y usuario de negocio. | Ambos pudieron volver a su vista autorizada. El servidor rechazó los cambios con 403. |
| Aislamiento | Consultar B mientras A está desactivado y pedir una reseña ajena por ID. | B siguió operativo. La API devolvió 404 para una reseña ajena. |
| Ayuda de acceso | Abrir «¿Olvidaste tu contraseña?» e iniciar sesión con una contraseña incorrecta. | La ayuda indica a quién contactar. El formulario distingue las credenciales inválidas del aviso de sesión terminada. |

La suite incluye arranque sobre una base existente y revocación de sesiones en PostgreSQL. La prueba en el despliegue compartido queda pendiente hasta disponer de una versión que incluya estos cambios y cuentas de prueba para ambos negocios.
