from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airway.config import AppConfig, BishengConfig


@pytest.fixture
def config():
    return AppConfig(
        bisheng=BishengConfig(base_url="http://bisheng-test:7860"),
    )


def _make_sse_lines(events: list[dict]) -> list[str]:
    import json

    return [f"data: {json.dumps(e)}" for e in events]


class AsyncIterator:
    def __init__(self, items):
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration


@pytest.mark.asyncio
async def test_invoke_collects_sse_events(config):
    """T019: Successfully collects SSE events and returns full text"""
    from airway.adapters.bisheng.workflow import BishengWorkflowAdapter

    adapter = BishengWorkflowAdapter(config)

    sse_events = [
        {"session_id": "sess-123", "data": {"event": "stream", "data": "Hello "}},
        {"data": {"event": "stream", "data": "World"}},
        {"data": {"event": "end"}},
    ]
    sse_lines = _make_sse_lines(sse_events)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.aiter_lines.return_value = AsyncIterator(sse_lines)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_client_instance = MagicMock()
    mock_client_instance.stream.return_value = mock_response
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        answer, session_id = await adapter.invoke("wf-uuid", "test query", "token123")

    assert answer == "Hello World"
    assert session_id == "sess-123"


@pytest.mark.asyncio
async def test_invoke_timeout_raises_error(config):
    """T020: SSE timeout returns error"""
    import httpx

    from airway.adapters.bisheng.workflow import BishengWorkflowAdapter

    adapter = BishengWorkflowAdapter(config)

    with patch("httpx.AsyncClient", side_effect=httpx.ReadTimeout("timeout")):
        with pytest.raises(Exception):
            await adapter.invoke("wf-uuid", "test query", "token123")


@pytest.mark.asyncio
async def test_invoke_extracts_session_id(config):
    """T021: Extracts session_id from SSE response"""
    from airway.adapters.bisheng.workflow import BishengWorkflowAdapter

    adapter = BishengWorkflowAdapter(config)

    sse_events = [
        {"session_id": "sess-456"},
        {"data": {"event": "stream", "data": "Answer"}},
        {"data": {"event": "end"}},
    ]
    sse_lines = _make_sse_lines(sse_events)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.aiter_lines.return_value = AsyncIterator(sse_lines)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_client_instance = MagicMock()
    mock_client_instance.stream.return_value = mock_response
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        answer, session_id = await adapter.invoke("wf-uuid", "test", "token")

    assert session_id == "sess-456"
    assert answer == "Answer"
