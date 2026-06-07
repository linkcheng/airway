import pytest
import httpx
import respx

from airway.bisheng_client import BishengAPIClient, BishengAPIError
from airway.rag_tools import knowledge_list, knowledge_search, knowledge_files
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
async def test_knowledge_list(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.get(f"{BISHENG_URL}/api/v1/knowledge").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "k1",
                        "name": "产品手册",
                        "description": "产品相关文档",
                        "file_list": [{"id": "f1"}, {"id": "f2"}],
                    }
                ],
            )
        )
        result = await knowledge_list(client)
        assert len(result) == 1
        assert result[0]["id"] == "k1"
        assert result[0]["name"] == "产品手册"
        assert result[0]["document_count"] == 2


@pytest.mark.asyncio
async def test_knowledge_list_with_keyword(client: BishengAPIClient) -> None:
    with respx.mock:
        route = respx.get(f"{BISHENG_URL}/api/v1/knowledge").mock(
            return_value=httpx.Response(200, json=[])
        )
        await knowledge_list(client, keyword="测试")
        assert "name" in str(route.calls[0].request.url)


@pytest.mark.asyncio
async def test_knowledge_search(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.get(f"{BISHENG_URL}/api/v1/knowledge/chunk").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "content": "相关内容片段",
                        "source": "doc1.pdf",
                        "score": 0.95,
                    }
                ],
            )
        )
        result = await knowledge_search(client, knowledge_id="k1", query="如何使用")
        assert len(result) == 1
        assert result[0]["content"] == "相关内容片段"
        assert result[0]["score"] == 0.95


@pytest.mark.asyncio
async def test_knowledge_search_api_error(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.get(f"{BISHENG_URL}/api/v1/knowledge/chunk").mock(
            return_value=httpx.Response(500, text="Internal Error")
        )
        with pytest.raises(BishengAPIError):
            await knowledge_search(client, knowledge_id="k1", query="test")


@pytest.mark.asyncio
async def test_knowledge_files(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.get(f"{BISHENG_URL}/api/v1/knowledge/file_list/k1").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "f1", "name": "doc.pdf", "status": "SUCCESS", "chunk_num": 10}
                ],
            )
        )
        result = await knowledge_files(client, knowledge_id="k1")
        assert len(result) == 1
        assert result[0]["name"] == "doc.pdf"
        assert result[0]["chunk_num"] == 10
