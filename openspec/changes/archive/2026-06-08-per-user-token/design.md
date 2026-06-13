# Design: per-user-token

## Architecture

```
Clawith Agent
   ↓ user_id in tool args
Airway MCP Tool
   ↓ resolve_token(user_id) → token_override
BishengAPIClient.request(token_override=...)
   ↓ Cookie: access_token={token_override or default}
Bisheng API
```

## Token Resolution

```python
def resolve_token(user_id: str | None) -> str | None:
    if user_id and user_id in settings.user_tokens:
        return settings.user_tokens[user_id]
    return None  # fallback to default token
```

## Settings

```python
class Settings:
    user_tokens: dict[str, str] = {}  # parsed from BISHENG_USER_TOKENS env var
```

环境变量格式：`user1:token1,user2:token2`

## BishengAPIClient 改造

现有 `request()` 方法新增 `token_override` 参数：

```python
async def request(self, method, path, *, token_override=None, **kwargs):
    token = token_override or self._token
    headers = {"Cookie": f"access_token={token}"} if token else {}
```

所有公共方法（get, post, delete, upload）透传 `token_override`。

## rag_tools 改造

每个函数新增 `token: str | None = None` 参数，传递给 client 方法。

## app.py 改造

每个 tool 函数调用 `resolve_token(user_id)` 获取 token_override。

## Backward Compatibility

- `token` 默认 `None`，不传时使用服务账号 token
- 已有测试不需要修改
- 新测试覆盖 token 映射场景
