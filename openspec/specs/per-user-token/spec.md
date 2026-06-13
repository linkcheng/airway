# Spec: per-user-token

## Overview

Per-user token mapping for Bisheng API access, enabling permission isolation between different Clawith users.

### Requirement: 用户 Token 映射配置

- Settings 新增 `user_tokens: dict[str, str]` 字段
- 从环境变量 `BISHENG_USER_TOKENS` 解析，格式 `user_id1:token1,user_id2:token2`
- 空值或未设置时返回空 dict

### Requirement: 按请求覆盖 Token

- BishengAPIClient 的 `request()` 方法新增 `token_override: str | None = None` 参数
- `get()`, `post()`, `delete()`, `upload()` 透传 `token_override`
- 当 `token_override` 不为 None 时，使用覆盖 token 替代默认 token
- 当 `token_override` 为 None 时，行为与改造前完全一致（使用服务账号 token）

### Requirement: Tool 层 Token 解析

- `rag_tools.py` 每个函数新增 `token: str | None = None` 参数
- `app.py` 新增 `resolve_token(user_id)` 辅助函数
- 每个 MCP tool 函数调用 `resolve_token(user_id)` 获取 token_override 并传递
- 未映射用户 fallback 到 None（使用默认 token）
