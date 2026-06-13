from unittest.mock import AsyncMock, MagicMock, patch

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


# --- US1: _ensure_user_mapping ---


def _make_session_factory(scalar_result=None):
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_result
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    @asynccontextmanager
    async def factory():
        yield mock_session

    from contextlib import asynccontextmanager

    return factory(), mock_session


@pytest.mark.asyncio
async def test_ensure_user_mapping_new_user_registers(config, mock_client):
    """T013: First call auto-registers and saves mapping"""
    import importlib
    import airway.server as srv

    importlib.reload(srv)
    srv._config = config
    srv._client = mock_client

    mock_auth = AsyncMock()
    mock_auth.register_user = AsyncMock(return_value=42)
    mock_auth.login_user = AsyncMock(return_value=(42, "token"))

    from contextlib import asynccontextmanager

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()

    @asynccontextmanager
    async def factory():
        yield mock_session

    srv._session_factory = factory

    with patch.object(srv, "_auth", mock_auth):
        user_id, user_name = await srv._ensure_user_mapping("new_clawith_user")

    assert user_id == 42
    assert "new_clawith_user" in user_name
    mock_auth.register_user.assert_called_once()
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_user_mapping_existing_returns_directly(config, mock_client):
    """T014: Existing active mapping returns directly"""
    import importlib
    import airway.server as srv

    importlib.reload(srv)
    srv._config = config
    srv._client = mock_client

    from airway.models.user_mapping import MappingStatus, UserMapping

    existing = UserMapping(
        clawith_user_id="existing_user",
        bisheng_user_id=10,
        bisheng_user_name="clawith_existing_user",
        status=MappingStatus.ACTIVE,
    )

    from contextlib import asynccontextmanager

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()

    @asynccontextmanager
    async def factory():
        yield mock_session

    srv._session_factory = factory

    user_id, user_name = await srv._ensure_user_mapping("existing_user")
    assert user_id == 10
    assert user_name == "clawith_existing_user"
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_user_mapping_conflict_fallback_login(config, mock_client):
    """T015: Register conflict falls back to login"""
    import importlib
    import airway.server as srv

    importlib.reload(srv)
    srv._config = config
    srv._client = mock_client

    mock_auth = AsyncMock()
    from airway.config import AirwayError

    mock_auth.register_user = AsyncMock(side_effect=AirwayError("USER_CONFLICT", "conflict"))
    mock_auth.login_user = AsyncMock(return_value=(99, "fallback_token"))

    from contextlib import asynccontextmanager

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()

    @asynccontextmanager
    async def factory():
        yield mock_session

    srv._session_factory = factory

    with patch.object(srv, "_auth", mock_auth):
        user_id, user_name = await srv._ensure_user_mapping("conflict_user")

    assert user_id == 99
    mock_auth.register_user.assert_called_once()
    mock_auth.login_user.assert_called_once()
    mock_session.add.assert_called_once()


# --- US2: rag_chat ---


@pytest.fixture
def config_with_workflow():
    return AppConfig(
        bisheng=BishengConfig(base_url="http://bisheng-test:7860"),
        knowledge_bases=[
            KnowledgeBaseEntry(
                name="faq",
                bisheng_knowledge_id=1,
                workflow_id="wf-faq-uuid",
                description="常见问题",
            ),
            KnowledgeBaseEntry(name="docs", bisheng_knowledge_id=2, description="文档"),
        ],
    )


@pytest.mark.asyncio
async def test_rag_chat_success(config_with_workflow):
    """T022: rag_chat returns complete answer"""
    import importlib
    import airway.server as srv

    importlib.reload(srv)
    srv._config = config_with_workflow
    mock_client = AsyncMock()
    srv._client = mock_client

    mock_workflow = AsyncMock()
    mock_workflow.invoke = AsyncMock(return_value=("产品退货政策：7天内可退", "sess-abc"))

    mock_auth = AsyncMock()
    mock_auth.register_user = AsyncMock(return_value=42)

    from contextlib import asynccontextmanager

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()

    @asynccontextmanager
    async def factory():
        yield mock_session

    srv._session_factory = factory
    srv._auth = mock_auth
    srv._workflow = mock_workflow

    result = await srv.rag_chat(query="退货政策是什么", knowledge_base="faq")
    assert "退货政策" in result
    assert "sess-abc" in result


@pytest.mark.asyncio
async def test_rag_chat_no_workflow(config_with_workflow):
    """T023: rag_chat returns error when no workflow configured"""
    import importlib
    import airway.server as srv

    importlib.reload(srv)
    srv._config = config_with_workflow
    srv._client = AsyncMock()

    with pytest.raises(ToolError) as exc_info:
        await srv.rag_chat(query="test", knowledge_base="docs")
    assert "未配置 Workflow" in str(exc_info.value)


@pytest.mark.asyncio
async def test_rag_chat_invalid_kb(config_with_workflow):
    """T024: rag_chat returns error for invalid knowledge base"""
    import importlib
    import airway.server as srv

    importlib.reload(srv)
    srv._config = config_with_workflow
    srv._client = AsyncMock()

    with pytest.raises(ToolError) as exc_info:
        await srv.rag_chat(query="test", knowledge_base="nonexistent")
    assert "不存在" in str(exc_info.value)


# --- US3: Multi-turn chat ---


@pytest.mark.asyncio
async def test_rag_chat_without_chat_id_returns_session(config_with_workflow):
    """T027: rag_chat without chat_id returns session_id in output"""
    import importlib
    import airway.server as srv

    importlib.reload(srv)
    srv._config = config_with_workflow
    srv._client = AsyncMock()

    mock_workflow = AsyncMock()
    mock_workflow.invoke = AsyncMock(return_value=("答案文本", "new-sess-789"))

    mock_auth = AsyncMock()
    mock_auth.register_user = AsyncMock(return_value=1)
    mock_auth.get_token = AsyncMock(return_value="token")

    from contextlib import asynccontextmanager

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()

    @asynccontextmanager
    async def factory():
        yield mock_session

    srv._session_factory = factory
    srv._auth = mock_auth
    srv._workflow = mock_workflow

    result = await srv.rag_chat(query="你好", knowledge_base="faq")
    assert "new-sess-789" in result
    assert "答案文本" in result


@pytest.mark.asyncio
async def test_rag_chat_with_chat_id_passes_to_workflow(config_with_workflow):
    """T028: rag_chat passes chat_id to workflow.invoke"""
    import importlib
    import airway.server as srv

    importlib.reload(srv)
    srv._config = config_with_workflow
    srv._client = AsyncMock()

    mock_workflow = AsyncMock()
    mock_workflow.invoke = AsyncMock(return_value=("继续回答", "existing-sess"))

    mock_auth = AsyncMock()
    mock_auth.register_user = AsyncMock(return_value=1)
    mock_auth.get_token = AsyncMock(return_value="token")

    from contextlib import asynccontextmanager

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()

    @asynccontextmanager
    async def factory():
        yield mock_session

    srv._session_factory = factory
    srv._auth = mock_auth
    srv._workflow = mock_workflow

    result = await srv.rag_chat(query="继续", knowledge_base="faq", chat_id="existing-sess")
    assert "继续回答" in result
    mock_workflow.invoke.assert_called_once_with(
        workflow_id="wf-faq-uuid", query="继续", token="token", session_id="existing-sess"
    )
