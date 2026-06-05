from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_adapter():
    adapter = AsyncMock()
    adapter.kb_map = {
        "docs": {"name": "docs", "assistant_id": "asst_1", "kb_id": "kb_1"},
        "wiki": {"name": "wiki", "assistant_id": "asst_2", "kb_id": "kb_2"},
    }
    return adapter


@pytest.fixture(autouse=True)
def patch_adapter(mock_adapter):
    with patch("server.adapter", mock_adapter):
        yield


async def test_rag_query_returns_answer(mock_adapter):
    import server

    mock_adapter.query.return_value = "答案是42"
    result = await server.rag_query("宇宙的答案是什么？")
    assert result == "答案是42"


async def test_rag_query_delegates_to_adapter(mock_adapter):
    import server

    mock_adapter.query.return_value = "ok"
    await server.rag_query("问题", knowledge_base="docs", top_k=10)
    mock_adapter.query.assert_awaited_once_with("问题", "docs", 10)


async def test_rag_kb_list_returns_map(mock_adapter):
    import server

    result = await server.rag_kb_list()
    assert result == [
        {"name": "docs", "assistant_id": "asst_1", "kb_id": "kb_1"},
        {"name": "wiki", "assistant_id": "asst_2", "kb_id": "kb_2"},
    ]


async def test_workflow_start_returns_task_id_and_status(mock_adapter):
    import server

    mock_adapter.start_workflow.return_value = "session_123"
    result = await server.workflow_start("wf_1")
    assert result == {"task_id": "session_123", "status": "working"}


async def test_workflow_start_delegates_to_adapter(mock_adapter):
    import server

    mock_adapter.start_workflow.return_value = "session_123"
    await server.workflow_start("wf_1", inputs={"key": "val"})
    mock_adapter.start_workflow.assert_awaited_once_with("wf_1", {"key": "val"})


async def test_workflow_status_returns_mapped_status(mock_adapter):
    import server

    mock_adapter.get_workflow_status.return_value = {
        "status": "completed",
        "session_id": "s1",
        "result": "done",
    }
    result = await server.workflow_status("s1")
    assert result == {"status": "completed", "session_id": "s1", "result": "done"}


async def test_workflow_continue_returns_working(mock_adapter):
    import server

    mock_adapter.continue_workflow.return_value = None
    result = await server.workflow_continue("s1", {"answer": "yes"}, "msg_1")
    assert result == {"task_id": "s1", "status": "working"}


async def test_workflow_continue_delegates_to_adapter(mock_adapter):
    import server

    mock_adapter.continue_workflow.return_value = None
    await server.workflow_continue("s1", {"answer": "yes"}, "msg_1")
    mock_adapter.continue_workflow.assert_awaited_once_with("s1", {"answer": "yes"}, "msg_1")
