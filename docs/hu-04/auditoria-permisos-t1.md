# HU-04 / T1 — Auditoría de permisos implementados

**Fuente del alcance:** OpenProject, historia [#3264 — Gestión de roles y permisos](https://computacion.mxl.uabc.mx/openproject/projects/is20262-gestorreviews/work_packages/3264) y tarea [#3551 — T1: Auditar los permisos implementados actualmente](https://computacion.mxl.uabc.mx/openproject/projects/is20262-gestorreviews/work_packages/3551). La T1 pide revisar dependencias de FastAPI, servicios de usuarios y acceso por rol. Su criterio de cierre es un inventario documentado de endpoints, permisos y brechas, con casos de cambio de rol y acceso cruzado identificados. La matriz de permisos se define y valida en T2; las validaciones reutilizables y su aplicación a endpoints corresponden a T3 y T4. Este documento registra el estado actual, sin decidir esa matriz.

**Corte auditado:** `origin/main` en `8bdd24e` (12 de octubre de 2026). Prefijo de API: `/api/v1`. La revisión cubre routers, dependencias, servicios, repositorios, esquemas, modelos y pruebas del backend; se comprobó además la navegación React actual.

## Controles compartidos existentes

- `get_current_user` (`backend/app/api/dependencies.py`) exige Bearer JWT válido, obtiene el usuario por `sub` desde la base de datos y rechaza usuarios inactivos. El rol y `tenant_id` usados por las rutas provienen del registro actual, no de los claims `rol` y `tenant_id` enviados en el token. Ausencia/token inválido: 401; usuario inactivo: 403.
- `require_admin_general` permite el CRUD de tenants solo a `admin_general`. `get_current_tenant_id` usa `resolve_tenant_id`: devuelve el tenant del usuario autenticado y rechaza a `admin_general` o a quien no tenga tenant (403). Estos controles separan la administración global de tenants del contenido operativo de reviews.
- `AuthenticatedUser` y la restricción `ck_users_rol_tenant` admiten los tres roles existentes y exigen `tenant_id IS NULL` para `admin_general`, y `tenant_id IS NOT NULL` para `usuario_negocio` y `admin_tenant` (`backend/app/schemas/auth.py`, `backend/app/models/user.py`).
- El servicio de usuarios exige `admin_tenant` del tenant actual; el repositorio lista y busca usuarios por `tenant_id`. Los repositorios de reviews filtran listados y búsquedas por `tenant_id`. Los ID de reviews ajenas e inexistentes producen el mismo 404.

## Inventario de endpoints y permisos actuales

| Endpoint | Permiso aplicado hoy | Alcance de datos y respuesta de rechazo |
| --- | --- | --- |
| `GET /api/v1/health` | Público | Solo estado del servicio; sin datos de tenant. |
| `POST /api/v1/auth/login` | Público, con credenciales | Acepta los tres roles; rechaza usuario inactivo (403), sin consultar el estado del tenant. |
| `POST /api/v1/tenants` | `admin_general` | Crea tenant; otros roles 403. |
| `GET /api/v1/tenants` | `admin_general` | Lista todos los tenants; otros roles 403. |
| `GET /api/v1/tenants/{tenant_id}` | `admin_general` | Consulta cualquier tenant; otros roles 403. |
| `PATCH /api/v1/tenants/{tenant_id}` | `admin_general` | Cambia nombre o estado de cualquier tenant; otros roles 403. No existe DELETE. |
| `GET /api/v1/users` | `admin_tenant` | Lista solo usuarios de su tenant; `usuario_negocio` y `admin_general` reciben 403. |
| `POST /api/v1/users` | `admin_tenant` | Crea únicamente `usuario_negocio` activo en su tenant; otros roles 403. |
| `PATCH /api/v1/users/{user_id}` | `admin_tenant` | Cambia nombre, correo o estado de usuario de su tenant; usuario ajeno/inexistente 404, otros roles 403. |
| `POST /api/v1/reviews` | Usuario autenticado con tenant (`usuario_negocio` o `admin_tenant`) | Crea review en el tenant del servidor; `admin_general` 403. |
| `POST /api/v1/reviews/import` | Usuario autenticado con tenant | Importa al tenant autenticado; `admin_general` 403. |
| `GET /api/v1/reviews` | Usuario autenticado con tenant | Lista y filtra solo reviews del tenant; `admin_general` 403. |
| `GET /api/v1/reviews/{review_id}` | Usuario autenticado con tenant | Review propia; ajena/inexistente 404; `admin_general` 403. |
| `PATCH /api/v1/reviews/{review_id}` | Usuario autenticado con tenant | Edita review propia; ajena/inexistente 404; `admin_general` 403. |
| `PATCH /api/v1/reviews/{review_id}/status` | Usuario autenticado con tenant | Cambia estado de review propia; ajena/inexistente 404; `admin_general` 403. |
| `POST /api/v1/imports/upload` | Usuario autenticado con tenant | Importa al tenant autenticado; `admin_general` 403. |
| `GET /api/v1/dashboard` | Usuario autenticado con tenant | Métricas de reviews del tenant; `admin_general` 403. |

Todas las rutas protegidas responden 401 sin autenticación válida. El inventario se deriva de `backend/app/api/routers/` y `backend/app/api/dependencies.py`; las restricciones de filas se revisaron en `backend/app/services/` y `backend/app/repositories/`.

## Campos de autoridad y escenarios de rol

`UserCreate` acepta solo nombre, correo y contraseña; el servicio fija `rol=usuario_negocio`, `estado=activo` y `tenant_id` desde el usuario autenticado. `UserUpdate` acepta solo nombre, correo y estado. Ambos esquemas usan `extra="forbid"`: solicitudes ordinarias con `rol` o `tenant_id` reciben 422. `UserRepository.update` tampoco escribe esos campos. Hoy no hay endpoint para promover a `admin_tenant`, asignar `admin_general`, cambiar el rol de un usuario existente ni crear cuentas administrativas mediante API. Tampoco hay un listado global de usuarios para `admin_general`. Son brechas funcionales de HU-04, no funciones que T1 deba implementar.

Casos que la matriz de T2 y la implementación posterior deben resolver explícitamente:

1. `admin_general` crea o promueve una cuenta `admin_tenant` mediante una operación autorizada, con asignación controlada del tenant y persistencia; hoy no existe esa operación.
2. `admin_tenant` intenta promover a otro usuario o a sí mismo a `admin_tenant` o `admin_general`; hoy los payloads con `rol` son rechazados con 422, pero el flujo autorizado futuro necesita pruebas negativas propias.
3. Un usuario intenta cambiar su propio rol o `tenant_id`; hoy esos campos se rechazan para todos los actores en `POST/PATCH /users`.
4. `admin_tenant` intenta listar, crear o editar usuarios del tenant B, incluso enviando `tenant_id` en el cliente o un `user_id` ajeno; hoy el contexto autenticado y la búsqueda por tenant impiden cruzarlo.
5. `usuario_negocio` o `admin_tenant` intenta acceder al CRUD global de tenants (403); `admin_general` intenta entrar en reviews, importaciones o dashboard sin contexto de tenant (403). La autorización de usuarios, tenants y reviews debe seguir siendo independiente.

## Brechas y decisiones pendientes

| Hallazgo | Evidencia | Tratamiento posterior |
| --- | --- | --- |
| No existe cambio de rol ni alta/promoción de administradores de tenant mediante API. | `UserCreate`, `UserUpdate`, `UserService`, `UserRepository` y `users.py` no aceptan ni persisten `rol` o `tenant_id`. | T2 debe definir operaciones y transiciones autorizadas; T3/T4 implementarlas. |
| `admin_general` no puede consultar usuarios globalmente ni gestionar cuentas administrativas. | `UserService` permite listar, crear y editar solo a `admin_tenant`; no hay router global de usuarios. | Validar el alcance preciso en T2 antes de crear endpoints. |
| El estado inactivo de un tenant no bloquea el login ni las rutas operativas de sus usuarios activos. | `AuthService.authenticate` y `get_current_user` comprueban `user.estado`, pero no `Tenant.estado`; `resolve_tenant_id` solo comprueba rol y presencia de ID. `PATCH /tenants/{id}` sí permite desactivarlo. | Registrar como brecha de seguridad/operación y decidir en T2 si HU-04 o una tarea específica la corrige; no se altera en T1. |
| La navegación React no diferencia roles. | `frontend/src/App.jsx` declara rutas sin guardas por rol; `frontend/src/services/authService.js` guarda el rol, pero las páginas no lo usan para decidir acceso. | T5 puede adaptar visibilidad y navegación; el backend seguirá siendo la autoridad. |

## Cobertura comprobada y límites

- `test_auth.py` cubre login de los tres roles, usuario inactivo y restricción rol/tenant de SQLite.
- `test_user_creation.py`, `test_user_listing.py` y `test_user_update.py` cubren rol `admin_tenant`, rechazo de otros roles, campos `rol`/`tenant_id` inyectados y usuarios de otros tenants.
- `test_tenant_isolation.py` y `test_tenant_crud.py` cubren aislamiento de reviews, acceso global de `admin_general`, 403 para otros roles, y activación/desactivación del tenant.
- `test_reviews_api.py`, `test_review_edit_api.py`, `test_review_status_api.py`, `test_imports_api.py` y `test_dashboard.py` cubren rutas operativas, aislamiento y parte de los rechazos de autenticación. La cobertura por rol no es exhaustiva en todas las combinaciones; T6 debe completar los casos que resulten de la matriz aprobada.
- No se encontró prueba de login o uso de token para un usuario activo cuyo tenant esté inactivo, ni prueba de cambio de rol autorizado: el primer comportamiento carece de control y el segundo carece de endpoint. Las pruebas locales usan SQLite; no hay ejecución PostgreSQL acreditada por esta auditoría.
- Validación local del corte auditado: `cd backend && python -m pytest -q` terminó con **366 passed, 2 warnings** (avisos de deprecación de Starlette/AnyIO). No se cambió código de aplicación ni pruebas en T1.
