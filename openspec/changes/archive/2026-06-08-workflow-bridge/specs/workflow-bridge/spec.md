# Spec: workflow-bridge

## Overview

Bridge Bisheng Workflow REST API via MCP tools. Enables Clawith Agent to list, execute, and inspect workflows.

### Requirement: 工作流列表查询

- Tool 暴露 `workflow_list` MCP Tool
- 调用 `GET /api/v1/workflow/list`，支持 keyword、page_size、page_num 可选参数
- 返回精简字段：id, name, description, status, flow_type
- 错误时返回 `{"error": ..., "status": ...}` JSON

### Requirement: 工作流执行

- Tool 暴露 `workflow_run` MCP Tool
- 调用 `POST /api/v2/workflow/invoke`，`stream=false` 模式
- 参数：workflow_id（必填）、input（可选 dict）、session_id（可选）
- 返回 session_id 和 outputs 列表
- 超时使用 settings.api_timeout

### Requirement: 单节点执行

- Tool 暴露 `workflow_run_once` MCP Tool
- 调用 `POST /api/v1/workflow/run_once`
- 参数：workflow_id（必填）、node_input（可选 dict）、node_data（可选 dict）
- 返回 outputs 列表
