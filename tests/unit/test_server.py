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
            KnowledgeBaseEntry(name="docs", bisheng_knowledge_id=2, description="文档"),
        ],
    )


@pytest.fixture
def mock_client():
    return AsyncMock()


def _import_server(config, mock_client):
    import importlib
    import airway.server as srv

    importlib.reload(srv)
    srv._config = config
    srv._client = mock_client
    return srv


@pytest.mark.asyncio
async def test_rag_query_success(config, mock_client):
    srv = _import_server(config, mock_client)
    mock_client.search_chunks = AsyncMock(
        return_value=[
            {"content": "退货政策：7天内...", "score": 0.95, "file_id": 10},
            {"content": "退货流程：联系客服...", "score": 0.87, "file_id": 11},
        ]
    )

    result = await srv.rag_query(query="退货政策", knowledge_base="faq")
    assert "退货" in result
    mock_client.search_chunks.assert_called_once_with(knowledge_id=1, keyword="退货政策", limit=5)


@pytest.mark.asyncio
async def test_rag_query_kb_not_found(config, mock_client):
    srv = _import_server(config, mock_client)

    with pytest.raises(ToolError) as exc_info:
        await srv.rag_query(query="test", knowledge_base="nonexistent")
    assert "不存在" in str(exc_info.value)


@pytest.mark.asyncio
async def test_rag_query_empty_query(config, mock_client):
    srv = _import_server(config, mock_client)

    with pytest.raises(ToolError) as exc_info:
        await srv.rag_query(query="", knowledge_base="faq")
    assert "不能为空" in str(exc_info.value)


@pytest.mark.asyncio
async def test_rag_query_top_k_validation(config, mock_client):
    srv = _import_server(config, mock_client)

    with pytest.raises(ToolError) as exc_info:
        await srv.rag_query(query="test", knowledge_base="faq", top_k=0)
    assert "top_k" in str(exc_info.value).lower() or "范围" in str(exc_info.value)

    with pytest.raises(ToolError) as exc_info:
        await srv.rag_query(query="test", knowledge_base="faq", top_k=21)
    assert "top_k" in str(exc_info.value).lower() or "范围" in str(exc_info.value)


@pytest.mark.asyncio
async def test_rag_query_custom_top_k(config, mock_client):
    srv = _import_server(config, mock_client)
    mock_client.search_chunks = AsyncMock(return_value=[])

    await srv.rag_query(query="test", knowledge_base="faq", top_k=10)
    mock_client.search_chunks.assert_called_once_with(knowledge_id=1, keyword="test", limit=10)


# --- US2: knowledge_list / knowledge_detail ---


@pytest.mark.asyncio
async def test_knowledge_list(config, mock_client):
    srv = _import_server(config, mock_client)
    mock_client.list_knowledge = AsyncMock(
        return_value=[
            {"id": 1, "name": "FAQ", "description": "常见问题"},
            {"id": 2, "name": "Docs", "description": "文档"},
        ]
    )
    result = await srv.knowledge_list()
    assert "faq" in result
    assert "docs" in result


@pytest.mark.asyncio
async def test_knowledge_detail(config, mock_client):
    srv = _import_server(config, mock_client)
    mock_client.get_knowledge = AsyncMock(
        return_value=[{"id": 1, "name": "FAQ", "description": "常见问题", "state": 2}]
    )
    result = await srv.knowledge_detail(knowledge_base="faq")
    assert "faq" in result
    assert "已就绪" in result


@pytest.mark.asyncio
async def test_knowledge_detail_not_found(config, mock_client):
    srv = _import_server(config, mock_client)
    with pytest.raises(ToolError) as exc_info:
        await srv.knowledge_detail(knowledge_base="nonexistent")
    assert "不存在" in str(exc_info.value)


# --- US4: knowledge_search ---


@pytest.mark.asyncio
async def test_knowledge_search(config, mock_client):
    srv = _import_server(config, mock_client)
    mock_client.search_chunks = AsyncMock(
        return_value=[
            {"content": "退货政策：7天内可退...", "score": 0.9, "file_id": 10},
        ]
    )
    result = await srv.knowledge_search(query="退货", knowledge_base="faq")
    assert "退货" in result
    assert "找到 1 个结果" in result


@pytest.mark.asyncio
async def test_knowledge_search_empty(config, mock_client):
    srv = _import_server(config, mock_client)
    mock_client.search_chunks = AsyncMock(return_value=[])

    result = await srv.knowledge_search(query="不存在的内容", knowledge_base="faq")
    assert "未找到结果" in result
