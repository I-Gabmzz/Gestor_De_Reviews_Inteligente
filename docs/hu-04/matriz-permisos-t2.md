# HU-04 / T2 — Matriz de permisos por rol

**Estado:** VALIDADA POR EL PRODUCT OWNER el 12 de octubre de 2026, según las decisiones aprobadas en esta conversación.  
**Fuente del alcance:** OpenProject [HU-04 #3264 — Gestión de roles y permisos](https://computacion.mxl.uabc.mx/openproject/projects/is20262-gestorreviews/work_packages/3264) y [T2 #3552 — Definir la matriz de permisos por rol](https://computacion.mxl.uabc.mx/openproject/projects/is20262-gestorreviews/work_packages/3552).  
**Base técnica:** [T1 — Auditoría de permisos implementados](./auditoria-permisos-t1.md).  
**Propósito:** acordar acciones por rol y transiciones válidas/rechazadas antes de implementar T3/T4. Este documento no afirma que los permisos propuestos estén implementados.

## 1. Principios de autorización

1. FastAPI es la autoridad de autorización; ocultar botones o rutas en React no sustituye las validaciones del backend.
2. Toda operación sobre reviews, importaciones y dashboard queda limitada al tenant del usuario autenticado. El tenant se deriva de la sesión validada en servidor, no de un `tenant_id` enviado por el cliente.
3. No conceder al administrador general acceso global a contenido interno de reviews, importaciones o dashboard. Ese acceso requeriría una decisión explícita adicional.
4. El rol y tenant usados para autorizar se leen del usuario actual en base de datos. No se confía en el rol o tenant recibido del cliente.
5. Cambiar el estado de seguimiento de una review no equivale a cambiar su prioridad o clasificación.
6. Desactivar un tenant no debe borrar usuarios ni reviews. Decisión aprobada: bloquear el login y las operaciones, incluidos los tokens emitidos anteriormente, mientras el tenant esté inactivo. La reactivación permite recuperar el acceso si el usuario sigue activo.

## 2. Matriz de acciones por rol

Leyenda: **Permitido** = acción autorizada; **Denegado** = acción no autorizada; **Condicionado** = solo bajo la condición indicada; **Por decidir** = pendiente de decisión explícita.

| Acción | usuario_negocio | admin_tenant | admin_general |
| --- | --- | --- | --- |
| Iniciar sesión con credenciales válidas y usuario activo | Permitido si su tenant está activo | Permitido si su tenant está activo | Permitido sin tenant |
| Consultar dashboard del tenant | Permitido, solo su tenant | Permitido, solo su tenant | Denegado |
| Listar, consultar, buscar y filtrar reviews | Permitido, solo su tenant | Permitido, solo su tenant | Denegado; sin acceso global |
| Importar reviews CSV/Excel | Permitido, solo en su tenant | Permitido, solo en su tenant | Denegado |
| Registrar o editar reviews y cambiar su estado de seguimiento | Permitido, solo su tenant y campos permitidos | Permitido, solo su tenant y campos permitidos | Denegado |
| Exportar reviews | Por decidir según alcance de HU-19 | Por decidir según alcance de HU-19 | Denegado por defecto; no habilitar acceso global |
| Consultar/listar usuarios del tenant | Denegado | Permitido, solo su tenant | No tiene directorio global operativo definido; ver sección 5 |
| Crear usuario operativo `usuario_negocio` | Denegado | Permitido, solo en su tenant | No mediante el endpoint operativo de AT; posible administración global de cuentas queda limitada a las operaciones explícitas de la sección 5 |
| Editar nombre/correo/estado de usuario operativo del tenant | Denegado | Permitido, solo su tenant; no puede cambiar rol ni tenant_id | No mediante endpoint operativo de AT |
| Cambiar roles o asignar `tenant_id` | Denegado | Denegado | Permitido solo mediante operación administrativa explícita autorizada; no implica acceso a reviews |
| Crear, consultar, activar o desactivar tenants | Denegado | Denegado | Permitido |
| Consultar contenido de reviews de todos los tenants | Denegado | Denegado | Denegado salvo decisión explícita posterior |
| Administrar configuración global del sistema no definida en HU-04 | Por decidir | Por decidir | Por decidir |

**Nota sobre el estado actual:** T1 identificó que la API ya permite a `usuario_negocio` y `admin_tenant` realizar operaciones de reviews/importaciones/dashboard dentro de su tenant, y que el CRUD de tenants está limitado a `admin_general`. Las capacidades de exportación y los permisos nuevos de administración de roles no se consideran existentes por esta matriz.

## 3. Contrato propuesto para cambios de rol

### Reglas generales

- El rol solo puede modificarse mediante una operación administrativa explícita del backend; no se acepta `rol` ni `tenant_id` en las rutas ordinarias de creación/edición de usuarios.
- Solo `admin_general` puede autorizar altas/promociones a `admin_tenant` y degradaciones de `admin_tenant` a `usuario_negocio`, mediante operaciones administrativas explícitas que se diseñen y protejan en T3/T4.
- `admin_tenant` no puede promover, degradar ni cambiar el rol de ninguna cuenta.
- Ningún usuario puede cambiar su propio rol, su propio tenant ni elevar sus privilegios a través de su perfil.
- Ninguna ruta ordinaria permite asignar `admin_general`; las cuentas de ese rol se gestionan fuera de las operaciones normales de tenant. No crear un mecanismo de autopromoción.
- La operación administrativa debe validar explícitamente la combinación rol/tenant antes de persistirla: `admin_general` sin tenant; `admin_tenant` y `usuario_negocio` con tenant válido.
- Rechazar solicitudes con campos de autoridad inesperados en endpoints ordinarios (422 según el contrato actual); rechazar con 403 las operaciones administrativas invocadas por roles sin autorización. Para recursos ajenos al tenant, mantener el comportamiento 404 cuando corresponda para no revelar su existencia.
- Registrar quién realizó el cambio, cuenta afectada, rol anterior/nuevo, tenant implicado y fecha sería recomendable, pero la auditoría persistente de cambios es **propuesta adicional pendiente de alcance**, no requisito confirmado de T2.

### Transiciones válidas propuestas

| Estado inicial | Transición | Actor autorizado | Resultado propuesto |
| --- | --- | --- | --- |
| Cuenta nueva dentro de un tenant activo | Crear como `usuario_negocio` | `admin_tenant` de ese tenant | Permitido; cuenta ligada al tenant autenticado |
| `usuario_negocio` | `admin_tenant` | `admin_general` mediante operación específica | Permitido tras validar tenant y reglas de cuenta |
| Cuenta existente `admin_tenant` | `usuario_negocio` | `admin_general` mediante operación administrativa específica | Permitido; degradación aprobada por el PO |
| `admin_general` | Cualquier rol de tenant | Ninguna ruta ordinaria; solo proceso administrativo separado si se define | Por decidir; no incluir en T3/T4 sin decisión explícita |
| Cuenta de tenant A | Mover a tenant B | Ningún actor mediante actualización ordinaria | Denegado por defecto; traslado entre tenants requiere decisión y flujo específico |

### Transiciones y solicitudes rechazadas

| Solicitud | Resultado propuesto | Motivo |
| --- | --- | --- |
| `usuario_negocio` intenta crear o editar usuarios | 403 | No administra usuarios |
| `admin_tenant` intenta asignar `admin_tenant` o `admin_general` al crear/editar usuario | 422 en endpoint ordinario; 403 si invoca una operación administrativa reservada | Evitar escalada de privilegios |
| `admin_tenant` intenta cambiar su propio rol | Denegado | Prohibida la autopromoción/autodegradación por perfil |
| Cualquier usuario intenta cambiar su `tenant_id` en endpoint ordinario | 422 | El tenant no es un campo editable por el usuario |
| Cualquier actor no autorizado invoca operación de cambio de rol | 403 | Permiso insuficiente |
| Asignar `admin_general` con `tenant_id` no nulo | Rechazado por validación | Inconsistencia rol/tenant |
| Asignar `admin_tenant` o `usuario_negocio` sin tenant válido | Rechazado por validación | Inconsistencia rol/tenant |
| Usuario intenta acceder a reviews o dashboard de otro tenant | No exponer datos; 404 para recursos individuales ajenos y filtros limitados al tenant propio | Aislamiento multi-tenant |
| Usuario activo pertenece a tenant inactivo | Denegar login y operaciones, incluidos tokens anteriores, hasta reactivación; conservar usuarios y reviews | Regla aprobada por el PO; T1 identificó que hoy el estado del tenant no bloquea el acceso |

## 4. Tenants inactivos — decisión aprobada

Cuando `Tenant.estado = inactivo`, los usuarios `usuario_negocio` y `admin_tenant` de ese tenant no pueden iniciar sesión ni continuar usando tokens previamente emitidos para acceder a endpoints operativos. La reactivación permite volver a operar, siempre que el usuario también esté activo. La desactivación no elimina ni modifica usuarios o reviews.

**Implementación pendiente:** T2 documenta la regla, pero no modifica el código. La regla debe reflejarse en T3/T4 (o asignarse explícitamente a una tarea separada antes de comenzar la implementación). T6 deberá probar login, token previo, endpoints operativos y reactivación.

## 5. Alcance de `admin_general` — decisiones aprobadas y pendientes

Decisiones aprobadas:

- Puede crear, consultar, editar, activar y desactivar tenants.
- Puede autorizar altas/promociones a `admin_tenant` y degradaciones a `usuario_negocio` mediante operaciones administrativas explícitas.
- No tiene acceso global a reviews, importaciones ni dashboard de los tenants.
- Puede crear, consultar, editar, activar y desactivar tenants.

Pendiente de decisión:
- El directorio global de usuarios queda pendiente; no debe implementarse hasta que el PO determine su necesidad y límites.
- La gestión de cuentas `admin_general` no queda definida por esta tarea y requiere decisión explícita.
- Toda futura operación global debe limitarse a los campos y acciones autorizados, sin aceptar cambios arbitrarios de rol o tenant.

## 6. Registro de validación del Product Owner

El PO validó explícitamente las siguientes decisiones el 12 de octubre de 2026:

1. **Promoción a `admin_tenant`: aprobada.** Solo `admin_general`, mediante operación administrativa explícita, puede autorizar la promoción.
2. **Tenant inactivo: aprobado.** Bloquear inicio de sesión y operaciones, incluidos tokens anteriores, mientras el tenant permanezca inactivo; conservar usuarios y reviews.
3. **Límite de `admin_general`: aprobado.** Puede administrar tenants y cuentas administrativas mediante operaciones explícitas, pero no tiene acceso global a reviews ni dashboard internos. La importación operativa también queda denegada.
4. **Degradación de `admin_tenant`: aprobada.** `admin_general` puede degradar una cuenta a `usuario_negocio` mediante operación administrativa autorizada.
5. **Directorio global de usuarios: pendiente.** No implementarlo hasta una decisión posterior.

También quedan como reglas aprobadas la prohibición de autopromoción y de cambiar el propio rol o `tenant_id` mediante rutas ordinarias, así como la separación entre autorización backend y visibilidad de interfaz.

**Pendientes fuera de la aprobación actual:** alcance del directorio global; gestión de cuentas `admin_general`; si se exige auditoría persistente de cambios de rol; alcance de exportación de reviews según HU-19. No ampliar estas funciones sin decisión explícita.

**Criterio de finalización T2:** la matriz y las transiciones válidas/rechazadas están revisadas por el PO y el contrato de cambio de rol queda acordado en los términos anteriores. T3/T4 pueden basarse en estas decisiones aprobadas; los puntos marcados como pendientes deben permanecer fuera de implementación hasta resolverse.
## 7. Trazabilidad con T1 y tareas siguientes

- **T1 (#3551):** evidencia de endpoints, controles actuales y brechas en `auditoria-permisos-t1.md`.
- **T2 (#3552):** matriz y contrato de cambio de rol validados por el PO; directorio global y otros puntos señalados permanecen pendientes.
- **T3:** implementar validaciones reutilizables FastAPI conforme a la matriz aprobada.
- **T4:** aplicar la matriz a endpoints y añadir solo operaciones administrativas aprobadas.
- **T5:** ajustar navegación/acciones de React por rol, sin sustituir autorización backend.
- **T6:** probar transiciones autorizadas y rechazadas, acceso cruzado entre tenants, tenant inactivo y rutas protegidas conforme a la matriz final.
