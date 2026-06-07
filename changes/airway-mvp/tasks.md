## 1. 项目脚手架

- [x] 1.1 初始化 Python 项目结构（pyproject.toml、src/airway/ 包目录、tests/）
- [x] 1.2 添加核心依赖（fastapi、uvicorn、httpx、mcp、pydantic-settings、pytest、pytest-asyncio）
- [x] 1.3 实现 Pydantic Settings 配置加载（.env 支持，包含 bisheng_api_url、bisheng_token、server_host、server_port、api_timeout）

## 2. 认证桥接 (auth-bridge)

- [x] 2.1 实现 BishengAPIClient 类，封装 httpx AsyncClient，统一注入 Cookie header
- [x] 2.2 实现 service account token 管理：内存持有 + 401 检测
- [x] 2.3 实现 token 自动刷新：检测 401 → 调用 Bisheng login API → 更新内存 token → 重试原请求
- [x] 2.4 编写 auth-bridge 单元测试（mock Bisheng API 响应，验证 token 注入和刷新逻辑）

## 3. RAG 代理 (rag-proxy)

- [x] 3.1 实现 knowledge_list 工具：调用 Bisheng GET /api/v1/knowledge，映射返回字段
- [x] 3.2 实现 knowledge_search 工具：调用 Bisheng chunk 查询 API，映射返回字段
- [x] 3.3 实现 knowledge_files 工具：调用 Bisheng GET /api/v1/knowledge/file_list/{id}，映射返回字段
- [x] 3.4 统一错误处理：Bisheng 非 2xx → MCP error、超时 → timeout error
- [x] 3.5 编写 rag-proxy 单元测试（mock Bisheng API，验证各工具输入输出和错误场景）

## 4. MCP Server (mcp-server)

- [x] 4.1 创建 FastAPI app，集成 MCP SSE server（使用 mcp SDK 的 FastMCP 或 sse-server）
- [x] 4.2 注册所有 RAG 工具（knowledge_list、knowledge_search、knowledge_files），定义参数 JSON Schema
- [x] 4.3 实现工具调用分发：根据 tool name 路由到对应处理函数
- [x] 4.4 实现 /health 健康检查端点（含 Bisheng API 可达性检测）
- [x] 4.5 实现 user_id 透传日志（从 MCP tool 参数提取 user_id，记录到结构化日志）
- [x] 4.6 编写 mcp-server 集成测试（启动 server，验证 tool list 和 tool call）

## 5. 部署与文档

- [x] 5.1 编写 Dockerfile（Python 3.12 slim，安装依赖，运行 FastAPI）
- [x] 5.2 编写 docker-compose.yml（Airway 服务定义，环境变量配置）
- [x] 5.3 编写 .env.example 示例配置文件
- [x] 5.4 编写 README.md（项目简介、快速启动、Clawith MCP 配置说明）
