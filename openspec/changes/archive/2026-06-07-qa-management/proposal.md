## Why

Bisheng 支持 QA 类型的知识库（结构化问答对），比文档型知识库更适合 FAQ 场景。当前 Airway 只代理了文档型知识库的操作，Agent 无法管理 QA 知识库中的问答对。用户常说"帮我更新 FAQ"，Agent 需要对应的工具来添加、查询和删除 QA 条目。

## What Changes

- 新增 `qa_list` MCP Tool：调用 Bisheng `GET /api/v1/knowledge/qa/list/{qa_knowledge_id}` 列出 QA 条目
- 新增 `qa_add` MCP Tool：调用 Bisheng `POST /api/v1/knowledge/qa/add` 添加 QA 条目
- 新增 `qa_delete` MCP Tool：调用 Bisheng `DELETE /api/v1/knowledge/qa/delete` 删除 QA 条目

## Capabilities

### New Capabilities

- `qa-management`: QA 知识库管理能力，支持结构化问答对的查询、添加和删除

### Modified Capabilities

（无）

## Impact

- **代码**: `rag_tools.py` 新增 3 个工具函数；`app.py` 注册 3 个新 MCP tools
- **API**: 3 个新 MCP Tool 暴露给 Clawith Agent
- **Bisheng**: 仅调用现有 REST API，无代码修改
- **测试**: 新增单元测试
