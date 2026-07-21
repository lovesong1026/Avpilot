"""Root API router."""

from fastapi import APIRouter

from app.api.routes import auth, chat, health, images, knowledge

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(knowledge.router)
api_router.include_router(chat.router)
api_router.include_router(images.router)
