import httpx
import pytest
import respx

from airway.bisheng_client import BishengAPIClient
from airway.rag_tools import qa_list, qa_add, qa_delete
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
async def test_qa_list(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.get(f"{BISHENG_URL}/api/v1/knowledge/qa/list/kqa1").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "q1", "question": "什么是Airway?", "answer": "MCP代理"},
                    {"id": "q2", "question": "如何使用?", "answer": "配置MCP连接"},
                ],
            )
        )
        result = await qa_list(client, knowledge_id="kqa1")
        assert len(result) == 2
        assert result[0]["id"] == "q1"
        assert result[0]["question"] == "什么是Airway?"
        assert result[1]["answer"] == "配置MCP连接"


@pytest.mark.asyncio
async def test_qa_add(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.post(f"{BISHENG_URL}/api/v1/knowledge/qa/add").mock(
            return_value=httpx.Response(
                200, json={"id": "q3", "question": "新问题", "answer": "新答案"}
            )
        )
        result = await qa_add(client, knowledge_id="kqa1", question="新问题", answer="新答案")
        assert result["id"] == "q3"
        assert result["question"] == "新问题"


@pytest.mark.asyncio
async def test_qa_delete(client: BishengAPIClient) -> None:
    with respx.mock:
        respx.delete(f"{BISHENG_URL}/api/v1/knowledge/qa/delete").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        result = await qa_delete(client, qa_id="q1")
        assert result["deleted"] is True
        assert result["qa_id"] == "q1"
