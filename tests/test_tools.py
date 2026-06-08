import json

import httpx
import pytest

from airway.mcp.tools import AirwayTools


@pytest.fixture
def mock_proxy():
    class MockProxy:
        async def get_session(self, uid):
            return f"token_{uid}"

        async def refresh_session(self, uid):
            return f"token_{uid}_refreshed"

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

        async def workflow_list(self, token, page=1, size=10, name=None):
            return {
                "list": [
                    {"id": "w1", "name": "数据处理", "description": "ETL", "flow_type": 10, "status": 1},
                ],
                "total": 1,
            }

        async def workflow_invoke(self, token, workflow_id, *, input=None, overrides=None):
            return {
                "session_id": "sess_test",
                "events": [{"event": "output_msg", "data": {"message": "完成"}}],
            }

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


@pytest.mark.asyncio
async def test_knowledge_search_retry_on_401():
    call_count = 0

    class FailingProxy:
        async def get_session(self, uid):
            return f"token_{uid}"

        async def refresh_session(self, uid):
            return f"token_{uid}_new"

    class FailingBisheng:
        async def knowledge_search(self, token, query, knowledge_id, top_k=5):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError(
                    "Unauthorized",
                    request=httpx.Request("POST", "http://test"),
                    response=httpx.Response(401),
                )
            return [{"chunk_text": f"结果: {query}", "score": 0.95}]

    tools = AirwayTools(proxy=FailingProxy(), client=FailingBisheng())
    result = await tools.knowledge_search(
        user_id="u_test", query="重试测试", knowledge_id="k1",
    )
    assert call_count == 2
    parsed = json.loads(result)
    assert parsed[0]["score"] == 0.95


@pytest.mark.asyncio
async def test_workflow_list_tool(tools: AirwayTools):
    result = await tools.workflow_list(user_id="u_test", page=1, size=10)
    parsed = json.loads(result)
    assert parsed["total"] == 1
    assert parsed["list"][0]["name"] == "数据处理"


@pytest.mark.asyncio
async def test_workflow_run_caches_result(tools: AirwayTools):
    result = await tools.workflow_run(user_id="u_test", workflow_id="w1")
    parsed = json.loads(result)
    assert parsed["session_id"] == "sess_test"
    assert "sess_test" in tools._results


@pytest.mark.asyncio
async def test_workflow_status_found(tools: AirwayTools):
    await tools.workflow_run(user_id="u_test", workflow_id="w1")
    result = await tools.workflow_status(user_id="u_test", workflow_id="w1", session_id="sess_test")
    parsed = json.loads(result)
    assert parsed["session_id"] == "sess_test"


@pytest.mark.asyncio
async def test_workflow_status_not_found(tools: AirwayTools):
    result = await tools.workflow_status(user_id="u_test", workflow_id="w1", session_id="nonexistent")
    parsed = json.loads(result)
    assert parsed["status"] == "not_found"


@pytest.mark.asyncio
async def test_workflow_run_with_overrides(tools: AirwayTools):
    result = await tools.workflow_run(
        user_id="u_test", workflow_id="w1",
        input="查询", overrides={"node_1": {"key": "val"}},
    )
    parsed = json.loads(result)
    assert parsed["session_id"] == "sess_test"
