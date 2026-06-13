## ADDED Requirements

### Requirement: 文件上传到知识库

Airway SHALL 提供名为 `knowledge_upload` 的 MCP Tool，上传文件到指定的 Bisheng 知识库。

#### Scenario: 上传单个文件

- **WHEN** MCP 客户端调用 `knowledge_upload` 工具，传入 knowledge_id、file_name 和 file_content_base64 参数
- **THEN** Airway 解码 base64 内容，调用 Bisheng `POST /api/v1/knowledge/upload/{knowledge_id}` 构造 multipart/form-data 请求上传文件，返回上传结果（file_id、file_name）

#### Scenario: 上传文件 base64 解码失败

- **WHEN** 调用 `knowledge_upload` 时 file_content_base64 不是有效的 base64 编码
- **THEN** Airway 返回 MCP 错误响应，包含 "Invalid base64 encoding" 信息

#### Scenario: 目标知识库不存在

- **WHEN** 调用 `knowledge_upload` 时传入不存在的 knowledge_id
- **THEN** Airway 返回 MCP 错误响应，包含 Bisheng 返回的错误信息

### Requirement: 触发文档解析处理

Airway SHALL 提供名为 `knowledge_process` 的 MCP Tool，触发已上传文件的解析处理（分块、向量化）。

#### Scenario: 触发文件处理

- **WHEN** MCP 客户端调用 `knowledge_process` 工具，传入 knowledge_id 和 file_ids 参数
- **THEN** Airway 调用 Bisheng `POST /api/v1/knowledge/process`，返回处理任务状态

#### Scenario: 文件处理 API 返回错误

- **WHEN** 调用 `knowledge_process` 时 Bisheng 返回非 2xx 状态码
- **THEN** Airway 返回 MCP 错误响应，包含 Bisheng 的错误信息
