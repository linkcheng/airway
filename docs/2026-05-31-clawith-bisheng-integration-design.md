# Clawith + Airway 企业级 AI 平台整合设计

> 版本：v20 | 日期：2026-06-04
> 架构：Clawith Agent（MCP）→ Airway（协议转换 + 状态同步 + 统一认证 + 统一审计 + 统一路由）→ RAG 后端
>
> **实施文档**：→ [Airway MVP 设计 + 迭代路线](2026-06-04-airway-mvp-design.md)（从本文档提取的最小可行方案，按数据驱动迭代）

## 1. 目标

构建以 Clawith Agent 为核心、通过 Airway（AI Runtime Layer）接入多种 RAG 后端的企业级 AI 平台。Airway 是不拥有业务引擎的协议转换层：不实现 Workflow/Knowledge/Prompt/Agent Engine，但持有 SSE 长连接、PG 任务缓存和 Outbox 通知等运行时状态。Bisheng 是第一个被接入的 RAG Runtime。

## 2. 核心原则

- **Agent + Runtime 分离**：Agent 层专注身份/记忆/自主性/多渠道，Runtime 层专注 RAG/Workflow
- **Airway 不拥有业务**：Airway 只做协议转换、状态同步、统一认证、统一审计、统一路由。不做 Workflow Engine / Knowledge Engine / Prompt Engine / Agent Engine
- **Single Source of Truth**：活跃任务的状态 SSOT 是 Runtime（Bisheng Redis），Airway 只缓存和同步；终态因 Runtime 清理而由 Airway PG 固化
- **Adapter 模式**：统一接口，每个后端一个 Adapter（Bisheng、Dify、RagFlow...）
- **Event/Audit Store**：统一事件记录表，同时服务系统排障（按 task_id 时间线）和合规审计（按 actor_id 操作历史）
- **用户上下文传递**：MCP Tool 参数显式传递 user_id / tenant_id，Identity Gateway 统一映射到 Runtime 用户
- **混合通知**：Webhook（实时推送）+ MCP Tool Polling（兜底查询），适配 Clawith 当前能力
- **开闭原则**：不修改 Clawith 和任何 RAG 后端源码
- **升级兼容**：所有开源项目独立 git pull 升级；Clawith 支持 MCP Task 后，Airway 可直接暴露标准 Task 接口

## 3. 架构总览

### 3.1 分层架构

```
┌─────────────────────────────────────────────────────┐
│                    Clawith Agent                     │
│   用户入口 / Agent 身份 / 长期记忆 / 自主触发 /      │
│   A2A 协作 / 多渠道集成 / 企业管理 / The Plaza       │
└───────────┬─────────────────────┬───────────────────┘
            │                     │
            │ 普通 MCP Tool       │ Webhook Trigger
            │ (含 user_id/        │ (异步事件推送)
            │  tenant_id)         │
            ▼                     │
┌─────────────────────────────────────────────────────┐
│                Airway（协议转换层，有运行时状态）       │
│                                                      │
│   对外接口（普通 MCP Tool，Clawith 当前可消费）：    │
│   ├── rag_query / rag_upload / rag_kb_list (同步)   │
│   ├── workflow_start    → 返回 task_id              │
│   ├── workflow_status   → 缓存优先，过期刷新        │
│   └── workflow_continue → 提交人工输入               │
│                                                      │
│   Airway 核心能力（不拥有业务引擎）：                │
│   ├── 协议转换:    MCP Tool ↔ Runtime API           │
│   ├── 状态同步:    Runtime SSOT → PG 缓存 + 终态固化 │
│   ├── 统一认证:    Identity Gateway 映射用户身份     │
│   ├── 统一审计:    Event Store 记录所有操作          │
│   └── 统一路由:    capabilities 匹配 + Adapter 分发  │
│                                                      │
│   SSE 消费: 9 种 Bisheng 事件 → 缓存状态 + 事件桥接  │
│   SSE 断连: 查询 Redis 状态补偿恢复（轮询）          │
│   事件桥接: input_required → Clawith Webhook 推送   │
│                                                      │
│   Adapter 层（每个 Adapter 声明 capabilities）：     │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│   │ Bisheng  │  │   Dify   │  │ RagFlow  │  ...     │
│   │ Adapter  │  │ Adapter  │  │ Adapter  │          │
│   └──────────┘  └──────────┘  └──────────┘          │
└─────────────────────────────────────────────────────┘
         │              │              │
         ▼              ▼              ▼
    Bisheng 后端    Dify 后端    RagFlow 后端
```

### 3.2 混合通知模式

三种机制各司其职，不选其一，而是分层协作：

| 层 | 机制 | 方向 | 职责 |
|----|------|------|------|
| **Airway 内部** | Task 状态机（MCP Task 语义） | — | 管理异步生命周期，标准化状态转换 |
| **Agent → Airway** | 普通 MCP Tool | Agent → Airway | 同步调用 + Polling 兜底 |
| **Airway → Agent** | Clawith Webhook Trigger | Airway → Agent | `input_required` 时即时唤醒 Agent |
| **Airway 后台** | SSE 消费 | Bisheng → Airway | 消费 Bisheng 9 种 SSE 事件，驱动状态机 |

**为什么不用纯 MCP Task**：Clawith MCP Client 当前不支持 SEP-1686（无 extension 协商、无 CreateTaskResult、无 tasks/get）。Airway 内部用 Task 语义管理状态，对外降级为 Clawith 能理解的普通 Tool + Webhook。未来 Clawith 支持 MCP Task 后，Airway 可直接暴露标准 Task 接口，核心代码零改动。

### 3.3 Bisheng 的定位：RAG Runtime

Bisheng Assistant 不是竞争者，而是 RAG Runtime——提供：
- 知识库管理（CRUD + 权限）
- 文档解析（高精度 OCR + 表格/版面识别）
- 向量化流水线（Milvus + ES 混合检索 + RRF 融合 + Rerank）
- Workflow 引擎（含 Human-in-the-Loop）
- 问答生成（检索 + LLM 一体）

## 4. 同步与异步两种交互模式

### 4.1 同步操作（RAG 问答/上传/管理）

```
Agent → MCP: rag_query → Airway → BishengAdapter → Bisheng v2 API
         ← 即时返回结果 ←
```

适用于：问答、文档上传、知识库列表等短周期操作（< 30s）。

### 4.2 异步操作（Workflow + Human-in-the-Loop）

企业审批流可能持续数小时，采用 Task 状态机 + 事件驱动闭环：

```
正向流（触发）：
  Agent → MCP: workflow_start(workflow_id="模板UUID")
    → BishengAdapter → POST /api/v2/workflow/invoke
    → Bisheng 生成 unique_id（格式 {chat_id}_async_task_id）
    → Airway 创建 Task(task_id=unique_id, workflow_id=模板UUID)
    → 返回 { task_id: unique_id, status: "working" }
    → Airway 后台持有 SSE 流，持续消费

事件驱动（状态转换）：
  Bisheng SSE: input 事件（input_schema 包含结构化表单）
    → Airway Task(input_required)
    → 事件桥接 → Clawith Webhook: POST /api/webhooks/t/{token}
      { type: "workflow_input", task_id, input_schema }
    → Clawith 触发 Agent (webhook trigger)

唤醒闭环：
  Agent 被唤醒
    → 推送 Plaza / 飞书群 / 钉钉群
    → 人工或 Agent 讨论出结果
    → Agent → MCP: workflow_continue(task_id, inputs, message_id)
      → Airway → POST /api/v2/workflow/invoke（携带 session_id=unique_id, user_input + message_id）
      → Task(working)，获取新 SSE 流
      → 循环直到 Task(completed)

最终通知：
  Bisheng SSE: close 事件（workflow 执行结束）
    → Airway Task(completed)
    → 事件桥接 → Clawith Webhook
    → Agent 通知用户结果

Polling 兜底：
  任何时候 Agent 可调用 workflow_status(task_id) 查询当前状态
  用于：Webhook 失败恢复、Agent 重连后状态恢复
  SSE 断连后：查询 Redis 状态（RUNNING/INPUT/SUCCESS/FAILED）补偿恢复
```

### 4.3 完整闭环示例

```
1. 用户: "提交采购审批"
2. Agent → MCP: workflow_start(workflow_id="wf_purchase_template_uuid")
3. Airway → Bisheng invoke → 获取 unique_id="abc123_async_task_id"
4. Airway: Task(task_id="abc123_async_task_id", working) → 持有 SSE 流
5. Agent 收到: { task_id: "abc123_async_task_id", status: "working" }
6. Agent 回复: "已提交"

...30分钟后...

7. Bisheng SSE: input 事件（input_schema: { input_type: "form_input", value: [{ key: "approval", type: "select", label: "审批决定", options: ["同意", "驳回"] }] }）
8. Airway: Task(input_required)，保存 input_schema
9. Airway → Clawith Webhook → Agent 被唤醒
10. Agent → 飞书群: "@经理 请审批采购申请"

...2小时后...

11. 经理回复: "同意"
12. Agent → MCP: workflow_continue("abc123_async_task_id", { approval: "同意" }, message_id="msg_xxx")
13. Airway → Bisheng: POST /api/v2/workflow/invoke（session_id="abc123_async_task_id", user_input, message_id）→ Task(working)

...Workflow 继续执行...

14. Bisheng SSE: close 事件（包含最终输出）
15. Airway: Task(completed) → Clawith Webhook
16. Agent → 通知用户: "审批已通过"
```

### 4.4 Task 状态与 Bisheng Workflow 的映射

| Airway Task 状态 | Bisheng Workflow 状态 | 触发事件 | Agent 感知 |
|------------------|----------------------|---------|-----------|
| `working` | `WAITING` → `RUNNING` | `node_run` | workflow_status 可查询 |
| `working` | `RUNNING` | `stream_msg` / `guide_word` / `guide_question` | 进度更新 |
| `input_required` | `INPUT` | `input` / `output_with_input_msg` / `output_with_choose_msg` | Webhook 即时通知 + 可 Polling |
| `working` | `INPUT_OVER` | — | 用户提交输入后自动恢复 |
| `completed` | `SUCCESS` | `close` | Webhook 通知 + 可 Polling |
| `failed` | `FAILED` | `error` → `close` | Webhook 通知 + 可 Polling |
| `cancelled` | — | — | Agent 主动取消 |

## 5. Airway 设计

### 5.1 目录结构

```
airway/
├── pyproject.toml
├── server.py                    # MCP Server 入口（FastMCP，未来可切换为 MCP Task）
├── task_sync.py                 # 任务同步服务（状态同步 + 终态固化）
├── task_repo.py                 # 任务数据访问（PG CRUD + 乐观锁）
├── task_recovery.py             # 任务恢复服务（重启恢复 + 轮询补偿）
├── task_health.py               # 任务健康检查（定期扫描过期任务，兜底静默失败）
├── event_bridge.py              # 事件桥接（写 outbox，不直接发 HTTP）
├── outbox_worker.py             # Outbox 投递 Worker（后台轮询 + 重试）
├── event_store.py               # 事件/审计记录（操作历史，非状态源）
├── identity.py                  # Identity Gateway（external_user → runtime_user 映射）
├── registry.py                  # Runtime Registry（capability + preference 路由）
├── tracing.py                   # Trace ID 传播（ContextVar，全链路串联）
├── config.py                    # 配置管理（YAML + 环境变量）
│
├── db/                          # 数据库（SQLModel + Alembic）
│   ├── models.py                # SQLModel 模型定义
│   ├── database.py              # 连接管理
│   └── migrations/              # Alembic 迁移
│
├── interface/                   # 统一的 RAG Runtime 接口
│   └── rag_runtime.py           # ABC: query / upload / workflow_* / capabilities
│
├── adapters/                    # 每个后端一个 Adapter
│   ├── bisheng/
│   │   ├── adapter.py           # BishengAdapter
│   │   ├── client.py            # v1/v2 API 客户端
│   │   ├── auth.py              # default_operator + JWT
│   │   └── sse_consumer.py      # SSE 流消费 → 缓存状态 + 事件桥接
│   ├── dify/
│   │   └── adapter.py           # DifyAdapter（未来）
│   └── ragflow/
│       └── adapter.py           # RagFlowAdapter（未来）
│
└── skills/                      # Clawith Skill 文件（可选补充）
    └── rag_query.md
```

### 5.2 MCP Tools 定义（对外接口，Clawith 当前可消费）

```python
# server.py — 普通 MCP Tools
# 所有 Tool 接受 user_id / tenant_id 参数，用于审计追踪

@tool
async def rag_query(query: str, knowledge_base: str | None = None,
                    top_k: int = 5,
                    user_id: str = "", tenant_id: str = "") -> str:
    """RAG 问答：检索 + LLM 生成（同步）"""

@tool
async def rag_upload(file_path: str, knowledge_base: str,
                     user_id: str = "", tenant_id: str = "") -> str:
    """上传文档到知识库（同步）"""

@tool
async def rag_kb_list(user_id: str = "", tenant_id: str = "") -> list[dict]:
    """列出可用知识库（同步）"""

@tool
async def rag_kb_info(knowledge_base: str,
                      user_id: str = "", tenant_id: str = "") -> dict:
    """查看知识库详情（同步）"""

@tool
async def rag_doc_list(knowledge_base: str,
                       user_id: str = "", tenant_id: str = "") -> list[dict]:
    """列出知识库中的文档（同步）"""

@tool
async def workflow_start(workflow_id: str, inputs: dict,
                         user_id: str = "", tenant_id: str = "") -> dict:
    """启动异步 Workflow。
    workflow_id 是 Bisheng Workflow 模板 UUID。
    返回 task_id（运行实例 ID），状态变化通过 Clawith Webhook 异步通知。
    可随时通过 workflow_status 查询当前状态。"""

@tool
async def workflow_status(task_id: str,
                          user_id: str = "", tenant_id: str = "") -> dict:
    """查询 Workflow 运行实例状态。
    缓存优先：缓存新鲜（<30s）直接返回，过期则从 Runtime 刷新。
    已终态的任务直接返回固化结果（Runtime 已清理）。"""

@tool
async def workflow_continue(task_id: str, inputs: dict,
                            message_id: str,
                            user_id: str = "", tenant_id: str = "") -> dict:
    """提交人工输入，恢复 Workflow 运行实例。
    幂等保护：通过 claim_input 原子清除 pending_input，重复调用返回 INPUT_ALREADY_CLAIMED。
    task_id 来自 workflow_start 返回值或 workflow_input 通知。
    message_id 来自 workflow_input 通知或 workflow_status 返回的 pending_input.message_id。
    inputs 的 key 对应 input_schema.value[].key。"""
    # 1. 获取 TaskRecord，校验 inputs key 与 pending_input.input_schema 一致
    record = await sync_service.repo.get(task_id)
    if record and record.pending_input:
        schema = record.pending_input.get("input_schema", {})
        expected_keys = {v["key"] for v in schema.get("value", []) if "key" in v}
        actual_keys = set(inputs.keys())
        if expected_keys and actual_keys != expected_keys:
            missing = expected_keys - actual_keys
            extra = actual_keys - expected_keys
            raise AirwayError(
                error_code="INPUT_SCHEMA_MISMATCH",
                message=f"Input keys mismatch. missing={missing}, extra={extra}. "
                        f"Workflow template may have been modified during execution.")
    # 2. 原子认领 input（清除 pending_input + 写入 input_submitted_at，同一条 UPDATE）
    await sync_service.claim_input(task_id, message_id)
    # 3. 从 pending_input 获取 node_id（SSE input 事件中携带，用于构造嵌套 input）
    node_id = record.pending_input.get("node_id") if record and record.pending_input else None
    if not node_id:
        raise AirwayError(error_code="MISSING_NODE_ID",
                          message="node_id not found in pending_input, cannot construct nested input")
    # 4. 调用 Bisheng invoke（不自动重试，§5.3d）
    return await adapter.continue_workflow(task_id, inputs, message_id, node_id)

@tool
async def workflow_cancel(task_id: str,
                          user_id: str = "", tenant_id: str = "") -> dict:
    """取消 Workflow 运行实例"""
```

### 5.3 Task 模块拆分（Runtime SSOT，PG 缓存 + 终态固化）

Airway 不管理任务状态，只从 Runtime 同步和缓存。SSOT 是 Runtime（Bisheng Redis），PG 是缓存层 + 终态归档。

TaskSyncManager 拆分为五个独立模块，各司其职：

```
┌─────────────────────────────────────────────────────┐
│                  TaskSyncService                     │
│   状态同步 + 终态固化 + 有序性校验 + 乐观锁         │
│   不直接依赖 DB，通过 TaskRepo 访问数据              │
├─────────────────────────────────────────────────────┤
│                  TaskRepository                      │
│   PG CRUD + 乐观锁更新 + pending_input 管理         │
│   纯数据访问层，不含业务逻辑                         │
├─────────────────────────────────────────────────────┤
│                  TaskRecoveryService                 │
│   重启恢复 + 轮询补偿 + 分布式锁                     │
│   Airway 启动时调用，恢复未 finalize 的 Task          │
├─────────────────────────────────────────────────────┤
│                  TaskHealthChecker（§5.3c）           │
│   定期扫描过期任务 + 主动同步 Runtime 状态            │
│   独立于 SSE 断连异常处理，兜底静默失败               │
├─────────────────────────────────────────────────────┤
│                  EventBridge（通知）                  │
│   写 outbox（5.4），不直接发 HTTP                     │
│   由 TaskSyncService 在状态变化时调用                 │
└─────────────────────────────────────────────────────┘
```

```python
# === task_sync.py — TaskRecord + TaskSyncService ===

@dataclass
class TaskRecord:
    task_id: str
    runtime: str
    runtime_task_id: str
    workflow_id: str
    state_version: int
    last_sync_at: datetime | None
    cached_state: dict | None
    final_state: dict | None
    pending_input: dict | None
    trace_id: str | None
    created_by: str | None
    tenant_id: str | None
    created_at: datetime
    finalized_at: datetime | None   # 终态固化时间，区分 Runtime 终态与 Airway 固化
    input_schema_hash: str | None   # 首次 input_schema 的 SHA256 摘要，检测模板变更
    input_submitted_at: datetime | None  # claim_input 成功时间，防止 Bisheng 侧重复提交

    def is_cache_fresh(self, ttl_seconds: int = 30) -> bool:
        if not self.last_sync_at or not self.cached_state:
            return False
        return datetime.utcnow() - self.last_sync_at < timedelta(seconds=ttl_seconds)


class TaskSyncService:
    """状态同步 + 终态固化——不含数据访问和恢复逻辑
    状态有序性校验委托给 Adapter（adapter.state_order），不在 Service 层硬编码。
    原因：不同 Runtime 的状态机不同（Bisheng vs Dify vs RagFlow），
    硬编码会导致新增 Runtime 时需改 Service 层代码，违反开闭原则。"""

    def __init__(self, repo: TaskRepository, bridge: EventBridge,
                 events: EventStore):
        self.repo = repo
        self.bridge = bridge
        self.events = events

    async def create(self, task_id: str, runtime_task_id: str,
                     workflow_id: str, runtime: str,
                     user_id: str | None = None,
                     tenant_id: str | None = None) -> TaskRecord:
        record = TaskRecord(
            task_id=task_id, runtime=runtime,
            runtime_task_id=runtime_task_id, workflow_id=workflow_id,
            state_version=0, last_sync_at=None, cached_state=None,
            final_state=None, pending_input=None,
            trace_id=get_trace_id(), created_by=user_id,
            tenant_id=tenant_id, created_at=datetime.utcnow(),
        )
        await self.repo.insert(record)
        await self.events.record(record, "task_created")
        return record

    def _is_regression(self, current_status: str, new_status: str,
                       state_order: dict[str, int]) -> bool:
        return (state_order.get(new_status, 0)
                < state_order.get(current_status, 0))

    async def sync_from_runtime(self, task_id: str, adapter) -> dict:
        """从 Runtime 查询最新状态，在单一 PG 事务内完成所有写入。
        保证 update_cached + update_pending_input + outbox 原子性：
        要么全部成功，要么全部回滚。不存在"状态已更新但通知未发出"的中间态。"""
        record = await self.repo.get(task_id)
        if record.final_state:
            return record.final_state

        runtime_state = await adapter.get_runtime_status(record.runtime_task_id)
        new_status = runtime_state.get("status")

        current_status = (record.cached_state or {}).get("status")
        if current_status and self._is_regression(
                current_status, new_status, adapter.state_order):
            return record.cached_state

        # --- 单一事务：状态更新 + pending_input + outbox ---
        async with self.repo.transaction():
            updated = await self.repo.update_cached(
                task_id, record.state_version, runtime_state)
            if not updated:
                return (await self.repo.get(task_id)).cached_state

            record.state_version += 1
            record.cached_state = runtime_state

            if new_status == "INPUT":
                new_msg_id = runtime_state.get("message_id")
                old_msg_id = (record.pending_input or {}).get("message_id")
                pending = {
                    "message_id": new_msg_id,
                    "input_schema": runtime_state.get("input_schema"),
                    "requested_at": datetime.utcnow().isoformat(),
                }
                await self.repo.update_pending_input(task_id, pending)
                record.pending_input = pending
                if not record.input_schema_hash and runtime_state.get("input_schema"):
                    schema_hash = hashlib.sha256(
                        json.dumps(runtime_state["input_schema"], sort_keys=True).encode()
                    ).hexdigest()[:16]
                    await self.repo.update_input_schema_hash(task_id, schema_hash)
                    record.input_schema_hash = schema_hash
                if new_msg_id != old_msg_id:
                    await self.bridge.notify_clawith(record, runtime_state)

            elif new_status in ("SUCCESS", "FAILED"):
                await self.repo.update_pending_input(task_id, None)
                await self.repo.finalize(task_id, record.state_version, runtime_state)
                record.finalized_at = datetime.utcnow()
                await self.bridge.notify_clawith(record, runtime_state)

        # 事务提交成功后，异步记录审计事件（不参与事务，丢失不影响一致性）
        await self.events.record(record, "state_synced",
                                 metadata={"runtime_state": runtime_state})
        if new_status in ("SUCCESS", "FAILED"):
            await self.events.record(record, "task_finalized",
                                     metadata={"final_status": new_status})

        return runtime_state

    async def finalize(self, task_id: str, final_state: dict):
        """SSE close/error 事件直接触发终态固化。
        在事务内完成 finalize + outbox 写入，保证原子性。"""
        record = await self.repo.get(task_id)
        async with self.repo.transaction():
            updated = await self.repo.finalize(task_id, record.state_version,
                                                final_state)
            if not updated:
                return
            record.finalized_at = datetime.utcnow()
            await self.repo.update_pending_input(task_id, None)
            await self.bridge.notify_clawith(record, final_state)
        # 审计事件在事务外记录，丢失不影响一致性
        await self.events.record(record, "task_finalized",
                                 metadata={"final_status": final_state.get("status")})

    async def claim_input(self, task_id: str, message_id: str) -> TaskRecord:
        """原子认领 input，防止重复 workflow_continue。
        通过乐观锁 + pending_input 上的 message_id 匹配，保证同一 input 只被认领一次。
        成功后 pending_input 被清除，后续重复调用会在 repo 层因版本冲突失败。
        注意：inputs schema 校验在 server.py workflow_continue tool 中执行（claim_input 无 inputs 参数）。"""
        record = await self.repo.get(task_id)
        if not record:
            raise AirwayError(error_code="NOT_FOUND", message=f"Task {task_id} not found")
        if record.final_state:
            raise AirwayError(error_code="TASK_ALREADY_FINISHED",
                              message=f"Task {task_id} is {record.final_state.get('status')}")
        if not record.pending_input:
            raise AirwayError(error_code="INPUT_ALREADY_CLAIMED",
                              message=f"Task {task_id} has no pending input")
        if record.pending_input.get("message_id") != message_id:
            raise AirwayError(error_code="MESSAGE_ID_MISMATCH",
                              message=f"message_id {message_id} does not match pending input")
        # compare_and_clear_pending 原子清除 pending_input 并写入 input_submitted_at（同一条 UPDATE）
        claimed = await self.repo.compare_and_clear_pending(
            task_id, record.state_version, message_id)
        if not claimed:
            raise AirwayError(error_code="INPUT_ALREADY_CLAIMED",
                              message="Concurrent claim won, input already submitted")
        await self.events.record(record, "input_claimed",
                                 metadata={"message_id": message_id})
        record.pending_input = None
        record.state_version += 1
        return record

    async def get_status(self, task_id: str, adapter) -> dict:
        record = await self.repo.get(task_id)
        if not record:
            return {"status": "not_found"}
        if record.final_state:
            return record.final_state
        if record.is_cache_fresh(ttl_seconds=30):
            result = dict(record.cached_state)
        else:
            result = await self.sync_from_runtime(task_id, adapter)
        if record.pending_input:
            result["pending_input"] = record.pending_input
        return result
```

```python
# === task_repo.py — TaskRepository（纯数据访问）===

class TaskRepository:
    """PG CRUD + 乐观锁——不含业务逻辑"""

    def __init__(self, db: Database):
        self.db = db

    @asynccontextmanager
    async def transaction(self):
        """获取 PG 事务上下文。sync_from_runtime 在事务内完成所有写入，
        保证 update_cached + update_pending_input + outbox 原子性。"""
        async with self.db.session() as session:
            async with session.begin():
                yield session

    async def insert(self, record: TaskRecord) -> None: ...
    async def get(self, task_id: str) -> TaskRecord | None: ...
    async def query_active(self) -> list[TaskRecord]:
        """查询所有未 finalize 的 Task（恢复用）。
        finalized_at IS NULL 标识 Airway 未完成固化的任务，
        包括：仍在运行 / Runtime 已终态但 finalize 失败 / 刚创建"""
        ...

    async def update_cached(self, task_id: str, expected_version: int,
                             cached_state: dict) -> bool:
        """乐观锁更新 cached_state，返回是否成功"""
        # UPDATE tasks SET cached_state=?, state_version=state_version+1, ...
        # WHERE task_id=? AND state_version=? RETURNING 1

    async def update_pending_input(self, task_id: str,
                                    pending: dict | None) -> None: ...

    async def update_input_schema_hash(self, task_id: str,
                                        schema_hash: str) -> None:
        """记录首次 input_schema 的 SHA256 摘要"""
        # UPDATE tasks SET input_schema_hash=? WHERE task_id=? AND input_schema_hash IS NULL

    async def compare_and_clear_pending(self, task_id: str,
                                         expected_version: int,
                                         message_id: str) -> bool:
        """乐观锁原子清除 pending_input + 写入 input_submitted_at（幂等认领）。
        同时验证 message_id 防止认领错误的 input 轮次。
        input_submitted_at 与 pending_input 清除在同一条 UPDATE 中，保证原子性。"""
        # UPDATE tasks
        # SET pending_input = NULL, input_submitted_at = NOW(),
        #     state_version = state_version + 1, last_sync_at = NOW()
        # WHERE task_id = ? AND state_version = ?
        #   AND pending_input->>'message_id' = ?
        #   AND final_state IS NULL
        # RETURNING 1

    async def finalize(self, task_id: str, expected_version: int,
                        final_state: dict) -> bool:
        """乐观锁终态固化，同时设置 finalized_at"""
        # UPDATE tasks SET final_state=?, cached_state=?, state_version=state_version+1,
        #                  finalized_at=NOW()
        # WHERE task_id=? AND state_version=? AND final_state IS NULL RETURNING 1

    async def touch_last_sync(self, task_id: str) -> None:
        """轻量更新 last_sync_at（进度事件用），供 _sse_probe 判断连接健康。
        不更新 state_version，不触发乐观锁冲突。"""
        # UPDATE tasks SET last_sync_at = NOW() WHERE task_id = ? AND final_state IS NULL
```

```python
# === task_recovery.py — TaskRecoveryService ===

class TaskRecoveryService:
    """Airway 重启恢复 + 轮询补偿 + 分布式锁"""

    def __init__(self, repo: TaskRepository, sync: TaskSyncService):
        self.repo = repo
        self.sync = sync

    async def recover_active(self, adapter) -> list[TaskRecord]:
        """启动时恢复未 finalize 的 Task"""
        active = await self.repo.query_active()
        for record in active:
            try:
                locked = await acquire_task_lock(record.task_id)
                if not locked:
                    continue  # 其他实例已接管
                runtime_state = await self.sync.sync_from_runtime(
                    record.task_id, adapter)
                if runtime_state.get("status") == "RUNNING":
                    asyncio.create_task(
                        self._poll_until_change(adapter, record.task_id))
            except Exception:
                log.error("recovery_failed", task_id=record.task_id)
        return active

    async def _poll_until_change(self, adapter, task_id: str,
                                  interval: int = 30):
        """轮询 Runtime 状态直到变化"""
        while True:
            await asyncio.sleep(interval)
            record = await self.repo.get(task_id)
            if record.final_state:
                await release_task_lock(task_id)
                return
            if not await renew_task_lock(task_id):
                return  # 锁丢失，其他实例接管
            state = await self.sync.sync_from_runtime(task_id, adapter)
            if state.get("status") in ("INPUT", "SUCCESS", "FAILED"):
                await release_task_lock(task_id)
                return
```

### 5.3a 并发控制（Redis 分布式锁）

多 Airway 实例同时 sync 同一 task 时，通过 Redis 锁保证只有一个实例拥有 SSE 消费权。

```python
# task_sync.py — 锁相关方法

INSTANCE_ID = uuid4().hex[:8]  # 每个 Airway 实例的唯一标识

async def acquire_task_lock(task_id: str, ttl: int = 60) -> bool:
    """尝试获取 task 的 SSE 消费权"""
    return await redis.set(
        f"airway:task_lock:{task_id}", INSTANCE_ID,
        nx=True, ex=ttl
    )

async def renew_task_lock(task_id: str, ttl: int = 60):
    """续期锁（只有持有者能续，Lua 脚本保证原子性）"""
    await redis.eval(
        "if redis.call('get',KEYS[1])==ARGV[1] "
        "then return redis.call('expire',KEYS[1],ARGV[2]) else return 0 end",
        1, f"airway:task_lock:{task_id}", INSTANCE_ID, str(ttl)
    )

async def release_task_lock(task_id: str):
    """主动释放锁（Task 终态时）"""
    await redis.eval(
        "if redis.call('get',KEYS[1])==ARGV[1] "
        "then return redis.call('del',KEYS[1]) else return 0 end",
        1, f"airway:task_lock:{task_id}", INSTANCE_ID
    )
```

**锁语义**：
- `acquire_task_lock`：start_workflow 时获取，NX + EX 保证互斥和自动过期
- `renew_task_lock`：SSE 消费循环每次迭代续期，锁丢失时主动放弃 SSE
- `release_task_lock`：Task 终态时主动释放，允许其他实例立即接管
- 锁 TTL 60s，SSE 消费循环每 30s 续期一次，留足容错

### 5.3b SSE 连接资源管理

高并发时活跃 SSE 连接可能耗尽文件描述符。通过信号量控制上限，达到上限时拒绝新请求。

```python
# sse_pool.py

class SSEConnectionPool:
    def __init__(self, max_connections: int = 100, max_ttl: int = 86400):
        self.semaphore = asyncio.Semaphore(max_connections)
        self.active: dict[str, asyncio.Task] = {}
        self.max_ttl = max_ttl  # 单连接最大存活秒数（默认 24h，匹配 Bisheng Workflow 上限）

    async def consume(self, task_id: str, stream, handler):
        """获取槽位后启动 SSE 消费，结束时自动释放。
        max_ttl 防止异常场景下连接永不释放（Bisheng 24h 上限兜底）。"""
        if task_id in self.active:
            raise AirwayError(error_code="TASK_ALREADY_CONSUMING",
                              message=f"Task {task_id} already has active SSE consumer")
        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=0.1)
        except asyncio.TimeoutError:
            raise AirwayError(error_code="SSE_POOL_FULL",
                              message="SSE connection pool exhausted, retry later")
        try:
            task = asyncio.create_task(handler(task_id, stream))
            self.active[task_id] = task
            await asyncio.wait_for(task, timeout=self.max_ttl)
        except asyncio.TimeoutError:
            # TTL 超限，强制取消僵尸连接
            task.cancel()
            log.warning("sse_ttl_expired", task_id=task_id, ttl=self.max_ttl)
        finally:
            self.active.pop(task_id, None)
            self.semaphore.release()

    @property
    def utilization(self) -> float:
        return len(self.active) / self.semaphore._value if self.semaphore._value else 1.0
```

**配置**：

```yaml
# config.yaml
sse_pool:
  max_connections: 100  # 根据 ulimit -n 和内存调整
  max_ttl: 86400        # 单连接最大存活秒数（24h，匹配 Bisheng Workflow 上限）
  idle_timeout: 300     # 空闲超时秒数（无事件/ping 视为假死）
```

**背压策略**：连接池满时 `workflow_start` 返回错误码 `SSE_POOL_FULL`，Agent 可重试。Airway 健康检查暴露 `sse_pool.utilization` 指标。

### 5.3c 任务健康检查（独立于 SSE 断连处理的兜底）

SSE 断连补偿依赖 `_consume_sse` 的异常处理链正确执行，任何未捕获的异常都会导致状态停滞。TaskHealthChecker 作为独立兜底机制，不依赖 SSE 异常处理。

```python
# task_health.py

class TaskHealthChecker:
    """定期扫描过期任务，主动从 Runtime 同步状态。
    独立于 SSE 断连的异常处理路径，覆盖静默失败场景。"""

    def __init__(self, repo: TaskRepository, sync: TaskSyncService,
                 adapter, interval: int = 60, stale_seconds: int = 60):
        self.repo = repo
        self.sync = sync
        self.adapter = adapter
        self.interval = interval
        self.stale_seconds = stale_seconds

    async def run(self):
        """主循环：Airway 启动时作为后台任务运行"""
        while True:
            await asyncio.sleep(self.interval)
            try:
                stale = await self.repo.query_stale(self.stale_seconds)
                for record in stale:
                    try:
                        await self.sync.sync_from_runtime(
                            record.task_id, self.adapter)
                        log.info("health_sync_ok",
                                 task_id=record.task_id)
                    except Exception:
                        log.error("health_sync_failed",
                                  task_id=record.task_id)
            except Exception:
                log.error("health_check_loop_error")
```

```python
# task_repo.py — 新增方法

async def query_stale(self, stale_seconds: int) -> list[TaskRecord]:
    """查询未固化且 last_sync_at 过期的 Task。
    覆盖场景：SSE 断连异常未被捕获、Airway GC 停顿导致心跳丢失、
    网络分区导致 SSE 静默断开但 _consume_sse 未感知。"""
    # SELECT * FROM tasks
    # WHERE finalized_at IS NULL
    #   AND (last_sync_at IS NULL
    #        OR last_sync_at < NOW() - INTERVAL '? seconds')
    # ORDER BY last_sync_at ASC NULLS FIRST
    # LIMIT 50
```

**设计要点**：
- 独立于 SSE 消费路径，不依赖 `_consume_sse` 的 except 块
- 只扫描未固化任务，终态任务不参与
- `stale_seconds` 默认 60s，大于 SSE 心跳间隔（30s），避免与正常消费竞争
- 每次 sync 内部有乐观锁保护，不会与 SSE 消费的正常同步冲突

**配置**：

```yaml
# config.yaml
health_check:
  interval: 60         # 扫描间隔秒数
  stale_seconds: 60    # last_sync_at 过期阈值
```

### 5.3d Bisheng invoke 幂等防护

`claim_input` 保证了 Airway 侧幂等，但 Bisheng `POST /api/v2/workflow/invoke` 在 INPUT 状态下的幂等性未确认。防护策略：

**Phase 1 验证项**：向 INPUT 状态的 Workflow 发送相同 `message_id` 的 invoke 两次，观察 Bisheng 行为（重复处理 / 忽略 / 报错）。

**防护机制**（不依赖 Bisheng 行为假设）：
1. `claim_input` 通过 `compare_and_clear_pending` 原子清除 `pending_input` 并写入 `input_submitted_at`（同一条 UPDATE，保证原子性）
2. `continue_workflow` 调用 Bisheng invoke 时，**不实现自动重试**
3. 如果 Bisheng 调用失败（网络错误 / 超时），`pending_input` 已被清除、`input_submitted_at` 已记录，Agent 查询 `workflow_status` 可看到 `input_submitted_at` 存在但无新 SSE 流，自行决定是否人工干预
4. 避免了"Airway 重试 → Bisheng 收到两次输入"的风险

### 5.4 事件桥接 + Outbox Pattern（通知可靠性保证）

状态变更和通知写入同一个 PG 事务，由独立 OutboxWorker 可靠投递。解决"PG 写成功但 Webhook 推送失败"的静默失败问题。

```python
# event_bridge.py

class EventBridge:
    """Runtime 事件 → Outbox 记录（不直接发 HTTP）"""

    def __init__(self, db: Database):
        self.db = db

    async def notify_clawith(self, record: TaskRecord, runtime_state: dict):
        """构造 payload 并写入 outbox 表（与状态更新同一事务）"""
        status = runtime_state.get("status", "unknown").lower()
        payload = {
            "type": f"workflow_{status}",
            "task_id": record.task_id,
            "workflow_id": record.workflow_id,
            "runtime_status": runtime_state.get("status"),
            "created_by": record.created_by,
            "tenant_id": record.tenant_id,
            "trace_id": get_trace_id(),
        }
        if runtime_state.get("input_schema"):
            payload["input_schema"] = runtime_state["input_schema"]
        if runtime_state.get("result"):
            payload["result"] = runtime_state["result"]
        if runtime_state.get("error"):
            payload["error"] = runtime_state["error"]

        await self.db.insert_outbox(
            task_id=record.task_id,
            event_type=f"workflow_{status}",
            payload=payload,
        )
```

### 5.4a OutboxWorker（后台投递 + 重试）

```python
# outbox_worker.py

class OutboxWorker:
    """从 outbox 表读取待发送记录，可靠投递 Webhook"""

    def __init__(self, db: Database, webhook_url: str, webhook_token: str,
                 webhook_secret: str | None = None,
                 poll_interval: float = 1.0, max_retries: int = 5,
                 dead_replay_interval: float = 300.0):
        self.db = db
        self.webhook_url = f"{webhook_url}/t/{webhook_token}"
        self.webhook_secret = webhook_secret
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self.dead_replay_interval = dead_replay_interval

    def _sign_payload(self, body: bytes) -> str | None:
        if not self.webhook_secret:
            return None
        sig = hmac.new(self.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        return f"sha256={sig}"

    async def run(self):
        """主循环：Airway 启动时作为后台任务运行"""
        while True:
            records = await self.db.query_outbox(
                status="pending",
                limit=50,
                skip_locked=True,  # 多实例时避免重复消费
            )
            for rec in records:
                try:
                    body = json.dumps(rec.payload).encode()
                    headers = {"Content-Type": "application/json"}
                    sig = self._sign_payload(body)
                    if sig:
                        headers["x-hub-signature-256"] = sig

                    async with httpx.AsyncClient(timeout=10) as client:
                        resp = await client.post(self.webhook_url, content=body, headers=headers)
                        resp.raise_for_status()

                    await self.db.update_outbox(rec.id, status="sent")
                except Exception:
                    new_retry = rec.retry_count + 1
                    if new_retry >= self.max_retries:
                        await self.db.update_outbox(rec.id, status="dead")
                        log.error("outbox_dead", task_id=rec.task_id, retries=new_retry)
                    else:
                        await self.db.update_outbox(rec.id, retry_count=new_retry)
                        log.warning("outbox_retry", task_id=rec.task_id, retry=new_retry)

            await asyncio.sleep(self.poll_interval)

    async def _replay_dead(self):
        """低优先级循环：定期重试 dead 记录。
        Webhook 端点恢复后，dead 消息可被重新投递。
        重试成功重置为 sent，失败保持 dead 等待下一轮。"""
        while True:
            await asyncio.sleep(self.dead_replay_interval)
            dead_records = await self.db.query_outbox(
                status="dead",
                limit=20,
                skip_locked=True,
            )
            for rec in dead_records:
                # 只重放未过终态补偿窗口的记录（任务仍活跃）
                task = await self.db.get_task(rec.task_id)
                if task and task.final_state is None:
                    try:
                        body = json.dumps(rec.payload).encode()
                        headers = {"Content-Type": "application/json"}
                        sig = self._sign_payload(body)
                        if sig:
                            headers["x-hub-signature-256"] = sig
                        async with httpx.AsyncClient(timeout=10) as client:
                            resp = await client.post(self.webhook_url, content=body,
                                                     headers=headers)
                            resp.raise_for_status()
                        await self.db.update_outbox(rec.id, status="sent")
                        log.info("outbox_dead_replayed", task_id=rec.task_id)
                    except Exception:
                        log.warning("outbox_dead_replay_failed", task_id=rec.task_id)
                else:
                    # 任务已终态，标记 dead 为 expired 避免反复重试
                    await self.db.update_outbox(rec.id, status="expired")
                    log.info("outbox_dead_expired", task_id=rec.task_id)
```

**可靠性保证**：

| 场景 | 行为 |
|------|------|
| Webhook 推送成功 | outbox 标记 `sent` |
| 网络抖动 | 指数退避重试（最多 5 次），保留 `pending` |
| Airway 崩溃 | 重启后 OutboxWorker 从 PG 重新读取 `pending` 记录 |
| 重试耗尽 | 标记 `dead`，告警；`_replay_dead` 每 5 分钟重试（仅活跃任务）；Agent Polling 兜底 |
| dead 重放成功 | 重置为 `sent`，Agent 收到延迟通知 |
| dead 对应任务已终态 | 标记 `expired`，不再重试 |
| 多实例并发 | `SELECT ... FOR UPDATE SKIP LOCKED` 无锁轮询 |
| 重复投递 | Clawith 30s 幂等窗口兜底 |

**Clawith Webhook Payload 说明**：

Clawith 对 webhook payload **无固定格式要求**，任意 JSON 都接受。自定义字段直接合并到 Agent trigger config 中，Agent 可直接读取 `task_id`、`input_schema`、`created_by` 等字段。安全机制：Token 路径 + 可选 HMAC 签名 + 速率限制（默认 5 req/min/agent）+ 幂等去重（30s 窗口）。

### 5.5 Identity Gateway（统一认证映射）

将外部用户身份映射到 Runtime 用户身份。当前阶段所有用户映射到 default_operator，未来按需扩展。

```python
# identity.py

@dataclass
class RuntimeIdentity:
    runtime_user_id: str   # Runtime 侧用户标识
    tenant_id: str | None

class IdentityGateway:
    """external_user_id → runtime_user_id 映射"""

    def __init__(self, db: Database, default_runtime_user: dict[str, str]):
        self.db = db
        self.defaults = default_runtime_user  # {"bisheng": "default_operator_uid"}

    async def resolve(self, external_user_id: str | None,
                      runtime: str) -> RuntimeIdentity:
        if external_user_id:
            mapping = await self.db.get_identity_mapping(external_user_id, runtime)
            if mapping:
                return RuntimeIdentity(
                    runtime_user_id=mapping.runtime_user_id,
                    tenant_id=mapping.tenant_id,
                )
        # fallback: 使用该 runtime 的默认身份
        return RuntimeIdentity(
            runtime_user_id=self.defaults.get(runtime, "unknown"),
            tenant_id=None,
        )
```

### 5.6 Event Store + Audit Log（统一事件记录）

一张 `events` 表，两种查询视角：系统排障按 task_id 查时间线，合规审计按 actor_id 查操作历史。

```python
# event_store.py

@dataclass
class Event:
    event_id: str
    task_id: str
    event_type: str          # task_created / state_synced / task_finalized / user_action
    actor_type: str          # system / user / agent
    actor_id: str            # user_id 或 "airway-system"
    action: str              # create / sync / query / upload / continue
    trace_id: str | None     # 全链路追踪 ID
    tenant_id: str | None
    metadata: dict | None    # runtime_state 快照等
    created_at: datetime

class EventStore:
    def __init__(self, db: Database):
        self.db = db

    async def record(self, record: TaskRecord, event_type: str, **kwargs):
        event = Event(
            event_id=uuid4().hex,
            task_id=record.task_id,
            event_type=event_type,
            actor_type=kwargs.get("actor_type", "system"),
            actor_id=kwargs.get("actor_id", "airway-system"),
            action=kwargs.get("action", event_type),
            trace_id=record.trace_id,
            tenant_id=record.tenant_id,
            metadata=kwargs.get("metadata"),
            created_at=datetime.utcnow(),
        )
        await self.db.insert_event(event)

    async def get_task_timeline(self, task_id: str) -> list[Event]:
        """按 task_id 查完整时间线（系统排障用）"""
        return await self.db.query_events(task_id=task_id, order_by="created_at")

    async def get_user_audit(self, actor_id: str, tenant_id: str | None = None,
                             action: str | None = None,
                             date_start: datetime | None = None,
                             date_end: datetime | None = None) -> list[Event]:
        """按 actor_id 查操作历史（合规审计用）"""
        return await self.db.query_events(
            actor_id=actor_id, tenant_id=tenant_id,
            action=action, date_start=date_start, date_end=date_end,
            order_by="created_at"
        )
```

### 5.7 数据库 Schema

```sql
-- tasks 表（同步记录，不是状态机）
CREATE TABLE tasks (
    task_id          VARCHAR(64) PRIMARY KEY,
    runtime          VARCHAR(32) NOT NULL DEFAULT 'bisheng',
    runtime_task_id  VARCHAR(64) NOT NULL,
    workflow_id      VARCHAR(64) NOT NULL,
    state_version    INTEGER NOT NULL DEFAULT 0,  -- 乐观锁版本号，每次 sync 递增
    last_sync_at     TIMESTAMPTZ,
    cached_state     JSONB,         -- Runtime 状态快照（缓存，非 SSOT）
    final_state      JSONB,         -- 终态快照（Runtime 清理后 PG 成为 SSOT）
    pending_input    JSONB,         -- INPUT 状态完整输入请求：{message_id, input_schema, requested_at}
    trace_id         VARCHAR(32),   -- 全链路追踪 ID
    created_by       VARCHAR(64),
    tenant_id        VARCHAR(64),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finalized_at     TIMESTAMPTZ,        -- 终态固化时间，NULL 表示未固化（Runtime 可能已终态但 Airway 未写入）
    input_schema_hash VARCHAR(32),       -- 首次 input_schema SHA256 摘要前 16 字符，检测模板热更
    input_submitted_at TIMESTAMPTZ       -- claim_input 成功时间，防止 Bisheng 侧重复提交
);

CREATE INDEX idx_tasks_final_state ON tasks(final_state) WHERE final_state IS NULL;
CREATE INDEX idx_tasks_unfinalized ON tasks(finalized_at) WHERE finalized_at IS NULL AND final_state IS NULL;
CREATE INDEX idx_tasks_tenant ON tasks(tenant_id);
CREATE INDEX idx_tasks_runtime_task ON tasks(runtime, runtime_task_id);
CREATE INDEX idx_tasks_trace_id ON tasks(trace_id);

-- 乐观锁更新（防止并发写覆盖）
-- 用法: UPDATE tasks SET cached_state=?, state_version=state_version+1, ...
--       WHERE task_id=? AND state_version=?  RETURNING 1;
-- affected_rows = 0 表示版本冲突，跳过此次更新
```

-- events 表（统一 Event Store + Audit Log）
CREATE TABLE events (
    event_id      VARCHAR(64) PRIMARY KEY,
    task_id       VARCHAR(64) REFERENCES tasks(task_id),
    event_type    VARCHAR(32) NOT NULL,
    actor_type    VARCHAR(16) NOT NULL,
    actor_id      VARCHAR(64) NOT NULL,
    action        VARCHAR(32) NOT NULL,
    trace_id      VARCHAR(32),          -- 全链路追踪 ID
    tenant_id     VARCHAR(64),
    metadata      JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_task_id ON events(task_id);
CREATE INDEX idx_events_actor_id ON events(actor_id);
CREATE INDEX idx_events_trace_id ON events(trace_id);
CREATE INDEX idx_events_tenant_action ON events(tenant_id, action);
CREATE INDEX idx_events_created_at ON events(created_at);

-- identity_mappings 表（用户身份映射）
CREATE TABLE identity_mappings (
    external_user_id  VARCHAR(64) NOT NULL,
    runtime           VARCHAR(32) NOT NULL,
    runtime_user_id   VARCHAR(64) NOT NULL,
    tenant_id         VARCHAR(64),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (external_user_id, runtime)
);

-- outbox 表（通知可靠投递，Outbox Pattern）
CREATE TABLE outbox (
    id            BIGSERIAL PRIMARY KEY,
    task_id       VARCHAR(64) NOT NULL REFERENCES tasks(task_id),
    event_type    VARCHAR(32) NOT NULL,
    payload       JSONB NOT NULL,
    status        VARCHAR(16) NOT NULL DEFAULT 'pending',  -- pending / sent / dead / expired
    retry_count   SMALLINT NOT NULL DEFAULT 0,
    trace_id      VARCHAR(32),          -- 全链路追踪 ID
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at       TIMESTAMPTZ
);

CREATE INDEX idx_outbox_status ON outbox(status) WHERE status = 'pending';
CREATE INDEX idx_outbox_task_id ON outbox(task_id);
CREATE INDEX idx_outbox_trace_id ON outbox(trace_id);
```

### 5.8 RAG Runtime 接口

```python
# interface/rag_runtime.py

class RuntimeCapability(Enum):
    QUERY = "query"
    UPLOAD = "upload"
    WORKFLOW = "workflow"
    KNOWLEDGE_BASE = "knowledge_base"

class RAGRuntime(ABC):
    """所有 RAG 后端必须实现的统一接口"""

    @property
    @abstractmethod
    def capabilities(self) -> set[RuntimeCapability]:
        """声明该 Runtime 支持的能力集（为未来 Runtime Registry 预留）"""
        ...

    @property
    @abstractmethod
    def state_order(self) -> dict[str, int]:
        """声明该 Runtime 的状态优先级映射（值越大越接近终态）。
        用于 TaskSyncService 判断状态是否倒退。
        例：{"RUNNING": 1, "INPUT": 2, "SUCCESS": 3, "FAILED": 3}
        不同 Runtime 的状态机不同，由 Adapter 自行定义。"""
        ...

    @abstractmethod
    async def get_runtime_status(self, runtime_task_id: str) -> dict:
        """查询 Runtime 侧任务状态（SSOT 查询）。
        返回: { status, input_schema?, result?, error? }"""
        ...

    # 同步
    @abstractmethod
    async def query(self, query: str, knowledge_base: str | None = None,
                    top_k: int = 5) -> str: ...

    @abstractmethod
    async def upload(self, file_path: str, knowledge_base: str) -> str: ...

    @abstractmethod
    async def list_knowledge_bases(self) -> list[dict]: ...

    @abstractmethod
    async def list_documents(self, knowledge_base: str) -> list[dict]: ...

    # 异步 Workflow（返回 SSE 事件流，由 Airway 后台消费）
    @abstractmethod
    async def start_workflow(self, workflow_id: str,
                             inputs: dict) -> AsyncIterator: ...

    @abstractmethod
    async def continue_workflow(self, workflow_id: str,
                                inputs: dict, message_id: str) -> str: ...

    @abstractmethod
    async def get_workflow_status(self, workflow_id: str) -> dict: ...

    @abstractmethod
    async def cancel_workflow(self, workflow_id: str) -> None: ...
```

### 5.9 Runtime Registry（按 capability 路由）

即使当前只有一个 Bisheng，也尽早建立路由模式。未来新增 Runtime 只需 register。

```python
# registry.py

class RuntimeRegistry:
    def __init__(self):
        self.runtimes: dict[str, RAGRuntime] = {}

    def register(self, name: str, runtime: RAGRuntime):
        self.runtimes[name] = runtime

    def resolve(self, capability: RuntimeCapability,
                preference: str | None = None) -> RAGRuntime:
        if preference and preference in self.runtimes:
            rt = self.runtimes[preference]
            if capability in rt.capabilities:
                return rt
        for name, rt in self.runtimes.items():
            if capability in rt.capabilities:
                return rt
        raise AirwayError(
            error_code="NO_RUNTIME",
            message=f"No runtime with capability {capability.value}"
        )

    def get(self, name: str) -> RAGRuntime:
        return self.runtimes[name]
```

### 5.10 Trace ID 传播（全链路追踪）

三层 trace_id 串联，支持跨系统排障。

```python
# tracing.py

from contextvars import ContextVar

trace_id: ContextVar[str] = ContextVar("trace_id", default="")

def new_trace_id() -> str:
    tid = uuid4().hex[:16]
    trace_id.set(tid)
    return tid

def get_trace_id() -> str:
    tid = trace_id.get()
    if not tid:
        return new_trace_id()
    return tid
```

**传播路径**：

```
Clawith Agent
  → MCP Tool 调用（Airway 生成 trace_id）
    → Adapter 调用 Bisheng API（HTTP Header: X-Request-ID: {trace_id}）
      → Bisheng 内部 trace_id_var 关联
    → EventBridge Webhook（payload 中携带 trace_id）
      → Clawith Agent 上下文中可见 trace_id
    → Event Store 记录（metadata.trace_id）
      → 排障时按 trace_id 查询完整链路
```

**日志格式**（structlog）：

```json
{
    "timestamp": "2026-06-02T15:30:00Z",
    "level": "info",
    "event": "runtime_status_synced",
    "trace_id": "a1b2c3d4e5f6g7h8",
    "task_id": "abc123_async_task_id",
    "runtime": "bisheng",
    "runtime_status": "INPUT",
    "user_id": "user_456",
    "tenant_id": "tenant_789"
}
```

### 5.11 技术栈

| 组件 | 选型 | 用途 |
|------|------|------|
| **ORM** | SQLModel | Pydantic + SQLAlchemy 融合，TaskRecord/Event 直接是 model |
| **迁移** | Alembic | SQLModel 原生支持，自动生成迁移 |
| **MCP Server** | FastMCP（mcp-python-sdk） | Streamable HTTP，Tool 装饰器，未来可切换为 MCP Task |
| **HTTP** | httpx | async 原生，EventBridge + Adapter |
| **Logging** | structlog | 结构化 JSON，trace_id/task_id 自动注入 |
| **配置** | pydantic-settings | YAML + 环境变量 + 类型校验 |

**MCP Server 切换路径**：当前 server.py 用 FastMCP 暴露普通 Tool。未来 Clawith 支持 MCP Task（SEP-1686）后，只需替换 server.py 的传输层（Tool → Task），TaskSyncManager / Adapter / EventBridge 核心代码零改动。

**pyproject.toml 核心依赖**：

```toml
[project]
name = "airway"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=0.1",
    "sqlmodel>=0.0.22",
    "alembic>=1.13",
    "httpx>=0.27",
    "structlog>=24.0",
    "pydantic-settings>=2.0",
    "pyyaml>=6.0",
]
```

**配置示例**：

```yaml
# config.yaml
adapter: bisheng

server:
  host: "0.0.0.0"
  port: 8090

database:
  url: "postgresql://airway:${AIRWAY_DB_PASSWORD}@airway-db:5432/airway"

identity:
  defaults:
    bisheng: "${BISHENG_DEFAULT_OPERATOR_UID}"

clawith:
  webhook_url: "http://clawith-backend:8000/api/webhooks"
  webhook_token: "${CLAWITH_WEBHOOK_TOKEN}"
  webhook_secret: "${CLAWITH_WEBHOOK_SECRET}"

bisheng:
  v2_api_url: "http://bisheng-backend:7860/api/v2"
  v1_api_url: "http://bisheng-backend:7860/api/v1"
  admin_username: "${BISHENG_ADMIN_USER}"
  admin_password: "${BISHENG_ADMIN_PASS}"
  jwt_refresh_interval: 82800
  knowledge_bases:
    - name: "产品文档"
      assistant_id: "asst_product_001"
      kb_id: "kb_prod_001"
    - name: "技术规范"
      assistant_id: "asst_tech_001"
      kb_id: "kb_tech_001"
```

## 6. Bisheng Adapter

### 6.1 Bisheng API 技术约束

#### v1 vs v2 API

| 维度 | v1 (`/api/v1`) | v2 (`/api/v2`) |
|------|---------------|---------------|
| **定位** | 管理端：完整 CRUD + 权限 | 开放端：面向外部系统 |
| **认证** | JWT + RBAC | `default_operator`（免登录） |
| **Knowledge** | 完整 CRUD | 仅元数据 |
| **Chat** | WebSocket | OpenAI 兼容 |
| **Workflow** | 同步 `run_once()` | 异步 + SSE 流式 `invoke` |

#### 检索链路

Bisheng 不暴露独立"纯检索" API，检索绑定在 Chat/Assistant/Workflow 中：

```
v2 调用链（BishengAdapter 使用）：
  POST /api/v2/assistant/chat/completions（OpenAI 兼容）
    → Milvus（向量，HNSW，L2）+ ES（关键词，BM25）
    → RRFRerank（c=60）+ 可选 Rerank
    → LLM 生成
```

#### Workflow Runtime

```
POST /api/v2/workflow/invoke → SSE 事件流
  ├── node_run:           节点执行开始/结束
  ├── stream_msg:         LLM 流式输出（status: stream/end）
  ├── guide_word:         破冰引导语
  ├── guide_question:     引导提问
  ├── input:              Human-in-the-Loop 输入请求
  ├── output_msg:         普通输出消息
  ├── output_with_input_msg:   输出 + 内嵌输入请求
  ├── output_with_choose_msg:  输出 + 选项选择请求
  ├── close:              Workflow 执行结束（成功或失败）
  └── error:              错误事件（自动转为 close）

Continue 机制：复用 invoke 端点
  POST /api/v2/workflow/invoke
    { workflow_id, user_input: {...}, message_id: "msg_xxx" }
  → 返回新 SSE 流

状态持久化：Redis（workflow:{id}:status/data/event/input/stop）
最大运行时间：24 小时

模板版本假设：
  invoke 时 Bisheng 将当前模板快照到 Redis 运行实例中。
  后续 continue 使用 session_id 定位运行实例，不重新加载模板。
  如果此假设不成立（continue 时重新从 DB 读模板），则：
    - 管理员在运行中修改模板（变更 input_schema 的 key/type/options）
    - Agent 用旧 schema 构造的 inputs 会被 Bisheng 拒绝
    - Airway 通过 input_schema_hash + claim_input 校验提前拦截
  Phase 1 需验证此假设（修改运行中模板后 continue 是否成功）
```

#### SSE 事件 data 结构

**已验证（2026-06-04）**：SSE 事件有外层 wrapper，格式为 `{session_id, data: {...}}`。
Airway `_consume_sse` 解析时应取 `event.get("data", {})` 后再读取字段。

**input 事件（Human-in-the-Loop）**：

```json
{
  "session_id": "a4adb4f2d8c840969f35cc39d1f66f14_async_task_id",
  "data": {
    "event": "input",
    "message_id": "11",
    "status": "end",
    "node_id": "input_cc36c",
    "node_name": "输入",
    "node_execution_id": null,
    "output_schema": null,
    "input_schema": {
      "input_type": "dialog_input",
      "value": [
        {
          "key": "user_input",
          "type": "text",
          "value": "",
          "label": null,
          "multiple": false,
          "required": true,
          "options": null,
          "file_type": null
        }
      ]
    }
  }
}
```

**关键发现**：
- SSE data 有 `session_id` + `data` 双层嵌套，`event`/`input_schema` 等字段在 `data` 内
- `message_id` 在 SSE 中为 string（`"11"`），在请求 body 中为 int（`11`）
- input 事件包含 `node_id` 字段，标识 input 节点——submit 时必须匹配
- `input_type` 实际值为 `dialog_input`（对话型），非文档假设的 `form_input`

`input_type` 可选值：`dialog_input`（对话）、`form_input`（表单）
`type` 可选值：`text`、`select`、`dialog_file`、`dialog_file_accept`

**stream_msg 事件**（验证确认，替代文档中的 `output_msg`）：

```json
{
  "session_id": "..._async_task_id",
  "data": {
    "event": "stream_msg",
    "message_id": "3",
    "status": "end",
    "node_id": "rag_896ca",
    "node_name": "文档知识库问答",
    "node_execution_id": "...",
    "output_schema": {
      "message": "根据提供的参考文本，没有找到相关内容。",
      "reasoning_content": null,
      "output_key": "output_user_input",
      "files": null,
      "source_url": "resouce/.../3",
      "extra": null
    },
    "input_schema": null
  }
}
```

**close 事件**：

```json
{
  "session_id": "..._async_task_id",
  "data": {
    "event": "close",
    "message_id": "msg_zzz",
    "status": "end"
  }
}
```

**guide_question 事件**（验证确认）：

```json
{
  "session_id": "..._async_task_id",
  "data": {
    "event": "guide_question",
    "message_id": null,
    "status": "end",
    "node_id": "start_fa9af",
    "node_name": "开始",
    "output_schema": {"message": [""], ...},
    "input_schema": null
  }
}
```

**node_run 事件**（过滤未暴露给 v2，内部事件）。

#### user_input 提交格式（已验证）

`POST /api/v2/workflow/invoke` 的 `input` 参数（Body alias，非 `user_input`）必须是 `{node_id: {key: value}}` 嵌套格式：

```json
{
  "workflow_id": "de68c5d2b9404e50a6f6f784c7f10f59",
  "session_id": "c4c07c93e2cc4068b235f7d3dfd0a95a_async_task_id",
  "stream": true,
  "input": {"input_cc36c": {"user_input": "什么是知识库？"}},
  "message_id": 1
}
```

**关键**：`node_id` 来自 input 事件的 `data.node_id` 字段，不是 `input_schema` 中的 key。

**Bisheng 无服务端幂等**：相同 message_id 可以重复提交，每次都执行。Airway 的 `claim_input` 是必要的防护层。

#### SSE 断连与补偿

Bisheng **不提供 SSE 断点续传**。SSE 流一旦断开，无法重新订阅。

**源码确认**：用已有 session_id 重新调用 invoke 时：
- `RUNNING` 状态：invoke 不处理此场景，无法重订阅 SSE
- `INPUT` 状态：**必须提供 user_input**，否则抛出 ServerError
- `SUCCESS` / `FAILED`：Workflow 已结束

**Airway SSE 断连补偿路径**：

```
场景 1：运行中 SSE 断连（Airway 进程仍存活）

  双层检测，不依赖单一异常处理路径：

  层 1 — 被动（_consume_sse except 块）：
    1. _consume_sse 捕获 BaseException（ConnectionError / TimeoutError / CancelledError 等）
    2. 调用 sync_from_runtime → 查询 Bisheng status API
    3. 根据状态更新 Task：
       - RUNNING → 启动 _poll_until_change 后台轮询（30s 间隔）
       - INPUT → 保存 input_schema，触发 EventBridge 通知 Agent
       - SUCCESS / FAILED → 更新终态

  层 2 — 主动（_sse_probe 协程，与 SSE 消费并行运行）：
    1. 每 30s 检查 last_sync_at 是否超过 60s 未更新
    2. 正常 SSE 消费持续更新 last_sync_at（进度事件通过 touch_last_sync），探活为 no-op
    3. SSE 死亡后 last_sync_at 停滞 → 探活检测到 stale → 主动 sync_from_runtime
    4. 检测时延：最坏 60s（两轮探活），优于被动等待 300s idle_timeout

场景 2：Airway 重启（SSE 流已丢失）
  1. 启动时 TaskSyncManager.recover_active() 从 PG 恢复未 finalize 记录
  2. 对每条记录，查询 Bisheng status API 同步
  3. RUNNING → 启动后台轮询直到状态变化
  4. INPUT → 重新触发 EventBridge 通知 Agent
  5. SUCCESS / FAILED → 更新终态并通知 Agent
```

**SSE 断连与 input 事件的竞态窗口**：

断连最危险的时序是：Bisheng 恰好在 SSE 连接断裂的瞬间发出 `input` 事件。此时事件在网络层丢失，Airway 无法通过 SSE 收到通知。

```
竞态时序：
  Bisheng                    网络                    Airway
     │                        │                        │
     │── SSE: input 事件 ────→│ ← 连接断裂             │
     │                        │   事件丢失              │
     │   Redis: status=INPUT  │                        │
     │                        │                        │ _consume_sse 抛出 ConnectionError
     │                        │                        │ → 查询 Redis → 检测到 INPUT
     │                        │                        │ → 触发 EventBridge（非延迟，是恢复）

风险：
  1. 如果 Airway 断连后未正确捕获异常（如 kill -9），状态停留在 INPUT，
     但没有进程轮询恢复 → Agent 永远不被通知（静默失败）
  2. 恢复路径依赖 _consume_sse 的异常处理正确执行，
     任何未捕获的异常都会导致 INPUT 状态丢失

缓解措施（分层，不依赖单一机制）：
  1. _consume_sse 的 except 块捕获 BaseException，覆盖所有异常类型（秒级）
  2. _sse_probe 协程每 30s 检查 last_sync_at，60s 内检测到 stale（分钟级）
  3. TaskHealthChecker（§5.3c）每 60s 扫描过期任务，全局兜底（分钟级）
  4. Airway 重启时 recover_active() 恢复所有未 finalize 的 INPUT 状态
  5. Agent 侧的 workflow_status Polling 作为最终兜底（主动查询）
  6. Phase 3 必须专项测试"断连发生在 input 事件发送瞬间"这一时序
```

#### Bisheng 状态查询 API 补丁（建议 PR）

Airway 补偿链依赖查询 Bisheng 任务状态（SSE 断连恢复、HealthChecker、启动恢复）。
当前实现直接读 Bisheng Redis（key 格式 `workflow:{id}:status`），耦合了内部实现，
Bisheng 升级时 key 格式变化会导致 Airway 静默 break。

**建议向 Bisheng 提交最小 PR**，增加状态查询端点：

```
GET /api/v2/workflow/sessions/{session_id}/status

Response:
{
  "status": "RUNNING" | "INPUT" | "SUCCESS" | "FAILED",
  "input_schema": {...},  // INPUT 状态时返回
  "message_id": "...",    // INPUT 状态时返回
  "result": {...},        // SUCCESS 状态时返回
  "error": "..."          // FAILED 状态时返回
}
```

实现参考（约 20 行，只读 Redis 返回 JSON）：

```python
# Bisheng 源码中 workflow 状态已在 Redis 中维护
# 只需读取并返回，核心逻辑：
redis_data = await redis.get(f"workflow:{session_id}:status")
return json.loads(redis_data) if redis_data else {"status": "NOT_FOUND"}
```

**收益**：

| 维度 | 改善 |
|------|------|
| 耦合性 | Airway 不再依赖 Redis key 格式，Bisheng 升级只验证 API 契约 |
| 补偿链 | 断连后调 HTTP API 而非直连 Redis，消除一层依赖（无需 Redis 客户端配置） |
| 可观测性 | 其他系统（监控、运维面板）可复用此端点查看 Workflow 状态 |
| 对 Bisheng 影响 | 纯新增只读端点，零侵入，无副作用 |

**如果 PR 未被接受**：退化为当前方案（BishengAdapter 内部读 Redis），但需在 Bisheng 每次升级时验证 key 格式不变。

#### 知识库权限模型

```
auth_type: public / private / approval
权限: KNOWLEDGE (读) / KNOWLEDGE_WRITE (读写)
隔离: 每个 Assistant 绑定特定知识库
```

#### default_operator 权限边界（源码确认）

default_operator **不是超级管理员**，是普通用户，权限受 `role_access` 表控制。

```
认证流程（v2 API）：
  get_default_operator()
    → settings.get_from_db('default_operator').get('user')  → 获取 user_id
    → UserDao.get_user(user_id)                             → 查用户
    → UserPayload.init_login_user_sync(...)                 → 普通用户身份

权限检查流程：
  login_user.access_check(owner_user_id, target_id, access_type)
    ├── self.user_id == owner_user_id ?  → 资源所有者直接通过
    └── RoleAccessDao.judge_role_access(user_role, target_id, access_type) → 查表
```

| 问题 | 结论 |
|------|------|
| 能否访问所有知识库？ | **不能**。只能访问 `role_access` 表中授权给该用户角色的资源 |
| private 知识库能否读取？ | **取决于配置**。需管理员在 `role_access` 中给 default_operator 角色授权 |
| auth_type 是否影响 v2 访问？ | `auth_type` 主要影响知识空间的自助订阅逻辑，实际读写由 `role_access` 控制 |

**初始化要求**：部署时必须为 default_operator 角色配置所需的 `role_access` 记录，否则 v2 API 无法访问目标知识库和 Assistant。

#### v2 API 审计能力（源码确认）

```
审计现状：
  ├── trace_id:         有，ContextVar 追踪请求（仅内部日志关联）
  ├── 操作日志:         有，散布在业务代码中（logger.info）
  ├── 区分调用者:       无——所有调用都显示为 default_operator
  ├── 专用审计表:       无
  └── 结论:             Bisheng v2 无法区分不同外部调用者的操作
```

**Airway 审计补偿**（设计文档 5.6 Event Store）：
- Airway 在 MCP Tool 调用层记录真实 `user_id` / `tenant_id`
- 所有操作写入 `events` 表，独立于 Bisheng 的日志
- 切换 Runtime 后审计机制不受影响

### 6.2 BishengAdapter 实现

```python
# adapters/bisheng/adapter.py

class BishengAdapter(RAGRuntime):
    def __init__(self, config: BishengConfig, sync_manager: TaskSyncManager):
        self.v2 = BishengV2Client(config.v2_api_url)
        self.v1 = BishengV1Client(config.v1_api_url)
        self.sync = sync_manager
        self.kb_map = config.knowledge_bases

    @property
    def capabilities(self) -> set[RuntimeCapability]:
        return {
            RuntimeCapability.QUERY,
            RuntimeCapability.UPLOAD,
            RuntimeCapability.WORKFLOW,
            RuntimeCapability.KNOWLEDGE_BASE,
        }

    @property
    def state_order(self) -> dict[str, int]:
        return {"RUNNING": 1, "INPUT": 2, "SUCCESS": 3, "FAILED": 3}

    async def query(self, query, knowledge_base=None, top_k=5) -> str:
        assistant_id = self._resolve_assistant(knowledge_base)
        return await self.v2.chat_completions(
            model=assistant_id,
            messages=[{"role": "user", "content": query}],
        )

    async def upload(self, file_path, knowledge_base) -> str:
        kb_id = self._resolve_kb(knowledge_base)
        return await self.v1.upload_document(kb_id, file_path)

    async def list_knowledge_bases(self) -> list[dict]:
        return await self.v1.list_knowledge_bases()

    async def get_runtime_status(self, runtime_task_id: str) -> dict:
        """查询 Bisheng 任务状态（SSOT 查询）。
        优先使用 v2 status API（§6.1 Bisheng PR 提案）；
        退化方案：直接读 Bisheng Redis key。"""
        return await self.v2.get_workflow_status(runtime_task_id)

    async def start_workflow(self, workflow_id, inputs):
        sse_stream, unique_id = await self.v2.invoke_workflow_stream(
            workflow_id, inputs, return_unique_id=True
        )
        # 后台任务：消费 SSE 流，同步状态到 PG
        asyncio.create_task(self._consume_sse(unique_id, sse_stream))
        return unique_id

    async def _consume_sse(self, runtime_task_id, stream,
                            idle_timeout: int = 300):
        """消费 Bisheng SSE 事件流，实时同步状态到 PG 缓存。
        双层检测机制：
        1. 被动：idle_timeout（300s）兜底 Bisheng 假死
        2. 主动：_sse_probe 每 30s 检查连接健康（基于 last_sync_at），
           检测时延从 300s 降至 60s，不依赖 except 块执行"""
        probe = asyncio.create_task(
            self._sse_probe(runtime_task_id))
        try:
            async for raw_event in self._with_idle_timeout(stream, idle_timeout):
                # SSE 事件有 wrapper：{session_id, data: {event, ...}}
                # 已验证（2026-06-04）：必须取 data 层
                event = raw_event.get("data", raw_event)
                category = event.get("event")
                node_id = event.get("node_id")

                if category == "input":
                    # 提取 node_id 用于后续 workflow_continue 构造嵌套 input
                    # input_schema 中不包含 node_id，需从事件顶层获取
                    await self.sync.sync_from_runtime(runtime_task_id, self)
                    # 缓存 node_id 到 pending_input，供 workflow_continue 使用
                    if node_id:
                        record = await self.sync.repo.get(runtime_task_id)
                        if record and record.pending_input:
                            record.pending_input["node_id"] = node_id
                            await self.sync.repo.update_pending_input(
                                runtime_task_id, record.pending_input)

                elif category in ("output_with_input_msg", "output_with_choose_msg"):
                    await self.sync.sync_from_runtime(runtime_task_id, self)

                elif category == "stream_msg" and event.get("status") == "end":
                    # stream_msg status=end 时包含最终输出
                    # 进度事件（status=stream）由 touch_last_sync 更新 last_sync_at
                    pass

                elif category == "close":
                    output = event.get("output_schema", {})
                    await self.sync.finalize(runtime_task_id, {
                        "status": "SUCCESS",
                        "result": output or {"status": "ended"},
                    })

                elif category == "error":
                    await self.sync.finalize(runtime_task_id, {
                        "status": "FAILED",
                        "error": event.get("output_schema", {}).get("message", "unknown"),
                    })

                else:
                    # node_run / stream_msg / guide_word / guide_question：
                    # 进度事件，更新 last_sync_at 供探活协程判断连接健康
                    await self.sync.repo.touch_last_sync(runtime_task_id)

        except BaseException:
            # 捕获所有异常（含 httpx.RemoteProtocolError / asyncio.CancelledError 等），
            # 不局限于 ConnectionError / TimeoutError。
            # sync_from_runtime 内部会查询 Runtime SSOT 决定后续动作：
            # INPUT → 保存 pending_input + EventBridge 通知 Agent
            # RUNNING → 启动后台轮询（由 recover_active 或 _poll_until_change 处理）
            # SUCCESS / FAILED → 终态固化
            log.warning("sse_disconnect_or_idle", runtime_task_id=runtime_task_id)
            await self.sync.sync_from_runtime(runtime_task_id, self)
        finally:
            probe.cancel()

    async def _with_idle_timeout(self, stream, timeout: int):
        """包装 SSE 流，每个事件读取加入空闲超时。
        每次读取下一个事件时用 asyncio.wait_for 限制等待时间。
        超时未收到任何数据 → 抛出 asyncio.TimeoutError 中断消费。"""
        async_iterator = stream.__aiter__()
        while True:
            try:
                event = await asyncio.wait_for(
                    async_iterator.__anext__(), timeout=timeout)
                yield event
            except StopAsyncIteration:
                return

    class IdleTimeoutError(Exception):
        """SSE 流空闲超时（Bisheng 侧假死）"""

    async def _sse_probe(self, runtime_task_id: str,
                          interval: int = 30, stale_seconds: int = 60):
        """独立探活协程：每 interval 秒检查 SSE 连接健康。
        不依赖 _consume_sse 的 except 块执行，独立检测连接死亡。

        检查逻辑：last_sync_at 超过 stale_seconds 未更新 → SSE 可能已死 → 主动 sync。
        正常 SSE 消费持续更新 last_sync_at（进度事件通过 touch_last_sync），
        探活为 no-op；SSE 死亡后探活检测到 stale，主动恢复状态。

        相比被动等待 300s 超时，探活将检测时延降至 60s（最坏两轮探活）。
        与 TaskHealthChecker 的区别：探活是 per-connection，HealthChecker 是 global scan。"""
        while True:
            await asyncio.sleep(interval)
            try:
                record = await self.sync.repo.get(runtime_task_id)
                if not record or record.final_state:
                    return  # Task 已终态，退出探活
                if record.last_sync_at and \
                   (datetime.utcnow() - record.last_sync_at).total_seconds() < stale_seconds:
                    continue  # 近期有同步，连接正常
                log.info("sse_probe_stale", runtime_task_id=runtime_task_id)
                await self.sync.sync_from_runtime(runtime_task_id, self)
            except Exception:
                log.warning("sse_probe_failed", runtime_task_id=runtime_task_id)

    async def continue_workflow(self, runtime_task_id, inputs, message_id,
                                 node_id: str):
        """复用 invoke 端点提交用户输入，获取新 SSE 流。
        调用前必须先通过 TaskSyncService.claim_input 认领，保证 Airway 侧幂等。

        已验证（2026-06-04）：
        - Bisheng 无服务端幂等，相同 message_id 重复提交会重复执行
        - input 参数必须嵌套 node_id：{node_id: {key: value}}
        - 请求 body 用 "input" 作为 key（FastAPI alias），非 "user_input"
        - message_id 类型为 int"""
        # claim_input 由 server.py workflow_continue tool 调用，
        # 此处假设已通过认领检查
        nested_input = {node_id: inputs}
        sse_stream = await self.v2.invoke_workflow_stream(
            session_id=runtime_task_id,
            input=nested_input,
            message_id=int(message_id),
        )
        asyncio.create_task(self._consume_sse(runtime_task_id, sse_stream))
```

### 6.3 认证

```
v2 API（问答/Workflow）：
  → default_operator，免登录
  → Bisheng 数据库 settings 表配置 default_operator.user
  → 该用户是普通用户，非管理员
  → 权限范围完全由 role_access 表控制
  → 部署时需为该用户配置目标知识库/Assistant 的访问权限

v1 API（知识库/文档管理）：
  → JWT token（管理员账号）
  → 默认有效期：86400 秒（24 小时），配置项 jwt_token_expire_time
  → 无 refresh token 机制（refresh_token = access_token 同值）
  → 过期后必须重新登录（POST /user/login）
  → Airway 策略：提前 1 小时（第 23 小时）自动重新登录获取新 token
  → 刷新失败降级：保留 v2 问答能力（default_operator 不受影响），暂停 v1 上传操作
  → 管理员拥有完整 CRUD 权限
```

**权限隔离策略**：
- default_operator 只授权**需要的** Assistant 和知识库（最小权限）
- 不同部门的 Assistant 绑定不同知识库，通过 Assistant 隔离实现租户间数据隔离
- v1 管理员 JWT 仅用于文档上传等管理操作，不用于用户查询

## 7. Clawith 集成

### 7.1 MCP 连接

```yaml
# Clawith 企业设置 → MCP Server 配置
mcp_servers:
  - name: "airway"
    url: "http://airway:8090/mcp"
    transport: "streamable_http"
```

Agent 自动发现所有 rag_query、workflow_start 等 MCP 工具。

### 7.2 Webhook Trigger 配置

```yaml
# Agent 设置 Webhook Trigger，接收 Airway 异步事件
triggers:
  - type: "webhook"
    name: "workflow-event"
    config:
      secret: "${CLAWITH_WEBHOOK_SECRET}"  # HMAC 签名密钥（生产环境必配）
    # Clawith 自动生成 webhook token（URL 路径中的唯一标识）
    # Airway 配置此 token 用于事件回调 URL
```

**Clawith Webhook 安全机制**：
- Token 路径：`POST /api/webhooks/t/{token}`，token 由 `secrets` 模块生成（8 字符 URL-safe）
- HMAC 签名：配置 `secret` 后，验证 `x-hub-signature-256` header（Airway EventBridge 实现）
- 速率限制：全局 60 req/min，每 Agent 可配（默认 5 req/min），Redis 滑动窗口
- Payload 限制：64KB
- 幂等去重：30s 窗口内相同 payload 跳过
- 静默拒绝：始终返回 200，避免 token 枚举

**Payload 格式**：无固定 schema 要求。自定义 JSON 字段直接合并到 Agent trigger config，Agent 可读取 `task_id`、`input_schema`、`created_by` 等字段。

### 7.3 Skill 文件（可选）

```markdown
# RAG 知识库查询技能

## 何时使用
用户问题涉及企业内部知识时，使用 rag_query 工具。
需要提交审批/复杂流程时，使用 workflow_start 工具。

## 知识库映射
- 产品相关: knowledge_base="产品文档"
- 技术相关: knowledge_base="技术规范"

## Workflow 映射
- 采购审批: workflow_id="wf_purchase"
- 出差申请: workflow_id="wf_travel"

## 异步流程
- workflow_start 后不需要等待，结果通过 webhook 异步通知
- 收到 workflow_input 通知时，input_schema 包含结构化表单（字段 key/type/label/options）
- 根据 input_schema 构造 inputs（key 对应 input_schema.value[].key）
- 调用 workflow_continue 时必须携带 message_id（来自通知的 pending_input.message_id）
- 如果通知丢失，调用 workflow_status 获取 pending_input 恢复完整上下文
- 收到审批结果后，通知原始请求人
- 随时可用 workflow_status 查询当前状态
```

### 7.4 用户系统与审计

Clawith 为用户主系统：
- Airway 不管理用户，但通过 MCP Tool 参数接收 `user_id` / `tenant_id`
- Bisheng v2 用 default_operator，v1 用管理员 JWT
- 权限隔离：不同部门配置不同 assistant_id / kb_id
- Bisheng 知识库 auth_type 做二次隔离
- **审计追踪**：Airway 独立记录真实用户操作（覆盖 default_operator 的身份屏蔽），所有 Tool 调用写入 Event Store

### 7.5 Clawith 技术约束

**SSO**：完整支持，租户级，飞书/钉钉/企业微信/Google/GitHub。

**Tool 机制**：50 轮循环，MCP 工具自动发现和调用。

**MCP Client**：当前不支持 MCP Task（SEP-1686）。Airway 通过普通 Tool + Webhook 适配。

**Webhook Trigger**：原生支持，用于接收 Airway 异步事件回调。

## 8. 部署架构

### 8.1 Docker Compose

```yaml
services:
  # ===== 共享基础设施 =====
  redis:
    image: redis:7-alpine
  minio:
    image: minio/minio
  nginx:
    image: nginx:alpine

  # ===== Clawith（Agent 层） =====
  clawith-db:
    image: pgvector/pgvector:pg16
  clawith-backend:
    build: ./Clawith/backend
    depends_on: [clawith-db, redis, minio]
  clawith-frontend:
    build: ./Clawith/frontend

  # ===== Airway（统一服务层） =====
  airway-db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_DB=airway
      - POSTGRES_USER=airway
      - POSTGRES_PASSWORD=${AIRWAY_DB_PASSWORD}
    volumes:
      - airway-db-data:/var/lib/postgresql/data
  airway:
    build: ./airway
    depends_on: [airway-db, redis, minio]
    environment:
      - ADAPTER=bisheng
      - DATABASE_URL=postgresql://airway:${AIRWAY_DB_PASSWORD}@airway-db:5432/airway
      - BISHENG_V2_API_URL=http://bisheng-backend:7860/api/v2
      - BISHENG_V1_API_URL=http://bisheng-backend:7860/api/v1
      - CLAWITH_WEBHOOK_URL=http://clawith-backend:8000/api/webhooks
      - CLAWITH_WEBHOOK_TOKEN=${CLAWITH_WEBHOOK_TOKEN}

  # ===== RAG Runtime 后端（Bisheng） =====
  bisheng-db:
    image: mysql:8.0
  bisheng-etcd:
    image: quay.io/coreos/etcd:v3.5.5
  bisheng-milvus:
    image: milvusdb/milvus:v2.4-latest
  bisheng-es:
    image: elasticsearch:8.13.0
  bisheng-backend:
    image: dataelement/bisheng-backend:latest
    depends_on: [bisheng-db, redis, minio, bisheng-milvus, bisheng-es]
  bisheng-worker:
    image: dataelement/bisheng-backend:latest
    command: celery worker
    depends_on: [bisheng-backend]

volumes:
  airway-db-data:
```

### 8.2 Nginx 路由

```
/              → Clawith 前端（主入口）
/api           → Clawith 后端
/bisheng-admin → Bisheng 前端（仅管理员）
```

### 8.3 初始化

**Bisheng**：
1. 创建 default_operator 用户（普通用户角色）
2. 配置 `default_operator.user`（数据库 settings 表）
3. 按部门创建知识库，上传文档
4. 每个部门创建 Assistant，绑定对应知识库
5. 在 `role_access` 表中为 default_operator 授权目标知识库和 Assistant 的访问权限
6. 可选：创建 RAG Workflow
7. 设置知识库 auth_type

**Clawith**：
1. 配置 MCP Server 连接（指向 Airway）
2. 创建 Agent，配置 Webhook Trigger
3. 可选：放置 Skill 文件到 Agent workspace

## 9. 目录结构

```
/Users/zhenglong/ai-native/rag/
├── Clawith/          # git clone，不改源码（Agent 层）
├── bisheng/          # git clone，不改源码（RAG Runtime 后端）
├── airway/           # 新建：协议转换 + 状态同步 + 统一认证 + 统一审计 + 统一路由
│   ├── server.py
│   ├── task_sync.py
│   ├── event_bridge.py
│   ├── event_store.py
│   ├── identity.py
│   ├── db/
│   │   ├── database.py
│   │   └── migrations/
│   ├── interface/
│   ├── adapters/
│   │   ├── bisheng/
│   │   ├── dify/     # 未来
│   │   └── ragflow/  # 未来
│   └── skills/
├── deployment/       # 统一 docker-compose + nginx
└── docs/
```

## 10. 资源估算

| 组件 | 最低配置 |
|------|---------|
| Clawith（App + PostgreSQL） | 2C/4G |
| Airway（App + PostgreSQL） | 1C/2G |
| Bisheng（App + MySQL + Milvus + ES） | 4C/16G |
| 共享（Redis + MinIO + Nginx） | 1C/2G |
| **合计** | **~8C/24G** |

## 11. 开闭原则实现

| 系统 | 改动 | 升级影响 |
|------|------|---------|
| Clawith | 不改源码，MCP 配置连接 Airway，Tool 参数传递 user_id | git pull 无冲突 |
| Bisheng | 零改动，仅 API 调用和数据库配置 | git pull 无冲突 |
| Airway | 独立项目（含 PG schema） | 独立版本管理 |
| 新 RAG 后端 | 新增 Adapter 目录，不改现有代码 | 开闭原则 |

**未来演进**：
- Clawith 支持 MCP Task（SEP-1686）后，Airway 新增标准 Task 接口暴露，TaskManager / Adapter / EventBridge 核心代码零改动
- 接入第二个 RAG Runtime 时，从 `capabilities` 属性构建 Runtime Registry，按能力路由请求

## 12. 实施路径

### Phase 1：基础部署（1-2 天）

1. 部署 Bisheng，验证 RAG
2. 创建 default_operator 用户，配置 settings 表
3. 创建知识库和 Assistant，配置 role_access 权限
4. 验证 v2 API 通过 default_operator 可访问目标资源
5. 部署 Clawith，验证 Agent 基础功能
6. 验证 Clawith MCP 连接能力

### Phase 2：Airway 同步核心 + 审计基础（2-3 天）

1. 部署 Airway PostgreSQL，初始化 tasks / events 表
2. 定义 `RAGRuntime` 接口（含 `capabilities` 属性）
3. 实现 MCP Server 框架（MCP SDK + Streamable HTTP）
4. 实现 BishengAdapter 同步操作（query、upload、kb_list）
5. 实现 EventStore 基础写入（所有 Tool 调用记录审计事件）
6. 端到端测试：MCP Tool（含 user_id）→ BishengAdapter → Bisheng API → 审计记录

### Phase 3：最小异步闭环（2-3 天）

目标：跑通 `workflow_start → SSE 消费 → input → continue → close` 完整闭环，验证 Bisheng v2 API 稳定性。

1. 实现 TaskSyncService 基础（create / sync_from_runtime / finalize / get_status / claim_input）
2. 实现 TaskRepository（PG CRUD + 乐观锁 + compare_and_clear_pending）
3. 实现 BishengAdapter 异步操作（start/continue + SSE 消费 + get_runtime_status）
4. 实现 EventBridge + Outbox Pattern（状态变更 + 通知写入同一 PG 事务）
5. 实现 OutboxWorker（后台轮询 + HMAC 签名投递 + 基础重试，最多 5 次）
6. 配置 Clawith Webhook Trigger（含 HMAC secret）
7. 实现 IdentityGateway（全映射 default_operator）
8. 实现 v1 JWT 自动刷新（23 小时定时重新登录 + 失败降级）
9. SSE 断连处理：`except BaseException → sync_from_runtime`（调用 Bisheng status API），RUNNING 启动 `_poll_until_change`
10. 启动恢复：`recover_active` 查询未 finalize 记录 → 调用 status API 同步
11. 端到端异步闭环测试

**此阶段不实现**（留待 Phase 4 观测结果决定）：

| 机制 | 理由 | 替代兜底 |
|------|------|---------|
| SSEConnectionPool（信号量） | 先验证连接数是否是实际问题 | 简单 `asyncio.Task` |
| TaskHealthChecker | 先靠重启恢复 + Agent Polling 兜底 | `recover_active` + Polling |
| SSE 空闲超时 / TTL 上限 | 先靠 Bisheng 24h 上限 | Bisheng 自动清理 |
| Outbox dead replay | 先靠 Agent Polling 兜底 | `workflow_status` 查询 |
| Redis 分布式锁 | 先单实例部署 | 无并发问题 |

### Phase 4：集成测试 + 观测期（2-3 天）

目标：在 staging 环境运行，验证端到端流程，收集 SSE 断连率、Webhook 投递延迟等指标。

1. Skill 文件编写和放置
2. 审计查询接口验证（按 task_id 时间线 + 按 actor_id 操作历史）
3. 统一 docker-compose + Nginx
4. 异步闭环压力测试（连续 50+ 次 workflow 执行，统计断连率和端到端延迟）
5. SSE 断连场景手动测试（网络抖动 / Airway 重启 / Bisheng 重启）
6. Webhook 端点不可用场景测试
7. 多租户权限测试

**观测指标清单**（决定 Phase 5 加固范围）：

| 指标 | 采集方式 | 阈值建议 |
|------|---------|---------|
| SSE 断连率 | `sse_disconnect_or_error` 日志 / 总启动数 | > 5% 需加 HealthChecker |
| SSE 平均连接时长 | `last_sync_at` - `created_at` | < 30s 说明 API 不稳定 |
| Webhook 投递成功率 | `outbox_dead` / `outbox_sent` 日志 | < 99% 需加 dead replay |
| SSE 僵尸连接 | 活跃 SSE Task 数 vs Bisheng 活跃 Workflow 数 | 有差异需加 idle timeout |
| 单实例 QPS | MCP Tool 调用频率 | > 50 req/s 需考虑多实例 + 分布式锁 |

### Phase 5：按需加固（1-2 天）

基于 Phase 4 观测结果，**仅实现被数据证明需要的机制**：

| 机制 | 触发条件 | 复杂度 |
|------|---------|-------|
| SSEConnectionPool | 活跃连接需要控制或出现资源泄漏 | 低 |
| TaskHealthChecker | SSE 断连恢复不可靠或断连率 > 5% | 中 |
| SSE 空闲超时 / TTL 上限 | 出现僵尸连接 | 低 |
| Outbox dead replay | dead 记录堆积且 Webhook 端点恢复周期 < 5 min | 低 |
| Redis 分布式锁 | 需要多实例部署 | 中 |

未触发的机制不实现，避免防御从未发生的故障。

### Phase 6（未来）：扩展

1. 新增 Dify Adapter（实现 RAGRuntime + capabilities）
2. 新增 RagFlow Adapter
3. 基于 capabilities 构建 Runtime Registry
4. Clawith 支持 MCP Task 后，Airway 直接暴露标准 Task 接口

## 13. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Bisheng v2 API 不稳定 | Adapter 调用失败 | v1 作为 fallback，Adapter 内部自动降级 |
| default_operator 权限配置不当 | 部署后无法访问目标知识库/Assistant | 部署 checklist 中明确 role_access 配置步骤；Airway 启动时健康检查验证权限 |
| v2 API 无法区分调用者 | 审计盲区，无法追踪"谁做了什么" | Airway Event Store 独立记录真实 user_id / tenant_id，不依赖 Bisheng 审计 |
| SSE 流中断 | 状态缓存停止更新 | **双层检测**：①被动：`except BaseException` 秒级捕获 + `sync_from_runtime` 查 status API 恢复；②主动：`_sse_probe` 协程每 30s 检查 `last_sync_at`，60s 内检测 stale 并主动 sync。**三层兜底**：TaskHealthChecker 全局扫描（60s）→ Airway 重启 `recover_active()` → Agent Polling。input 竞态窗口：断连瞬间 input 事件丢失，探活 60s 内检测到 INPUT 并恢复通知 |
| Webhook 推送失败 | Agent 未被唤醒（静默失败） | Outbox Pattern：状态 + 通知同一事务写入 PG，OutboxWorker 后台重试（最多 5 次），**dead 后 `_replay_dead` 每 5 分钟自动重试活跃任务的 dead 记录**；Airway 重启后自动恢复未投递通知；**最终兜底**：Agent 主动调用 workflow_status 获取 pending_input（含 message_id + input_schema），无需 Webhook 也能完成 workflow_continue 闭环 |
| Airway 重启 | SSE 流丢失 | 从 PG 恢复未 finalize 记录 → 查询 Bisheng Redis 状态同步 → RUNNING 启动轮询 / INPUT 重新通知 Agent / 终态直接固化 |
| Airway PG 不可用 | Airway 不可用（MCP Tool 全部失败） | PG 是 Airway 的硬依赖，不可用等于 Airway 不可用。不设计应用层降级——由基础设施处理（PG HA / 容器自动重启）。重启后 `recover_active()` 从 Runtime 恢复未固化状态 |
| finalize 写入失败（PG 不可用 / Airway 崩溃） | Redis SUCCESS 但 PG `final_state = NULL`，恢复前 PG 显示 RUNNING | `finalized_at IS NULL` 精确标识未固化任务；`recover_active` 重启后查 Runtime 状态补调 `finalize`；监控可告警 `finalized_at IS NULL AND cached_state->>'status' IN ('SUCCESS','FAILED')` |
| MCP 工具超时（60s） | 长查询失败 | 同步操作控制复杂度；异步操作走 Task + 事件桥接 |
| Bisheng 升级破坏 API | Adapter 失效 | Adapter 版本锁定 API，升级前验证 |
| Bisheng JWT 过期 | v1 管理操作失败 | 提前 1 小时自动重新登录；刷新失败降级为只保留 v2 问答能力 |
| 审计数据膨胀 | PG 存储压力 | events 表按 created_at 分区（月），定期归档历史数据 |
| 多实例并发 sync 同一 task | 状态覆盖、重复 Webhook 推送 | Redis 分布式锁（airway:task_lock:{task_id}），只有锁持有者消费 SSE + 推送通知 |
| SSE 连接耗尽 | 新 workflow 被拒绝 | SSEConnectionPool 信号量控制上限（默认 100），满时返回 SSE_POOL_FULL，Agent 可重试 |
| Bisheng 静默假死（不发送 close/error/ping） | SSE 消费 Task 永久挂起，连接池槽位泄漏，最终 SSE_POOL_FULL | **双层超时**：`_with_idle_timeout` 对每个事件读取设置 300s 空闲超时 → 超时触发 Redis 状态补偿 + 轮询恢复；`SSEConnectionPool.max_ttl` 24h 绝对上限 → 强制 cancel 僵尸 Task 释放槽位 |
| 延迟事件导致状态倒退 | 显示 RUNNING 但实际在等待审批 | state_version 乐观锁（PG UPDATE WHERE version=?）+ 状态有序性校验（INPUT → RUNNING 视为倒退跳过） |
| workflow_continue 重复调用 | Webhook + Polling 双触发 / SSE 断连恢复竞态导致同一 input 被提交两次 | `claim_input` 原子操作：乐观锁 + `pending_input->>'message_id'` 匹配后清除，重复调用返回 `INPUT_ALREADY_CLAIMED`；**Bisheng 侧幂等防护（§5.3d）**：claim 成功后立即记录 `input_submitted_at`，Bisheng 调用失败不自动重试，避免双重提交；Phase 1 验证 Bisheng invoke 在 INPUT 状态对相同 message_id 的幂等行为 |
| Workflow 模板热更（管理员修改运行中的模板） | 运行中 Task 的 `input_schema` 与当前模板不一致，`workflow_continue` 提交的 inputs key 不匹配导致 Bisheng 报错 | `input_schema_hash` 记录首次 input 指纹；`claim_input` 校验 inputs key 与 `pending_input.input_schema` 的 key 集合一致，不匹配返回 `INPUT_SCHEMA_MISMATCH`；Agent 可提示用户重新查询状态获取最新 schema |

## 14. TDD 策略

### 14.1 测试分层与职责

```
┌─────────────────────────────────────────────────────────┐
│                  E2E Tests（Phase 4）                     │
│   MCP Tool 调用 → Adapter → Mock Bisheng → 验证响应     │
│   覆盖：完整用户路径、多租户隔离、审计链路               │
├─────────────────────────────────────────────────────────┤
│              Integration Tests（Phase 3）                 │
│   SSE 消费 → TaskSync → EventBridge → Outbox → PG       │
│   覆盖：跨模块协作、状态转换链、Outbox 投递              │
├─────────────────────────────────────────────────────────┤
│                Unit Tests（Phase 2-3）                    │
│   单个类/函数，所有外部依赖 mock                          │
│   覆盖：状态机转换、乐观锁、事件解析、认证映射            │
└─────────────────────────────────────────────────────────┘
```

| 层 | 占比目标 | Mock 范围 | 运行频率 |
|----|---------|----------|---------|
| Unit | ~60% | Bisheng API / Redis / PG / httpx | 每次 commit |
| Integration | ~30% | 仅 mock Bisheng API 和 httpx（PG/Redis 用真实实例） | PR 合并前 |
| E2E | ~10% | 仅 mock Bisheng API（Clawith Webhook 用真实 HTTP） | Phase 4 专属 |

### 14.2 Mock 边界定义

外部依赖在边界处 mock，Airway 内部模块不 mock：

```
Mock 边界（外部系统）           不 Mock（Airway 内部）
─────────────────────────────────────────────────────
BishengV2Client（API 调用）     TaskSyncService
BishengV1Client（API 调用）     TaskRepository
httpx.AsyncClient（Webhook）    EventBridge
Redis（分布式锁/缓存）          OutboxWorker
                               SSEConnectionPool
                               IdentityGateway
                               EventStore
```

**PG 和 Redis 的 mock 策略**：
- Unit 测试：mock `TaskRepository` 接口，不依赖真实 PG
- Integration 测试：用 testcontainers 启动真实 PG，验证 SQL 行为
- 乐观锁等 PG 特有语法（`RETURNING`、`WHERE version=?`）必须在真实 PG 上测试

### 14.3 测试目录结构

```
airway/
├── tests/
│   ├── conftest.py              # 公共 fixtures
│   ├── fixtures/
│   │   ├── bisheng_responses.py # Bisheng API mock 响应数据
│   │   ├── sse_events.py        # 9 种 SSE 事件 mock
│   │   └── db.py                # 测试数据库初始化
│   │
│   ├── unit/                    # Phase 2-3，无外部依赖
│   │   ├── test_task_sync.py
│   │   ├── test_task_repo.py
│   │   ├── test_task_recovery.py
│   │   ├── test_event_bridge.py
│   │   ├── test_outbox_worker.py
│   │   ├── test_event_store.py
│   │   ├── test_identity.py
│   │   ├── test_sse_consumer.py
│   │   ├── test_sse_pool.py
│   │   ├── test_tracing.py
│   │   └── test_config.py
│   │
│   ├── integration/             # Phase 3，跨模块协作
│   │   ├── test_sync_to_outbox.py      # TaskSync → EventBridge → Outbox 写入
│   │   ├── test_sse_to_finalized.py    # SSE 消费 → 状态同步 → 终态固化
│   │   ├── test_outbox_delivery.py     # Outbox → Webhook 投递 + 重试
│   │   ├── test_recovery_flow.py       # 重启恢复完整链路
│   │   └── test_optimistic_lock.py     # 并发 sync 乐观锁（真实 PG）
│   │
│   └── e2e/                     # Phase 4
│       ├── test_rag_query.py            # MCP Tool → Adapter → Mock Bisheng
│       ├── test_workflow_lifecycle.py   # start → input → continue → completed
│       ├── test_workflow_polling_fallback.py  # Webhook 丢失 → Agent polling → continue → completed
│       ├── test_audit_trail.py          # 按 task_id / actor_id 查询
│       └── test_tenant_isolation.py     # 租户间数据隔离
```

### 14.4 状态机测试矩阵

从 §4.4 Task 状态映射表和 §6.1 SSE 事件格式直接推导。

#### 14.4.1 正向状态转换

| # | 初始状态 | 触发事件/操作 | 期望状态 | 测试文件 |
|---|---------|-------------|---------|---------|
| 1 | — | `workflow_start` | `working` | test_task_sync |
| 2 | `working` | SSE `node_run` | `working`（缓存更新） | test_sse_consumer |
| 3 | `working` | SSE `stream_msg` | `working`（进度更新） | test_sse_consumer |
| 4 | `working` | SSE `input` | `input_required` + EventBridge | test_sse_to_finalized |
| 5 | `working` | SSE `output_with_input_msg` | `input_required` + EventBridge | test_sse_consumer |
| 6 | `working` | SSE `output_with_choose_msg` | `input_required` + EventBridge | test_sse_consumer |
| 7 | `input_required` | `workflow_continue` | `working`（新 SSE 流） | test_workflow_lifecycle |
| 8 | `working` | SSE `close(status=end)` | `completed`（终态固化） | test_sse_to_finalized |
| 9 | `working` | SSE `error` → `close` | `failed`（终态固化） | test_sse_to_finalized |

#### 14.4.2 状态有序性校验

| # | 当前状态 | 新状态 | 期望行为 | 测试名 |
|---|---------|-------|---------|-------|
| 1 | `INPUT` | `RUNNING` | 拒绝（倒退） | test_regression_input_to_running_rejected |
| 2 | `SUCCESS` | `RUNNING` | 拒绝（终态不可变） | test_regression_success_to_running_rejected |
| 3 | `SUCCESS` | `INPUT` | 拒绝（终态不可变） | test_regression_success_to_input_rejected |
| 4 | `RUNNING` | `INPUT` | 接受 | test_running_to_input_accepted |
| 5 | `INPUT` | `SUCCESS` | 接受 | test_input_to_success_accepted |

#### 14.4.3 乐观锁冲突

| # | 场景 | 期望行为 | 测试名 |
|---|------|---------|-------|
| 1 | 两个并发 sync 同一 task | 仅一个成功，另一个跳过 | test_concurrent_sync_one_wins |
| 2 | sync 期间版本已被更新 | 返回最新缓存，不覆盖 | test_stale_version_update_fails |
| 3 | finalize 时版本冲突 | 不重复固化 | test_finalize_version_conflict_skips |

### 14.5 可靠性测试矩阵

从 §13 风险表直接推导。每个风险项至少一个测试覆盖。

| 风险项 | 测试场景 | 测试名 | 类型 |
|-------|---------|-------|------|
| SSE 流中断 + RUNNING | SSE 断连后启动轮询直到状态变化 | test_disconnect_running_starts_polling | unit |
| SSE 流中断 + INPUT | SSE 断连后恢复 input_schema 并通知 Agent | test_disconnect_input_notifies_agent | unit |
| SSE 断连瞬间 input 事件丢失 | 断连发生在 Bisheng 发出 input 事件的同时，事件在 SSE 层丢失；Airway 通过异常处理 → Redis 查询 → 检测 INPUT → EventBridge 恢复通知 | test_disconnect_during_input_event_race | unit |
| Webhook 丢失 + Agent Polling 兜底 | Webhook 投递失败（Outbox 重试耗尽或 Agent 未配置 Trigger），Agent 通过 workflow_status 获取 pending_input.message_id + input_schema，构造 workflow_continue 完成闭环 | test_workflow_polling_fallback | e2e |
| SSE 流中断 + 终态 | SSE 断连后查询到 SUCCESS，直接固化 | test_disconnect_success_finalizes | unit |
| Airway 重启 | 从 PG 恢复未 finalize 记录，查询 Runtime 状态同步 | test_recovery_syncs_unfinalized_tasks | integration |
| Webhook 推送失败 | 网络错误重试最多 5 次，之后标记 dead | test_outbox_retry_then_dead | unit |
| dead 记录自动重放 | Webhook 恢复后 dead 被重试并标记 sent | test_dead_replay_success | unit |
| dead 记录任务已终态 | 终态任务的 dead 标记为 expired 不再重试 | test_dead_expired_when_finalized | unit |
| Webhook Airway 崩溃 | 重启后 OutboxWorker 从 PG 重新读取 pending | test_outbox_survives_restart | integration |
| 重复 Webhook 投递 | 相同 payload 30s 内不重复触发 | test_webhook_idempotent | unit |
| 多实例并发 | 分布式锁保证只有一个实例消费 SSE | test_lock_prevents_duplicate_sse | unit |
| SSE 连接池满 | 超过上限返回 SSE_POOL_FULL | test_pool_full_rejects_new | unit |
| SSE 假死超时 | 300s 无事件 → IdleTimeout → Redis 状态补偿 | test_sse_idle_timeout_triggers_recovery | unit |
| SSE TTL 绝对上限 | 24h max_ttl 到期 → 强制 cancel → 释放槽位 | test_pool_ttl_cancels_zombie | unit |
| v1 JWT 过期 | 第 23 小时自动刷新 | test_jwt_refresh_before_expiry | unit |
| JWT 刷新失败 | 降级为仅 v2 能力 | test_jwt_failure_degrades_to_v2 | unit |
| Bisheng v2 不可用 | v1 fallback 降级 | test_v2_down_falls_back_to_v1 | integration |
| 延迟事件状态倒退 | version + 有序性校验双重保护 | test_delayed_event_rejected | unit |
| workflow_continue 重复调用 | 第一次 claim_input 成功，第二次返回 INPUT_ALREADY_CLAIMED | test_workflow_continue_idempotent | unit |
| workflow_continue message_id 不匹配 | claim_input 检测到 message_id 与 pending_input 不一致，拒绝 | test_claim_input_message_id_mismatch | unit |
| workflow_continue 并发竞态 | 两个 Agent 同时 claim 同一 input，仅一个成功 | test_claim_input_concurrent_race | integration |
| 模板热更导致 input_schema 变更 | inputs key 与 pending_input.input_schema 的 key 不匹配，返回 INPUT_SCHEMA_MISMATCH | test_input_schema_mismatch_detected | unit |
| input_schema_hash 记录 | 首次 input 事件写入 hash，后续 input 事件（多轮）不覆盖 | test_input_schema_hash_first_only | unit |
| INPUT 事件重复同步不重复通知 | sync_from_runtime 检测到相同 message_id 的 INPUT，跳过 EventBridge | test_input_duplicate_sync_no_duplicate_notify | unit |
| HealthChecker 触发 INPUT 同步 | TaskHealthChecker 扫描到过期任务，同步后发现 INPUT 状态，仅在新 message_id 时触发 EventBridge | test_health_checker_input_notify_idempotent | unit |
| input_submitted_at 与 clear_pending 原子性 | compare_and_clear_pending 同一条 UPDATE 写入 input_submitted_at + 清除 pending_input，PG 异常时两者一致 | test_claim_atomic_submitted_at | integration |

### 14.6 SSE 事件解析测试

基于 §6.1 SSE 事件 data 结构，每种事件至少一个解析测试。

```python
# tests/unit/test_sse_consumer.py

sse_event_test_cases = [
    ("input",                 "test_parse_input_event",              "保存 input_schema + 触发 EventBridge"),
    ("output_with_input_msg", "test_parse_output_with_input_event",  "保存 output + 触发 EventBridge"),
    ("output_with_choose_msg","test_parse_output_with_choose_event", "保存 options + 触发 EventBridge"),
    ("close",                 "test_parse_close_event",              "终态固化 SUCCESS"),
    ("error",                 "test_parse_error_event",              "终态固化 FAILED"),
    ("node_run",              "test_parse_node_run_event",           "缓存进度（节点开始/结束）"),
    ("stream_msg",            "test_parse_stream_msg_event",         "缓存流式输出（stream/end）"),
    ("guide_word",            "test_parse_guide_word_event",         "缓存引导语"),
    ("guide_question",        "test_parse_guide_question_event",     "缓存引导提问"),
]
```

### 14.7 公共 Fixtures

```python
# tests/conftest.py 核心设计

@pytest.fixture
def mock_bisheng_v2():
    """Mock BishengV2Client，返回预设响应"""

@pytest.fixture
def mock_bisheng_sse():
    """生成可控制的 SSE 事件流，支持按序列发送和中断模拟"""

@pytest.fixture
def test_db():
    """SQLite 内存数据库（Unit 测试用，快速）"""

@pytest.fixture
def real_pg():
    """testcontainers PostgreSQL（Integration 测试用，验证真实 SQL）"""

@pytest.fixture
def sample_task_record():
    """标准 TaskRecord 实例，各字段已填充合理默认值"""

@pytest.fixture
def mock_webhook_response():
    """Mock httpx.AsyncClient，记录 Webhook 调用次数和 payload"""
```

### 14.8 Phase 级 TDD 工作流

每个 Phase 的开发节奏：**Red → Green → Refactor**，粒度按 Phase 调整。

#### Phase 2（同步核心）

```
循环（每个 MCP Tool）：
  1. Red:   写 Tool 的契约测试（参数类型 + 返回格式）
  2. Green: 实现 BishengAdapter 对应方法
  3. Red:   写 Adapter 的边界测试（API 错误、超时）
  4. Green: 实现错误处理
  5. Red:   写 EventStore 审计记录测试
  6. Green: 实现 EventStore
  Refactor: 提取公共 mock 和 fixture
```

**先写测试的模块顺序**（依赖关系由底向上）：

1. `test_config.py` — 配置加载
2. `test_tracing.py` — trace_id 传播
3. `test_task_repo.py` — 数据访问
4. `test_event_store.py` — 事件记录
5. `test_identity.py` — 身份映射
6. `test_sse_consumer.py`（仅解析部分）— SSE 事件解析
7. `test_server.py` — MCP Tool 端到端

#### Phase 3（异步状态）

```
循环（每个状态转换）：
  1. Red:   写状态转换测试（从 §14.4 矩阵取一行）
  2. Green: 实现 TaskSyncService 对应逻辑
  3. Red:   写可靠性测试（从 §14.5 矩阵取一行）
  4. Green: 实现补偿/恢复逻辑
  5. Red:   写跨模块集成测试
  6. Green: 连接各模块
  Refactor: 合并重复的 fixture 和 setup
```

**先写测试的模块顺序**：

1. `test_task_sync.py` — 状态同步核心（§14.4.1 + §14.4.2 + §14.4.3）
2. `test_event_bridge.py` — Outbox 写入
3. `test_outbox_worker.py` — 投递 + 重试
4. `test_sse_pool.py` — 连接池控制
5. `test_task_recovery.py` — 恢复逻辑
6. `test_sync_to_outbox.py` — 集成：同步 → 桥接 → Outbox
7. `test_sse_to_finalized.py` — 集成：SSE → 同步 → 终态
8. `test_outbox_delivery.py` — 集成：Outbox → Webhook
9. `test_recovery_flow.py` — 集成：重启恢复
10. `test_optimistic_lock.py` — 集成：并发（真实 PG）

#### Phase 4（集成验证）

不再严格 TDD，改为**验收测试驱动**：
1. 从 §14.5 未覆盖的风险项补充 E2E 测试
2. 多租户隔离测试
3. 审计链路完整性测试
4. 全链路异常注入（SSE 断连 + Webhook 失败 + Airway 重启组合场景）

### 14.9 覆盖率要求

| 模块 | 最低行覆盖率 | 原因 |
|------|------------|------|
| `task_sync.py` | 90% | 状态机核心，bug 影响面最大 |
| `sse_consumer.py` | 90% | 9 种事件解析，遗漏即 bug |
| `event_bridge.py` | 80% | Outbox 写入逻辑相对简单 |
| `outbox_worker.py` | 85% | 重试/死信逻辑需完整覆盖 |
| `task_recovery.py` | 80% | 恢复逻辑分支有限 |
| `task_repo.py` | 70% | CRUD 相对简单，乐观锁部分重点覆盖 |
| `identity.py` | 60% | 当前全映射 default_operator，逻辑极少 |
| `server.py` | 70% | MCP Tool 入口，参数校验重点覆盖 |

**排除**：`config.py`（纯配置加载）、`tracing.py`（ContextVar 工具函数）、`db/models.py`（SQLModel 定义）。

### 14.10 测试优化

#### 运行速度

```
目标：
  Unit 测试套件 < 10s（无 IO，纯内存）
  Integration 测试套件 < 60s（testcontainers 启动 PG ~5s）
  E2E 测试套件 < 120s

手段：
  - Unit 测试用 SQLite 内存数据库，不启动 testcontainers
  - Integration 测试共享一个 PG 实例（module scope fixture）
  - 并行执行：pytest-xdist -n auto（Unit/Integration 分开运行）
```

#### Mock 数据管理

所有 mock 响应集中存放在 `tests/fixtures/`，不在测试文件中硬编码。

```
tests/fixtures/
├── bisheng_responses.py    # 按 API 端点组织的响应模板
│   ├── CHAT_COMPLETION_OK  # 正常问答响应
│   ├── WORKFLOW_STARTED    # Workflow 启动响应
│   ├── WORKFLOW_STATUS_*   # RUNNING / INPUT / SUCCESS / FAILED
│   └── ERROR_*             # 超时 / 500 / 认证失败
│
├── sse_events.py           # 按 event type 组织的事件模板
│   ├── INPUT_EVENT         # §6.1 input 事件
│   ├── CLOSE_EVENT         # §6.1 close 事件
│   ├── ERROR_EVENT         # §6.1 error 事件
│   └── ...                 # 其余 6 种
│
└── db.py                   # 测试数据库 factory
    ├── make_task_record()  # 构建标准 TaskRecord
    └── make_event()        # 构建标准 Event
```

#### CI 集成

```yaml
# .github/workflows/test.yml
jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - run: pytest tests/unit/ -x -q --tb=short

  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env: { POSTGRES_DB: airway_test, POSTGRES_USER: airway, POSTGRES_PASSWORD: test }
    steps:
      - run: pytest tests/integration/ -x -q --tb=short

  e2e:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - run: pytest tests/e2e/ -x -q --tb=short
```
