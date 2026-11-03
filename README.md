# Gestor Inteligente de Reviews

Plataforma web multi-tenant para que distintos negocios centralicen, consulten y administren reviews de clientes. El producto está preparado para incorporar capacidades de inteligencia artificial en etapas futuras, fuera del alcance del bootstrap técnico.

## Arquitectura

El sistema adopta una arquitectura Cliente-Servidor complementada con una Arquitectura Basada en Capas. React funciona como cliente, FastAPI como servidor y la comunicación se realiza mediante HTTP, REST y JSON.

## Stack Tecnológico

- Frontend: React 19, JavaScript, JSX, Vite, Tailwind CSS v4, React Router DOM, Axios y Lucide React.
- Backend: Python 3.13, FastAPI, SQLAlchemy, Pydantic Settings y Uvicorn.
- Persistencia: SQLite para desarrollo, con diseño compatible con PostgreSQL.
- Herramientas: Git, GitHub Actions y ESLint.

## Arquitectura del Proyecto

- Presentación: interfaces, navegación y consumo de la API dentro de `frontend/`.
- Aplicación / Negocio: casos de uso y reglas del producto dentro de `backend/app/services/`, expuestos por routers FastAPI.
- Acceso a Datos: persistencia aislada dentro de `backend/app/repositories/` y `backend/app/db/`.
- Datos: SQLite en desarrollo y PostgreSQL como objetivo compatible.

El flujo interno acordado es `React → Router → Service → Repository → Base de datos`.

## Estructura del repositorio

```text
frontend/
├── public/
└── src/
    ├── components/
    ├── layouts/
    ├── pages/
    ├── services/
    ├── hooks/
    ├── utils/
    ├── App.jsx
    └── main.jsx
backend/
├── app/
│   ├── api/routers/
│   ├── services/
│   ├── repositories/
│   ├── models/
│   ├── schemas/
│   ├── db/
│   ├── core/
│   └── main.py
└── tests/
docs/
├── arquitectura/
├── diagramas/
└── api/
samples/
.github/workflows/
```

## Convenciones oficiales

- Prefijo de API: `/api/v1`.
- Propiedades JSON: `snake_case`.
- Fechas: ISO 8601.
- Estados de tenant: `activo`, `inactivo`.
- Estados de review: `nueva`, `en_revision`, `atendida`.
- Roles: `usuario_negocio`, `admin_tenant`, `admin_general`.
- Categoría y prioridad: `null` inicialmente.
- Comunicación: REST sobre HTTP y respuestas JSON.

## Flujo Git

`main` conserva la versión estable. `BaseDelProyecto` contiene la base arquitectónica oficial y cada Historia de Usuario se desarrolla en una rama independiente, mediante commit, push, Pull Request, revisión y CI antes de integrarse.

## Scrum

La organización del trabajo sigue `Epic → Historia de Usuario → Task`. El bootstrap establece infraestructura compartida y no forma parte de una Historia de Usuario.

## Cómo ejecutar Frontend

```bash
cd frontend
npm install
npm run dev
```

## Cómo ejecutar Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

En Windows, la activación equivalente es `.venv\Scripts\activate`.

## Conexión con PostgreSQL

El backend conserva SQLite como opción local. Para usar PostgreSQL, instalar
las dependencias de `backend/requirements.txt` y definir `DATABASE_URL` en el
entorno del backend. Se aceptan los prefijos `postgres://`, `postgresql://` y
`postgresql+psycopg://`; los dos primeros seleccionan automáticamente Psycopg 3.
Las credenciales y opciones de conexión, incluido `sslmode`, se conservan.

En Render, el backend y PostgreSQL deben estar en la misma región y workspace
para utilizar la conexión interna. Para conexiones externas, usar la URL externa
con TLS según la configuración del proveedor. Guardar las URLs y claves como
variables privadas; no agregarlas al repositorio.

Al iniciar, el backend crea las tablas que faltan y aplica las migraciones
aditivas existentes. Esto prepara una base nueva; **no copia automáticamente
los datos de SQLite a PostgreSQL**. La carga de datos y la creación de las
cuentas de producción se realizan como pasos posteriores del despliegue.

### Verificar la compatibilidad

Desde `backend`, ejecutar la regresión local:

```bash
python -m pytest --ignore=tests/postgres
```

Para las pruebas reales, definir `TEST_POSTGRES_URL` con una base PostgreSQL de
pruebas y ejecutar:

```bash
python -m pytest tests/postgres -q
```

Cada caso crea y elimina exclusivamente su propio esquema temporal. La cuenta
de pruebas necesita permisos para crear esquemas. Estas pruebas verifican
migraciones, autenticación, aislamiento entre negocios, reviews, archivos,
resultados de análisis, notificaciones y concurrencia. Los proveedores externos
son simulados: la ejecución no consume Gemini ni SerpApi. Sin la variable, los
casos PostgreSQL se omiten; las pruebas SQLite siguen disponibles.

GitHub Actions ejecuta la regresión habitual y un trabajo adicional con un
servidor PostgreSQL 17 temporal. Sus datos y credenciales son exclusivamente
de prueba y no corresponden al entorno de producción.

## Dominios autorizados del frontend

El backend lee `CORS_ORIGINS` como una lista JSON de orígenes completos. Sin la
variable, conserva `http://localhost:5173` para desarrollo. Al configurarla, la
lista reemplaza ese valor: incluir localhost explícitamente si también se necesita.

En el servicio **backend** de Render, agregar en **Environment**:

```text
CORS_ORIGINS=["https://gestorreviews-web.onrender.com"]
```

El valor es la lista completa, incluidos los corchetes y comillas dobles. Usar
solo esquema, dominio y puerto opcional; no agregar `/api/v1`, rutas, credenciales
ni comodines. Una configuración inválida impide iniciar el servicio. Una lista
vacía desactiva el acceso desde otros orígenes. Esto configura CORS; los endpoints
siguen requiriendo sus permisos y autenticación habituales.

Después de integrar este cambio, guardar la variable y desplegar el último commit
de `main`. Guardar solo la variable no modifica un proceso que ya está ejecutándose.
Las instalaciones creadas mediante **Public Git Repository** requieren desplegar
manualmente. Verificar el inicio de sesión desde el frontend y que la exportación
conserve el nombre del archivo. Las cuentas de producción se crean por separado.

## Alta inicial de un negocio en Render

Con el backend desplegado y las tablas ya creadas, un operador de la base puede
crear un negocio y su administrador desde una terminal local. Instalar primero
las dependencias del backend y ejecutar desde `backend`:

```bash
python -m scripts.create_business --name "Nombre del negocio" --email admin.demo@example.com
```

El comando pide la **External Database URL** de Render con entrada oculta, muestra
el destino y solicita escribir `CREAR`. Después pide y confirma una contraseña
de al menos 12 caracteres, también oculta. No pasar secretos como argumentos ni
guardarlos en archivos o en el historial. La conexión usa TLS y la contraseña
del usuario se almacena únicamente como hash Argon2.

El negocio y la cuenta `admin_tenant` se crean en una sola transacción. Repetir
el alta conserva los identificadores, los datos y la contraseña original. Si el
correo ya pertenece a otro negocio o tiene otro rol, o el nombre es ambiguo o
inactivo, se cancela sin cambios parciales. No crea un administrador general,
reseñas ni conexiones externas. El administrador puede crear usuarios desde
el panel después de iniciar sesión. Este comando no se ejecuta al desplegar y
no requiere volver a desplegar la web para que aparezca el negocio nuevo.

## Estado actual

Bootstrap V2 completado.
## Importación manual de reseñas Google

La integración usa SerpApi en el backend. La clave nunca se configura en el frontend.
La importación está deshabilitada por defecto y cada negocio requiere una conexión
Google aprobada. Un lote puede contener sólo una parte de las reseñas públicas;
los registros sin comentario se cuentan como omitidos y no se inventa texto.

Para habilitar una conexión existente, desde `backend` ejecutar en una terminal:

```bash
python -m scripts.configure_external_reviews --tenant-id ID --name 'Nombre exacto del negocio' --data-id '0xabc:0x123' --approval 'Referencia real de aprobación'
```

La URL externa de PostgreSQL de Render se introduce de forma oculta. El comando
verifica el ID y el nombre del negocio, no cambia usuarios ni contraseñas, no
reemplaza otra conexión Google y no importa reseñas. Repetirlo conserva la conexión.
No registrar credenciales en Git, comentarios o capturas.

Configuración de ejemplo para una demostración acotada en el backend de Render:

| Variable | Valor |
| --- | --- |
| `SERPAPI_API_KEY` | Clave privada de la cuenta |
| `SERPAPI_PAGE_SIZE` | `20` |
| `SERPAPI_MAX_PAGES` | `1` |
| `SERPAPI_SORT_BY` | `qualityScore` |
| `SERPAPI_TIMEOUT_SECONDS` | `60` |
| `EXTERNAL_IMPORT_ENABLED` | `true` |
| `EXTERNAL_IMPORT_PAGE_SIZE` | `20` |
| `EXTERNAL_IMPORT_MAX_PAGES` | `1` |
| `EXTERNAL_IMPORT_ALLOW_LIMITED_BATCHES` | `true` |
| `EXTERNAL_IMPORT_TENANT_REQUEST_BUDGET` | `5` |
| `EXTERNAL_IMPORT_ACCOUNT_REQUEST_BUDGET` | `5` |
| `EXTERNAL_IMPORT_BUDGET_WINDOW_SECONDS` | `3600` |

Los presupuestos cuentan intentos reservados, no créditos facturados por SerpApi.
El proveedor puede devolver menos registros que el tamaño solicitado. La opción
de lotes limitados sólo admite páginas exitosas detenidas por el límite del
servidor; los fallos, tokens repetidos y orígenes contradictorios no se guardan.

Después de desplegar backend y frontend, iniciar sesión en el negocio, abrir
Importaciones, seleccionar la conexión Google y pulsar Importar desde Google.
Verificar los contadores, consultar las reviews y recargar. Repetir el mismo lote
debe indicar repetidas sin crear duplicados. Comprobar también la exportación CSV
y que una cuenta de otro negocio no vea esas reseñas. Una operación con resultado
incierto requiere revisión del responsable antes de volver a importar.
