## ADDED Requirements

### Requirement: 知识库列表查询

Airway SHALL 提供名为 `knowledge_list` 的 MCP Tool，返回 Bisheng 中可用的知识库列表。

#### Scenario: 查询知识库列表

- **WHEN** MCP 客户端调用 `knowledge_list` 工具（可选参数：keyword 过滤）
- **THEN** Airway 调用 Bisheng `GET /api/v1/knowledge` API，返回知识库列表（id、name、description、document_count）

#### Scenario: Bisheng API 返回错误

- **WHEN** 调用 `knowledge_list` 时 Bisheng 返回非 2xx 状态码
- **THEN** Airway 返回 MCP 错误响应，包含 Bisheng 的错误信息

### Requirement: 知识库内容检索

Airway SHALL 提供名为 `knowledge_search` 的 MCP Tool，在指定知识库中检索相关内容。

#### Scenario: 关键词检索

- **WHEN** MCP 客户端调用 `knowledge_search` 工具，传入 knowledge_id 和 query 参数
- **THEN** Airway 调用 Bisheng 的 chunk 查询 API，返回匹配的文档片段列表（content、source、score）

#### Scenario: 知识库 ID 不存在

- **WHEN** 调用 `knowledge_search` 时传入不存在的 knowledge_id
- **THEN** Airway 返回 MCP 错误响应，包含 "Knowledge base not found" 信息

### Requirement: 知识库文件列表

Airway SHALL 提供名为 `knowledge_files` 的 MCP Tool，返回指定知识库中的文件列表。

#### Scenario: 查询知识库文件

- **WHEN** MCP 客户端调用 `knowledge_files` 工具，传入 knowledge_id
- **THEN** Airway 调用 Bisheng `GET /api/v1/knowledge/file_list/{knowledge_id}` API，返回文件列表（id、name、status、chunk_num）

### Requirement: Bisheng API 超时处理

Airway 对 Bisheng 的所有 API 调用 SHALL 设置超时时间，超时后返回明确错误。

#### Scenario: API 调用超时

- **WHEN** Bisheng API 在配置的超时时间内未响应
- **THEN** Airway 取消请求并返回 MCP 错误，包含 "Bisheng API timeout" 信息
