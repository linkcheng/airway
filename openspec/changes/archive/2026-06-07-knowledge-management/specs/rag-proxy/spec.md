## ADDED Requirements

### Requirement: 知识库创建

Airway SHALL 提供名为 `knowledge_create` 的 MCP Tool，在 Bisheng 中创建新知识库。

#### Scenario: 创建知识库

- **WHEN** MCP 客户端调用 `knowledge_create` 工具，传入 name 和 description 参数
- **THEN** Airway 调用 Bisheng `POST /api/v1/knowledge/create` API，返回创建的知识库信息（knowledge_id、name）

#### Scenario: 创建知识库名称重复

- **WHEN** 调用 `knowledge_create` 时 Bisheng 返回名称冲突错误
- **THEN** Airway 返回 MCP 错误响应，包含 "Knowledge base name already exists" 信息

### Requirement: 知识库删除

Airway SHALL 提供名为 `knowledge_delete` 的 MCP Tool，删除指定的 Bisheng 知识库。

#### Scenario: 删除知识库

- **WHEN** MCP 客户端调用 `knowledge_delete` 工具，传入 knowledge_id 参数
- **THEN** Airway 调用 Bisheng `DELETE /api/v1/knowledge` API，返回删除确认

#### Scenario: 删除不存在的知识库

- **WHEN** 调用 `knowledge_delete` 时传入不存在的 knowledge_id
- **THEN** Airway 返回 MCP 错误响应，包含 "Knowledge base not found" 信息

### Requirement: 知识库文件删除

Airway SHALL 提供名为 `knowledge_file_delete` 的 MCP Tool，删除知识库中的指定文件。

#### Scenario: 删除知识库文件

- **WHEN** MCP 客户端调用 `knowledge_file_delete` 工具，传入 file_id 参数
- **THEN** Airway 调用 Bisheng `DELETE /api/v1/knowledge/file/{file_id}` API，返回删除确认

#### Scenario: 删除不存在的文件

- **WHEN** 调用 `knowledge_file_delete` 时传入不存在的 file_id
- **THEN** Airway 返回 MCP 错误响应，包含 "File not found" 信息
