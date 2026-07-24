"""Run async application work safely inside a synchronous Celery process."""

import asyncio
from collections.abc import Awaitable, Callable

from app.infrastructure.cache.redis import close_redis
from app.infrastructure.database.postgres import close_postgres
from app.infrastructure.graph.neo4j import close_neo4j
from app.infrastructure.search.elasticsearch import close_elasticsearch


def run_async[T](factory: Callable[[], Awaitable[T]]) -> T:
    async def execute() -> T:
        try:
            return await factory()
        finally:
            await asyncio.gather(
                close_postgres(),
                close_redis(),
                close_elasticsearch(),
                close_neo4j(),
                return_exceptions=True,
            )

    return asyncio.run(execute())
