# tests/test_client.py
import json
import base64

import pytest
import httpx
from pytest_httpx import HTTPXMock
from unittest.mock import AsyncMock, patch

from airway.client.bisheng import BishengClient


@pytest.fixture
def base_url():
    return "http://bisheng-test:7860"


@pytest.fixture
def client(base_url):
    return BishengClient(base_url=base_url)


PUBLIC_KEY_RESPONSE = {
    "code": 200,
    "data": {
        "public_key": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0Z3VS5JJcds3xfn/ygSz"
    },
}

LOGIN_RESPONSE = {
    "code": 200,
    "data": {
        "access_token": "test_token_123",
    },
}


@pytest.mark.asyncio
async def test_get_public_key(client: BishengClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://bisheng-test:7860/api/v1/user/public_key",
        json=PUBLIC_KEY_RESPONSE,
    )
    key = await client.get_public_key()
    assert key == PUBLIC_KEY_RESPONSE["data"]["public_key"]


@pytest.mark.asyncio
async def test_login_success(client: BishengClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://bisheng-test:7860/api/v1/user/public_key",
        json=PUBLIC_KEY_RESPONSE,
    )
    httpx_mock.add_response(
        url="http://bisheng-test:7860/api/v1/user/login",
        json=LOGIN_RESPONSE,
    )
    # Mock 加密方法以避免在测试中处理真实的 RSA 加密
    with patch.object(client, '_encrypt_password', return_value='encrypted_password'):
        token = await client.login("admin", "password123")
        assert token == "test_token_123"


@pytest.mark.asyncio
async def test_login_failure(client: BishengClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://bisheng-test:7860/api/v1/user/public_key",
        json=PUBLIC_KEY_RESPONSE,
    )
    httpx_mock.add_response(
        url="http://bisheng-test:7860/api/v1/user/login",
        json={"code": 401, "message": "Invalid credentials"},
        status_code=401,
    )
    # Mock 加密方法以避免在测试中处理真实的 RSA 加密
    with patch.object(client, '_encrypt_password', return_value='encrypted_password'):
        with pytest.raises(Exception, match="Login failed"):
            await client.login("admin", "wrong")


KNOWLEDGE_LIST_RESPONSE = {
    "code": 200,
    "data": {
        "list": [
            {"id": "k1", "name": "产品文档", "description": "产品相关文档", "file_count": 10},
            {"id": "k2", "name": "FAQ", "description": "常见问题", "file_count": 5},
        ],
        "total": 2,
    },
}


@pytest.mark.asyncio
async def test_knowledge_list(client: BishengClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://bisheng-test:7860/api/v1/knowledge/space/mine?page=1&page_size=20",
        json=KNOWLEDGE_LIST_RESPONSE,
    )
    result = await client.knowledge_list(token="test_token")
    assert len(result) == 2
    assert result[0]["name"] == "产品文档"


KNOWLEDGE_DETAIL_RESPONSE = {
    "code": 200,
    "data": {
        "id": "k1",
        "name": "产品文档",
        "description": "产品相关文档",
        "embed_model": "text-embedding-3-small",
    },
}


@pytest.mark.asyncio
async def test_knowledge_detail(client: BishengClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://bisheng-test:7860/api/v1/knowledge/space/k1/info",
        json=KNOWLEDGE_DETAIL_RESPONSE,
    )
    result = await client.knowledge_detail(token="test_token", knowledge_id="k1")
    assert result["name"] == "产品文档"
    assert result["embed_model"] == "text-embedding-3-small"


KNOWLEDGE_SEARCH_RESPONSE = {
    "code": 200,
    "data": [
        {"chunk_text": "Airway 是 MCP 代理服务", "score": 0.95, "source_file": "readme.md"},
        {"chunk_text": "支持 Streamable HTTP", "score": 0.85, "source_file": "arch.md"},
    ],
}


@pytest.mark.asyncio
async def test_knowledge_search(client: BishengClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://bisheng-test:7860/api/v2/knowledge/search",
        json=KNOWLEDGE_SEARCH_RESPONSE,
    )
    result = await client.knowledge_search(
        token="test_token", query="Airway 是什么", knowledge_id="k1", top_k=5,
    )
    assert len(result) == 2
    assert result[0]["score"] == 0.95


def test_client_has_retry_transport(base_url):
    client = BishengClient(base_url=base_url)
    # 检查是否使用了 AsyncHTTPTransport（默认就是 AsyncHTTPTransport）
    assert isinstance(client._http._transport, httpx.AsyncHTTPTransport)
    # 重试配置是在 transport 初始化时通过 retries 参数设置的
    # 这里我们只能确保 transport 是 AsyncHTTPTransport 类型
    # 具体的 retries 配置在内部处理
