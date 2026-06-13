## 1. QA 工具实现

- [x] 1.1 实现 `qa_list` 工具函数：调用 Bisheng `GET /api/v1/knowledge/qa/list/{id}`
- [x] 1.2 实现 `qa_add` 工具函数：调用 Bisheng `POST /api/v1/knowledge/qa/add`
- [x] 1.3 实现 `qa_delete` 工具函数：调用 Bisheng `DELETE /api/v1/knowledge/qa/delete`

## 2. MCP Server 注册

- [x] 2.1 在 app.py 注册 3 个新 MCP Tool（qa_list、qa_add、qa_delete）

## 3. 测试

- [x] 3.1 编写 QA 工具单元测试（mock Bisheng API 响应）
