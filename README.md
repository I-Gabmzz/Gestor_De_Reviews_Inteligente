# Gestor Inteligente de Reviews

Aplicación web multi-tenant para centralizar y gestionar reseñas de distintos negocios. Ayuda a los equipos a consultar comentarios dispersos, dar seguimiento a su atención y utilizar análisis asistido por inteligencia artificial como apoyo a la toma de decisiones.

**Demo:** [gestorreviews-web.onrender.com](https://gestorreviews-web.onrender.com/). La disponibilidad y la versión desplegada dependen del entorno de Render; para acceder se necesita una cuenta autorizada.

## Funcionalidades

- Acceso con roles de administración general, administración de negocio y usuario de negocio; las reseñas y operaciones de negocio se aíslan por tenant.
- Registro y edición de reseñas; autor, fecha y puntuación pueden estar ausentes. El comentario es obligatorio y la puntuación, cuando existe, se valida de 1 a 5.
- Importación de CSV y Excel y exportación CSV con los filtros del listado. La importación de archivos es atómica: si una fila es inválida, se rechaza el lote y se informa el motivo.
- Bandeja con búsqueda, filtros, detalle y seguimiento de estados; dashboard con indicadores y enlaces a la bandeja filtrada.
- Clasificación, resumen, tema, prioridad, posible solución y borrador de respuesta asistidos por IA. Las sugerencias requieren revisión humana y no se publican automáticamente.
- Notificaciones de prioridad alta, administración de usuarios y negocios, e interfaz adaptada para navegación móvil y teclado.
- Integración de reseñas externas de Google mediante SerpApi, con conexión autorizada y controles de admisión y deduplicación. Su uso depende de la configuración del servidor, credenciales y presupuesto; los proveedores se simulan en las pruebas automatizadas.

## Arquitectura y tecnologías

El frontend React se comunica por HTTP/REST y JSON con una API FastAPI. El backend organiza los casos de uso en routers, servicios, repositorios y modelos, con SQLAlchemy para persistencia. Las rutas de negocio obtienen el tenant de la sesión autenticada.

| Capa | Tecnologías principales |
| --- | --- |
| Frontend | React 19, JavaScript/JSX, Vite, React Router, Tailwind CSS 4 y Axios. |
| Backend | Python 3.13 o superior, FastAPI, Pydantic y SQLAlchemy. |
| Datos | SQLite para desarrollo; PostgreSQL mediante Psycopg para entornos configurados. |
| Pruebas y CI | pytest, Node test runner, ESLint y GitHub Actions; CI incluye PostgreSQL 17. |

Más información: [arquitectura lógica](docs/arquitectura/arquitectura-logica.md), [capas](docs/arquitectura/responsabilidades-capas.md), [modelo de datos](docs/arquitectura/modelo-datos.md) y [convenciones de API](docs/arquitectura/convenciones-api.md).

## Estructura

```text
frontend/           Aplicación React, componentes, páginas y pruebas
backend/app/        API, servicios, repositorios, modelos y configuración
backend/tests/      Pruebas unitarias, HTTP e integración PostgreSQL
backend/scripts/    Herramientas operativas y de validación
docs/               Arquitectura, contratos y evidencias por historia
samples/            Archivos de ejemplo
.github/workflows/  Automatización de integración continua
```

## Requisitos y configuración

- Python **3.13 o superior** y un entorno virtual; en Windows se recomienda Python de 64 bits para instalar las dependencias binarias.
- Node.js **20** y npm para el frontend, como en el workflow de CI.
- PostgreSQL accesible si se desea usar ese motor o ejecutar sus pruebas. SQLite es suficiente para el desarrollo básico.

Los archivos [backend/.env.example](backend/.env.example) y [frontend/.env.example](frontend/.env.example) enumeran las variables disponibles. Copiarlos como `.env` en sus respectivos directorios y ajustar los valores para el entorno. No subir `.env`, contraseñas, claves ni URLs de conexión privadas al repositorio.

| Variable | Uso |
| --- | --- |
| `DATABASE_URL` | Conexión del backend; SQLite por defecto o PostgreSQL. |
| `SECRET_KEY` | Clave privada para sesiones; usar un valor seguro en el servidor. |
| `CORS_ORIGINS` | Lista JSON de orígenes frontend permitidos; por defecto `http://localhost:5173`. |
| `VITE_API_URL` | URL base de la API para Vite; ejemplo: `http://localhost:8000/api/v1`. |
| `GEMINI_API_KEY`, `AI_PROVIDER`, `AI_MODEL` | Configuración del proveedor de IA cuando se utilicen esas funciones. |
| `SERPAPI_API_KEY`, `SERPAPI_*`, `EXTERNAL_IMPORT_*` | Proveedor y política de importación externa; la adquisición real está deshabilitada por defecto. |
| `HU24_ALLOW_REVIEW_NULLABLE_MIGRATION` | Autorización explícita para transformar una base antigua que lo requiera; desactivada por defecto. |
| `TEST_POSTGRES_URL` | Base **de pruebas** para la suite PostgreSQL; no utilizar una base compartida o productiva. |

Para PostgreSQL se aceptan URLs `postgres://`, `postgresql://` y `postgresql+psycopg://`. Antes de migrar una base existente, verificar un respaldo y su restauración y seguir el [procedimiento de HU-24/T2](docs/hu-24/t2-persistencia-migraciones.md). La autorización de migración no reemplaza esos pasos. Una base nueva puede inicializarse sin habilitarla.

Las cuentas y conexiones de Google se administran por operadores autorizados. Los procedimientos de alta inicial y sus límites están en la [documentación de importación externa](docs/hu-21/a-21b-api-importacion-externa.md); no se necesitan claves reales para ejecutar las pruebas automatizadas.

## Ejecución local

En una terminal, desde la raíz:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

En otra terminal:

```bash
cd frontend
npm ci
npm run dev
```

Vite sirve por defecto en `http://localhost:5173` y FastAPI en `http://localhost:8000`; la documentación interactiva de la API está en `http://localhost:8000/docs`. Para entrar se requiere una cuenta creada por un administrador. Para permitir un frontend remoto, añadir su origen a `CORS_ORIGINS` en el backend; la lista configurada sustituye el valor predeterminado.

## Pruebas

Desde `backend/`, con un entorno virtual y una base de pruebas aislada:

```bash
python -m pytest --ignore=tests/postgres
```

Para la integración PostgreSQL, configurar `TEST_POSTGRES_URL` con una base de pruebas autorizada y ejecutar:

```bash
python -m pytest tests/postgres -q
```

Cada caso PostgreSQL crea y elimina su propio esquema; la cuenta de pruebas necesita permisos para crearlos. Sin `TEST_POSTGRES_URL`, esos casos se omiten. Las pruebas simulan los proveedores externos y no requieren consumir SerpApi ni Gemini.

Desde `frontend/`:

```bash
npm run lint
node --test tests/*.test.mjs
npm run build
```

En PowerShell, para expandir los nombres de archivo: `node --test (Get-ChildItem tests/*.test.mjs).FullName`. GitHub Actions ejecuta la regresión backend, la integración con PostgreSQL 17 y las pruebas, lint y build del frontend. Consultar los resultados de la ejecución correspondiente al commit evaluado.

## Evolución y evidencias

- **Sprint 0:** la documentación registra los casos de uso iniciales de autenticación, negocios, importación, consulta y dashboard en el [diagrama de casos de uso](docs/diagramas/casos-de-uso-sprint-0.md). Ese diagrama describe el alcance planificado de esa etapa.
- **Sprint 1:** la evolución de edición y sus contratos está documentada en [edición de reviews](docs/api/review-edit.md).
- **Sprint 2:** el repositorio conserva historias y pruebas por funcionalidad; no se incluye aquí una asignación detallada a ese Sprint sin un backlog independiente verificable.
- **Sprint 3:** se documentaron capacidades de análisis asistido; por ejemplo, [posible solución HU-17](docs/hu-17/contrato-solucion-v1.md).
- **Sprint 4:** se integraron bandeja, indicadores y filtros, datos opcionales, administración y accesibilidad móvil. Consultar el [informe de validación integrada](docs/hu-24/validacion-funcional-integracion-sprint4.md), la [evidencia E2E de HU-24](docs/hu-24/t6-pruebas-e2e.md) y la [prueba móvil de HU-26](docs/hu-26/t6-prueba-humo-movil-tableta.md). Los documentos conservan resultados históricos y sus límites; una ejecución simulada no equivale a validar Google/SerpApi real.

El historial y los pull requests del repositorio complementan estas evidencias. La aceptación funcional y el estado del despliegue deben verificarse para la versión que se vaya a evaluar.
