# MVP 补全设计方案

> 日期：2026-06-07
> 状态：待审阅
> 前置文档：[airway-mcp-server-design.md](./2026-06-05-airway-mcp-server-design.md)

## 1. 目标

补全 MVP 设计文档中已规划但尚未实现的 4 项功能，使 Airway 达到生产可部署状态。

## 2. 改动范围

| # | 功能 | 影响模块 | 新增/修改文件 |
|---|------|----------|---------------|
| 1 | JWT 验证 | auth | 新增 `auth/jwt.py`，修改 `server.py`、`mcp/tools.py` |
| 2 | HTTP 重试 | client | 修改 `client/bisheng.py` |
| 3 | Session 过期自动重登 | auth + mcp | 修改 `auth/proxy.py`、`mcp/tools.py` |
| 4 | Redis 降级 | auth + server | 修改 `auth/proxy.py`、`server.py` |

## 3. 详细设计

### 3.1 JWT 验证

新增 `src/airway/auth/jwt.py`：

```python
import jwt

def verify_clawith_jwt(token: str, secret: str, algorithm: str = "HS256") -> str:
    """验证 Clawith JWT，返回 user_id。"""
    payload = jwt.decode(token, secret, algorithms=[algorithm])
    return payload["sub"]
```

**集成方式：** FastMCP 无原生中间件，通过 Context 注入。每个 MCP tool 从 `ctx` 中提取已验证的 user_id。

Tool 签名变更（移除 `user_id` 参数，改为 Context 注入）：

```python
@mcp.tool()
async def knowledge_list(ctx: Context, page: int = 1, size: int = 20) -> str:
    user_id = _extract_user_id(ctx)
    return await _get_tools().knowledge_list(user_id, page=page, size=size)
```

`_extract_user_id(ctx)` 从 `ctx.meta` 或请求头中提取 JWT 并验证。测试环境下支持传入 `user_id` 覆盖，避免测试需要构造 JWT。

### 3.2 HTTP 重试

修改 `BishengClient.__init__`，使用 httpx 内置 transport retries：

```python
transport = httpx.AsyncHTTPTransport(retries=3)
self._http = httpx.AsyncClient(
    base_url=self.base_url, timeout=30.0, transport=transport,
)
```

httpx `retries` 参数在 transport 层实现，对连接错误自动重试 3 次，指数退避由底层 urllib3 处理。

### 3.3 Session 过期自动重登

在 `AirwayTools` 层统一处理 401 重试逻辑：

```python
class AirwayTools:
    async def _with_retry(self, user_id: str, fn):
        try:
            return await fn()
        except Exception as e:
            if self._is_auth_error(e):
                await self._proxy.refresh_session(user_id)
                return await fn()
            raise

    @staticmethod
    def _is_auth_error(e: Exception) -> bool:
        return "401" in str(e) or "Unauthorized" in str(e)
```

`AuthProxy.refresh_session(user_id)` 清除缓存后重新走登录流程。

每个 tool 方法通过 `_with_retry` 包装。

### 3.4 Redis 降级

`AuthProxy.__init__` 中 `redis` 参数改为 `Optional`：

```python
def __init__(self, client, redis, session, key_prefix="airway:", session_ttl=3600):
    self._redis = redis  # None 时跳过缓存
```

`get_session` / `refresh_session` 中条件检查 `if self._redis:` 后再读写缓存。

`server.py` 初始化时捕获 Redis 连接异常，降级为 `redis=None`。

## 4. 测试策略

| 功能 | 测试文件 | 关键用例 |
|------|----------|----------|
| JWT 验证 | `test_jwt.py` | 有效 token、过期 token、无效签名 |
| HTTP 重试 | `test_client.py` 扩展 | 模拟连接失败后重试成功 |
| Session 过期 | `test_tools.py` 扩展 | 模拟 401 → 自动重登 → 重试成功 |
| Redis 降级 | `test_auth.py` 扩展 | redis=None 时正常工作 |

## 5. 不做的事

- 不引入 decorator / middleware 抽象框架
- 不改变现有 public API 返回格式
- 不新增 Python 依赖（jwt / httpx 已在依赖中）

## 6. 开发顺序

1. HTTP 重试（client 层，独立，无依赖）
2. Redis 降级（auth 层，独立）
3. Session 过期自动重登（依赖 1、2）
4. JWT 验证（auth + server 层，改动面最大，最后做）
