# qa-management Specification

## Purpose
TBD - created by archiving change qa-management. Update Purpose after archive.
## Requirements
### Requirement: QA 条目列表查询

Airway SHALL 提供名为 `qa_list` 的 MCP Tool，返回指定 QA 知识库中的问答对列表。

#### Scenario: 查询 QA 列表

- **WHEN** MCP 客户端调用 `qa_list` 工具，传入 knowledge_id 参数
- **THEN** Airway 调用 Bisheng `GET /api/v1/knowledge/qa/list/{knowledge_id}` API，返回 QA 条目列表（id、question、answer）

#### Scenario: 非 QA 类型的知识库

- **WHEN** 调用 `qa_list` 时传入文档型知识库的 knowledge_id
- **THEN** Airway 返回 Bisheng 的错误响应

### Requirement: QA 条目添加

Airway SHALL 提供名为 `qa_add` 的 MCP Tool，向指定 QA 知识库添加问答对。

#### Scenario: 添加 QA 条目

- **WHEN** MCP 客户端调用 `qa_add` 工具，传入 knowledge_id、question 和 answer 参数
- **THEN** Airway 调用 Bisheng `POST /api/v1/knowledge/qa/add` API，返回创建的 QA 条目（id、question、answer）

### Requirement: QA 条目删除

Airway SHALL 提供名为 `qa_delete` 的 MCP Tool，删除指定的 QA 问答对。

#### Scenario: 删除 QA 条目

- **WHEN** MCP 客户端调用 `qa_delete` 工具，传入 qa_id 参数
- **THEN** Airway 调用 Bisheng `DELETE /api/v1/knowledge/qa/delete` API，返回删除确认

