## Context

两个独立开源产品需要桥接：
- **Clawith**：Agent 平台（FastAPI + PostgreSQL + SQLAlchemy async），已有 MCP 客户端支持（SSE/Streamable HTTP transport），可通过 MCP 协议调用外部工具
- **Bisheng**：RAG 平台（FastAPI + SQLModel + MySQL），暴露 REST API 用于知识库管理、文档处理、向量检索

两者认证体系不同（Clawith JWT vs Bisheng JWT cookie），数据库不同（PostgreSQL vs MySQL），但都基于 FastAPI。Airway 作为中间层，以 MCP Server 身份对 Clawith 暴露 Bisheng 的 RAG 能力。

## Goals / Non-Goals

**Goals:**
- Clawith Agent 能通过 MCP 协议调用 Bisheng 的知识库查询和文档检索
- Airway 无状态，不持久化业务数据，仅做协议转换和身份映射
- 两个上游项目零代码修改，可独立 git pull 升级
- MVP 聚焦核心检索场景，后续迭代扩展

**Non-Goals:**
- 不合并两个系统的数据库
- 不实现 Bisheng 的文档上传/解析（MVP 阶段由 Bisheng 原生 UI 操作）
- 不实现 Workflow 引擎桥接
- 不做 SSO 单点登录集成（MVP 用 service account 方案）
- 不做多租户隔离

## Decisions

### D1: MCP 协议选择 — SSE transport

Clawith MCP 客户端同时支持 SSE 和 Streamable HTTP。选择 SSE 因为实现更简单，社区文档更成熟。Airway 使用 `mcp` Python SDK 实现 SSE server。

**备选**: Streamable HTTP（未来可切换，协议层面兼容）

### D2: 身份映射 — Service Account + 用户 ID 透传

MVP 阶段不实现完整的 SSO 桥接。Airway 持有一个 Bisheng service account 的 JWT token，所有对 Bisheng 的 API 调用使用此 token。Clawith 用户 ID 通过 MCP tool 参数透传，供后续审计使用。

**备选**: 为每个 Clawith 用户创建 Bisheng 账号并维护 token 映射（复杂度高，非 MVP）

### D3: 技术栈 — FastAPI + httpx async + mcp SDK

- FastAPI：与两个上游项目技术栈一致
- httpx async：异步 HTTP 客户端调用 Bisheng API
- mcp SDK：实现 MCP Server（SSE transport）
- Pydantic v2：数据校验和配置管理
- 不引入数据库 ORM（无状态代理不需要）

### D4: 配置管理 — 环境变量 + Pydantic Settings

通过 `.env` 文件和环境变量配置，使用 Pydantic Settings 做类型安全的配置加载。配置项包括：Bisheng API base URL、service account token、MCP server port 等。

### D5: 部署 — Docker Compose 独立服务

Airway 作为独立容器部署，与 Bisheng 和 Clawith 的 Docker Compose 并列。Clawith 的 MCP 客户端指向 Airway 的 SSE endpoint。

## Risks / Trade-offs

- **[Service Account 单点]** → MVP 可接受，后续迭代支持 per-user token 映射
- **[Bisheng API 变更]** → 通过 Bisheng 的 `/api/v1/` 版本化 API 降低风险；Airway 封装适配层
- **[Token 过期]** → Bisheng JWT 有过期时间，需实现自动刷新或使用长期 token
- **[无状态限制]** → 无法追踪会话状态，复杂场景（如分页）需要客户端管理
