## Context

Airway MVP 已实现 3 个只读 RAG 工具（knowledge_list、knowledge_search、knowledge_files），通过 BishengAPIClient 封装 HTTP 调用。客户端当前只支持 GET 和 POST JSON 请求，不支持文件上传（multipart/form-data）和 DELETE 方法。

Bisheng 的文档处理流程：upload（上传到临时存储）→ process（解析、分块、向量化）。文件通过 multipart form 上传，Bisheng 返回 file_id 后，调用 process API 触发异步解析。

## Goals / Non-Goals

**Goals:**
- 补全知识库写操作：创建/删除知识库、上传/删除文件
- 实现文档上传到处理的一站式流程
- 复用现有 BishengAPIClient 的认证和错误处理机制
- 所有新工具遵循已有 MCP tool 模式（参数 → 调用 → JSON 返回）

**Non-Goals:**
- 不实现文档预览（preview）和分块编辑
- 不实现 QA 知识库管理
- 不实现知识库权限控制
- 不实现上传进度回调

## Decisions

### D1: BishengAPIClient 扩展方式

新增 `upload()` 和 `delete()` 方法，复用已有的认证（cookie 注入）和 token 刷新机制。`upload()` 接收文件字节流和文件名，构造 multipart/form-data 请求。

### D2: 上传流程设计 — 两步操作

拆分为 `knowledge_upload`（上传文件）和 `knowledge_process`（触发解析）两个工具，而非合并为一个。原因：
- Agent 可能需要上传多个文件后批量处理
- Bisheng 的 upload 和 process 是独立 API
- 给 Agent 更多控制粒度

### D3: 文件传输方式

MCP tool 参数中文件以 base64 编码字符串传入，Airway 解码后构造 multipart 请求上传。这是 MCP 协议下传输二进制数据的标准方式。

### D4: MCP Tool 参数设计

- `knowledge_create(name, description)` → 返回 knowledge_id
- `knowledge_delete(knowledge_id)` → 返回确认
- `knowledge_upload(knowledge_id, file_name, file_content_base64)` → 返回 file_id 列表
- `knowledge_file_delete(file_id)` → 返回确认
- `knowledge_process(knowledge_id, file_ids)` → 返回处理任务状态

## Risks / Trade-offs

- **[大文件传输]** → base64 编码增大 33% 体积。MVP 阶段限制单文件 50MB，后续可探索 streaming
- **[异步处理]** → Bisheng process 是异步的，Airway 只返回"已触发"，Agent 需轮询 knowledge_files 检查状态
- **[批量上传]** → 单次 upload 调用只上传一个文件，多文件需多次调用。保持简单
