## 1. BishengAPIClient 扩展

- [x] 1.1 在 BishengAPIClient 新增 `delete()` 方法，支持 HTTP DELETE 请求
- [x] 1.2 在 BishengAPIClient 新增 `upload()` 方法，支持 multipart/form-data 文件上传
- [x] 1.3 编写 `delete()` 和 `upload()` 方法的单元测试

## 2. RAG 工具扩展 — 知识库管理

- [x] 2.1 实现 `knowledge_create` 工具函数：调用 Bisheng `POST /api/v1/knowledge/create`
- [x] 2.2 实现 `knowledge_delete` 工具函数：调用 Bisheng `DELETE /api/v1/knowledge`
- [x] 2.3 实现 `knowledge_file_delete` 工具函数：调用 Bisheng `DELETE /api/v1/knowledge/file/{file_id}`
- [x] 2.4 编写知识库管理工具的单元测试（mock Bisheng API 响应）

## 3. RAG 工具扩展 — 文档上传

- [x] 3.1 实现 `knowledge_upload` 工具函数：base64 解码 + 调用 Bisheng upload API
- [x] 3.2 实现 `knowledge_process` 工具函数：调用 Bisheng `POST /api/v1/knowledge/process`
- [x] 3.3 编写文档上传工具的单元测试（含 base64 解码和 multipart 构造验证）

## 4. MCP Server 注册

- [x] 4.1 在 app.py 注册 5 个新 MCP Tool（knowledge_create、knowledge_delete、knowledge_upload、knowledge_file_delete、knowledge_process），定义参数 JSON Schema
- [x] 4.2 编写集成测试验证新工具注册和调用
