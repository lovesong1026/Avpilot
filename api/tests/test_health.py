import httpx
import pytest

from app.main import app


@pytest.mark.anyio
async def test_health() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Avpilot",
        "environment": "development",
    }


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
