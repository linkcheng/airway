from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airway.config import AirwayError


@pytest.fixture
def mock_auth():
    auth = AsyncMock()
    auth.get_token = AsyncMock(return_value="jwt_token_123")
    return auth


@pytest.fixture
def config():
    from airway.config import AppConfig, BishengConfig

    return AppConfig(
        bisheng=BishengConfig(base_url="http://bisheng-test:7860"),
    )


@pytest.mark.asyncio
async def test_list_knowledge(mock_auth, config):
    from airway.adapters.bisheng.client import BishengHttpClient

    client = BishengHttpClient(config, mock_auth)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status_code": 200,
        "data": {
            "data": [
                {"id": 1, "name": "FAQ", "description": "常见问题", "type": 1},
                {"id": 2, "name": "Docs", "description": "文档", "type": 1},
            ],
            "total": 2,
        },
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        result = await client.list_knowledge()
        assert len(result) == 2
        assert result[0]["name"] == "FAQ"


@pytest.mark.asyncio
async def test_get_knowledge(mock_auth, config):
    from airway.adapters.bisheng.client import BishengHttpClient

    client = BishengHttpClient(config, mock_auth)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status_code": 200,
        "data": [{"id": 1, "name": "FAQ", "description": "常见问题"}],
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        result = await client.get_knowledge([1])
        assert len(result) == 1
        assert result[0]["id"] == 1


@pytest.mark.asyncio
async def test_search_chunks(mock_auth, config):
    from airway.adapters.bisheng.client import BishengHttpClient

    client = BishengHttpClient(config, mock_auth)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status_code": 200,
        "data": {
            "data": [
                {"id": 1, "content": "退货政策...", "score": 0.95, "file_id": 10},
            ],
            "total": 1,
        },
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        result = await client.search_chunks(knowledge_id=1, keyword="退货")
        assert len(result) == 1
        assert "退货" in result[0]["content"]


@pytest.mark.asyncio
async def test_api_error_mapping(mock_auth, config):
    from airway.adapters.bisheng.client import BishengHttpClient

    client = BishengHttpClient(config, mock_auth)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status_code": 502,
        "status_message": "Backend Error",
        "data": None,
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        with pytest.raises(AirwayError) as exc_info:
            await client.list_knowledge()
        assert exc_info.value.code == "BISHENG_ERROR"


@pytest.mark.asyncio
async def test_connection_timeout(mock_auth, config):
    import httpx

    from airway.adapters.bisheng.client import BishengHttpClient

    client = BishengHttpClient(config, mock_auth)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.TimeoutException("timeout")):
        with pytest.raises(AirwayError) as exc_info:
            await client.list_knowledge()
        assert "不可用" in exc_info.value.message
