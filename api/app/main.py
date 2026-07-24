"""FastAPI application factory."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.infrastructure.cache.redis import close_redis
from app.infrastructure.database.postgres import close_postgres
from app.infrastructure.graph.memory_graph import ensure_memory_graph_schema
from app.infrastructure.graph.neo4j import close_neo4j
from app.infrastructure.search.chunk_index import ensure_chunk_index
from app.infrastructure.search.elasticsearch import close_elasticsearch
from app.shared.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Release all lazily-created async clients during application shutdown."""
    try:
        await ensure_chunk_index()
    except Exception:
        logger.warning("Elasticsearch index initialization failed", exc_info=True)
    try:
        await ensure_memory_graph_schema()
    except Exception:
        logger.warning("Neo4j memory schema initialization failed", exc_info=True)
    yield
    results = await asyncio.gather(
        close_postgres(),
        close_redis(),
        close_elasticsearch(),
        close_neo4j(),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Failed to close an infrastructure client", exc_info=result)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=f"{settings.app_name} API",
        version="0.8.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)
    return application


app = create_app()
