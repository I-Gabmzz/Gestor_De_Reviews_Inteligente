# Gestor Inteligente de Reviews

Base técnica para una plataforma web de gestión de reviews, preparada para el desarrollo colaborativo durante el Sprint 0.

## Arquitectura general

El proyecto utiliza una arquitectura de monorepo con un frontend independiente y un backend independiente. Ambos módulos se comunican mediante una API HTTP versionada bajo `/api/v1`.

## Stack tecnológico

- Frontend: React 19, JavaScript/JSX, Vite, Tailwind CSS v4, React Router DOM, Axios y Lucide React.
- Backend: Python 3.13+, FastAPI, SQLAlchemy, SQLite para desarrollo, PostgreSQL como compatibilidad futura, Pydantic Settings y Uvicorn.
- Calidad y colaboración: Git, GitHub Actions y ESLint.

## Estructura de carpetas

```text
frontend/              Aplicación React y configuración de Vite.
backend/               Aplicación FastAPI y módulos de backend.
docs/                  Documentación técnica del proyecto.
samples/               Archivos de referencia para desarrollo.
.github/workflows/     Automatizaciones de integración continua.
```

## Ejecutar el frontend

```bash
cd frontend
npm install
npm run dev
```

Para validar la compilación:

```bash
npm run build
```

## Ejecutar el backend

```bash
cd backend
python -m venv .venv
```

Activar el entorno virtual y después instalar dependencias:

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

## Flujo de ramas Git

- `main`: rama estable del proyecto.
- `chore/project-bootstrap`: rama de preparación de la arquitectura base.
- Cada Historia de Usuario debe desarrollarse en una rama independiente y abrir una Pull Request hacia la rama acordada por el equipo.

## Organización Scrum

La planificación se organiza como `Epic → Historia de Usuario (HU) → Task`. Cada HU debe dividirse en tareas pequeñas, implementarse en su propia rama y validarse antes de integrarse.
