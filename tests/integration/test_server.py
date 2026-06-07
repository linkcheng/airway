"""Integration tests: all 4 MCP tools with mocked Bisheng backend."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from fastmcp.exceptions import ToolError

from airway.config import AppConfig, BishengConfig, KnowledgeBaseEntry


@pytest.fixture
def config():
    return AppConfig(
        bisheng=BishengConfig(base_url="http://bisheng-test:7860"),
        knowledge_bases=[
            KnowledgeBaseEntry(name="faq", bisheng_knowledge_id=1, description="常见问题"),
            KnowledgeBaseEntry(name="docs", bisheng_knowledge_id=2, description="文档库"),
        ],
    )


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.list_knowledge = AsyncMock(
        return_value=[
            {"id": 1, "name": "FAQ", "description": "常见问题"},
            {"id": 2, "name": "Docs", "description": "文档库"},
        ]
    )
    client.get_knowledge = AsyncMock(
        return_value=[
            {"id": 1, "name": "FAQ", "description": "常见问题", "state": 2},
        ]
    )
    client.search_chunks = AsyncMock(
        return_value=[
            {"content": "退货政策：7天内可退...", "score": 0.95, "file_id": 10},
            {"content": "退货流程：联系客服...", "score": 0.87, "file_id": 11},
        ]
    )
    return client


def _setup_server(config, mock_client):
    import importlib

    import airway.server as srv

    importlib.reload(srv)
    srv._config = config
    srv._client = mock_client
    return srv


# --- All 4 tools with mocked Bisheng backend ---


@pytest.mark.asyncio
async def test_rag_query_integration(config, mock_client):
    srv = _setup_server(config, mock_client)
    result = await srv.rag_query(query="退货政策", knowledge_base="faq")
    assert "找到 2 个相关片段" in result
    assert "退货政策" in result
    assert "退货流程" in result
    mock_client.search_chunks.assert_called_once_with(knowledge_id=1, keyword="退货政策", limit=5)


@pytest.mark.asyncio
async def test_knowledge_list_integration(config, mock_client):
    srv = _setup_server(config, mock_client)
    result = await srv.knowledge_list()
    assert "faq" in result
    assert "docs" in result
    assert "共 2 个" in result
    mock_client.list_knowledge.assert_called_once()


@pytest.mark.asyncio
async def test_knowledge_detail_integration(config, mock_client):
    srv = _setup_server(config, mock_client)
    result = await srv.knowledge_detail(knowledge_base="faq")
    assert "faq" in result
    assert "已就绪" in result
    mock_client.get_knowledge.assert_called_once_with([1])


@pytest.mark.asyncio
async def test_knowledge_search_integration(config, mock_client):
    srv = _setup_server(config, mock_client)
    result = await srv.knowledge_search(query="退货", knowledge_base="faq")
    assert "找到 2 个结果" in result
    assert "退货" in result
    mock_client.search_chunks.assert_called_once_with(knowledge_id=1, keyword="退货", limit=10)


# --- Tool chain: list -> detail -> search -> query ---


@pytest.mark.asyncio
async def test_tool_chain(config, mock_client):
    """Simulate a realistic agent workflow: list -> detail -> search -> query."""
    srv = _setup_server(config, mock_client)

    listing = await srv.knowledge_list()
    assert "faq" in listing

    detail = await srv.knowledge_detail(knowledge_base="faq")
    assert "已就绪" in detail

    search = await srv.knowledge_search(query="退货", knowledge_base="faq")
    assert "退货" in search

    query_result = await srv.rag_query(query="退货政策", knowledge_base="faq")
    assert "退货政策" in query_result


# --- Error propagation ---


@pytest.mark.asyncio
async def test_bisheng_unavailable_propagates(config, mock_client):
    from airway.config import AirwayError

    mock_client.search_chunks = AsyncMock(
        side_effect=AirwayError("BISHENG_UNAVAILABLE", "RAG 服务暂时不可用")
    )

    srv = _setup_server(config, mock_client)
    with pytest.raises(ToolError) as exc_info:
        await srv.rag_query(query="test", knowledge_base="faq")
    assert "不可用" in str(exc_info.value)


# --- Concurrent requests ---


@pytest.mark.asyncio
async def test_concurrent_queries(config, mock_client):
    """Multiple rag_query calls should not interfere with each other."""
    srv = _setup_server(config, mock_client)

    call_count = 0

    async def track_calls(**kwargs):
        nonlocal call_count
        call_count += 1
        return [{"content": f"result-{call_count}", "score": 0.9, "file_id": call_count}]

    mock_client.search_chunks = track_calls

    results = await asyncio.gather(
        srv.rag_query(query="query1", knowledge_base="faq"),
        srv.rag_query(query="query2", knowledge_base="docs"),
        srv.rag_query(query="query3", knowledge_base="faq"),
    )

    assert len(results) == 3
    assert call_count == 3
    for r in results:
        assert "找到" in r


@pytest.mark.asyncio
async def test_concurrent_mixed_tools(config, mock_client):
    """Different tool types running concurrently should not interfere."""
    srv = _setup_server(config, mock_client)

    results = await asyncio.gather(
        srv.knowledge_list(),
        srv.knowledge_detail(knowledge_base="faq"),
        srv.knowledge_search(query="test", knowledge_base="faq"),
    )

    assert len(results) == 3
    assert "faq" in results[0]
    assert "已就绪" in results[1]
    assert "找到" in results[2]


# --- Tool registration & health check ---


@pytest.mark.asyncio
async def test_mcp_app_registered_tools(config, mock_client):
    """Verify all 4 tool functions are callable."""
    srv = _setup_server(config, mock_client)
    assert callable(srv.rag_query)
    assert callable(srv.knowledge_list)
    assert callable(srv.knowledge_detail)
    assert callable(srv.knowledge_search)


@pytest.mark.asyncio
async def test_health_check_endpoint(config, mock_client):
    """Verify health check route exists."""
    srv = _setup_server(config, mock_client)
    assert callable(srv.health_check)
