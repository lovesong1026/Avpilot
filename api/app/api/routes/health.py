"""Liveness and infrastructure readiness endpoints."""

from fastapi import APIRouter, Response, status

from app.infrastructure.health import ReadinessReport, check_readiness
from app.shared.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


@router.get("/health", response_model=ReadinessReport)
async def readiness(response: Response) -> ReadinessReport:
    report = await check_readiness()
    if report.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report
