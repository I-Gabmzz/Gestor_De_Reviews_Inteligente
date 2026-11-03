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

## Estado actual

Bootstrap V2 completado.
