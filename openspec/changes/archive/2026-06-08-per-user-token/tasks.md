# Tasks: per-user-token

## 1. Settings 扩展
- [ ] `settings.py` 新增 `user_tokens` 字段和解析逻辑

## 2. BishengAPIClient Token Override
- [ ] `request()` 新增 `token_override` 参数
- [ ] `get()`, `post()`, `delete()`, `upload()` 透传 `token_override`

## 3. rag_tools Token 参数
- [ ] 所有 14 个函数新增 `token: str | None = None` 参数
- [ ] 将 token 传递给 client 方法

## 4. app.py Token 解析
- [ ] 新增 `resolve_token(user_id)` 函数
- [ ] 所有 14 个 tool 函数传递 token_override

## 5. 测试
- [ ] 测试 Settings 解析 `BISHENG_USER_TOKENS`
- [ ] 测试 `request()` 使用 token_override
- [ ] 测试 fallback 到默认 token
- [ ] 已有测试不受影响
