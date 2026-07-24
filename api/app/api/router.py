"""Root API router."""

from fastapi import APIRouter

from app.api.routes import (
    auth,
    chat,
    health,
    images,
    knowledge,
    memory,
    navigation,
    observability,
    research,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(knowledge.router)
api_router.include_router(chat.router)
api_router.include_router(images.router)
api_router.include_router(memory.router)
api_router.include_router(navigation.router)
api_router.include_router(observability.router)
api_router.include_router(research.router)
