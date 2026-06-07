# Feature Specification: Airway MCP Proxy

**Feature Branch**: `001-airway-mcp-proxy`

**Created**: 2026-06-07

**Status**: Draft

**Input**: User description: "构建 Airway——一个连接 Clawith Agent 与 Bisheng RAG 后端的企业级 MCP 集成平台"

## User Scenarios & Testing

### User Story 1 - Agent 查询知识库 (Priority: P1)

Clawith 的数字员工（AI Agent）需要基于企业知识库回答用户问题。
Agent 通过 MCP 协议调用 Airway 的 `rag_query` 工具，传入用户问题和
知识库标识，Airway 将请求翻译为 Bisheng API 调用，返回检索结果和
生成的答案。整个过程 Agent 无需了解 Bisheng 的 API 结构。

**Why this priority**: 这是核心价值场景——让 Agent 具备 RAG 能力。
没有这个功能，其他功能没有意义。

**Independent Test**: 可以通过 MCP 客户端直接调用 `rag_query` 工具
验证，传入测试问题和知识库 ID，检查返回的答案内容。

**Acceptance Scenarios**:

1. **Given** Agent 已连接 Airway MCP 服务，**When** Agent 调用
   `rag_query(query="产品退货政策是什么？", knowledge_base="company-faq")`，
   **Then** Airway 返回包含答案文本和来源文档片段的响应
2. **Given** 知识库不存在，**When** Agent 调用 `rag_query`，
   **Then** Airway 返回明确的错误信息"知识库不存在"
3. **Given** 查询内容为空，**When** Agent 调用 `rag_query`，
   **Then** Airway 返回参数校验错误

---

### User Story 2 - 浏览知识库 (Priority: P2)

Agent 需要知道有哪些可用的知识库，才能引导用户选择正确的知识源。
Agent 调用 `knowledge_list` 获取可用知识库列表，调用
`knowledge_detail` 查看某个知识库的详细信息（文档数量、索引状态等）。

**Why this priority**: 辅助功能，Agent 可以通过其他方式（如配置硬编码）
获取知识库信息，但有这个工具更灵活。

**Independent Test**: 通过 MCP 客户端调用 `knowledge_list`，验证返回
的知识库列表包含预期的知识库名称和基本信息。

**Acceptance Scenarios**:

1. **Given** Bisheng 中存在 3 个知识库，**When** Agent 调用
   `knowledge_list()`，**Then** 返回包含 3 个知识库摘要的列表
2. **Given** Agent 选择某个知识库，**When** Agent 调用
   `knowledge_detail(knowledge_base="product-docs")`，
   **Then** 返回该知识库的详细信息（名称、文档数、状态）
3. **Given** 知识库 ID 无效，**When** Agent 调用
   `knowledge_detail`，**Then** 返回"知识库不存在"错误

---

### User Story 3 - 用户身份自动映射 (Priority: P3)

当 Clawith 用户首次通过 Agent 调用 RAG 工具时，Airway 自动在
Bisheng 中创建对应账号（或映射到已有账号），后续调用自动使用
映射后的 Bisheng 凭证。用户无感知，不需要二次登录。

**Why this priority**: 安全和身份集成是生产必需的，但 MVP 阶段可以
先用管理员账号代理所有请求，后续迭代加入用户映射。

**Independent Test**: 首次用一个新 Clawith 用户 ID 调用任意 RAG 工具，
验证 Airway 数据库中生成了用户映射记录，且后续调用使用该映射。

**Acceptance Scenarios**:

1. **Given** Clawith 用户 A 首次调用 `rag_query`，**When** Airway
   检测到无映射记录，**Then** 自动创建 Bisheng 账号并存储映射关系
2. **Given** Clawith 用户 A 已有映射，**When** 再次调用工具，
   **Then** 直接使用已映射的 Bisheng 凭证，不重复创建
3. **Given** Bisheng 中已存在同名用户，**When** Airway 尝试映射，
   **Then** 复用已有账号而非创建新的

---

### User Story 4 - 搜索知识库文档片段 (Priority: P4)

Agent 需要在知识库中搜索特定文档片段（非问答模式，而是关键词
检索），用于提供精确的参考来源。调用 `knowledge_search` 传入
关键词和知识库标识，返回匹配的文档片段列表。

**Why this priority**: 增强型检索，MVP 阶段 `rag_query` 已覆盖基本
检索需求，此功能作为补充。

**Independent Test**: 通过 MCP 客户端调用 `knowledge_search`，
传入测试关键词，验证返回的文档片段包含匹配内容。

**Acceptance Scenarios**:

1. **Given** 知识库中有包含"退货"的文档，**When** Agent 调用
   `knowledge_search(query="退货", knowledge_base="product-docs")`，
   **Then** 返回包含"退货"关键词的文档片段列表
2. **Given** 搜索无匹配结果，**When** Agent 调用
   `knowledge_search`，**Then** 返回空列表

---

### Edge Cases

- Bisheng 服务不可用时，Airway 如何响应？→ 返回明确的"RAG 服务暂时不可用"错误
- Bisheng JWT token 过期且刷新失败时？→ 返回认证错误，提示检查 Bisheng 配置
- 并发大量 Agent 同时查询时？→ 无状态设计 + 连接池，水平扩展
- 知识库正在索引中（状态为 processing）时查询？→ 返回结果但标注索引可能不完整
- MVP 阶段所有用户共享同一组知识库，通过配置的 Bisheng 管理员账号统一访问，无租户隔离

## Requirements

### Functional Requirements

- **FR-001**: Airway MUST 通过 MCP 协议暴露 `rag_query` 工具，接受查询文本和知识库标识，返回 RAG 问答结果
- **FR-002**: Airway MUST 通过 MCP 协议暴露 `knowledge_list` 工具，返回用户可访问的知识库列表
- **FR-003**: Airway MUST 通过 MCP 协议暴露 `knowledge_detail` 工具，接受知识库标识，返回详细信息
- **FR-004**: Airway MUST 通过 MCP 协议暴露 `knowledge_search` 工具，接受搜索关键词和知识库标识，返回匹配片段
- **FR-005**: Airway MUST 维护 Clawith 用户到 Bisheng 用户的映射关系，首次使用时自动创建映射
- **FR-006**: Airway MUST 使用 Bisheng 管理员凭证获取 JWT token，并缓存至过期前自动刷新
- **FR-007**: Airway MUST 将所有 Bisheng API 错误翻译为用户友好的错误消息返回给 Agent
- **FR-008**: Airway MUST 通过配置文件管理 Bisheng 连接信息（URL、管理员凭证、知识库映射等）
- **FR-009**: Airway MUST 支持 stdio 和 HTTP 两种 MCP 传输模式
- **FR-010**: Airway MUST 对所有工具输入参数进行校验，拒绝非法输入

### Key Entities

- **UserMapping**: Clawith 用户 ID 与 Bisheng 用户 ID 的映射关系，包含映射创建时间和状态
- **KnowledgeBase**: 知识库配置，包含 Bisheng 中的知识库标识和面向 Agent 的显示名称
- **BishengToken**: 缓存的 Bisheng JWT token 及其过期时间

## Success Criteria

### Measurable Outcomes

- **SC-001**: Agent 通过单次 MCP 工具调用即可完成知识库查询，无需额外配置或认证步骤
- **SC-002**: 用户身份映射对 Agent 完全透明，Agent 无需处理任何 Bisheng 认证细节
- **SC-003**: 系统支持至少 10 个 Agent 并发查询而不出现请求失败
- **SC-004**: Bisheng 服务故障时，Agent 在 5 秒内收到明确的错误响应（不会无限等待）
- **SC-005**: 所有 4 个 MCP 工具均可通过标准 MCP 客户端独立调用和验证

## Assumptions

- Bisheng 已部署且可通过 HTTP 访问，v1（认证）和 v2（业务）API 可用
- Clawith 已部署且 Agent 支持 MCP 协议工具调用
- MVP 阶段使用 Bisheng 管理员账号代理所有 RAG 请求，后续迭代加入细粒度用户映射
- PostgreSQL 和 Redis 已部署，Airway 可创建独立的数据库和 key prefix
- 知识库已在 Bisheng 中创建并完成文档索引，Airway 不负责知识库的创建和文档上传
- Clawith 用户 ID 是稳定的唯一标识符
