from fastapi import APIRouter

from app.api.routers import auth, dashboard, imports, priorities, reviews, summaries, tenants, topics, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(tenants.router)
api_router.include_router(users.router)
api_router.include_router(reviews.router)
api_router.include_router(summaries.router)
api_router.include_router(topics.router)
api_router.include_router(priorities.router)
api_router.include_router(imports.router)
api_router.include_router(dashboard.router)
