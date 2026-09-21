from fastapi import FastAPI

from api.routes.health import router as health_router

app = FastAPI(title="Gestor Inteligente de Reviews")
app.include_router(health_router)

