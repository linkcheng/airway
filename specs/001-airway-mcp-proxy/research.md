# Research: Airway MCP Proxy

**Branch**: `001-airway-mcp-proxy` | **Date**: 2026-06-07

## Decision 1: MCP 框架选择

**Decision**: FastMCP 3.x

**Rationale**:
- FastMCP 3.3.1 是当前最新稳定版，API 成熟
- 原生支持 `@mcp.tool` 装饰器，自动生成 JSON Schema
- 支持 stdio / streamable-http / sse 多种传输
- 内置 `ToolError` 错误处理，`Context` 日志/进度
- Bisheng 使用原始 MCP SDK 作为客户端，FastMCP 与之互补

**Alternatives considered**:
- 原始 MCP SDK（mcp>=1.20.0）：更底层，需要手动处理更多细节
- 自研 MCP server：重复造轮子，维护成本高

## Decision 2: Bisheng 认证方式

**Decision**: 使用 Bisheng v1 `/api/v1/user/login` 获取 JWT token，RSA 加密密码，Redis 缓存 token

**Rationale**:
- Bisheng 登录需要 RSA 加密密码（MD5 hash → RSA encrypt → base64）
- 需要先调用 `GET /api/v1/user/public_key` 获取公钥
- JWT token 有效期 24 小时，缓存到 Redis 并设置提前 5 分钟刷新
- Token 通过 `Authorization: Bearer <token>` 传递

**Alternatives considered**:
- 每次 API 调用都重新登录：性能差，Bisheng 可能有频率限制
- 使用 session cookie：不如 Bearer token 灵活

## Decision 3: 知识库 API 策略

**Decision**:
- 列表：`GET /api/v2/knowledge`（分页查询）
- 详情：`GET /api/v1/knowledge/info`（按 ID 批量查询）
- 文档搜索：`GET /api/v1/knowledge/chunk`（keyword + knowledge_id）
- RAG 问答：需通过 workflow/assistant 间接实现（Bisheng 无直接 RAG query API）

**Rationale**:
- Bisheng 的 RAG 问答能力嵌入在 workflow/assistant 系统中
- MVP 阶段使用 `chunk` 搜索 API 做文档检索，结合 Agent 自身能力生成答案
- 后续迭代可对接 Bisheng workflow 实现 complete RAG pipeline

**Alternatives considered**:
- 直接调用 Bisheng assistant API：需要预创建 assistant，配置复杂
- 直接访问 Milvus：违反"通过 Bisheng API 访问"的原则

## Decision 4: 数据库策略

**Decision**: SQLAlchemy 2.0 async ORM，PostgreSQL 15+，Alembic 迁移

**Rationale**:
- 与 Constitution VII (Async-First with ORM) 一致
- `Mapped` 类型注解 + `AsyncSession`
- Alembic 管理迁移，支持增量更新
- 独立 `airway_db` 数据库，与 Clawith/Bisheng 共享 PostgreSQL 服务器

**Alternatives considered**:
- SQLModel（Bisheng 使用）：轻量但社区活跃度不如 SQLAlchemy 2.0
- 同步 SQLAlchemy：违反 async-first 原则

## Decision 5: 配置管理

**Decision**: YAML 配置文件 + 环境变量覆盖 + pydantic-settings

**Rationale**:
- pydantic-settings 支持类型校验和默认值
- `${VAR_NAME}` 语法支持环境变量替换
- 配置文件结构清晰，便于运维

**Alternatives considered**:
- fastmcp.json 声明式配置：FastMCP 3.x 新特性，但与 YAML 配置不兼容
- 纯环境变量：缺少结构化配置能力

## Decision 6: FastMCP 版本约束

**Decision**: `fastmcp>=3.0`

**Rationale**:
- 3.0+ 提供 `ToolError`、`Context`、`Depends()`、`custom_route` 等关键特性
- 3.x API 稳定，向后兼容

## Decision 7: 错误处理策略

**Decision**: 自定义 `AirwayError` + FastMCP `ToolError` 双层

**Rationale**:
- Adapter 层抛出 `AirwayError`（携带 error_code + message）
- Tool 层捕获并转换为 `ToolError` 返回给 MCP 客户端
- FastMCP `mask_error_details=True` 隐藏内部堆栈

**Alternatives considered**:
- 全部用 ToolError：丢失业务错误码，不利于日志分析
- 全部用自定义异常：需要额外的 FastMCP 异常处理中间件

## Decision 8: HTTP 客户端超时

**Decision**: httpx.AsyncClient 默认 timeout=5.0s，连接超时 3.0s

**Rationale**:
- 与 SC-004（5 秒内返回错误）对齐
- Bisheng 正常响应 <1s，5s 足够覆盖慢查询
- 连接建立超时 3s，区分"连不上"和"处理慢"

## Decision 9: Adapter 抽象接口

**Decision**: 使用 Python Protocol 定义 BishengAdapter 接口

**Rationale**:
- 与 Constitution III (Dependency Inversion) 对齐
- auth.py 实现 `BishengAuth` Protocol（login, get_token）
- client.py 实现 `BishengClient` Protocol（list_knowledge, get_knowledge, search_chunks）
- server.py 依赖 Protocol 而非具体实现，便于测试 mock

## Decision 10: Bisheng 用户创建策略

**Decision**: 使用 `POST /api/v1/user/regist` 公开端点创建 Bisheng 用户

**Rationale**:
- 无需认证即可调用，适合自动注册场景
- 仅需 user_name + RSA 加密密码
- 首个用户自动成为 Super Admin，后续用户获得 Default role
- 密码加密方式与登录一致（复用 auth.py 的 RSA 加密逻辑）

**API Contract**:
- URL: `POST /api/v1/user/regist`
- Body: `{user_name: str, password: str}`（password 需 RSA 加密）
- Response: `{status_code: 200, data: {user_id, user_name, ...}}`
- 注意：如果 Bisheng 开启了 captcha，需要额外处理（MVP 假设 captcha 关闭）

**Alternatives considered**:
- `POST /api/v1/user/create`（管理员端点）：需要 Super Admin 认证，更复杂
- SSO 端点：仅 Bisheng Pro 可用
