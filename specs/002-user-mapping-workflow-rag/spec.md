# Feature Specification: 用户映射完善与 Workflow RAG 对接

**Feature Branch**: `002-user-mapping-workflow-rag`

**Created**: 2026-06-07

**Status**: Draft

**Input**: 基于已完成的 MVP（4 个 MCP 工具 + chunk 搜索），完善用户映射机制并对接 Bisheng Workflow 实现完整 RAG 问答能力

**Depends On**: `001-airway-mcp-proxy`（MVP 已完成，4 个 MCP 工具全部可用）

## User Scenarios & Testing

### User Story 1 - Clawith 用户自动映射到 Bisheng 真实账号 (Priority: P1)

当 Clawith 用户首次通过 Agent 调用任意 RAG 工具时，Airway 自动在 Bisheng 中
创建真实用户账号并建立映射关系。后续所有工具调用都使用该映射后的 Bisheng
用户身份，确保操作可审计、权限可管理。用户完全无感知，不需要二次登录。

**Why this priority**: 当前 MVP 使用管理员账号代理所有请求，无法区分不同用户的
操作。真实用户映射是生产环境必需的身份隔离和审计基础，且后续 Workflow 对话
依赖真实用户身份。

**Independent Test**: 使用一个新的 Clawith 用户 ID 调用任意 MCP 工具，验证
Airway 自动完成用户创建、映射建立，且后续调用使用映射后的身份。

**Acceptance Scenarios**:

1. **Given** Clawith 用户 A 首次调用 `rag_query`，Airway 数据库无该用户映射，
   **When** Airway 检测到无映射，**Then** 自动在 Bisheng 中创建用户账号，
   保存映射关系，并使用该用户身份完成本次工具调用
2. **Given** Clawith 用户 A 已有映射记录，**When** 再次调用任意工具，
   **Then** 直接使用已映射的 Bisheng 用户凭证，不重复创建
3. **Given** Bisheng 中已存在同名用户（用户之前在 Bisheng 直接注册过），
   **When** Airway 尝试创建用户，**Then** 检测到冲突后复用已有账号，
   仅建立映射关系
4. **Given** Bisheng 用户注册服务不可用，**When** 新用户首次调用工具，
   **Then** 返回明确的"用户注册服务暂时不可用"错误，不影响已有映射用户的正常使用

---

### User Story 2 - Agent 通过 Workflow 获得完整 RAG 答案 (Priority: P2)

Agent 需要获得 AI 生成的完整答案（而非仅文档片段）。Agent 调用新增的
`rag_chat` 工具，传入用户问题和知识库标识，Airway 通过 Bisheng Workflow
引擎生成完整回答。Agent 获得的是可直接使用的答案文本，无需自行从片段中
提取和总结。

**Why this priority**: 这是 MVP 迭代的核心升级——从"检索文档片段"升级为
"生成完整答案"。直接提升 Agent 回答用户问题的质量。

**Independent Test**: 通过 MCP 客户端调用 `rag_chat`，传入测试问题，
验证返回的是完整的 AI 生成答案而非文档片段列表。

**Acceptance Scenarios**:

1. **Given** Bisheng 中已配置好包含知识库引用的 RAG Workflow，
   **When** Agent 调用 `rag_chat(query="产品退货政策是什么？", knowledge_base="company-faq")`，
   **Then** 返回完整的 AI 生成答案，包含答案文本和引用来源
2. **Given** 知识库标识无效，**When** Agent 调用 `rag_chat`，
   **Then** 返回"知识库不存在"错误
3. **Given** 用户问题为空，**When** Agent 调用 `rag_chat`，
   **Then** 返回参数校验错误
4. **Given** Bisheng Workflow 执行超时（超过 30 秒），**When** Agent 调用 `rag_chat`，
   **Then** 返回"RAG 服务响应超时"错误，Agent 不会无限等待
5. **Given** 同时有多个 Agent 并发调用 `rag_chat`，**When** 各自传入不同问题，
   **Then** 每个请求独立获得正确答案，互不干扰

---

### User Story 3 - 查询历史对话上下文 (Priority: P3)

Agent 可以通过传入 `chat_id` 参数继续之前的对话，Bisheng Workflow 会
基于历史上下文生成连贯的回答。不传 `chat_id` 则开启全新对话。

**Why this priority**: 增强型功能。单轮问答已满足大部分场景，
多轮对话上下文是体验优化。

**Independent Test**: 连续两次调用 `rag_chat` 并传入相同的 `chat_id`，
验证第二次回答能基于第一次对话的上下文。

**Acceptance Scenarios**:

1. **Given** Agent 首次调用 `rag_chat` 且不传 `chat_id`，
   **When** 工具返回结果，**Then** 响应中包含新建的 `chat_id` 供后续使用
2. **Given** Agent 使用之前返回的 `chat_id` 再次调用，
   **When** 提出追问（如"能详细说一下第二点吗？"），
   **Then** Bisheng 基于历史上下文生成连贯回答

---

### Edge Cases

- Bisheng 用户注册 API 返回用户名冲突时，Airway 如何处理？→ 尝试以该用户名登录，成功则建立映射
- Bisheng 用户注册 API 需要验证码时？→ MVP 假设验证码已关闭，未关闭则返回配置错误提示
- Workflow 执行过程中连接中断？→ 设置合理超时（30s），超时返回错误，不无限等待
- 多个 Workflow 同时配置（不同知识库对应不同 Workflow）？→ 通过配置文件的知识库-Workflow 映射关系自动路由
- 映射表数据损坏（如 Bisheng 用户被删除）？→ 检测到映射失效时自动重新创建并更新映射

## Requirements

### Functional Requirements

- **FR-001**: Airway MUST 在首次工具调用时自动为 Clawith 用户创建 Bisheng 用户账号，并持久化映射关系
- **FR-002**: Airway MUST 复用已有映射关系，不重复创建 Bisheng 用户
- **FR-003**: Airway MUST 处理 Bisheng 用户名冲突（已存在同名用户），通过尝试登录复用已有账号
- **FR-004**: Airway MUST 新增 `rag_chat` MCP 工具，接受用户问题、知识库标识，返回 AI 生成的完整答案
- **FR-005**: Airway MUST 支持通过 `chat_id` 参数实现多轮对话上下文
- **FR-006**: Airway MUST 为每个工具调用使用映射后的 Bisheng 用户身份（非管理员代理）
- **FR-007**: Airway MUST 对 `rag_chat` 设置超时限制，防止无限等待
- **FR-008**: Airway MUST 保留原有 `rag_query`（chunk 搜索）工具不变，`rag_chat` 作为新增工具
- **FR-009**: Airway MUST 在用户注册服务不可用时返回明确错误，不影响已有映射用户的正常使用
- **FR-010**: Airway MUST 通过配置文件管理知识库与 Workflow 的映射关系

### Key Entities

- **UserMapping（增强）**: 在 MVP 基础上，增加 Bisheng 用户密码哈希字段，支持登录验证；增加映射状态（active/invalid），支持失效检测和重建
- **WorkflowConfig**: 知识库与 Bisheng Workflow 的映射关系，包含 Workflow 标识和对话参数
- **ChatSession**: 对话会话，关联 Workflow 执行实例和用户映射，支持多轮对话上下文

## Success Criteria

### Measurable Outcomes

- **SC-001**: 新用户首次调用工具时，用户映射和工具调用在 5 秒内完成（含 Bisheng 用户创建）
- **SC-002**: 已有映射用户的工具调用响应时间与 MVP 一致，映射查询增加延迟 < 50ms
- **SC-003**: `rag_chat` 返回的答案是完整的 AI 生成文本，Agent 可直接用于回复用户
- **SC-004**: 系统 10 个 Agent 并发调用 `rag_chat` 时，每个请求独立获得正确答案
- **SC-005**: 映射失效（Bisheng 用户被删除）时，系统自动重建映射，用户无需人工干预
- **SC-006**: 用户注册、映射建立、工具调用的全链路过程对 Agent 完全透明

## Assumptions

- Bisheng 已部署且用户注册 API (`/api/v1/user/regist`) 可用
- Bisheng 验证码（captcha）功能已关闭（MVP 阶段）
- Bisheng 中已配置好包含知识库引用的 RAG Workflow，可通过 Workflow ID 调用
- Workflow chat API 支持通过用户 JWT token 鉴权
- PostgreSQL 中 user_mappings 表结构可扩展（增加新字段）
- 原有 4 个 MCP 工具（rag_query, knowledge_list, knowledge_detail, knowledge_search）行为不变
