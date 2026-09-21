# Guía de demostración de HU-07

## Requisitos

- Python 3.13 o posterior.
- Node.js 20.19 o posterior.

## 1. Preparar el backend

Desde la raíz del repositorio:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m scripts.seed_demo
python -m uvicorn app.main:app --reload
```

El generador puede ejecutarse varias veces sin duplicar los datos. Sus credenciales son únicamente para desarrollo local:

```text
Usuario: demo@example.com
Contraseña: demo123
```

## 2. Preparar el frontend

```powershell
cd frontend
npm install
npm run dev
```

Abrir `http://localhost:5173` e iniciar sesión con las credenciales de demostración. La interfaz de HU-01 guarda el token y dirige al dashboard. Desde ahí, seleccionar **Consultar reviews**.

Si el backend utiliza otra dirección, definir `VITE_API_URL` incluyendo el prefijo `/api/v1` antes de iniciar Vite.

## 3. Recorrido de la demostración

1. Mostrar que la tabla contiene autor, resumen, fecha, fuente, calificación y estado.
2. Seleccionar una fila y señalar la petición de detalle.
3. Mostrar contenido completo, categoría y prioridad.
4. Explicar que el frontend nunca envía un `tenant_id`.
5. Explicar que el backend lo obtiene del usuario autenticado y filtra todas las consultas.
6. Como evidencia técnica, ejecutar `python -m pytest tests -q` y mostrar que las pruebas de aislamiento pasan.

## Mensaje breve para la exposición

> En HU-07 implementamos la consulta y el detalle de reviews. La característica importante no es solamente la tabla: todas las consultas quedan limitadas por el tenant del usuario autenticado. Una persona no puede solicitar información de otra organización cambiando un parámetro, porque el tenant se obtiene del token y se aplica nuevamente en el repositorio.
