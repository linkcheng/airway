from unittest.mock import AsyncMock, patch

import pytest

from adapters.bisheng.adapter import BishengAdapter


@pytest.fixture
def kbs():
    return [
        {"name": "产品文档", "assistant_id": "asst_001", "kb_id": "kb_001"},
        {"name": "FAQ", "assistant_id": "asst_002", "kb_id": "kb_002"},
    ]


@pytest.fixture
def adapter(kbs):
    with patch("adapters.bisheng.adapter.BishengV2Client") as V2Mock, \
         patch("adapters.bisheng.adapter.BishengV1Client") as V1Mock:
        a = BishengAdapter(
            v2_api_url="http://v2.local",
            v1_api_url="http://v1.local",
            redis_url="redis://localhost:6379/0",
            admin_user="admin",
            admin_pass="pass",
            knowledge_bases=kbs,
        )
        a._v2_mock = V2Mock.return_value
        a._v1_mock = V1Mock.return_value
        yield a


class TestQuery:
    @pytest.mark.asyncio
    async def test_query_resolves_assistant(self, adapter):
        adapter._v2_mock.chat_completions = AsyncMock(return_value="产品信息如下")
        result = await adapter.query("产品有哪些？", knowledge_base="产品文档")
        adapter._v2_mock.chat_completions.assert_awaited_once_with(
            model="asst_001",
            messages=[{"role": "user", "content": "产品有哪些？"}],
        )
        assert result == "产品信息如下"

    @pytest.mark.asyncio
    async def test_query_default_knowledge_base(self, adapter):
        adapter._v2_mock.chat_completions = AsyncMock(return_value="默认回复")
        result = await adapter.query("你好", knowledge_base=None)
        adapter._v2_mock.chat_completions.assert_awaited_once_with(
            model="asst_001",
            messages=[{"role": "user", "content": "你好"}],
        )
        assert result == "默认回复"

    @pytest.mark.asyncio
    async def test_query_unknown_knowledge_base_raises(self, adapter):
        with pytest.raises(ValueError, match="Unknown knowledge base"):
            await adapter.query("你好", knowledge_base="不存在的库")


class TestStartWorkflow:
    @pytest.mark.asyncio
    async def test_start_workflow_returns_session_id(self, adapter):
        adapter._v2_mock.invoke_workflow = AsyncMock(return_value="session_wf_001")
        result = await adapter.start_workflow("wf_123", inputs={"question": "你好"})
        adapter._v2_mock.invoke_workflow.assert_awaited_once_with(
            workflow_id="wf_123",
            user_input={"question": "你好"},
        )
        assert result == "session_wf_001"


class TestGetWorkflowStatus:
    @pytest.mark.asyncio
    async def test_get_workflow_status_maps_running(self, adapter):
        adapter._v2_mock.get_workflow_status = AsyncMock(
            return_value={"status": "RUNNING"}
        )
        result = await adapter.get_workflow_status("session_abc")
        assert result == {"status": "working", "session_id": "session_abc"}

    @pytest.mark.asyncio
    async def test_get_workflow_status_maps_input(self, adapter):
        adapter._v2_mock.get_workflow_status = AsyncMock(
            return_value={
                "status": "INPUT",
                "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
                "message_id": "11",
                "node_id": "input_cc36c",
            }
        )
        result = await adapter.get_workflow_status("session_input")
        assert result == {
            "status": "input_required",
            "session_id": "session_input",
            "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
            "message_id": "11",
            "node_id": "input_cc36c",
        }

    @pytest.mark.asyncio
    async def test_get_workflow_status_maps_success(self, adapter):
        adapter._v2_mock.get_workflow_status = AsyncMock(
            return_value={"status": "SUCCESS", "result": "最终结果"}
        )
        result = await adapter.get_workflow_status("session_done")
        assert result == {"status": "completed", "session_id": "session_done", "result": "最终结果"}

    @pytest.mark.asyncio
    async def test_get_workflow_status_maps_failed(self, adapter):
        adapter._v2_mock.get_workflow_status = AsyncMock(
            return_value={"status": "FAILED", "error": "超时"}
        )
        result = await adapter.get_workflow_status("session_fail")
        assert result == {"status": "failed", "session_id": "session_fail", "error": "超时"}


class TestContinueWorkflow:
    @pytest.mark.asyncio
    async def test_continue_workflow_constructs_nested_input(self, adapter):
        adapter._v2_mock.get_workflow_status = AsyncMock(
            return_value={
                "status": "INPUT",
                "node_id": "input_cc36c",
                "message_id": "11",
            }
        )
        adapter._v2_mock.invoke_workflow = AsyncMock(return_value="session_continue")
        await adapter.continue_workflow(
            task_id="session_input",
            inputs={"name": "测试"},
            message_id="11",
        )
        adapter._v2_mock.invoke_workflow.assert_awaited_once_with(
            session_id="session_input",
            input={"input_cc36c": {"name": "测试"}},
            message_id=11,
        )

    @pytest.mark.asyncio
    async def test_continue_workflow_missing_node_id_raises(self, adapter):
        adapter._v2_mock.get_workflow_status = AsyncMock(
            return_value={"status": "INPUT", "message_id": "11"}
        )
        with pytest.raises(ValueError, match="node_id"):
            await adapter.continue_workflow(
                task_id="session_input",
                inputs={"name": "测试"},
                message_id="11",
            )
