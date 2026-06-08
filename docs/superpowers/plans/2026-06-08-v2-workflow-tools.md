# v2 Workflow 工具实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Airway MCP Server 中新增 workflow_list、workflow_run、workflow_status 三个工具，让 Agent 能查询和执行 Bisheng Workflow。

**Architecture:** 遵循已有分层模式：BishengClient 封装 HTTP → AirwayTools 包装业务逻辑（retry + 缓存）→ server.py 暴露 MCP tool。workflow_run 同步调用 Bisheng invoke API（stream=false），结果缓存在 AirwayTools 内存 dict 中供 workflow_status 查询。

**Tech Stack:** Python 3.12 / httpx / pytest / pytest-asyncio / pytest-httpx

---

### Task 1: BishengClient workflow 方法

**Files:**
- Modify: `src/airway/client/bisheng.py:78-102`（在 `knowledge_search` 方法后新增 2 个方法）
- Test: `tests/test_client.py:155`（在文件末尾追加测试）

- [ ] **Step 1: 写 workflow_list 失败测试**

在 `tests/test_client.py` 末尾追加：

```python
WORKFLOW_LIST_RESPONSE = {
    "code": 200,
    "data": {
        "list": [
            {"id": "w1", "name": "数据处理", "description": "ETL 流程", "flow_type": 10, "status": 1},
            {"id": "w2", "name": "报告生成", "description": "自动生成报告", "flow_type": 10, "status": 1},
        ],
        "total": 2,
    },
}


@pytest.mark.asyncio
async def test_workflow_list(client: BishengClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://bisheng-test:7860/api/v1/workflow/list?page_num=1&page_size=10",
        json=WORKFLOW_LIST_RESPONSE,
    )
    result = await client.workflow_list(token="test_token")
    assert result["total"] == 2
    assert len(result["list"]) == 2
    assert result["list"][0]["name"] == "数据处理"


@pytest.mark.asyncio
async def test_workflow_list_with_name_filter(client: BishengClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://bisheng-test:7860/api/v1/workflow/list?page_num=1&page_size=10&name=%E6%95%B0%E6%8D%AE",
        json={
            "code": 200,
            "data": {
                "list": [
                    {"id": "w1", "name": "数据处理", "description": "ETL 流程", "flow_type": 10, "status": 1},
                ],
                "total": 1,
            },
        },
    )
    result = await client.workflow_list(token="test_token", name="数据")
    assert result["total"] == 1
    assert result["list"][0]["name"] == "数据处理"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/zhenglong/ai-native/rag/airway/superpower && ../.venv/bin/python -m pytest tests/test_client.py::test_workflow_list -v`
Expected: FAIL — `AttributeError: 'BishengClient' object has no attribute 'workflow_list'`

- [ ] **Step 3: 实现 workflow_list 和 workflow_invoke**

在 `src/airway/client/bisheng.py` 的 `knowledge_search` 方法后（第 102 行之后）追加：

```python
    async def workflow_list(self, token: str, page: int = 1, size: int = 10, name: str | None = None) -> dict:
        params: dict = {"page_num": page, "page_size": size}
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

- [ ] **Step 4: 运行 workflow_list 测试**

Run: `cd /Users/zhenglong/ai-native/rag/airway/superpower && ../.venv/bin/python -m pytest tests/test_client.py::test_workflow_list tests/test_client.py::test_workflow_list_with_name_filter -v`
Expected: PASS

- [ ] **Step 5: 写 workflow_invoke 测试**

在 `tests/test_client.py` 末尾追加：

```python
WORKFLOW_INVOKE_RESPONSE = {
    "code": 200,
    "data": {
        "session_id": "sess_abc123",
        "events": [
            {"event": "output_msg", "data": {"message": "处理完成", "output_key": "result"}},
        ],
    },
}


@pytest.mark.asyncio
async def test_workflow_invoke(client: BishengClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://bisheng-test:7860/api/v2/workflow/invoke",
        json=WORKFLOW_INVOKE_RESPONSE,
    )
    result = await client.workflow_invoke(token="test_token", workflow_id="w1")
    assert result["session_id"] == "sess_abc123"
    assert len(result["events"]) == 1


@pytest.mark.asyncio
async def test_workflow_invoke_with_input(client: BishengClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://bisheng-test:7860/api/v2/workflow/invoke",
        json=WORKFLOW_INVOKE_RESPONSE,
    )
    result = await client.workflow_invoke(
        token="test_token", workflow_id="w1",
        input="查询数据", overrides={"node_1": {"param": "value"}},
    )
    assert result["session_id"] == "sess_abc123"
```

- [ ] **Step 6: 运行全量测试确认无回归**

Run: `cd /Users/zhenglong/ai-native/rag/airway/superpower && ../.venv/bin/python -m pytest tests/ -v`
Expected: 所有测试 PASS

- [ ] **Step 7: 提交**

```bash
cd /Users/zhenglong/ai-native/rag/airway/superpower
git add src/airway/client/bisheng.py tests/test_client.py
git commit -m "feat: BishengClient workflow_list + workflow_invoke 方法"
```

---

### Task 2: AirwayTools workflow 方法 + 结果缓存

**Files:**
- Modify: `src/airway/mcp/tools.py:9-50`（`__init__` 加缓存，新增 3 个方法）
- Test: `tests/test_tools.py`（修改 MockBisheng，追加测试）

- [ ] **Step 1: 更新 MockBisheng 并写 workflow_list tool 测试**

修改 `tests/test_tools.py` 中的 `MockBisheng` 类（约第 23-42 行），在 `knowledge_search` 方法后追加：

```python
        async def workflow_list(self, token, page=1, size=10, name=None):
            return {
                "list": [
                    {"id": "w1", "name": "数据处理", "description": "ETL", "flow_type": 10, "status": 1},
                ],
                "total": 1,
            }

        async def workflow_invoke(self, token, workflow_id, *, input=None, overrides=None):
            return {
                "session_id": "sess_test",
                "events": [{"event": "output_msg", "data": {"message": "完成"}}],
            }
```

在文件末尾追加：

```python
@pytest.mark.asyncio
async def test_workflow_list_tool(tools: AirwayTools):
    result = await tools.workflow_list(user_id="u_test", page=1, size=10)
    parsed = json.loads(result)
    assert parsed["total"] == 1
    assert parsed["list"][0]["name"] == "数据处理"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/zhenglong/ai-native/rag/airway/superpower && ../.venv/bin/python -m pytest tests/test_tools.py::test_workflow_list_tool -v`
Expected: FAIL — `AttributeError: 'AirwayTools' object has no attribute 'workflow_list'`

- [ ] **Step 3: 实现 AirwayTools workflow 方法**

修改 `src/airway/mcp/tools.py`：

1. 在 `__init__` 中追加结果缓存：

```python
    def __init__(self, proxy: AuthProxy, client: BishengClient):
        self._proxy = proxy
        self._client = client
        self._results: dict[str, dict] = {}
```

2. 在文件末尾（`knowledge_search` 方法后）追加 3 个方法：

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

- [ ] **Step 4: 运行 workflow_list tool 测试**

Run: `cd /Users/zhenglong/ai-native/rag/airway/superpower && ../.venv/bin/python -m pytest tests/test_tools.py::test_workflow_list_tool -v`
Expected: PASS

- [ ] **Step 5: 写 workflow_run 和 workflow_status 测试**

在 `tests/test_tools.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_workflow_run_caches_result(tools: AirwayTools):
    result = await tools.workflow_run(user_id="u_test", workflow_id="w1")
    parsed = json.loads(result)
    assert parsed["session_id"] == "sess_test"
    assert "sess_test" in tools._results


@pytest.mark.asyncio
async def test_workflow_status_found(tools: AirwayTools):
    await tools.workflow_run(user_id="u_test", workflow_id="w1")
    result = await tools.workflow_status(user_id="u_test", workflow_id="w1", session_id="sess_test")
    parsed = json.loads(result)
    assert parsed["session_id"] == "sess_test"


@pytest.mark.asyncio
async def test_workflow_status_not_found(tools: AirwayTools):
    result = await tools.workflow_status(user_id="u_test", workflow_id="w1", session_id="nonexistent")
    parsed = json.loads(result)
    assert parsed["status"] == "not_found"


@pytest.mark.asyncio
async def test_workflow_run_with_overrides(tools: AirwayTools):
    result = await tools.workflow_run(
        user_id="u_test", workflow_id="w1",
        input="查询", overrides={"node_1": {"key": "val"}},
    )
    parsed = json.loads(result)
    assert parsed["session_id"] == "sess_test"
```

- [ ] **Step 6: 运行全量测试确认无回归**

Run: `cd /Users/zhenglong/ai-native/rag/airway/superpower && ../.venv/bin/python -m pytest tests/ -v`
Expected: 所有测试 PASS

- [ ] **Step 7: 提交**

```bash
cd /Users/zhenglong/ai-native/rag/airway/superpower
git add src/airway/mcp/tools.py tests/test_tools.py
git commit -m "feat: AirwayTools workflow_list/run/status 方法 + 结果缓存"
```

---

### Task 3: Server workflow MCP tool 端点

**Files:**
- Modify: `src/airway/server.py:1-120`（添加 import json，追加 3 个 tool 端点）

- [ ] **Step 1: 添加 import json**

在 `src/airway/server.py` 文件顶部，`import argparse` 之前追加：

```python
import json
```

- [ ] **Step 2: 新增 3 个 workflow tool 端点**

在 `src/airway/server.py` 的 `knowledge_search` 函数后（约第 97 行之后）追加：

```python
@mcp.tool()
async def workflow_list(ctx: Context, page: int = 1, size: int = 10, name: str | None = None) -> str:
    """列出可用的 Workflow。name 参数可模糊搜索。"""
    user_id = _resolve_user_id(ctx)
    return await _get_tools().workflow_list(user_id, page=page, size=size, name=name)


@mcp.tool()
async def workflow_run(ctx: Context, workflow_id: str, input: str | None = None, overrides: str | None = None) -> str:
    """执行 Workflow。workflow_id 是 Bisheng Workflow ID，input 是用户输入，overrides 是节点参数覆盖（JSON 字符串）。"""
    user_id = _resolve_user_id(ctx)
    overrides_dict = None
    if overrides:
        try:
            overrides_dict = json.loads(overrides)
        except json.JSONDecodeError:
            return json.dumps({"error": "overrides 不是有效的 JSON"}, ensure_ascii=False)
    return await _get_tools().workflow_run(user_id, workflow_id, input=input, overrides=overrides_dict)


@mcp.tool()
async def workflow_status(ctx: Context, workflow_id: str, session_id: str) -> str:
    """查询 Workflow 执行结果。session_id 来自 workflow_run 的返回。"""
    user_id = _resolve_user_id(ctx)
    return await _get_tools().workflow_status(user_id, workflow_id=workflow_id, session_id=session_id)
```

- [ ] **Step 3: 验证 server 可以正常导入**

Run: `cd /Users/zhenglong/ai-native/rag/airway/superpower && ../.venv/bin/python -c "from airway.server import mcp; print('OK')"`
Expected: 输出 `OK`

- [ ] **Step 4: 运行全量测试确认无回归**

Run: `cd /Users/zhenglong/ai-native/rag/airway/superpower && ../.venv/bin/python -m pytest tests/ -v`
Expected: 所有测试 PASS

- [ ] **Step 5: 提交**

```bash
cd /Users/zhenglong/ai-native/rag/airway/superpower
git add src/airway/server.py
git commit -m "feat: Server workflow_list/run/status MCP tool 端点"
```
