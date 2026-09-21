from fastapi import APIRouter

from app.api.routers import auth, dashboard, imports, reviews, tenants, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(tenants.router)
api_router.include_router(users.router)
api_router.include_router(reviews.router)
api_router.include_router(imports.router)
api_router.include_router(dashboard.router)
