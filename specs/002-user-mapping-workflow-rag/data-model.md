# Data Model: 用户映射完善与 Workflow RAG 对接

**Branch**: `002-user-mapping-workflow-rag` | **Date**: 2026-06-07

## Entity Definitions

### UserMapping（扩展）

在 MVP 基础上扩展的字段：

| Field | Type | Description |
|-------|------|-------------|
| id | Integer PK | 自增主键（已有） |
| clawith_user_id | String(64) UNIQUE | Clawith 用户唯一标识（已有） |
| bisheng_user_id | Integer | Bisheng 用户 ID（已有） |
| bisheng_user_name | String(30) | Bisheng 用户名（已有） |
| password_hash | String(64) NEW | 确定性密码的 MD5 哈希 |
| status | Enum(active/invalid) NEW | 映射状态 |
| created_at | DateTime | 创建时间（已有） |
| updated_at | DateTime | 更新时间（已有） |

**Status 状态转换**：
- `active` → `invalid`：检测到 Bisheng 用户已被删除
- `invalid` → `active`：自动重建映射

### WorkflowConfig（配置项）

通过 config.yaml 管理，`KnowledgeBaseEntry` 模型扩展：

| Field | Type | Description |
|-------|------|-------------|
| name | String | 知识库标识名（已有） |
| bisheng_knowledge_id | Integer | Bisheng 知识库 ID（已有） |
| workflow_id | String NEW | Bisheng Workflow UUID（可选） |
| description | String | 知识库描述（已有） |

### ChatSession（非持久化）

Workflow 对话会话，仅在 SSE 响应中传递：

| Field | Type | Description |
|-------|------|-------------|
| session_id | String(UUID) | Bisheng 分配的会话 ID，即 chat_id |
| workflow_id | String(UUID) | 关联的 Workflow ID |
| user_id | Integer | 关联的 Bisheng 用户 ID |

## Relationship Diagram

```
config.yaml
└── knowledge_bases[]
    ├── name: "faq"
    ├── bisheng_knowledge_id: 1
    └── workflow_id: "uuid" ──→ Bisheng Workflow

user_mappings (PostgreSQL)
├── clawith_user_id ←── Clawith Agent 请求中的用户标识
├── bisheng_user_id ──→ Bisheng 用户身份
└── status: active/invalid
```
