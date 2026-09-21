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

## Estado actual

Bootstrap V2 completado.
