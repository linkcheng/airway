import pytest
import httpx
import respx

from airway.bisheng_client import BishengAPIClient, BishengAPIError
from airway.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        bisheng_api_url="http://bisheng-test:7860",
        bisheng_token="initial-token",
        bisheng_username="admin",
        bisheng_password="secret",
        api_timeout=5.0,
    )


@pytest.fixture
def client(settings: Settings) -> BishengAPIClient:
    return BishengAPIClient(settings)


@pytest.mark.asyncio
async def test_request_injects_cookie(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.get("http://bisheng-test:7860/api/v1/test").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        result = await client.get("/api/v1/test")
        assert result == {"ok": True}

        req = respx.calls[0].request
        assert "access_token=initial-token" in str(req.headers.get("cookie", ""))


@pytest.mark.asyncio
async def test_401_triggers_refresh(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.get("http://bisheng-test:7860/api/v1/data").mock(
            side_effect=[
                httpx.Response(401, json={"detail": "Unauthorized"}),
                httpx.Response(200, json={"data": "ok"}),
            ]
        )
        respx.post("http://bisheng-test:7860/api/v1/user/login").mock(
            return_value=httpx.Response(200, json={"access_token": "new-token"})
        )

        result = await client.get("/api/v1/data")
        assert result == {"data": "ok"}
        assert client._token == "new-token"


@pytest.mark.asyncio
async def test_refresh_failure_raises(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.get("http://bisheng-test:7860/api/v1/data").mock(
            return_value=httpx.Response(401, json={"detail": "Unauthorized"})
        )
        respx.post("http://bisheng-test:7860/api/v1/user/login").mock(
            return_value=httpx.Response(403, json={"detail": "Forbidden"})
        )

        with pytest.raises(BishengAPIError) as exc_info:
            await client.get("/api/v1/data")
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_non_401_error_raises(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.get("http://bisheng-test:7860/api/v1/data").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        with pytest.raises(BishengAPIError) as exc_info:
            await client.get("/api/v1/data")
        assert exc_info.value.status_code == 500
