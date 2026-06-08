# v2 Workflow 工具设计方案

> 日期：2026-06-08
> 状态：待审阅
> 前置文档：[airway-mcp-server-design.md](./2026-06-05-airway-mcp-server-design.md)、[mvp-hardening-design.md](./2026-06-07-mvp-hardening-design.md)

## 1. 目标

在 Airway MCP Server 中新增 3 个 Workflow 工具，让 Clawith Agent 能够查询、执行 Bisheng Workflow 并获取结果。

## 2. 方案

**异步执行 + 同步等待（方案 A）：** `workflow_run` 调用 Bisheng v2 invoke API（`stream=false`），同步阻塞等待最终结果。执行结果缓存在 Airway 进程内存中，`workflow_status` 查询缓存。

不使用 SSE 流式、不做 fire-and-forget + 轮询、不引入外部状态存储。

## 3. 工具定义

| 工具 | 签名 | Bisheng API |
|------|------|-------------|
| `workflow_list` | `(ctx, page=1, size=10, name?)` | `GET /api/v1/workflow/list` |
| `workflow_run` | `(ctx, workflow_id, input?, overrides?)` | `POST /api/v2/workflow/invoke` (stream=false) |
| `workflow_status` | `(ctx, workflow_id, session_id)` | Airway 内存缓存查询 |

### 3.1 workflow_list

- 输入：`page: int = 1`、`size: int = 10`、`name: str | None = None`（模糊搜索）
- 输出：`{"list": [{ id, name, description, flow_type, status }], "total": int}`
- 映射到 `GET /api/v1/workflow/list`，参数 `page_num`、`page_size`、`name`

### 3.2 workflow_run

- 输入：`workflow_id: str`（必填）、`input: str | None`（用户输入）、`overrides: str | None`（JSON 字符串，节点参数覆盖）
- 输出：`{ session_id, result }`（Bisheng 返回的 events 中提取最终输出）
- 映射到 `POST /api/v2/workflow/invoke`，body: `{"workflow_id": ..., "stream": false, "input": ..., "override": ...}`
- 执行结果按 `session_id` 缓存到 `AirwayTools._results` 内存 dict
- `overrides` 参数为 JSON 字符串，Airway 在 `server.py` 层 parse 为 dict；parse 失败返回错误信息

### 3.3 workflow_status

- 输入：`workflow_id: str`、`session_id: str`
- 输出：缓存中存在则返回结果 JSON，不存在则返回 `{"status": "not_found"}`
- 查询 `AirwayTools._results[session_id]`，纯内存操作，不调 Bisheng API

## 4. 数据流

```
Agent → workflow_run(workflow_id, input)
  → server.py: _resolve_user_id(ctx), parse overrides JSON
  → AirwayTools.workflow_run(user_id, workflow_id, ...)
    → _with_retry(user_id, fn)
      → BishengClient.workflow_invoke(token, workflow_id, input, overrides)
      → Bisheng 同步返回 {session_id, events: [...]}
    → self._results[session_id] = result
    → json.dumps(result)
  → 返回给 Agent
```

## 5. 模块改动

不新增文件，修改 3 个现有文件：

### 5.1 client/bisheng.py

新增 2 个方法：

```python
async def workflow_list(self, token: str, page: int = 1, size: int = 10, name: str | None = None) -> dict:
    params = {"page_num": page, "page_size": size}
    if name:
        params["name"] = name
    return await self._request("GET", "/api/v1/workflow/list", token, params=params)

async def workflow_invoke(self, token: str, workflow_id: str, *, input: str | None = None, overrides: dict | None = None) -> dict:
    body: dict = {"workflow_id": workflow_id, "stream": False}
    if input:
        body["input"] = input
    if overrides:
        body["override"] = overrides
    return await self._request("POST", "/api/v2/workflow/invoke", token, json_body=body)
```

### 5.2 mcp/tools.py

新增 `__init__` 中 `_results: dict[str, dict] = {}` 缓存 + 3 个方法：

```python
async def workflow_list(self, user_id: str, page: int = 1, size: int = 10, name: str | None = None) -> str:
    async def _do(token: str):
        result = await self._client.workflow_list(token, page=page, size=size, name=name)
        return json.dumps(result, ensure_ascii=False)
    return await self._with_retry(user_id, _do)

async def workflow_run(self, user_id: str, workflow_id: str, *, input: str | None = None, overrides: dict | None = None) -> str:
    async def _do(token: str):
        result = await self._client.workflow_invoke(token, workflow_id, input=input, overrides=overrides)
        session_id = result.get("session_id", "")
        if session_id:
            self._results[session_id] = result
        return json.dumps(result, ensure_ascii=False)
    return await self._with_retry(user_id, _do)

async def workflow_status(self, user_id: str, workflow_id: str, session_id: str) -> str:
    result = self._results.get(session_id)
    if result is None:
        return json.dumps({"status": "not_found"}, ensure_ascii=False)
    return json.dumps(result, ensure_ascii=False)
```

### 5.3 server.py

新增 3 个 `@mcp.tool()` 端点，`workflow_run` 中处理 overrides JSON parse。

## 6. 错误处理

| 场景 | 处理方式 |
|------|----------|
| Workflow 不存在 | Bisheng 返回错误 → 透传 |
| 执行超时 | httpx 30s timeout → 异常返回 |
| session_id 未找到 | `workflow_status` 返回 `{"status": "not_found"}` |
| overrides JSON 解析失败 | `workflow_run` 返回错误信息字符串 |

## 7. 不做的事

- 不做 Workflow 输入参数 schema 校验（透传给 Bisheng）
- 不做执行结果结构化解析（原样 JSON 返回）
- 不缓存 `workflow_list` 结果
- 不做 SSE 流式响应
- 不做 fire-and-forget 模式
- 不引入外部状态存储（Redis/DB）

## 8. 测试策略

| 测试文件 | 用例 |
|----------|------|
| `test_client.py` 扩展 | `test_workflow_list`、`test_workflow_invoke` |
| `test_tools.py` 扩展 | `test_workflow_list`、`test_workflow_run_caches_result`、`test_workflow_status_found`、`test_workflow_status_not_found`、`test_workflow_run_invalid_overrides` |

测试 Mock BishengClient 返回，验证 AirwayTools 包装逻辑（retry、缓存、错误处理）。

## 9. 开发顺序

1. `client/bisheng.py` — 新增 `workflow_list`、`workflow_invoke` 方法 + 测试
2. `mcp/tools.py` — 新增 3 个 tool 方法 + 结果缓存 + 测试
3. `server.py` — 新增 3 个 MCP tool 端点
