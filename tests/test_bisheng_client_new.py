import base64

import httpx
import pytest
import respx

from airway.bisheng_client import BishengAPIClient, BishengAPIError
from airway.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        bisheng_api_url="http://bisheng-test:7860",
        bisheng_token="test-token",
        bisheng_username="admin",
        bisheng_password="secret",
        api_timeout=5.0,
    )


@pytest.fixture
def client(settings: Settings) -> BishengAPIClient:
    return BishengAPIClient(settings)


BISHENG_URL = "http://bisheng-test:7860"


@pytest.mark.asyncio
async def test_delete_sends_delete_request(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.delete(f"{BISHENG_URL}/api/v1/knowledge").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        result = await client.delete("/api/v1/knowledge", json={"knowledge_id": "k1"})
        assert result == {"status": "ok"}
        req = respx.calls[0].request
        assert req.method == "DELETE"


@pytest.mark.asyncio
async def test_upload_sends_multipart(client: BishengAPIClient) -> None:
    file_data = b"hello world content"
    with respx.mock:
        respx.post(f"{BISHENG_URL}/api/v1/knowledge/upload/k1").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "f1", "name": "test.pdf"}]})
        )
        result = await client.upload(
            "/api/v1/knowledge/upload/k1",
            file_name="test.pdf",
            file_data=file_data,
        )
        assert result["data"][0]["id"] == "f1"
        req = respx.calls[0].request
        assert "multipart/form-data" in req.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_upload_rejects_oversized_file(client: BishengAPIClient) -> None:
    big_data = b"x" * (51 * 1024 * 1024)  # 51MB
    with pytest.raises(BishengAPIError) as exc_info:
        await client.upload("/api/v1/knowledge/upload/k1", file_name="big.pdf", file_data=big_data)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_upload_refreshes_token_on_401(client: BishengAPIClient) -> None:
    file_data = b"content"
    with respx.mock:
        respx.post(f"{BISHENG_URL}/api/v1/knowledge/upload/k1").mock(
            side_effect=[
                httpx.Response(401, json={"detail": "Unauthorized"}),
                httpx.Response(200, json={"data": [{"id": "f1", "name": "doc.pdf"}]}),
            ]
        )
        respx.post(f"{BISHENG_URL}/api/v1/user/login").mock(
            return_value=httpx.Response(200, json={"access_token": "refreshed-token"})
        )
        result = await client.upload(
            "/api/v1/knowledge/upload/k1", file_name="doc.pdf", file_data=file_data
        )
        assert result["data"][0]["id"] == "f1"
        assert client._token == "refreshed-token"
