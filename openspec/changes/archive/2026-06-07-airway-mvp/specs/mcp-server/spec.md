## ADDED Requirements

### Requirement: MCP SSE Server 启动

Airway SHALL 作为 MCP Server 通过 SSE transport 对外提供服务，监听配置的端口。

#### Scenario: 正常启动 MCP Server

- **WHEN** Airway 启动并加载配置
- **THEN** MCP Server 在配置的 host:port 上监听 SSE 连接，日志输出启动信息

#### Scenario: 配置缺失时拒绝启动

- **WHEN** 必要配置项（Bisheng API URL、service account token）缺失
- **THEN** Airway 启动失败并输出明确的错误信息

### Requirement: MCP Tool 注册

Airway SHALL 向 MCP 客户端注册可用的 RAG 工具列表，每个工具包含名称、描述和参数 schema。

#### Scenario: Clawith 连接后获取工具列表

- **WHEN** Clawith MCP 客户端连接到 Airway 并请求 tools/list
- **THEN** 返回包含 `knowledge_list`、`knowledge_search` 等工具的列表，每个工具有 JSON Schema 定义参数

### Requirement: MCP Tool 调用分发

Airway SHALL 接收 MCP tool 调用请求，路由到对应的处理函数，并返回结果。

#### Scenario: 调用已注册的工具

- **WHEN** MCP 客户端发送 tools/call 请求，指定工具名和参数
- **THEN** Airway 调用对应的处理函数，返回执行结果

#### Scenario: 调用不存在的工具

- **WHEN** MCP 客户端请求调用未注册的工具名
- **THEN** 返回错误响应，包含 "Tool not found" 信息

### Requirement: 健康检查端点

Airway SHALL 暴露 HTTP 健康检查端点 `/health`，用于部署探针检测。

#### Scenario: 服务正常时返回健康状态

- **WHEN** GET `/health` 请求到达
- **THEN** 返回 HTTP 200，body 包含 `{"status": "ok"}`

#### Scenario: Bisheng API 不可达时返回降级状态

- **WHEN** GET `/health` 请求到达且 Bisheng API 不可达
- **THEN** 返回 HTTP 503，body 包含 `{"status": "degraded", "detail": "bisheng api unreachable"}`
