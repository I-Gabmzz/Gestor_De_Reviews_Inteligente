from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import api_router
from app.core.config import LOCAL_FRONTEND_ORIGIN, settings

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[LOCAL_FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/v1/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "project": settings.app_name,
    }
