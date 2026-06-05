# Airway MCP Server 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建独立 MCP Server，让 Clawith Agent 通过 MCP 协议调用 Bisheng RAG 能力

**Architecture:** Airway 作为独立进程运行 FastMCP Server，通过 Streamable HTTP 或 stdio 接收 Clawith Agent 的工具调用。内部包含 Auth Proxy（用户映射 + session 缓存）、Bisheng Client（HTTP API 封装）、MCP Tools（3 个知识库工具）三个模块。

**Tech Stack:** Python 3.12, FastMCP 3.4, httpx, SQLModel + asyncpg, pydantic-settings, PyJWT, redis-py, pytest + pytest-asyncio + pytest-httpx + fakeredis

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `pyproject.toml` | 项目元数据、依赖、入口点 |
| `.env.example` | 环境变量模板 |
| `src/airway/__init__.py` | 包初始化 |
| `src/airway/config.py` | pydantic-settings 配置管理 |
| `src/airway/models/__init__.py` | 包初始化 |
| `src/airway/models/mapping.py` | SQLModel 用户映射表 |
| `src/airway/client/__init__.py` | 包初始化 |
| `src/airway/client/bisheng.py` | Bisheng HTTP API 客户端（认证 + 知识库） |
| `src/airway/auth/__init__.py` | 包初始化 |
| `src/airway/auth/proxy.py` | Session 代理（Redis 缓存 + 用户映射查找） |
| `src/airway/mcp/__init__.py` | 包初始化 |
| `src/airway/mcp/tools.py` | MCP 工具定义 |
| `src/airway/server.py` | FastMCP Server 入口 |
| `tests/conftest.py` | 测试 fixtures |
| `tests/test_config.py` | 配置模块测试 |
| `tests/test_models.py` | 用户映射模型测试 |
| `tests/test_client.py` | Bisheng 客户端测试 |
| `tests/test_auth.py` | Auth proxy 测试 |
| `tests/test_tools.py` | MCP 工具测试 |

---

### Task 1: 项目脚手架

**Files:**
- Create: `pyproject.toml`
- Create: `src/airway/__init__.py`
- Create: `src/airway/models/__init__.py`
- Create: `src/airway/client/__init__.py`
- Create: `src/airway/auth/__init__.py`
- Create: `src/airway/mcp/__init__.py`
- Create: `.env.example`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "airway"
version = "0.1.0"
description = "MCP Server bridging Clawith Agent and Bisheng RAG"
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=3.4.0",
    "httpx>=0.28.0",
    "sqlmodel[asyncpg]>=0.0.22",
    "pydantic-settings>=2.7.0",
    "PyJWT>=2.10.0",
    "redis>=5.2.0",
    "cryptography>=44.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-httpx>=0.35.0",
    "fakeredis>=2.26.0",
    "aiosqlite>=0.20.0",
]

[project.scripts]
airway = "airway.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/airway"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: 创建目录结构和空 __init__.py 文件**

```bash
mkdir -p src/airway/{models,client,auth,mcp} tests
touch src/airway/__init__.py
touch src/airway/models/__init__.py
touch src/airway/client/__init__.py
touch src/airway/auth/__init__.py
touch src/airway/mcp/__init__.py
touch tests/__init__.py
```

- [ ] **Step 3: 创建 .env.example**

```env
# Bisheng
BISHENG_BASE_URL=http://localhost:7860
BISHENG_ADMIN_USER=admin
BISHENG_ADMIN_PASSWORD=changeme

# Clawith
CLAWITH_JWT_SECRET=changeme
CLAWITH_JWT_ALGORITHM=HS256

# PostgreSQL（共享 Clawith 实例，独立数据库）
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/airway

# Redis（共享实例）
REDIS_URL=redis://localhost:6379/0
REDIS_KEY_PREFIX=airway:

# Airway
AIRWAY_LOG_LEVEL=INFO
```

- [ ] **Step 4: 创建 tests/conftest.py**

```python
import asyncio
from collections.abc import AsyncGenerator

import pytest
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()
```

- [ ] **Step 5: 安装依赖并验证**

```bash
cd /Users/zhenglong/ai-native/rag/airway/superpower
pip install -e ".[dev]"
pytest --co
```
Expected: 无报错，0 tests collected

- [ ] **Step 6: 提交**

```bash
git add pyproject.toml .env.example src/ tests/
git commit -m "chore: project scaffolding with dependencies"
```

---

### Task 2: Config 模块

**Files:**
- Create: `src/airway/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 编写配置测试**

```python
# tests/test_config.py
import os

import pytest


def test_config_loads_from_env():
    os.environ["BISHENG_BASE_URL"] = "http://test:7860"
    os.environ["BISHENG_ADMIN_USER"] = "admin"
    os.environ["BISHENG_ADMIN_PASSWORD"] = "secret"
    os.environ["CLAWITH_JWT_SECRET"] = "jwt_secret"
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://u:p@localhost/airway"
    os.environ["REDIS_URL"] = "redis://localhost:6379/1"
    os.environ["REDIS_KEY_PREFIX"] = "test:"

    from airway.config import Settings

    s = Settings()
    assert s.bisheng_base_url == "http://test:7860"
    assert s.bisheng_admin_user == "admin"
    assert s.clawith_jwt_secret == "jwt_secret"
    assert s.redis_key_prefix == "test:"

    # cleanup
    for key in [
        "BISHENG_BASE_URL", "BISHENG_ADMIN_USER", "BISHENG_ADMIN_PASSWORD",
        "CLAWITH_JWT_SECRET", "DATABASE_URL", "REDIS_URL", "REDIS_KEY_PREFIX",
    ]:
        os.environ.pop(key, None)


def test_config_has_defaults():
    from airway.config import Settings

    s = Settings(
        bisheng_admin_password="x",
        clawith_jwt_secret="x",
        database_url="postgresql+asyncpg://u:p@h/d",
    )
    assert s.bisheng_base_url == "http://localhost:7860"
    assert s.clawith_jwt_algorithm == "HS256"
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.redis_key_prefix == "airway:"
    assert s.airway_log_level == "INFO"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_config.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'airway.config'`

- [ ] **Step 3: 实现 config.py**

```python
# src/airway/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Bisheng
    bisheng_base_url: str = "http://localhost:7860"
    bisheng_admin_user: str = "admin"
    bisheng_admin_password: str

    # Clawith
    clawith_jwt_secret: str
    clawith_jwt_algorithm: str = "HS256"

    # PostgreSQL
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_key_prefix: str = "airway:"

    # Airway
    airway_log_level: str = "INFO"

    model_config = {"env_file": ".env", "extra": "ignore"}


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_config.py -v
```
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add src/airway/config.py tests/test_config.py
git commit -m "feat: config module with pydantic-settings"
```

---

### Task 3: User Mapping 模型

**Files:**
- Create: `src/airway/models/mapping.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: 编写模型测试**

```python
# tests/test_models.py
import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from airway.models.mapping import UserMapping


@pytest.mark.asyncio
async def test_create_user_mapping(db_session: AsyncSession):
    mapping = UserMapping(
        clawith_uid="u_abc123",
        bisheng_uid="42",
        bisheng_username="clawith_u_abc123",
    )
    db_session.add(mapping)
    await db_session.commit()
    await db_session.refresh(mapping)

    assert mapping.id is not None
    assert mapping.clawith_uid == "u_abc123"
    assert mapping.bisheng_uid == "42"
    assert mapping.created_at is not None


@pytest.mark.asyncio
async def test_find_mapping_by_clawith_uid(db_session: AsyncSession):
    mapping = UserMapping(
        clawith_uid="u_xyz",
        bisheng_uid="99",
        bisheng_username="clawith_u_xyz",
    )
    db_session.add(mapping)
    await db_session.commit()

    result = await db_session.execute(
        select(UserMapping).where(UserMapping.clawith_uid == "u_xyz")
    )
    found = result.scalar_one()
    assert found.bisheng_uid == "99"


@pytest.mark.asyncio
async def test_unique_clawith_uid(db_session: AsyncSession):
    from sqlalchemy.exc import IntegrityError

    m1 = UserMapping(clawith_uid="u_dup", bisheng_uid="1", bisheng_username="c_u_dup")
    db_session.add(m1)
    await db_session.commit()

    m2 = UserMapping(clawith_uid="u_dup", bisheng_uid="2", bisheng_username="c_u_dup2")
    db_session.add(m2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_models.py -v
```
Expected: FAIL — `ImportError: cannot import name 'UserMapping'`

- [ ] **Step 3: 实现模型**

```python
# src/airway/models/mapping.py
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class UserMapping(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    clawith_uid: str = Field(index=True, unique=True)
    bisheng_uid: str
    bisheng_username: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_models.py -v
```
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/airway/models/mapping.py tests/test_models.py
git commit -m "feat: UserMapping model with SQLModel"
```

---

### Task 4: Bisheng Client — 认证

**Files:**
- Create: `src/airway/client/bisheng.py`
- Create: `tests/test_client.py`

Bisheng 登录流程：获取 RSA 公钥 → 加密密码 → 登录获取 token。

- [ ] **Step 1: 编写认证测试**

```python
# tests/test_client.py
import json
import base64

import pytest
from pytest_httpx import HTTPXMock

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
    with pytest.raises(Exception, match="Login failed"):
        await client.login("admin", "wrong")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_client.py::test_get_public_key -v
```
Expected: FAIL — `ImportError`

- [ ] **Step 3: 实现 BishengClient 认证部分**

```python
# src/airway/client/bisheng.py
from base64 import b64encode

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_der_public_key


class BishengClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        self._public_key: str | None = None

    async def close(self):
        await self._http.aclose()

    async def get_public_key(self) -> str:
        resp = await self._http.get("/api/v1/user/public_key")
        resp.raise_for_status()
        data = resp.json()
        self._public_key = data["data"]["public_key"]
        return self._public_key

    def _encrypt_password(self, password: str, public_key_b64: str) -> str:
        key_bytes = base64.b64decode(public_key_b64)
        public_key = load_der_public_key(key_bytes)
        encrypted = public_key.encrypt(
            password.encode(),
            padding.PKCS1v15(),
        )
        return b64encode(encrypted).decode()

    async def login(self, username: str, password: str) -> str:
        if not self._public_key:
            await self.get_public_key()

        encrypted_pwd = self._encrypt_password(password, self._public_key)
        resp = await self._http.post(
            "/api/v1/user/login",
            json={
                "user_name": username,
                "password": encrypted_pwd,
            },
        )
        if resp.status_code != 200:
            raise Exception(f"Login failed: {resp.status_code} {resp.text}")

        data = resp.json()
        if data.get("code") != 200:
            raise Exception(f"Login failed: {data.get('message')}")

        return data["data"]["access_token"]
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_client.py -v
```
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/airway/client/bisheng.py tests/test_client.py
git commit -m "feat: Bisheng client with RSA auth and login"
```

---

### Task 5: Bisheng Client — 知识库 API

**Files:**
- Modify: `src/airway/client/bisheng.py`
- Modify: `tests/test_client.py`

- [ ] **Step 1: 编写知识库 API 测试**

追加到 `tests/test_client.py`：

```python
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
        token="test_token",
        query="Airway 是什么",
        knowledge_id="k1",
        top_k=5,
    )
    assert len(result) == 2
    assert result[0]["score"] == 0.95
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_client.py::test_knowledge_list -v
```
Expected: FAIL — `AttributeError: 'BishengClient' has no attribute 'knowledge_list'`

- [ ] **Step 3: 实现知识库 API 方法**

追加到 `src/airway/client/bisheng.py` 的 `BishengClient` 类中：

```python
    async def _request(
        self,
        method: str,
        path: str,
        token: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict:
        headers = {"Authorization": f"Bearer {token}"}
        resp = await self._http.request(
            method, path, headers=headers, params=params, json=json_body,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 200:
            raise Exception(f"Bisheng API error: {data.get('message')}")
        return data["data"]

    async def knowledge_list(self, token: str, page: int = 1, size: int = 20) -> list[dict]:
        data = await self._request(
            "GET",
            "/api/v1/knowledge/space/mine",
            token,
            params={"page": page, "page_size": size},
        )
        return data.get("list", [])

    async def knowledge_detail(self, token: str, knowledge_id: str) -> dict:
        return await self._request(
            "GET",
            f"/api/v1/knowledge/space/{knowledge_id}/info",
            token,
        )

    async def knowledge_search(
        self,
        token: str,
        query: str,
        knowledge_id: str,
        top_k: int = 5,
    ) -> list[dict]:
        return await self._request(
            "POST",
            "/api/v2/knowledge/search",
            token,
            json_body={
                "query": query,
                "knowledge_id": knowledge_id,
                "top_k": top_k,
            },
        )
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_client.py -v
```
Expected: 6 passed

- [ ] **Step 5: 提交**

```bash
git add src/airway/client/bisheng.py tests/test_client.py
git commit -m "feat: Bisheng client knowledge list/detail/search APIs"
```

---

### Task 6: Auth Proxy

**Files:**
- Create: `src/airway/auth/proxy.py`
- Create: `tests/test_auth.py`

Auth Proxy 负责：Redis 缓存查找 → 数据库映射查找 → 自动注册 → 登录获取 session。

- [ ] **Step 1: 编写 Auth Proxy 测试**

```python
# tests/test_auth.py
import pytest
import fakeredis.aioredis

from airway.auth.proxy import AuthProxy
from airway.client.bisheng import BishengClient
from airway.models.mapping import UserMapping


@pytest.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis()
    yield r
    await r.aclose()


@pytest.fixture
def mock_client():
    class MockClient:
        async def login(self, username, password):
            if password == "wrong":
                raise Exception("Login failed")
            return f"token_{username}"

    return MockClient()


@pytest.mark.asyncio
async def test_get_session_cache_hit(redis, mock_client, db_session):
    proxy = AuthProxy(
        client=mock_client,
        redis=redis,
        session=db_session,
        key_prefix="airway:",
    )
    # 直接设置缓存
    await redis.set("airway:session:u_test", "cached_token_123")

    token = await proxy.get_session("u_test")
    assert token == "cached_token_123"


@pytest.mark.asyncio
async def test_get_session_from_mapping(redis, mock_client, db_session):
    proxy = AuthProxy(
        client=mock_client,
        redis=redis,
        session=db_session,
        key_prefix="airway:",
    )
    # 数据库中有映射，Redis 无缓存
    mapping = UserMapping(
        clawith_uid="u_abc",
        bisheng_uid="42",
        bisheng_username="clawith_u_abc",
    )
    db_session.add(mapping)
    await db_session.commit()

    token = await proxy.get_session("u_abc")
    assert token == "token_clawith_u_abc"

    # 验证已缓存到 Redis
    cached = await redis.get("airway:session:u_abc")
    assert cached == b"token_clawith_u_abc"


@pytest.mark.asyncio
async def test_get_session_auto_register(redis, mock_client, db_session):
    proxy = AuthProxy(
        client=mock_client,
        redis=redis,
        session=db_session,
        key_prefix="airway:",
    )
    # 无映射、无缓存 → 自动注册
    token = await proxy.get_session("u_new")
    assert token == "token_clawith_u_new"

    # 验证映射已写入数据库
    from sqlmodel import select

    result = await db_session.execute(
        select(UserMapping).where(UserMapping.clawith_uid == "u_new")
    )
    mapping = result.scalar_one()
    assert mapping.bisheng_username == "clawith_u_new"

    # 验证已缓存
    cached = await redis.get("airway:session:u_new")
    assert cached == b"token_clawith_u_new"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_auth.py -v
```
Expected: FAIL — `ImportError`

- [ ] **Step 3: 实现 Auth Proxy**

```python
# src/airway/auth/proxy.py
from datetime import datetime, timezone

import redis.asyncio as aioredis
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from airway.client.bisheng import BishengClient
from airway.models.mapping import UserMapping


class AuthProxy:
    def __init__(
        self,
        client: BishengClient,
        redis: aioredis.Redis,
        session: AsyncSession,
        key_prefix: str = "airway:",
        session_ttl: int = 3600,
    ):
        self._client = client
        self._redis = redis
        self._session = session
        self._key_prefix = key_prefix
        self._session_ttl = session_ttl

    def _cache_key(self, clawith_uid: str) -> str:
        return f"{self._key_prefix}session:{clawith_uid}"

    async def get_session(self, clawith_uid: str) -> str:
        # 1. 查 Redis 缓存
        cache_key = self._cache_key(clawith_uid)
        cached = await self._redis.get(cache_key)
        if cached:
            return cached.decode()

        # 2. 查数据库映射
        result = await self._session.execute(
            select(UserMapping).where(UserMapping.clawith_uid == clawith_uid)
        )
        mapping = result.scalar_one_or_none()

        if mapping is None:
            # 3. 自动注册：创建映射
            bisheng_username = f"clawith_{clawith_uid}"
            token = await self._client.login(bisheng_username, bisheng_username)
            mapping = UserMapping(
                clawith_uid=clawith_uid,
                bisheng_uid=bisheng_username,
                bisheng_username=bisheng_username,
            )
            self._session.add(mapping)
            await self._session.commit()
        else:
            # 4. 用映射的账号登录
            token = await self._client.login(
                mapping.bisheng_username, mapping.bisheng_username
            )

        # 5. 缓存
        await self._redis.set(cache_key, token, ex=self._session_ttl)
        return token
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_auth.py -v
```
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/airway/auth/proxy.py tests/test_auth.py
git commit -m "feat: AuthProxy with Redis caching and auto-register"
```

---

### Task 7: MCP Tools

**Files:**
- Create: `src/airway/mcp/tools.py`
- Create: `tests/test_tools.py`

工具通过 Auth Proxy 获取 session，调用 Bisheng Client。

- [ ] **Step 1: 编写工具测试**

```python
# tests/test_tools.py
import json

import pytest

from airway.mcp.tools import AirwayTools


@pytest.fixture
def mock_proxy():
    class MockProxy:
        async def get_session(self, uid):
            return f"token_{uid}"

    return MockProxy()


@pytest.fixture
def mock_bisheng():
    class MockBisheng:
        async def knowledge_list(self, token, page=1, size=20):
            return [
                {"id": "k1", "name": "文档库", "description": "测试", "file_count": 5},
            ]

        async def knowledge_detail(self, token, knowledge_id):
            return {
                "id": knowledge_id,
                "name": "文档库",
                "description": "测试",
                "embed_model": "text-embedding-3-small",
            }

        async def knowledge_search(self, token, query, knowledge_id, top_k=5):
            return [
                {"chunk_text": f"结果: {query}", "score": 0.9, "source_file": "a.md"},
            ]

    return MockBisheng()


@pytest.fixture
def tools(mock_proxy, mock_bisheng):
    return AirwayTools(proxy=mock_proxy, client=mock_bisheng)


@pytest.mark.asyncio
async def test_knowledge_list_tool(tools: AirwayTools):
    result = await tools.knowledge_list(user_id="u_test", page=1, size=10)
    parsed = json.loads(result)
    assert len(parsed) == 1
    assert parsed[0]["name"] == "文档库"


@pytest.mark.asyncio
async def test_knowledge_detail_tool(tools: AirwayTools):
    result = await tools.knowledge_detail(user_id="u_test", knowledge_id="k1")
    parsed = json.loads(result)
    assert parsed["id"] == "k1"
    assert parsed["embed_model"] == "text-embedding-3-small"


@pytest.mark.asyncio
async def test_knowledge_search_tool(tools: AirwayTools):
    result = await tools.knowledge_search(
        user_id="u_test", query="测试问题", knowledge_id="k1", top_k=5,
    )
    parsed = json.loads(result)
    assert len(parsed) == 1
    assert parsed[0]["score"] == 0.9
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_tools.py -v
```
Expected: FAIL — `ImportError`

- [ ] **Step 3: 实现 AirwayTools**

```python
# src/airway/mcp/tools.py
import json

from airway.auth.proxy import AuthProxy
from airway.client.bisheng import BishengClient


class AirwayTools:
    def __init__(self, proxy: AuthProxy, client: BishengClient):
        self._proxy = proxy
        self._client = client

    async def knowledge_list(self, user_id: str, page: int = 1, size: int = 20) -> str:
        token = await self._proxy.get_session(user_id)
        result = await self._client.knowledge_list(token, page=page, size=size)
        return json.dumps(result, ensure_ascii=False)

    async def knowledge_detail(self, user_id: str, knowledge_id: str) -> str:
        token = await self._proxy.get_session(user_id)
        result = await self._client.knowledge_detail(token, knowledge_id)
        return json.dumps(result, ensure_ascii=False)

    async def knowledge_search(
        self,
        user_id: str,
        query: str,
        knowledge_id: str,
        top_k: int = 5,
    ) -> str:
        token = await self._proxy.get_session(user_id)
        result = await self._client.knowledge_search(
            token, query=query, knowledge_id=knowledge_id, top_k=top_k,
        )
        return json.dumps(result, ensure_ascii=False)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_tools.py -v
```
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/airway/mcp/tools.py tests/test_tools.py
git commit -m "feat: AirwayTools with knowledge list/detail/search"
```

---

### Task 8: MCP Server 入口

**Files:**
- Create: `src/airway/server.py`

将 AirwayTools 注册到 FastMCP Server，支持 stdio 和 streamable-http 传输。

- [ ] **Step 1: 编写 server.py**

```python
# src/airway/server.py
import argparse
import asyncio
import logging

import redis.asyncio as aioredis
from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from airway.auth.proxy import AuthProxy
from airway.client.bisheng import BishengClient
from airway.config import get_settings
from airway.mcp.tools import AirwayTools

logger = logging.getLogger("airway")

mcp = FastMCP("Airway RAG Server")

_tools: AirwayTools | None = None
_engine = None


async def _init_deps() -> AirwayTools:
    global _tools, _engine

    settings = get_settings()

    # PostgreSQL
    _engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    # Redis
    redis = aioredis.from_url(settings.redis_url)

    # Bisheng Client
    client = BishengClient(base_url=settings.bisheng_base_url)

    # Auth Proxy
    async with session_factory() as session:
        proxy = AuthProxy(
            client=client,
            redis=redis,
            session=session,
            key_prefix=settings.redis_key_prefix,
        )
        _tools = AirwayTools(proxy=proxy, client=client)

    return _tools


def _get_tools() -> AirwayTools:
    if _tools is None:
        raise RuntimeError("Server not initialized")
    return _tools


@mcp.tool()
async def knowledge_list(user_id: str, page: int = 1, size: int = 20) -> str:
    """列出用户可访问的知识库。user_id 是 Clawith 用户 ID。"""
    return await _get_tools().knowledge_list(user_id, page=page, size=size)


@mcp.tool()
async def knowledge_detail(user_id: str, knowledge_id: str) -> str:
    """获取知识库详情。knowledge_id 是 Bisheng 知识库 ID。"""
    return await _get_tools().knowledge_detail(user_id, knowledge_id)


@mcp.tool()
async def knowledge_search(
    user_id: str,
    query: str,
    knowledge_id: str,
    top_k: int = 5,
) -> str:
    """在知识库中进行 RAG 检索。query 是检索问题，knowledge_id 是知识库 ID。"""
    return await _get_tools().knowledge_search(
        user_id, query=query, knowledge_id=knowledge_id, top_k=top_k,
    )


def main():
    parser = argparse.ArgumentParser(description="Airway MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, get_settings().airway_log_level))

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证模块可导入**

```bash
python -c "from airway.server import mcp; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: 运行全部测试**

```bash
pytest -v
```
Expected: 所有测试通过

- [ ] **Step 4: 提交**

```bash
git add src/airway/server.py
git commit -m "feat: MCP Server entry point with stdio and streamable-http"
```

---

### Task 9: .gitignore 更新

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: 追加 Airway 相关忽略规则**

追加到 `.gitignore`：

```
# Airway
.env
data/
.superpowers/
```

- [ ] **Step 2: 提交**

```bash
git add .gitignore
git commit -m "chore: update gitignore for Airway project"
```

---

## 自检结果

**1. Spec 覆盖度：**
- 背景与目标 → Task 1 项目设置
- 架构方案 → Task 8 server.py
- Auth Proxy → Task 6
- MCP Tools → Task 7
- Bisheng Client → Task 4 + 5
- 项目结构 → Task 1
- 技术选型 → Task 1 pyproject.toml
- 配置项 → Task 2
- 部署方式 → Task 8
- 错误处理 → Task 4/5 client 层 + Task 6 proxy 层

**2. 占位符扫描：** 无 TBD/TODO/实现待定 内容

**3. 类型一致性：** 所有方法签名在定义和调用处一致
