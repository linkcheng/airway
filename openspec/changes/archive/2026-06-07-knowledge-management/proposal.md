## Why

MVP 只暴露了知识库的读操作（list、search、files），Clawith Agent 无法自主管理知识库内容——创建知识库、上传文档、处理文档、删除资源都需要人工在 Bisheng UI 操作。这打破了 Agent 自治闭环：当用户对 Agent 说"帮我建一个产品文档知识库并上传这些 PDF"，Agent 没有对应的 MCP 工具可用。

## What Changes

- 新增 `knowledge_create` MCP Tool：调用 Bisheng `POST /api/v1/knowledge/create` 创建知识库
- 新增 `knowledge_delete` MCP Tool：调用 Bisheng `DELETE /api/v1/knowledge` 删除知识库
- 新增 `knowledge_upload` MCP Tool：调用 Bisheng `POST /api/v1/knowledge/upload/{id}` 上传文件到知识库
- 新增 `knowledge_file_delete` MCP Tool：调用 Bisheng `DELETE /api/v1/knowledge/file/{id}` 删除知识库文件
- 新增 `knowledge_process` MCP Tool：调用 Bisheng `POST /api/v1/knowledge/process` 触发文档解析处理
- 扩展 `BishengAPIClient` 支持 multipart/form-data 文件上传和 DELETE 方法

## Capabilities

### New Capabilities

- `doc-upload`: 文档上传代理能力，支持通过 MCP 工具上传文件到 Bisheng 知识库并触发文档解析处理

### Modified Capabilities

- `rag-proxy`: 扩展知识库管理工具，新增知识库创建、删除和文件删除能力

## Impact

- **代码**: `rag_tools.py` 新增 5 个工具函数；`bisheng_client.py` 新增 `upload` 和 `delete` 方法；`app.py` 注册新 MCP tools
- **API**: 5 个新 MCP Tool 暴露给 Clawith Agent
- **Bisheng**: 仅调用现有 REST API，无代码修改
- **依赖**: 无新依赖，httpx 已支持 multipart upload
- **测试**: 新增单元测试覆盖所有新工具和客户端方法
