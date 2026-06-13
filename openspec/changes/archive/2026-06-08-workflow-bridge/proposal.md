# Proposal: workflow-bridge

## Problem

Clawith Agent 无法调用 Bisheng 的 Workflow 能力。Agent 需要能够列出可用工作流、执行工作流并获取结果，以实现 RAG + Workflow 的复合场景（如：先检索知识库，再调用工作流生成报告）。

## Solution

在 Airway MCP Server 中新增 3 个 Workflow 工具，桥接 Bisheng Workflow REST API：

1. **workflow_list** — 列出可用工作流（调用 `GET /api/v1/workflow/list`）
2. **workflow_run** — 执行完整工作流并返回结果（调用 `POST /api/v2/workflow/invoke`，非流式模式）
3. **workflow_run_once** — 执行工作流中的单个节点（调用 `POST /api/v1/workflow/run_once`）

## Why not WebSocket

Bisheng Workflow 的主要交互方式是 WebSocket（`/api/v1/workflow/chat/{workflow_id}`），但 MCP 协议是请求-响应模型，不支持长连接。因此：

- 使用 REST API 的 `run_once` 和 `invoke`（非流式）端点
- `invoke` 端点支持 `stream=false`，同步返回完整结果
- 不桥接 WebSocket chat — 超出 MCP 工具的能力范围

## Impact

- 新增 3 个 MCP Tool
- `rag_tools.py` 新增 3 个工具函数
- `app.py` 注册 3 个新 Tool
- 不影响已有的 11 个工具
