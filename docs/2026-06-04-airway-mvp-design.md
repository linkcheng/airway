# Airway MVP 设计 + 迭代路线

> 版本：v0.1 | 日期：2026-06-04
> 前置文档：2026-05-31-clawith-bisheng-integration-design.md（完整设计）
> 本文档：从完整设计中提取 MVP，定义迭代升级步骤

## 1. 设计原则

- Airway 是无状态的 MCP 代理——Bisheng 是唯一的状态源
- 不持有 SSE 连接，不写 PG，不走 Outbox
- Agent 通过轮询驱动异步流程
- 文件数量：~5 个

## 2. 架构

```
Clawith Agent
    │ MCP Tool 调用
    ▼
Airway（无状态 FastMCP 代理）
    │ HTTP
    ▼
Bisheng（状态在 Redis）
```

## 3. 目录结构

```
airway/
├── pyproject.toml
├── server.py              # FastMCP 入口，所有 Tool
├── config.py              # YAML 配置
├── adapters/bisheng/
│   ├── client.py          # v1/v2 HTTP 客户端
│   └── auth.py            # v1 JWT + v2 default_operator
└── config.yaml
```

## 4. 依赖

```toml
[project]
name = "airway"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=0.1",
    "httpx>=0.27",
    "pydantic-settings>=2.0",
    "pyyaml>=6.0",
]
```

## 5. MCP Tools（6 个）

```python
# server.py

@tool
async def rag_query(query: str, knowledge_base: str | None = None, top_k: int = 5) -> str:
    """RAG 问答"""
    return await adapter.query(query, knowledge_base, top_k)

@tool
async def rag_upload(file_path: str, knowledge_base: str) -> str:
    """上传文档"""
    return await adapter.upload(file_path, knowledge_base)

@tool
async def rag_kb_list() -> list[dict]:
    """列出知识库"""
    return await adapter.list_knowledge_bases()

@tool
async def workflow_start(workflow_id: str, inputs: dict | None = None) -> dict:
    """启动 Workflow，返回 {task_id, status: "working"}。
    用 workflow_status 轮询进度，status 为 input_required 时调用 workflow_continue。"""
    session_id = await adapter.start_workflow(workflow_id, inputs)
    return {"task_id": session_id, "status": "working"}

@tool
async def workflow_status(task_id: str) -> dict:
    """查询 Workflow 状态。
    返回 {status, input_schema?, result?, error?, message_id?}。
    status: working / input_required / completed / failed"""
    return await adapter.get_workflow_status(task_id)

@tool
async def workflow_continue(task_id: str, inputs: dict, message_id: str) -> dict:
    """提交人工输入，恢复 Workflow。返回 {task_id, status: "working"}。
    inputs 的 key 对应 workflow_status 返回的 input_schema.value[].key。
    message_id 来自 workflow_status 返回值。"""
    await adapter.continue_workflow(task_id, inputs, message_id)
    return {"task_id": task_id, "status": "working"}
```

## 6. BishengAdapter 核心实现

### 6.1 v2 客户端

```python
# adapters/bisheng/client.py

class BishengV2Client:
    def __init__(self, base_url: str, redis_url: str):
        self.base_url = base_url
        self.redis_url = redis_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30)

    async def chat_completions(self, model: str, messages: list) -> str:
        """OpenAI 兼容问答"""
        resp = await self.client.post("/assistant/chat/completions",
            json={"model": model, "messages": messages, "stream": False})
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def invoke_workflow(self, workflow_id: str, inputs: dict | None = None,
                              session_id: str | None = None,
                              input_data: dict | None = None,
                              message_id: int | None = None) -> str:
        """调用 workflow invoke，从 SSE 首事件提取 session_id，关闭流。
        返回 session_id"""
        body = {"workflow_id": workflow_id, "stream": True}
        if session_id:
            body["session_id"] = session_id
        if inputs:
            body["user_input"] = inputs
        if input_data:
            body["input"] = input_data
        if message_id is not None:
            body["message_id"] = message_id

        async with self.client.stream("POST", "/workflow/invoke", json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    event = json.loads(line[5:])
                    sid = event.get("session_id")
                    if sid:
                        return sid
        raise AirwayError("NO_SESSION_ID", "Failed to extract session_id from SSE")

    async def get_workflow_status(self, session_id: str) -> dict:
        """直读 Bisheng Redis 获取 workflow 状态（MVP 过渡方案）。
        后续替换为 GET /api/v2/workflow/sessions/{session_id}/status。"""
        import redis.asyncio as aioredis
        r = aioredis.from_url(self.redis_url)
        raw = await r.get(f"workflow:{session_id}:status")
        if not raw:
            return {"status": "NOT_FOUND"}
        data = json.loads(raw)
        if data.get("status") == "INPUT":
            input_raw = await r.get(f"workflow:{session_id}:input")
            if input_raw:
                input_data = json.loads(input_raw)
                data["input_schema"] = input_data.get("input_schema")
                data["message_id"] = input_data.get("message_id")
                data["node_id"] = input_data.get("node_id")
        return data
```

### 6.2 v1 客户端

```python
# adapters/bisheng/auth.py

class BishengV1Client:
    """v1 管理端 API：知识库 CRUD + 文档上传"""
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.username = username
        self.password = password
        self._token: str | None = None
        self._token_expires: datetime | None = None

    async def _ensure_token(self):
        if self._token and self._token_expires and \
           datetime.utcnow() < self._token_expires - timedelta(hours=1):
            return
        async with httpx.AsyncClient(base_url=self.base_url) as client:
            resp = await client.post(
                "/user/login",
                json={"user_name": self.username, "password": self.password}
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            self._token_expires = datetime.utcnow() + timedelta(seconds=86400)

    async def upload_document(self, kb_id: str, file_path: str) -> str: ...
    async def list_knowledge_bases(self) -> list[dict]: ...
```

### 6.3 Adapter

```python
# adapters/bisheng/adapter.py

class BishengAdapter:
    def __init__(self, config: BishengConfig):
        self.v2 = BishengV2Client(config.v2_api_url, config.redis_url)
        self.v1 = BishengV1Client(config.v1_api_url, config.admin_user, config.admin_pass)
        self.kb_map = config.knowledge_bases

    def _resolve_assistant(self, knowledge_base: str | None) -> str:
        if knowledge_base and knowledge_base in self.kb_map:
            return self.kb_map[knowledge_base]["assistant_id"]
        return next(iter(self.kb_map.values()))["assistant_id"]

    async def query(self, query: str, knowledge_base: str | None, top_k: int) -> str:
        return await self.v2.chat_completions(
            model=self._resolve_assistant(knowledge_base),
            messages=[{"role": "user", "content": query}]
        )

    async def upload(self, file_path: str, knowledge_base: str) -> str:
        kb_id = self.kb_map[knowledge_base]["kb_id"]
        return await self.v1.upload_document(kb_id, file_path)

    async def list_knowledge_bases(self) -> list[dict]:
        return await self.v1.list_knowledge_bases()

    async def start_workflow(self, workflow_id: str, inputs: dict | None) -> str:
        session_id = await self.v2.invoke_workflow(workflow_id, inputs)
        return session_id

    async def get_workflow_status(self, session_id: str) -> dict:
        raw = await self.v2.get_workflow_status(session_id)
        status = raw.get("status", "unknown")
        result = {
            "status": {
                "RUNNING": "working",
                "INPUT": "input_required",
                "SUCCESS": "completed",
                "FAILED": "failed",
            }.get(status, status),
        }
        if status == "INPUT":
            result["input_schema"] = raw.get("input_schema")
            result["message_id"] = raw.get("message_id")
            result["node_id"] = raw.get("node_id")
        if status == "SUCCESS":
            result["result"] = raw.get("result")
        if status == "FAILED":
            result["error"] = raw.get("error")
        return result

    async def continue_workflow(self, task_id: str, inputs: dict,
                                 message_id: str) -> None:
        status = await self.get_workflow_status(task_id)
        node_id = status.get("node_id")
        if not node_id:
            raise AirwayError("MISSING_NODE_ID",
                              "Call workflow_status first to get node_id")
        nested_input = {node_id: inputs}
        await self.v2.invoke_workflow(
            workflow_id="",
            session_id=task_id,
            input_data=nested_input,
            message_id=int(message_id),
        )
```

## 7. 配置

```yaml
# config.yaml
server:
  host: "0.0.0.0"
  port: 8090

bisheng:
  v2_api_url: "http://bisheng-backend:7860/api/v2"
  v1_api_url: "http://bisheng-backend:7860/api/v1"
  admin_username: "${BISHENG_ADMIN_USER}"
  admin_password: "${BISHENG_ADMIN_PASS}"
  redis_url: "redis://redis:6379/0"
  knowledge_bases:
    - name: "产品文档"
      assistant_id: "asst_xxx"
      kb_id: "kb_xxx"
```

## 8. MVP 不做的事

| 机制 | 为什么不做 | 替代 |
|------|----------|------|
| SSE 消费 | Agent 轮询即可 | `workflow_status` 主动查询 |
| Webhook 通知 | 需要事件桥接 + Outbox 基础设施 | Agent 轮询 |
| PG 数据库 | 无状态代理不需要持久化 | Bisheng Redis 是 SSOT |
| Outbox Pattern | 无 Webhook 场景不需要 | — |
| Event Store / 审计 | 先跑通功能，再加可观测性 | 结构化日志 |
| Identity Gateway | 只有一个 default_operator | 硬编码 |
| 乐观锁 / 分布式锁 | 单实例无状态 | — |
| TaskRecovery / HealthCheck | 无后台任务，无需恢复 | — |
| RAGRuntime 接口抽象 | 只有一个 Adapter | 直接实现 |

## 9. 资源估算

| 组件 | 配置 |
|------|------|
| Airway（无状态 MCP 代理） | 0.5C/512M |
| 无额外 PG | — |
| **增量** | **几乎为零** |

## 10. Agent Skill 文件

```markdown
# RAG 技能

## 知识库查询
用户提到企业内部知识时，调用 rag_query。
knowledge_base 映射：产品相关 → "产品文档"

## Workflow 流程
1. workflow_start 启动，返回 task_id
2. 每 30 秒调用 workflow_status 检查进度
3. status 为 input_required 时，读取 input_schema 构造 inputs，调用 workflow_continue
4. status 为 completed 时，返回结果给用户
5. status 为 failed 时，返回 error 给用户

## 注意
- workflow_continue 必须先调用 workflow_status 获取 node_id
- message_id 来自 workflow_status 的返回值
```

---

## 11. 迭代路线

### v0.1 → v0.2：加 PG + 审计（1-2 天）

**触发条件**：MVP 跑通，需要知道"谁调了什么"

**新增**：
```
airway/
├── db/
│   ├── models.py       # TaskRecord + Event
│   └── database.py     # SQLModel + SQLite/PG
├── event_store.py      # 审计记录
└── task_repo.py        # Task CRUD
```

**变更**：
- `workflow_start` 写 TaskRecord 到 PG
- 每个 MCP Tool 调用写审计事件
- `workflow_status` 优先读 PG 缓存，miss 时查 Bisheng
- 引入 PG（SQLite 也可，单实例足够）

**删除**：无（纯增量）

### v0.2 → v0.3：加 SSE 消费 + Webhook 通知（2-3 天）

**触发条件**：Agent 轮询延迟不可接受，需要实时通知

**新增**：
```
airway/
├── adapters/bisheng/sse_consumer.py  # SSE 消费
├── event_bridge.py                   # 通知（fire-and-forget）
└── outbox_worker.py                  # （可选）Outbox 投递
```

**变更**：
- `workflow_start` 启动后台 SSE 消费
- SSE 消费实时更新 PG 缓存状态
- `input_required` 时直接 HTTP POST Clawith Webhook（fire-and-forget）
- `workflow_status` 读 PG 缓存（fresh < 30s 直接返回）
- Agent 仍可轮询兜底

**关键决策点**：
- Webhook 投递失败率 < 1%？→ fire-and-forget 够用
- Webhook 投递失败率 > 1%？→ 加 Outbox Pattern

### v0.3 → v0.4：加可靠性（按需，2-3 天）

**触发条件**：观测到 SSE 断连率 > 5% 或 Webhook 投递失败率 > 1%

**按数据选择性实现**：

| 观测结果 | 加的机制 |
|---------|---------|
| SSE 断连后状态停滞 | `except BaseException → sync_from_runtime` |
| SSE 假死（无事件） | `_sse_probe` 协程 |
| Webhook dead 堆积 | Outbox + `_replay_dead` |
| Airway 重启丢状态 | `recover_active` |
| 多实例部署 | Redis 分布式锁 |
| SSE 连接泄漏 | `SSEConnectionPool` 信号量 |
| 全局 stale 任务 | `TaskHealthChecker` |

### v0.4 → v0.5：加抽象 + 多后端（按需）

**触发条件**：需要接入第二个 RAG 后端

**新增**：
```
airway/
├── interface/
│   └── rag_runtime.py    # RAGRuntime ABC
├── registry.py           # RuntimeRegistry
├── adapters/
│   ├── dify/             # 新 Adapter
│   └── ragflow/          # 新 Adapter
└── identity.py           # Identity Gateway
```

**变更**：
- `BishengAdapter` 实现 `RAGRuntime` 接口
- `server.py` 通过 Registry 路由
- 不同用户映射到不同 Runtime 身份

## 12. 迭代总览

```
v0.1  MVP           无状态代理 + 轮询          ~3 天
  │
  ▼ 加 PG
v0.2  审计          TaskRecord + EventStore     ~2 天
  │
  ▼ 加 SSE + Webhook
v0.3  实时通知      SSE 消费 + fire-and-forget  ~3 天
  │
  ▼ 按观测数据
v0.4  可靠性加固    按需选择补偿机制            ~2 天
  │
  ▼ 有第二个后端需求时
v0.5  多后端        RAGRuntime + Registry       ~3 天
```
