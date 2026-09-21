# Casos de uso del Sprint 0

El diagrama representa las historias seleccionadas para el Sprint 0. Indica alcance funcional, no que todas las historias estén terminadas o integradas en `main`.

```mermaid
flowchart LR
    AG["👤 Administrador general"]
    AT["👤 Administrador de tenant"]
    UN["👤 Usuario de negocio"]

    subgraph GRI["Gestor Inteligente de Reviews"]
        HU01(["HU-01 · Iniciar sesión"])
        HU02(["HU-02 · Gestionar tenants"])
        HU05(["HU-05 · Importar reviews"])
        HU07(["HU-07 · Consultar reviews"])
        DETAIL(["Ver detalle de review"])
        HU11(["HU-11 · Consultar dashboard"])
        ISOLATION(["Aplicar aislamiento por tenant"])
    end

    AG --> HU01
    AG --> HU02
    AT --> HU01
    AT --> HU05
    AT --> HU07
    AT --> HU11
    UN --> HU01
    UN --> HU05
    UN --> HU07
    UN --> HU11

    HU07 -. "incluye" .-> DETAIL
    HU05 -. "incluye" .-> ISOLATION
    HU07 -. "incluye" .-> ISOLATION
    HU11 -. "incluye" .-> ISOLATION
```

## Límites del Sprint 0

- Incluye la arquitectura base, autenticación, tenants, importación inicial, consulta de reviews y dashboard básico.
- Excluye el procesamiento real con inteligencia artificial, integraciones con plataformas externas, notificaciones y reportes avanzados.
