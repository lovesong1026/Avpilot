import httpx
import pytest

from app.api.routes import health
from app.infrastructure.health import DependencyStatus, ReadinessReport
from app.main import app


@pytest.mark.anyio
async def test_liveness() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Avpilot",
        "environment": "development",
    }


@pytest.mark.anyio
async def test_readiness_returns_503_when_dependency_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def degraded_report() -> ReadinessReport:
        return ReadinessReport(
            status="degraded",
            dependencies={
                "postgres": DependencyStatus(
                    status="unavailable",
                    latency_ms=1.0,
                    error="ConnectionError",
                )
            },
        )

    monkeypatch.setattr(health, "check_readiness", degraded_report)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
