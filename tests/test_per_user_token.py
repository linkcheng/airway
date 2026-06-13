import httpx
import pytest
import respx

from airway.bisheng_client import BishengAPIClient
from airway.rag_tools import knowledge_list
from airway.settings import Settings


BISHENG_URL = "http://bisheng-test:7860"


@pytest.mark.asyncio
async def test_request_uses_token_override() -> None:
    settings = Settings(
        bisheng_api_url="http://bisheng-test:7860",
        bisheng_token="default-token",
        api_timeout=5.0,
    )
    client = BishengAPIClient(settings)
    with respx.mock:
        route = respx.get(f"{BISHENG_URL}/api/v1/test").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await client.get("/api/v1/test", token_override="user-specific-token")
        cookie = route.calls[0].request.headers.get("cookie", "")
        assert "user-specific-token" in cookie
        assert "default-token" not in cookie


@pytest.mark.asyncio
async def test_request_fallback_to_default_token() -> None:
    settings = Settings(
        bisheng_api_url="http://bisheng-test:7860",
        bisheng_token="default-token",
        api_timeout=5.0,
    )
    client = BishengAPIClient(settings)
    with respx.mock:
        route = respx.get(f"{BISHENG_URL}/api/v1/test").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await client.get("/api/v1/test")
        cookie = route.calls[0].request.headers.get("cookie", "")
        assert "default-token" in cookie


@pytest.mark.asyncio
async def test_request_none_override_uses_default() -> None:
    settings = Settings(
        bisheng_api_url="http://bisheng-test:7860",
        bisheng_token="default-token",
        api_timeout=5.0,
    )
    client = BishengAPIClient(settings)
    with respx.mock:
        route = respx.get(f"{BISHENG_URL}/api/v1/test").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await client.get("/api/v1/test", token_override=None)
        cookie = route.calls[0].request.headers.get("cookie", "")
        assert "default-token" in cookie


def test_settings_parse_user_tokens() -> None:
    settings = Settings(
        bisheng_api_url="http://test:7860",
        bisheng_token="default",
        user_tokens="user1:token1,user2:token2",
    )
    assert settings.user_tokens == {"user1": "token1", "user2": "token2"}


def test_settings_empty_user_tokens() -> None:
    settings = Settings(
        bisheng_api_url="http://test:7860",
        bisheng_token="default",
        user_tokens="",
    )
    assert settings.user_tokens == {}


def test_settings_dict_user_tokens() -> None:
    settings = Settings(
        bisheng_api_url="http://test:7860",
        bisheng_token="default",
        user_tokens={"user1": "token1"},
    )
    assert settings.user_tokens == {"user1": "token1"}


@pytest.mark.asyncio
async def test_rag_tool_passes_token() -> None:
    settings = Settings(
        bisheng_api_url="http://bisheng-test:7860",
        bisheng_token="default-token",
        api_timeout=5.0,
    )
    client = BishengAPIClient(settings)
    with respx.mock:
        route = respx.get(f"{BISHENG_URL}/api/v1/knowledge").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        await knowledge_list(client, token="user-token")
        cookie = route.calls[0].request.headers.get("cookie", "")
        assert "user-token" in cookie
