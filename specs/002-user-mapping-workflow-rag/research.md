# Research: 用户映射完善与 Workflow RAG 对接

**Branch**: `002-user-mapping-workflow-rag` | **Date**: 2026-06-07

## Decision 1: Workflow 调用方式

**Decision**: 使用 HTTP SSE（`POST /api/v2/workflow/invoke`）而非 WebSocket

**Rationale**:
- Bisheng 提供 `POST /api/v2/workflow/invoke` HTTP SSE 端点，支持流式和非流式两种模式
- SSE 比 WebSocket 简单得多：标准 HTTP 请求，httpx 原生支持 `aiter_lines()`
- MCP tool 是同步语义（调用→返回），SSE 收集完所有事件后返回结果即可
- 请求格式：`{workflow_id, stream: true, session_id?}`，响应为 `text/event-stream`

**Alternatives considered**:
- WebSocket (`WS /api/v1/workflow/chat/{workflow_id}`)：需要维护连接、复杂消息协议、Cookie 鉴权
- 单次执行节点 (`POST /api/v1/workflow/run_once`)：粒度太细，需要了解节点结构

## Decision 2: 用户注册冲突处理策略

**Decision**: 注册失败（10605）→ 尝试用同密码登录 → 成功则建立映射

**Rationale**:
- Bisheng 注册 API 返回 `status_code: 10605, status_message: "User Name already exist"` 表示用户名冲突
- 此时用相同凭据尝试登录，登录成功返回 `access_token`
- 从登录响应获取 `user_id`，建立映射关系
- 密码使用确定性生成方式（基于 clawith_user_id 派生），保证每次生成一致

**Alternatives considered**:
- 直接报错让管理员处理：用户体验差
- 使用随机后缀避免冲突：用户名不可预测，不便于管理

## Decision 3: 用户密码生成策略

**Decision**: 使用 `airway_{clawith_user_id}` 的 MD5 哈希作为密码，RSA 加密后传输

**Rationale**:
- 密码需要确定性生成（注册和登录使用相同密码）
- 基于 clawith_user_id 派生，无需额外存储
- RSA 加密流程与现有 auth.py 一致：MD5(password) → RSA encrypt → base64
- 安全性由 Bisheng 侧保证（用户只通过 Airway 交互，不直接使用 Bisheng 密码）

## Decision 4: Workflow 配置管理

**Decision**: 在 config.yaml 的 knowledge_bases 配置中新增 `workflow_id` 字段

**Rationale**:
- 每个知识库可以关联一个 Workflow（可选）
- 不关联 Workflow 的知识库仅支持 chunk 搜索（rag_query）
- 关联了 Workflow 的知识库同时支持 chunk 搜索和 RAG 问答（rag_chat）

**Format**:
```yaml
knowledge_bases:
  - name: faq
    bisheng_knowledge_id: 1
    workflow_id: "uuid-of-workflow"
    description: "常见问题"
```

## Decision 5: SSE 响应收集策略

**Decision**: 收集所有 SSE 事件直到收到 `end` 或 `over` 类型消息，拼接为完整文本

**Rationale**:
- Bisheng SSE 响应格式：`data: {"session_id": "...", "data": {"event": "...", ...}}`
- 事件类型包含 `stream`（流式文本片段）和 `end`（完成标记）
- 设置 30s 超时，防止无限等待
- 提取 `session_id` 作为 `chat_id` 返回，支持后续多轮对话

**Alternatives considered**:
- 逐 token 转发：MCP tool 不支持流式响应（返回 string）
- 只取最终结果：可能丢失中间有用的引用信息

## Decision 6: UserMapping 模型扩展

**Decision**: 新增 `password_hash` 和 `status` 字段

**Rationale**:
- `password_hash`：存储确定性密码的哈希，用于验证映射一致性
- `status`：支持 active/invalid 状态，当 Bisheng 用户被删除时标记为 invalid，触发重建
- 保留现有字段不变，通过 Alembic 迁移添加新列

## Decision 7: auth.py 注册方法设计

**Decision**: 在 `BishengAuth` Protocol 中新增 `register_user` 和 `login_user` 方法

**Rationale**:
- `register_user(user_name, password)` → 调用 `POST /api/v1/user/regist`
- `login_user(user_name, password)` → 调用 `POST /api/v1/user/login`，返回 user_id + token
- 复用现有 RSA 加密逻辑（`encrypt_password`）
- Protocol 扩展自然，与现有 `login`（管理员登录）方法共存
