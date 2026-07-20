"""Readiness checks for external infrastructure."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from time import perf_counter

from pydantic import BaseModel

from app.infrastructure.cache.redis import check_redis
from app.infrastructure.database.postgres import check_postgres
from app.infrastructure.graph.neo4j import check_neo4j
from app.infrastructure.search.elasticsearch import check_elasticsearch
from app.shared.config import get_settings

logger = logging.getLogger(__name__)

Check = Callable[[], Awaitable[None]]


class DependencyStatus(BaseModel):
    status: str
    latency_ms: float
    error: str | None = None


class ReadinessReport(BaseModel):
    status: str
    dependencies: dict[str, DependencyStatus]


async def _run_check(name: str, check: Check) -> tuple[str, DependencyStatus]:
    started_at = perf_counter()
    try:
        await asyncio.wait_for(check(), timeout=get_settings().health_check_timeout_seconds)
    except Exception as exc:
        logger.warning("Infrastructure health check failed: %s", name, exc_info=exc)
        result = DependencyStatus(
            status="unavailable",
            latency_ms=round((perf_counter() - started_at) * 1000, 2),
            error=type(exc).__name__,
        )
    else:
        result = DependencyStatus(
            status="ok",
            latency_ms=round((perf_counter() - started_at) * 1000, 2),
        )
    return name, result


async def check_readiness() -> ReadinessReport:
    checks: dict[str, Check] = {
        "postgres": check_postgres,
        "elasticsearch": check_elasticsearch,
        "neo4j": check_neo4j,
        "redis": check_redis,
    }
    results = await asyncio.gather(*(_run_check(name, check) for name, check in checks.items()))
    dependencies = dict(results)
    overall_status = (
        "ok" if all(item.status == "ok" for item in dependencies.values()) else "degraded"
    )
    return ReadinessReport(status=overall_status, dependencies=dependencies)
