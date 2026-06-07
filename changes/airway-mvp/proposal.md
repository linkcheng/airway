## Why

企业需要同时具备 Agent 编排能力和 RAG 知识检索能力的 AI 平台。Clawith 擅长 Agent 管理、多渠道集成和 MCP 工具调用；Bisheng 擅长知识库管理、文档解析和向量化检索。两者独立运行时各自闭环，但缺少统一入口让 Agent 直接调用 RAG 能力。Airway 作为无状态 MCP 代理，以最小侵入方式桥接两者，使 Clawith Agent 能直接使用 Bisheng 的知识检索能力。

## What Changes

- 新增 Airway 项目：一个 Python FastAPI 服务，作为 MCP Server 暴露 Bisheng RAG 能力
- Airway 实现 MCP 协议（SSE transport），Clawith 通过 MCP 客户端连接
- Airway 代理 Bisheng 的知识库查询、文档检索等 REST API
- 实现 Clawith 用户到 Bisheng API 调用的身份映射
- 不修改 Bisheng 和 Clawith 源码，两个上游项目可独立升级

## Capabilities

### New Capabilities

- `mcp-server`: Airway 的 MCP 服务器框架，实现 SSE transport，注册并暴露 RAG 工具给 Clawith Agent 调用
- `rag-proxy`: 代理 Bisheng RAG API（知识库列表、文档检索、chunk 查询），将 Bisheng REST API 封装为 MCP Tool
- `auth-bridge`: 用户身份桥接，将 Clawith 用户请求映射为 Bisheng API 认证（通过 Bisheng 的 JWT token 机制），确保 API 调用有合法身份

### Modified Capabilities

（无，全新项目）

## Impact

- **新增代码**: 全新 Python 项目（Airway），独立部署
- **Bisheng**: 无代码修改，仅通过 REST API 调用（`/api/v1/knowledge` 等）
- **Clawith**: 无代码修改，通过现有 MCP 客户端连接 Airway MCP Server
- **基础设施**: Airway 独立部署，依赖 Bisheng API 可达；可选共享 Redis
- **技术栈**: Python 3.12, FastAPI, async, MCP SDK, SQLModel ORM
