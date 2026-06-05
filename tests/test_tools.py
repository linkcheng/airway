# tests/test_tools.py
import json
import pytest
from airway.mcp.tools import AirwayTools


@pytest.fixture
def mock_proxy():
    class MockProxy:
        async def get_session(self, uid):
            return f"token_{uid}"
    return MockProxy()


@pytest.fixture
def mock_bisheng():
    class MockBisheng:
        async def knowledge_list(self, token, page=1, size=20):
            return [
                {"id": "k1", "name": "文档库", "description": "测试", "file_count": 5},
            ]

        async def knowledge_detail(self, token, knowledge_id):
            return {
                "id": knowledge_id,
                "name": "文档库",
                "description": "测试",
                "embed_model": "text-embedding-3-small",
            }

        async def knowledge_search(self, token, query, knowledge_id, top_k=5):
            return [
                {"chunk_text": f"结果: {query}", "score": 0.9, "source_file": "a.md"},
            ]
    return MockBisheng()


@pytest.fixture
def tools(mock_proxy, mock_bisheng):
    return AirwayTools(proxy=mock_proxy, client=mock_bisheng)


@pytest.mark.asyncio
async def test_knowledge_list_tool(tools: AirwayTools):
    result = await tools.knowledge_list(user_id="u_test", page=1, size=10)
    parsed = json.loads(result)
    assert len(parsed) == 1
    assert parsed[0]["name"] == "文档库"


@pytest.mark.asyncio
async def test_knowledge_detail_tool(tools: AirwayTools):
    result = await tools.knowledge_detail(user_id="u_test", knowledge_id="k1")
    parsed = json.loads(result)
    assert parsed["id"] == "k1"
    assert parsed["embed_model"] == "text-embedding-3-small"


@pytest.mark.asyncio
async def test_knowledge_search_tool(tools: AirwayTools):
    result = await tools.knowledge_search(
        user_id="u_test", query="测试问题", knowledge_id="k1", top_k=5,
    )
    parsed = json.loads(result)
    assert len(parsed) == 1
    assert parsed[0]["score"] == 0.9
