import base64

import httpx
import pytest
import respx

from airway.bisheng_client import BishengAPIClient, BishengAPIError
from airway.rag_tools import (
    knowledge_create,
    knowledge_delete,
    knowledge_upload,
    knowledge_file_delete,
    knowledge_process,
)
from airway.settings import Settings


@pytest.fixture
def client() -> BishengAPIClient:
    settings = Settings(
        bisheng_api_url="http://bisheng-test:7860",
        bisheng_token="test-token",
        api_timeout=5.0,
    )
    return BishengAPIClient(settings)


BISHENG_URL = "http://bisheng-test:7860"


@pytest.mark.asyncio
async def test_knowledge_create(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.post(f"{BISHENG_URL}/api/v1/knowledge/create").mock(
            return_value=httpx.Response(200, json={"id": "k-new", "name": "新知识库"})
        )
        result = await knowledge_create(client, name="新知识库", description="测试用")
        assert result["id"] == "k-new"
        assert result["name"] == "新知识库"


@pytest.mark.asyncio
async def test_knowledge_delete(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.delete(f"{BISHENG_URL}/api/v1/knowledge").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        result = await knowledge_delete(client, knowledge_id="k1")
        assert result["deleted"] is True
        assert result["knowledge_id"] == "k1"


@pytest.mark.asyncio
async def test_knowledge_delete_not_found(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.delete(f"{BISHENG_URL}/api/v1/knowledge").mock(
            return_value=httpx.Response(404, text="Knowledge base not found")
        )
        with pytest.raises(BishengAPIError) as exc_info:
            await knowledge_delete(client, knowledge_id="missing")
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_knowledge_file_delete(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.delete(f"{BISHENG_URL}/api/v1/knowledge/file/f1").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        result = await knowledge_file_delete(client, file_id="f1")
        assert result["deleted"] is True
        assert result["file_id"] == "f1"


@pytest.mark.asyncio
async def test_knowledge_upload(client: BishengAPIClient) -> None:
    content = base64.b64encode(b"file content here").decode()
    with respx.mock:
        respx.post(f"{BISHENG_URL}/api/v1/knowledge/upload/k1").mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "f1", "name": "doc.pdf"}]}
            )
        )
        result = await knowledge_upload(
            client, knowledge_id="k1", file_name="doc.pdf", file_content_base64=content
        )
        assert len(result) == 1
        assert result[0]["id"] == "f1"


@pytest.mark.asyncio
async def test_knowledge_upload_invalid_base64(client: BishengAPIClient) -> None:
    with pytest.raises(BishengAPIError) as exc_info:
        await knowledge_upload(
            client, knowledge_id="k1", file_name="doc.pdf",
            file_content_base64="!!!invalid!!!"
        )
    assert exc_info.value.status_code == 400
    assert "Invalid base64" in exc_info.value.detail


@pytest.mark.asyncio
async def test_knowledge_process(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.post(f"{BISHENG_URL}/api/v1/knowledge/process").mock(
            return_value=httpx.Response(200, json={"status": "processing"})
        )
        result = await knowledge_process(
            client, knowledge_id="k1", file_ids=["f1", "f2"]
        )
        assert result["status"] == "processing"


@pytest.mark.asyncio
async def test_knowledge_process_api_error(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.post(f"{BISHENG_URL}/api/v1/knowledge/process").mock(
            return_value=httpx.Response(500, text="Internal Error")
        )
        with pytest.raises(BishengAPIError):
            await knowledge_process(client, knowledge_id="k1", file_ids=["f1"])
