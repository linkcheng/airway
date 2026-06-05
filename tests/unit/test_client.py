import json
from unittest.mock import AsyncMock

import pytest
import respx
import httpx

from adapters.bisheng.client import BishengV2Client, AirwayError


@pytest.fixture
def client():
    return BishengV2Client(base_url="http://bisheng-test.local", redis_url="redis://localhost:6379/0")


class TestChatCompletions:
    @respx.mock
    @pytest.mark.asyncio
    async def test_chat_completions_returns_content(self, client):
        respx.post("http://bisheng-test.local/api/v2/assistant/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={"choices": [{"message": {"content": "你好世界"}}]},
            )
        )
        result = await client.chat_completions(
            model="assistant_123",
            messages=[{"role": "user", "content": "你好"}],
        )
        assert result == "你好世界"

    @respx.mock
    @pytest.mark.asyncio
    async def test_chat_completions_api_error_raises(self, client):
        respx.post("http://bisheng-test.local/api/v2/assistant/chat/completions").mock(
            return_value=httpx.Response(500, json={"detail": "internal error"})
        )
        with pytest.raises(AirwayError) as exc_info:
            await client.chat_completions(
                model="assistant_123",
                messages=[{"role": "user", "content": "你好"}],
            )
        assert exc_info.value.error_code == "BISHENG_API_ERROR"


class TestInvokeWorkflow:
    @respx.mock
    @pytest.mark.asyncio
    async def test_invoke_workflow_extracts_session_id(self, client):
        async def mock_sse_stream(request):
            events = [
                {"session_id": "abc_async_task_123", "event": "start"},
                {"event": "progress", "data": "processing"},
            ]
            lines = ""
            for event in events:
                lines += f"data: {json.dumps(event)}\n\n"
            return httpx.Response(200, text=lines, headers={"content-type": "text/event-stream"})

        respx.post("http://bisheng-test.local/api/v2/workflow/invoke").mock(
            side_effect=mock_sse_stream
        )
        session_id = await client.invoke_workflow(
            workflow_id="wf_001",
            user_input={"question": "你好"},
        )
        assert session_id == "abc_async_task_123"

    @respx.mock
    @pytest.mark.asyncio
    async def test_invoke_workflow_no_session_id_raises(self, client):
        async def mock_sse_stream_no_session(request):
            events = [{"event": "start"}]
            lines = ""
            for event in events:
                lines += f"data: {json.dumps(event)}\n\n"
            return httpx.Response(200, text=lines, headers={"content-type": "text/event-stream"})

        respx.post("http://bisheng-test.local/api/v2/workflow/invoke").mock(
            side_effect=mock_sse_stream_no_session
        )
        with pytest.raises(AirwayError) as exc_info:
            await client.invoke_workflow(
                workflow_id="wf_001",
                user_input={"question": "你好"},
            )
        assert exc_info.value.error_code == "NO_SESSION_ID"


class TestGetWorkflowStatus:
    @pytest.mark.asyncio
    async def test_get_workflow_status_running(self, client):
        client._redis = AsyncMock()
        client._redis.get = AsyncMock(
            return_value=json.dumps({"status": "RUNNING"}).encode()
        )
        result = await client.get_workflow_status("session_abc")
        assert result == {"status": "RUNNING"}

    @pytest.mark.asyncio
    async def test_get_workflow_status_input_with_schema(self, client):
        async def fake_get(key):
            data = {
                "workflow:session_input:status": json.dumps({"status": "INPUT"}).encode(),
                "workflow:session_input:input": json.dumps({
                    "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
                    "message_id": "11",
                    "node_id": "input_cc36c",
                }).encode(),
            }
            return data.get(key)

        client._redis = AsyncMock()
        client._redis.get = AsyncMock(side_effect=fake_get)
        result = await client.get_workflow_status("session_input")
        assert result["status"] == "INPUT"
        assert result["input_schema"]["properties"]["name"]["type"] == "string"
        assert result["message_id"] == "11"

    @pytest.mark.asyncio
    async def test_get_workflow_status_not_found(self, client):
        client._redis = AsyncMock()
        client._redis.get = AsyncMock(return_value=None)
        result = await client.get_workflow_status("nonexistent")
        assert result == {"status": "NOT_FOUND"}
