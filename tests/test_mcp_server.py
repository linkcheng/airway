import json
import os

import httpx
import pytest
import respx

# Ensure test settings before importing app
os.environ.setdefault("AIRWAY_BISHENG_API_URL", "http://bisheng-test:7860")
os.environ.setdefault("AIRWAY_BISHENG_TOKEN", "test-token")

from airway.app import create_app

BISHENG_URL = "http://bisheng-test:7860"


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health_ok(client: httpx.AsyncClient) -> None:
    with respx.mock:
        respx.get(f"{BISHENG_URL}/api/v1/chat/chat/online").mock(
            return_value=httpx.Response(200, json={})
        )
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_degraded(client: httpx.AsyncClient) -> None:
    with respx.mock:
        respx.get(f"{BISHENG_URL}/api/v1/chat/chat/online").mock(
            side_effect=httpx.ConnectError("unreachable")
        )
        resp = await client.get("/health")
        assert resp.status_code == 503
        assert resp.json()["status"] == "degraded"


@pytest.mark.asyncio
async def test_mcp_sse_endpoint_exists(client: httpx.AsyncClient) -> None:
    resp = await client.get("/sse")
    # 307 = redirect (trailing slash), 200 = SSE stream
    assert resp.status_code in (200, 307, 405, 406)
