# HU-04 / T2 — Matriz propuesta de permisos por rol

**Estado:** BORRADOR — pendiente de validación explícita del Product Owner (David Escárcega).  
**Fuente del alcance:** OpenProject [HU-04 #3264 — Gestión de roles y permisos](https://computacion.mxl.uabc.mx/openproject/projects/is20262-gestorreviews/work_packages/3264) y [T2 #3552 — Definir la matriz de permisos por rol](https://computacion.mxl.uabc.mx/openproject/projects/is20262-gestorreviews/work_packages/3552).  
**Base técnica:** [T1 — Auditoría de permisos implementados](./auditoria-permisos-t1.md).  
**Propósito:** acordar acciones por rol y transiciones válidas/rechazadas antes de implementar T3/T4. Este documento no afirma que los permisos propuestos estén implementados.

## 1. Principios de autorización

1. FastAPI es la autoridad de autorización; ocultar botones o rutas en React no sustituye las validaciones del backend.
2. Toda operación sobre reviews, importaciones y dashboard queda limitada al tenant del usuario autenticado. El tenant se deriva de la sesión validada en servidor, no de un `tenant_id` enviado por el cliente.
3. No conceder al administrador general acceso global a contenido interno de reviews, importaciones o dashboard. Ese acceso requeriría una decisión explícita adicional.
4. El rol y tenant usados para autorizar se leen del usuario actual en base de datos. No se confía en el rol o tenant recibido del cliente.
5. Cambiar el estado de seguimiento de una review no equivale a cambiar su prioridad o clasificación.
6. Desactivar un tenant no debe borrar usuarios ni reviews. La regla propuesta es bloquear el acceso operativo a usuarios de ese tenant mientras esté inactivo; pendiente de aprobación del PO y de confirmar su ubicación en HU-04 u otra tarea.

## 2. Matriz de acciones por rol

Leyenda: **Permitido** = acción autorizada propuesta; **Denegado** = acción no autorizada; **Condicionado** = solo bajo la condición indicada; **Por decidir** = no implementar hasta resolverlo.

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
| Cambiar roles o asignar `tenant_id` | Denegado | Denegado | Condicionado a operación administrativa específica autorizada y auditada |
| Crear, consultar, activar o desactivar tenants | Denegado | Denegado | Permitido |
| Consultar contenido de reviews de todos los tenants | Denegado | Denegado | Denegado salvo decisión explícita posterior |
| Administrar configuración global del sistema no definida en HU-04 | Por decidir | Por decidir | Por decidir |

**Nota sobre el estado actual:** T1 identificó que la API ya permite a `usuario_negocio` y `admin_tenant` realizar operaciones de reviews/importaciones/dashboard dentro de su tenant, y que el CRUD de tenants está limitado a `admin_general`. Las capacidades de exportación y los permisos nuevos de administración de roles no se consideran existentes por esta matriz.

## 3. Contrato propuesto para cambios de rol

### Reglas generales

- El rol solo puede modificarse mediante una operación administrativa explícita del backend; no se acepta `rol` ni `tenant_id` en las rutas ordinarias de creación/edición de usuarios.
- Solo `admin_general` puede autorizar altas o promociones a `admin_tenant`, mediante la operación administrativa que se diseñe y proteja en T3/T4.
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
| Cuenta existente `admin_tenant` | `usuario_negocio` | `admin_general` mediante operación específica | Permitido como degradación administrativa, si el PO aprueba que se soporte |
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
| Usuario activo pertenece a tenant inactivo | Denegar login y operaciones operativas hasta reactivación, si el PO aprueba la regla | La T1 identificó que hoy el estado del tenant no bloquea el acceso |

## 4. Tenants inactivos

**Propuesta para validar:** cuando `Tenant.estado = inactivo`, los usuarios `usuario_negocio` y `admin_tenant` de ese tenant no pueden iniciar sesión ni continuar usando tokens previos para acceder a endpoints operativos. La reactivación permite volver a operar, sujeto al estado individual del usuario. No eliminar ni modificar reviews o usuarios por la desactivación.

**Motivo:** la T1 confirmó que actualmente se comprueba el estado del usuario, pero no el estado del tenant en login ni en `get_current_user`/resolución de tenant. Es una brecha observada, no una regla ya implementada.

**Pendiente de decisión:** confirmar si esta regla forma parte de HU-04/T3-T4 o si se asignará a una tarea separada. No se implementa en T2.

## 5. Alcance de `admin_general`

Propuesta de límites:

- Puede crear, consultar, editar, activar y desactivar tenants.
- Puede autorizar altas/promociones/degradaciones de `admin_tenant` mediante operaciones explícitas de administración de cuentas, una vez aprobadas y diseñadas.
- No obtiene por ello acceso a reviews, importaciones, dashboard ni contenido operativo de los tenants.
- La existencia de un directorio global de usuarios y la gestión de cuentas `admin_general` no están definidas suficientemente por T2. No implementarlas hasta que el PO determine su necesidad y límites.
- Toda futura operación global debe limitarse a los campos y acciones autorizados, no aceptar cambios arbitrarios de rol o tenant.

## 6. Validación requerida del Product Owner

Antes de dar T2 por finalizada, el PO debe aprobar o corregir explícitamente:

1. La matriz de acciones por rol de la sección 2.
2. Que solo `admin_general` pueda promover a `admin_tenant), y si también puede degradarlo.
3. La prohibición de autopromoción, de modificar el propio rol y de cambiar `tenant_id` mediante rutas ordinarias.
4. El bloqueo de acceso cuando un tenant esté inactivo y si corresponde a HU-04 o a otra tarea.
5. El límite de `admin_general`: sin acceso global a reviews internas, importaciones ni dashboard.
6. Si se requiere directorio global de usuarios, administración de cuentas `admin_general` o auditoría persistente de cambios de rol.

**Criterio de finalización T2:** matriz y transiciones válidas/rechazadas revisadas por el Product Owner; contrato de cambio de rol acordado. Hasta recibir esa aprobación, este documento permanece como borrador y T3/T4 no deben basarse en sus propuestas como decisiones definitivas.

## 7. Trazabilidad con T1 y tareas siguientes

- **T1 (#3551):** evidencia de endpoints, controles actuales y brechas en `auditoria-permisos-t1.md`.
- **T2 (#3552):** este borrador de matriz y contrato de cambio de rol; pendiente de validación del PO.
- **T3:** implementar validaciones reutilizables FastAPI conforme a la matriz aprobada.
- **T4:** aplicar la matriz a endpoints y añadir solo operaciones administrativas aprobadas.
- **T5:** ajustar navegación/acciones de React por rol, sin sustituir autorización backend.
- **T6:** probar transiciones autorizadas y rechazadas, acceso cruzado entre tenants, tenant inactivo y rutas protegidas conforme a la matriz final.
