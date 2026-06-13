import httpx
import pytest
import respx

from airway.bisheng_client import BishengAPIClient, BishengAPIError
from airway.rag_tools import (
    knowledge_search,
    knowledge_upload,
    qa_add,
    workflow_run,
)
from airway.settings import Settings


BISHENG_URL = "http://bisheng-test:7860"


@pytest.fixture
def client() -> BishengAPIClient:
    settings = Settings(
        bisheng_api_url="http://bisheng-test:7860",
        bisheng_token="default-token",
        bisheng_username="admin",
        bisheng_password="secret",
        api_timeout=5.0,
    )
    return BishengAPIClient(settings)


@pytest.mark.asyncio
async def test_token_override_no_refresh_on_401(client: BishengAPIClient) -> None:
    """When token_override is set and server returns 401, should NOT attempt refresh."""
    with respx.mock:
        respx.get(f"{BISHENG_URL}/api/v1/test").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        with pytest.raises(BishengAPIError) as exc_info:
            await client.get("/api/v1/test", token_override="user-token")
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_upload_with_token_override(client: BishengAPIClient) -> None:
    with respx.mock:
        route = respx.post(f"{BISHENG_URL}/api/v1/knowledge/upload/k1").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "f1", "name": "doc.pdf"}]})
        )
        await client.upload(
            "/api/v1/knowledge/upload/k1",
            file_name="doc.pdf",
            file_data=b"content",
            token_override="user-upload-token",
        )
        cookie = route.calls[0].request.headers.get("cookie", "")
        assert "user-upload-token" in cookie


@pytest.mark.asyncio
async def test_knowledge_search_with_token(client: BishengAPIClient) -> None:
    with respx.mock:
        route = respx.get(f"{BISHENG_URL}/api/v1/knowledge/chunk").mock(
            return_value=httpx.Response(200, json={"data": [
                {"content": "result", "source": "s1", "score": 0.9}
            ]})
        )
        result = await knowledge_search(
            client, knowledge_id="k1", query="test", token="search-token"
        )
        assert len(result) == 1
        cookie = route.calls[0].request.headers.get("cookie", "")
        assert "search-token" in cookie


@pytest.mark.asyncio
async def test_qa_add_with_token(client: BishengAPIClient) -> None:
    with respx.mock:
        route = respx.post(f"{BISHENG_URL}/api/v1/knowledge/qa/add").mock(
            return_value=httpx.Response(200, json={"id": "q1"})
        )
        await qa_add(client, knowledge_id="k1", question="Q?", answer="A", token="qa-token")
        cookie = route.calls[0].request.headers.get("cookie", "")
        assert "qa-token" in cookie


@pytest.mark.asyncio
async def test_workflow_run_with_token(client: BishengAPIClient) -> None:
    with respx.mock:
        route = respx.post(f"{BISHENG_URL}/api/v2/workflow/invoke").mock(
            return_value=httpx.Response(200, json={"session_id": "s1", "events": []})
        )
        await workflow_run(client, workflow_id="w1", token="wf-token")
        cookie = route.calls[0].request.headers.get("cookie", "")
        assert "wf-token" in cookie


@pytest.mark.asyncio
async def test_knowledge_upload_with_token(client: BishengAPIClient) -> None:
    import base64
    content = base64.b64encode(b"test data").decode()
    with respx.mock:
        route = respx.post(f"{BISHENG_URL}/api/v1/knowledge/upload/k1").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "f1", "name": "t.pdf"}]})
        )
        await knowledge_upload(
            client, knowledge_id="k1", file_name="t.pdf",
            file_content_base64=content, token="upload-token",
        )
        cookie = route.calls[0].request.headers.get("cookie", "")
        assert "upload-token" in cookie


@pytest.mark.asyncio
async def test_resolve_token_integration() -> None:
    import airway.app as app_module
    original_settings = app_module._settings
    app_module._settings = Settings(
        bisheng_api_url="http://test:7860",
        bisheng_token="default",
        user_tokens={"user-123": "mapped-token"},
    )

    try:
        assert app_module._resolve_token("user-123") == "mapped-token"
        assert app_module._resolve_token("unknown-user") is None
        assert app_module._resolve_token(None) is None
    finally:
        app_module._settings = original_settings


@pytest.mark.asyncio
async def test_delete_with_token_override(client: BishengAPIClient) -> None:
    with respx.mock:
        route = respx.delete(f"{BISHENG_URL}/api/v1/knowledge").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        await client.delete("/api/v1/knowledge", json={"id": "1"}, token_override="del-token")
        cookie = route.calls[0].request.headers.get("cookie", "")
        assert "del-token" in cookie


@pytest.mark.asyncio
async def test_post_with_token_override(client: BishengAPIClient) -> None:
    with respx.mock:
        route = respx.post(f"{BISHENG_URL}/api/v1/test").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await client.post("/api/v1/test", json={"key": "val"}, token_override="post-token")
        cookie = route.calls[0].request.headers.get("cookie", "")
        assert "post-token" in cookie
