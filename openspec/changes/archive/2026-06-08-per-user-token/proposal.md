# Proposal: per-user-token

## Problem

当前 Airway 使用单一服务账号 token 访问 Bisheng API。生产环境中，不同用户应有不同的权限隔离 — A 用户只能访问自己的知识库，不应使用管理员 token 操作他人的资源。

## Why

权限隔离是企业级部署的基本要求。单一服务账号意味着所有用户共享同一权限级别，存在数据泄露和越权操作风险。

## What Changes

新增 per-user token 映射机制：

1. **Settings 新增 `user_tokens` 配置** — 环境变量 `BISHENG_USER_TOKENS` 格式为 `user_id1:token1,user_id2:token2`
2. **BishengAPIClient 支持 per-request token** — 请求方法接受可选 `token_override` 参数
3. **Tool 层传递 user_id → token** — 根据 `user_id` 查找映射的 token，传递给 client
4. **Fallback** — 未映射的用户使用默认服务账号 token

## Impact

- `settings.py` 新增 `user_tokens` 字段
- `bisheng_client.py` 请求方法新增 `token_override` 参数
- `rag_tools.py` 各函数新增可选 `token` 参数
- `app.py` 各 tool 函数传递 token
- 不改变已有测试行为（fallback 到默认 token）
