"""Root API router."""

from fastapi import APIRouter

from app.api.routes import auth, health, knowledge

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(knowledge.router)
