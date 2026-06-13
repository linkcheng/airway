# Design: workflow-bridge

## Architecture

```
Clawith Agent → MCP Tool → Airway → Bisheng REST API
                              ↓
                   workflow_list   → GET  /api/v1/workflow/list
                   workflow_run    → POST /api/v2/workflow/invoke (stream=false)
                   workflow_run_once → POST /api/v1/workflow/run_once
```

## Decision: REST over WebSocket

Bisheng Workflow 交互有两条路径：

1. **WebSocket chat** — 实时双向通信，支持多轮对话
2. **REST invoke** — 一次性执行，返回完整结果

选择 REST invoke：
- MCP Tool 是同步请求-响应模型，无法维持 WebSocket 长连接
- Agent 等待完整结果更可靠
- `invoke` 的 `stream=false` 模式正是为此设计

## API Mapping

### workflow_list

| MCP Tool Param | Bisheng API Param | 说明 |
|---|---|---|
| keyword (optional) | name | 模糊搜索 |
| page_size (optional) | page_size | 默认 10 |
| page_num (optional) | page_num | 默认 1 |

Response 精简：`id`, `name`, `description`, `status`, `flow_type`

### workflow_run

| MCP Tool Param | Bisheng API Param | 说明 |
|---|---|---|
| workflow_id | workflow_id | 工作流 ID |
| input (optional) | input | 工作流输入 |
| session_id (optional) | session_id | 续接会话 |

Response 精简：`session_id`, `outputs` (key-value list)

### workflow_run_once

| MCP Tool Param | Bisheng API Param | 说明 |
|---|---|---|
| workflow_id | workflow_id | 工作流 ID |
| node_input (optional) | node_input | 节点输入 |
| node_data (optional) | node_data | 节点配置 |

Response 精简：`outputs` (key-value list)

## Error Handling

- 404: 工作流不存在
- 500: 工作流执行失败
- 超时：使用现有 `api_timeout` 配置

## No Existing Spec Modified

此变更不修改已有 spec，新增独立的 `workflow-bridge` spec。
