# HU-04 / T6 — Evidencia de permisos y aislamiento multi-tenant

**Fecha de ejecución:** 19 de octubre de 2026 (America/Tijuana).

**Rama:** `feature/HU-04-roles-permisos`.

**Revisión probada:** `63daad1` (T4 y T5 integradas) más los archivos de pruebas T6 añadidos en el árbol de trabajo. La ejecución ocurrió antes de confirmar este documento y esas pruebas en Git; no se modificó el código de aplicación después de probarlo.

**Fuentes de criterios:** [HU-04 #3264](https://computacion.mxl.uabc.mx/openproject/projects/is20262-gestorreviews/work_packages/3264) y [T6 #3556](https://computacion.mxl.uabc.mx/openproject/projects/is20262-gestorreviews/work_packages/3556), consultadas el 19 de octubre de 2026.

## Entorno y ejecución

- Windows, Python 3.13.9, SQLite 3.50.4 mediante las bases temporales de `backend/tests/conftest.py`; Node.js 24.12.0 y npm 11.6.2.
- `cd backend; python -m pytest -q tests/test_hu04_t3_authorization.py tests/test_hu04_t4_endpoints.py tests/test_hu04_t6_integration.py`: **19 aprobadas, 0 fallidas, 0 omitidas; 2 avisos de deprecación** de Starlette/AnyIO.
- `cd backend; python -m pytest -q`: **385 aprobadas, 0 fallidas, 0 omitidas; 2 avisos de deprecación**, en 169.36 s. Incluye las regresiones de autenticación, usuarios, reviews, importaciones, dashboard y tenants.
- `cd frontend; node --test --test-concurrency=1 tests/roleAccess.test.mjs tests/roleGuard.test.mjs tests/hu04T6Navigation.test.mjs`: **6 aprobadas, 0 fallidas, 0 omitidas**. Una primera ejecución paralela también pasó, pero mostró un aviso de puerto de Vite ocupado; la ejecución en serie pasó sin ese aviso.
- `cd frontend; npm run lint`: aprobado.
- `cd frontend; npm run build`: aprobado.

El repositorio no define un script de navegador E2E en `frontend/package.json`. Las pruebas de React anteriores renderizan componentes con el servidor de Vite y `react-dom/server`; no equivalen a una sesión de navegador con backend real.

## Escenarios cubiertos

| Área | Evidencia automatizada | Resultado comprobado |
| --- | --- | --- |
| Cambio de rol y persistencia | `backend/tests/test_hu04_t4_endpoints.py::test_admin_change_persists_and_old_token_uses_current_role`; `backend/tests/test_hu04_t6_integration.py::test_two_tenant_reviews_users_import_and_role_flow` | `admin_general` promueve y degrada; el rol queda en SQLite y las peticiones posteriores con el JWT anterior usan el rol vigente. |
| Transiciones y llamadas directas no autorizadas | `test_hu04_t4_endpoints.py::test_direct_role_change_without_permission_does_not_write`, `::test_invalid_transition_and_authority_fields_do_not_write`; `test_hu04_t6_integration.py::test_signed_jwt_claims_cannot_override_database_role_or_tenant` | Los roles de tenant reciben 403 al invocar el cambio de rol; transiciones y campos no permitidos se rechazan; claims de rol/tenant inconsistentes no sustituyen el registro del usuario. Se comprueba que no hubo cambios indebidos en la base. |
| Funciones restringidas por rol | `test_hu04_t6_integration.py::test_direct_http_role_matrix`; `test_hu04_t4_endpoints.py::test_operational_routes_reject_general_and_preserve_tenant_scope`; pruebas existentes de tenants y usuarios | `usuario_negocio` y `admin_tenant` acceden al contenido operativo de su tenant; solo `admin_tenant` gestiona usuarios de su tenant y solo `admin_general` administra tenants. `admin_general` recibe 403 en reviews, importaciones y dashboard. |
| Dos tenants, identificadores e importación | `test_hu04_t6_integration.py::test_two_tenant_reviews_users_import_and_role_flow`; pruebas existentes `test_tenant_isolation.py`, `test_imports_api.py`, `test_user_listing.py` y `test_user_update.py` | Los ID de reviews y usuarios ajenos devuelven 404; un `tenant_id` de query no cambia el ámbito; un `tenant_id` extra en cuerpos ordinarios da 422; la importación y el dashboard conservan datos separados entre A y B. |
| Tenant inactivo | `test_hu04_t6_integration.py::test_inactive_tenant_blocks_old_tokens_without_affecting_other_tenant`; `test_hu04_t3_authorization.py::test_inactive_tenant_blocks_login_and_existing_token_until_reactivation` | El login y las operaciones con tokens anteriores quedan bloqueados mientras A está inactivo; B conserva acceso. La reactivación restaura acceso a A sin borrar usuarios ni reviews. |
| Regresiones HU-03 y autenticación | Suite completa; en particular `test_auth.py`, `test_user_creation.py`, `test_user_listing.py`, `test_user_update.py`, `test_hu04_t4_endpoints.py::test_ordinary_users_and_tenants_keep_hu03_contracts` | Login válido e inválido, usuarios inactivos y contratos previos de usuarios pasan con la suite completa. |
| Interfaz T5 | `frontend/tests/roleAccess.test.mjs`, `frontend/tests/roleGuard.test.mjs`, `frontend/tests/hu04T6Navigation.test.mjs` | La guarda de rutas distingue los tres roles y una visita directa no abre una vista restringida. El dashboard renderiza el enlace de usuarios para `admin_tenant` y lo omite para `usuario_negocio`. |

## Cuatro criterios oficiales de HU-04

| Criterio de aceptación en #3264 | Evidencia disponible | Estado de la evidencia |
| --- | --- | --- |
| El sistema maneja roles diferenciados | Matriz HTTP de los tres roles y pruebas de rutas React; `test_auth.py::test_login_accepts_all_supported_roles`. | Demostrado en pruebas automatizadas. |
| Los permisos dependen del rol | `test_direct_http_role_matrix`, `roleAccess.test.mjs`, `roleGuard.test.mjs` y cambio de permisos efectivos tras promoción/degradación. | Demostrado en backend y en navegación basada en la sesión de login. |
| Usuarios no autorizados no acceden a funciones restringidas | Rechazos 403/404/422 en llamadas directas, acceso cruzado, claims de JWT y tenants inactivos; comprobaciones de no modificación. | Demostrado para los escenarios automatizados y contratos existentes. |
| El administrador puede cambiar roles cuando tenga permiso | Pruebas HTTP de promoción y degradación por `admin_general`, persistencia y efecto con token anterior. | Demostrado en SQLite. |

## Límites para la aceptación

- No se ejecutaron pruebas en PostgreSQL. La compatibilidad de persistencia fuera de SQLite queda pendiente de validación en un entorno PostgreSQL.
- No se ejecutó un flujo E2E en navegador con frontend y backend conectados. La integración de T5 se verificó mediante renderizado de componentes y la autorización efectiva mediante HTTP directo al backend.
- La interfaz T5 usa el rol guardado en la sesión del último login; si otro administrador cambia ese rol, su navegación puede seguir mostrando el rol anterior hasta volver a iniciar sesión. El backend aplica de inmediato el rol actual de la base de datos y rechaza cualquier acción ya no autorizada. La actualización visual sin nuevo login requiere coordinación con el responsable de T5 si se exige como parte de la aceptación.
- Esta evidencia respalda la revisión del equipo; no cambia el estado de HU-04 ni cierra la tarea T6 en OpenProject.
