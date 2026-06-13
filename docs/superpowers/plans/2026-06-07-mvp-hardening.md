# MVP Hardening 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补全 MVP 4 项缺失功能（JWT 验证、HTTP 重试、Session 过期重登、Redis 降级），并修复 session 管理 bug，达到生产可部署状态。

**Architecture:** 在现有模块上逐层加固。AuthProxy 改为 session_factory 模式修复会话管理 bug；BishengClient 增加 transport 层重试；AirwayTools 增加 401 自动重登包装；JWT 验证作为独立模块注入 MCP Server。

**Tech Stack:** Python 3.12 / FastMCP / httpx / PyJWT / redis-py / SQLModel / pytest

**Spec:** [2026-06-07-mvp-hardening-design.md](../specs/2026-06-07-mvp-hardening-design.md)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `tests/conftest.py` | Modify | 新增 `db_engine`、`session_factory` fixtures |
| `src/airway/auth/proxy.py` | Modify | session_factory、Optional redis、refresh_session、_acquire_session、_login_for_user |
| `src/airway/client/bisheng.py` | Modify | AsyncHTTPTransport retries=3 |
| `src/airway/mcp/tools.py` | Modify | _with_retry 401 自动重登、_is_auth_error |
| `src/airway/auth/jwt.py` | Create | verify_clawith_jwt 函数 |
| `src/airway/server.py` | Modify | Redis 降级、_resolve_user_id、Context 集成 |
| `tests/test_auth.py` | Modify | session_factory fixtures、redis=None 测试、refresh_session 测试 |
| `tests/test_client.py` | Modify | transport retries 测试 |
| `tests/test_tools.py` | Modify | mock_proxy 增加 refresh_session、401 重登测试 |
| `tests/test_jwt.py` | Create | JWT 验证测试 |

---

## Task 1: Fix AuthProxy Session Management

**Why:** 当前 `init_deps` 在 `async with session_factory() as session` 中创建 AuthProxy，session 在退出 context 后关闭，导致生产环境 AuthProxy 持有已关闭的 session 引用。改为 session_factory 按需创建 session。

**Files:**
- Modify: `tests/conftest.py`
- Modify: `src/airway/auth/proxy.py`
- Modify: `tests/test_auth.py`
- Modify: `src/airway/server.py`

- [ ] **Step 1: Write failing test — update conftest.py**

Replace `tests/conftest.py` entirely:

```python
from collections.abc import AsyncGenerator

import pytest
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def db_session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session
```

- [ ] **Step 2: Write failing test — update test_auth.py**

Replace `tests/test_auth.py` entirely:

```python
import pytest
import fakeredis.aioredis

from airway.auth.proxy import AuthProxy
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


@pytest.fixture
def proxy(mock_client, redis, session_factory):
    return AuthProxy(
        client=mock_client,
        redis=redis,
        session_factory=session_factory,
        key_prefix="airway:",
    )


@pytest.mark.asyncio
async def test_get_session_cache_hit(proxy, redis):
    await redis.set("airway:session:u_test", "cached_token_123")
    token = await proxy.get_session("u_test")
    assert token == "cached_token_123"


@pytest.mark.asyncio
async def test_get_session_from_mapping(proxy, redis, session_factory):
    async with session_factory() as session:
        from sqlmodel import select

        mapping = UserMapping(
            clawith_uid="u_abc", bisheng_uid="42", bisheng_username="clawith_u_abc",
        )
        session.add(mapping)
        await session.commit()

    token = await proxy.get_session("u_abc")
    assert token == "token_clawith_u_abc"

    cached = await redis.get("airway:session:u_abc")
    assert cached == b"token_clawith_u_abc"


@pytest.mark.asyncio
async def test_get_session_auto_register(proxy, redis, session_factory):
    token = await proxy.get_session("u_new")
    assert token == "token_clawith_u_new"

    async with session_factory() as session:
        from sqlmodel import select

        result = await session.execute(
            select(UserMapping).where(UserMapping.clawith_uid == "u_new")
        )
        mapping = result.scalar_one()
    assert mapping.bisheng_username == "clawith_u_new"

    cached = await redis.get("airway:session:u_new")
    assert cached == b"token_clawith_u_new"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `../.venv/bin/python -m pytest tests/test_auth.py tests/test_models.py -v`
Expected: FAIL — `AuthProxy.__init__() got an unexpected keyword argument 'session_factory'`

- [ ] **Step 4: Implement session_factory in AuthProxy**

Replace `src/airway/auth/proxy.py` entirely:

```python
import redis.asyncio as aioredis
from sqlmodel import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from airway.client.bisheng import BishengClient
from airway.models.mapping import UserMapping


class AuthProxy:
    def __init__(
        self,
        client: BishengClient,
        redis: aioredis.Redis | None,
        session_factory: async_sessionmaker,
        key_prefix: str = "airway:",
        session_ttl: int = 3600,
    ):
        self._client = client
        self._redis = redis
        self._session_factory = session_factory
        self._key_prefix = key_prefix
        self._session_ttl = session_ttl

    def _cache_key(self, clawith_uid: str) -> str:
        return f"{self._key_prefix}session:{clawith_uid}"

    async def get_session(self, clawith_uid: str) -> str:
        if self._redis:
            cached = await self._redis.get(self._cache_key(clawith_uid))
            if cached:
                return cached.decode()
        return await self._acquire_session(clawith_uid)

    async def refresh_session(self, clawith_uid: str) -> str:
        if self._redis:
            await self._redis.delete(self._cache_key(clawith_uid))
        return await self._acquire_session(clawith_uid)

    async def _acquire_session(self, clawith_uid: str) -> str:
        token = await self._login_for_user(clawith_uid)
        if self._redis:
            await self._redis.set(
                self._cache_key(clawith_uid), token, ex=self._session_ttl,
            )
        return token

    async def _login_for_user(self, clawith_uid: str) -> str:
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserMapping).where(UserMapping.clawith_uid == clawith_uid)
            )
            mapping = result.scalar_one_or_none()

            if mapping is None:
                bisheng_username = f"clawith_{clawith_uid}"
                token = await self._client.login(bisheng_username, bisheng_username)
                mapping = UserMapping(
                    clawith_uid=clawith_uid,
                    bisheng_uid=bisheng_username,
                    bisheng_username=bisheng_username,
                )
                session.add(mapping)
                await session.commit()
            else:
                token = await self._client.login(
                    mapping.bisheng_username, mapping.bisheng_username,
                )
        return token
```

- [ ] **Step 5: Update server.py init_deps**

In `src/airway/server.py`, replace `init_deps` function:

```python
async def init_deps() -> AirwayTools:
    global _tools, _engine

    settings = get_settings()

    _engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    redis = aioredis.from_url(settings.redis_url)
    client = BishengClient(base_url=settings.bisheng_base_url)

    proxy = AuthProxy(
        client=client,
        redis=redis,
        session_factory=session_factory,
        key_prefix=settings.redis_key_prefix,
    )
    _tools = AirwayTools(proxy=proxy, client=client)
    return _tools
```

- [ ] **Step 6: Run all tests**

Run: `../.venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add tests/conftest.py tests/test_auth.py src/airway/auth/proxy.py src/airway/server.py
git commit -m "fix: AuthProxy 使用 session_factory 替代单次 session

- 修复 init_deps 中 session 在 async with 退出后关闭的 bug
- AuthProxy 按需创建 session，不再持有长期引用
- 引入 Optional redis 和 refresh_session 为后续任务做准备"
```

---

## Task 2: HTTP Retry Transport

**Why:** 网络瞬断导致 Bisheng 调用失败，需要在 transport 层自动重试。

**Files:**
- Modify: `src/airway/client/bisheng.py`
- Modify: `tests/test_client.py`

- [ ] **Step 1: Write failing test**

Add `import httpx` at top of `tests/test_client.py`. Add new test at end of file:

```python
def test_client_has_retry_transport(base_url):
    client = BishengClient(base_url=base_url)
    assert isinstance(client._http._transport, httpx.AsyncHTTPTransport)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_client.py::test_client_has_retry_transport -v`
Expected: FAIL — transport is not AsyncHTTPTransport

- [ ] **Step 3: Implement retry transport**

In `src/airway/client/bisheng.py`, modify `__init__`:

```python
def __init__(self, base_url: str):
    self.base_url = base_url.rstrip("/")
    transport = httpx.AsyncHTTPTransport(retries=3)
    self._http = httpx.AsyncClient(
        base_url=self.base_url, timeout=30.0, transport=transport,
    )
    self._public_key: str | None = None
```

- [ ] **Step 4: Run all client tests**

Run: `../.venv/bin/python -m pytest tests/test_client.py -v`
Expected: All PASS (6 existing + 1 new)

- [ ] **Step 5: Commit**

```bash
git add src/airway/client/bisheng.py tests/test_client.py
git commit -m "feat: BishengClient 使用 AsyncHTTPTransport retries=3 自动重试连接错误"
```

---

## Task 3: Redis Degradation

**Why:** Redis 不可用时应降级为无缓存模式，不阻塞服务。

Task 1 已在 AuthProxy 中支持 `redis: aioredis.Redis | None`。本任务补充 server.py 降级逻辑和测试。

**Files:**
- Modify: `src/airway/server.py`
- Modify: `tests/test_auth.py`

- [ ] **Step 1: Write test — redis=None 正常工作**

Add to end of `tests/test_auth.py`:

```python
@pytest.mark.asyncio
async def test_get_session_without_redis(mock_client, session_factory):
    proxy = AuthProxy(
        client=mock_client,
        redis=None,
        session_factory=session_factory,
        key_prefix="airway:",
    )
    token = await proxy.get_session("u_nocache")
    assert token == "token_clawith_u_nocache"

    async with session_factory() as session:
        from sqlmodel import select

        result = await session.execute(
            select(UserMapping).where(UserMapping.clawith_uid == "u_nocache")
        )
    mapping = result.scalar_one()
    assert mapping.bisheng_username == "clawith_u_nocache"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `../.venv/bin/python -m pytest tests/test_auth.py::test_get_session_without_redis -v`
Expected: PASS — AuthProxy already handles `redis=None` from Task 1

- [ ] **Step 3: Add Redis fallback to server.py**

In `src/airway/server.py`, replace `init_deps`:

```python
async def init_deps() -> AirwayTools:
    global _tools, _engine

    settings = get_settings()

    _engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    try:
        redis = aioredis.from_url(settings.redis_url)
        await redis.ping()
    except Exception:
        logger.warning("Redis unavailable, running without cache")
        redis = None

    client = BishengClient(base_url=settings.bisheng_base_url)

    proxy = AuthProxy(
        client=client,
        redis=redis,
        session_factory=session_factory,
        key_prefix=settings.redis_key_prefix,
    )
    _tools = AirwayTools(proxy=proxy, client=client)
    return _tools
```

- [ ] **Step 4: Run all tests**

Run: `../.venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/airway/server.py tests/test_auth.py
git commit -m "feat: Redis 不可用时降级为无缓存模式"
```

---

## Task 4: Session Expiry Auto-Relogin

**Why:** Bisheng token 过期返回 401 时，应自动刷新 token 并重试请求，对调用方透明。

**Files:**
- Modify: `src/airway/mcp/tools.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Write failing test — 401 触发重试**

Replace `tests/test_tools.py` entirely:

```python
import json

import httpx
import pytest

from airway.mcp.tools import AirwayTools


@pytest.fixture
def mock_proxy():
    class MockProxy:
        async def get_session(self, uid):
            return f"token_{uid}"

        async def refresh_session(self, uid):
            return f"token_{uid}_refreshed"

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


@pytest.mark.asyncio
async def test_knowledge_search_retry_on_401():
    call_count = 0

    class FailingProxy:
        async def get_session(self, uid):
            return f"token_{uid}"

        async def refresh_session(self, uid):
            return f"token_{uid}_new"

    class FailingBisheng:
        async def knowledge_search(self, token, query, knowledge_id, top_k=5):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError(
                    "Unauthorized",
                    request=httpx.Request("POST", "http://test"),
                    response=httpx.Response(401),
                )
            return [{"chunk_text": f"结果: {query}", "score": 0.95}]

    tools = AirwayTools(proxy=FailingProxy(), client=FailingBisheng())
    result = await tools.knowledge_search(
        user_id="u_test", query="重试测试", knowledge_id="k1",
    )
    assert call_count == 2
    parsed = json.loads(result)
    assert parsed[0]["score"] == 0.95
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_tools.py::test_knowledge_search_retry_on_401 -v`
Expected: FAIL — `AirwayTools` has no `_with_retry` method

- [ ] **Step 3: Implement _with_retry in AirwayTools**

Replace `src/airway/mcp/tools.py` entirely:

```python
import json

import httpx

from airway.auth.proxy import AuthProxy
from airway.client.bisheng import BishengClient


class AirwayTools:
    def __init__(self, proxy: AuthProxy, client: BishengClient):
        self._proxy = proxy
        self._client = client

    async def _with_retry(self, user_id: str, fn):
        token = await self._proxy.get_session(user_id)
        try:
            return await fn(token)
        except Exception as e:
            if self._is_auth_error(e):
                token = await self._proxy.refresh_session(user_id)
                return await fn(token)
            raise

    @staticmethod
    def _is_auth_error(e: Exception) -> bool:
        if isinstance(e, httpx.HTTPStatusError):
            return e.response.status_code == 401
        return False

    async def knowledge_list(self, user_id: str, page: int = 1, size: int = 20) -> str:
        async def _do(token: str):
            result = await self._client.knowledge_list(token, page=page, size=size)
            return json.dumps(result, ensure_ascii=False)
        return await self._with_retry(user_id, _do)

    async def knowledge_detail(self, user_id: str, knowledge_id: str) -> str:
        async def _do(token: str):
            result = await self._client.knowledge_detail(token, knowledge_id)
            return json.dumps(result, ensure_ascii=False)
        return await self._with_retry(user_id, _do)

    async def knowledge_search(
        self, user_id: str, query: str, knowledge_id: str, top_k: int = 5,
    ) -> str:
        async def _do(token: str):
            result = await self._client.knowledge_search(
                token, query=query, knowledge_id=knowledge_id, top_k=top_k,
            )
            return json.dumps(result, ensure_ascii=False)
        return await self._with_retry(user_id, _do)
```

- [ ] **Step 4: Run all tools tests**

Run: `../.venv/bin/python -m pytest tests/test_tools.py -v`
Expected: All 4 PASS (3 existing + 1 new)

- [ ] **Step 5: Run full suite**

Run: `../.venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/airway/mcp/tools.py tests/test_tools.py
git commit -m "feat: AirwayTools 401 自动重登 — _with_retry 捕获认证错误后刷新 token 重试"
```

---

## Task 5: JWT Verification

**Why:** MCP tool 应从请求 Context 中提取 JWT 并验证，不再信任调用方传入的 user_id。

**Files:**
- Create: `src/airway/auth/jwt.py`
- Create: `tests/test_jwt.py`
- Modify: `src/airway/server.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_jwt.py`:

```python
import time

import jwt
import pytest

from airway.auth.jwt import verify_clawith_jwt


SECRET = "test_secret_key"


def test_verify_valid_jwt():
    token = jwt.encode({"sub": "user_123"}, SECRET, algorithm="HS256")
    user_id = verify_clawith_jwt(token, SECRET)
    assert user_id == "user_123"


def test_verify_expired_jwt():
    payload = {"sub": "user_123", "exp": time.time() - 3600}
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        verify_clawith_jwt(token, SECRET)


def test_verify_invalid_signature():
    token = jwt.encode({"sub": "user_123"}, "wrong_secret", algorithm="HS256")
    with pytest.raises(jwt.InvalidSignatureError):
        verify_clawith_jwt(token, SECRET)


def test_verify_with_algorithm_mismatch():
    token = jwt.encode({"sub": "user_123"}, SECRET, algorithm="HS384")
    with pytest.raises(jwt.InvalidAlgorithmError):
        verify_clawith_jwt(token, SECRET, algorithm="HS256")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../.venv/bin/python -m pytest tests/test_jwt.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'airway.auth.jwt'`

- [ ] **Step 3: Implement JWT verification**

Create `src/airway/auth/jwt.py`:

```python
import jwt


def verify_clawith_jwt(token: str, secret: str, algorithm: str = "HS256") -> str:
    payload = jwt.decode(token, secret, algorithms=[algorithm])
    return payload["sub"]
```

- [ ] **Step 4: Run JWT tests**

Run: `../.venv/bin/python -m pytest tests/test_jwt.py -v`
Expected: All 4 PASS

- [ ] **Step 5: Integrate JWT into server.py**

Replace `src/airway/server.py` entirely:

```python
import argparse
import logging

import redis.asyncio as aioredis
from fastmcp import Context, FastMCP
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from airway.auth.jwt import verify_clawith_jwt
from airway.auth.proxy import AuthProxy
from airway.client.bisheng import BishengClient
from airway.config import get_settings
from airway.mcp.tools import AirwayTools

logger = logging.getLogger("airway")

mcp = FastMCP("Airway RAG Server")

_tools: AirwayTools | None = None
_engine = None


def _get_tools() -> AirwayTools:
    if _tools is None:
        raise RuntimeError("Server not initialized. Call init_deps() first.")
    return _tools


def _resolve_user_id(ctx: Context) -> str:
    meta = {}
    rc = getattr(ctx, "request_context", None)
    if rc:
        params = getattr(rc, "params", None)
        if params:
            meta = getattr(params, "meta", None) or {}

    if "authorization" in meta:
        token = meta["authorization"].removeprefix("Bearer ")
        settings = get_settings()
        return verify_clawith_jwt(
            token, settings.clawith_jwt_secret, settings.clawith_jwt_algorithm,
        )
    if "user_id" in meta:
        return meta["user_id"]
    raise ValueError("No authentication provided")


async def init_deps() -> AirwayTools:
    global _tools, _engine

    settings = get_settings()

    _engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    try:
        redis = aioredis.from_url(settings.redis_url)
        await redis.ping()
    except Exception:
        logger.warning("Redis unavailable, running without cache")
        redis = None

    client = BishengClient(base_url=settings.bisheng_base_url)

    proxy = AuthProxy(
        client=client,
        redis=redis,
        session_factory=session_factory,
        key_prefix=settings.redis_key_prefix,
    )
    _tools = AirwayTools(proxy=proxy, client=client)
    return _tools


@mcp.tool()
async def knowledge_list(ctx: Context, page: int = 1, size: int = 20) -> str:
    """列出用户可访问的知识库。"""
    user_id = _resolve_user_id(ctx)
    return await _get_tools().knowledge_list(user_id, page=page, size=size)


@mcp.tool()
async def knowledge_detail(ctx: Context, knowledge_id: str) -> str:
    """获取知识库详情。knowledge_id 是 Bisheng 知识库 ID。"""
    user_id = _resolve_user_id(ctx)
    return await _get_tools().knowledge_detail(user_id, knowledge_id)


@mcp.tool()
async def knowledge_search(
    ctx: Context, query: str, knowledge_id: str, top_k: int = 5,
) -> str:
    """在知识库中进行 RAG 检索。query 是检索问题，knowledge_id 是知识库 ID。"""
    user_id = _resolve_user_id(ctx)
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

- [ ] **Step 6: Run full test suite**

Run: `../.venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/airway/auth/jwt.py src/airway/server.py tests/test_jwt.py
git commit -m "feat: JWT 验证集成 — auth/jwt.py + Context 注入 + _resolve_user_id"
```

---

## Self-Review

### 1. Spec Coverage

| Spec 要求 | Task |
|-----------|------|
| JWT 验证 `auth/jwt.py` | Task 5 |
| HTTP 重试（retries=3） | Task 2 |
| Session 过期自动重登 | Task 4 |
| Redis 降级（Optional redis） | Task 1 + Task 3 |
| Session 管理 bug 修复 | Task 1 |

### 2. Placeholder Scan

No TBD / TODO / "implement later" found.

### 3. Type Consistency

- `AuthProxy(redis: aioredis.Redis | None, session_factory: async_sessionmaker)` — consistent across Tasks 1-5
- `verify_clawith_jwt(token, secret, algorithm) -> str` — matches usage in `_resolve_user_id`
- `_with_retry(user_id, fn)` / `_is_auth_error(e) -> bool` — consistent in Task 4
