# Airway MCP Server 设计方案

> 日期：2026-06-05
> 状态：已确认

## 1. 背景与目标

将 Bisheng（RAG 平台）和 Clawith（Agent 平台）集成为一套企业级 AI 平台。Airway 作为中间层，以 MCP Server 方式桥接两者。

**约束：**

- 不修改 Bisheng 和 Clawith 源码
- 两个上游项目可独立 git pull 升级
- 单机/小团队部署（< 100 用户）

**MVP 范围：** Agent + RAG 对话（后续迭代加 Workflow 编排）

## 2. 架构方案

采用**独立 MCP 服务**（方案 A）。Airway 作为独立进程运行，Clawith Agent 通过 MCP 协议调用 Bisheng RAG 能力。

```
Clawith Agent ──MCP (stdio/SSE)──▶ Airway ──HTTP REST──▶ Bisheng API
   │                                  │                      │
   PostgreSQL                    Redis (共享)               MySQL
```

**共享基础设施：** Redis 实例通过 key prefix 隔离（`airway:` 前缀）。

**数据库各自独立**，零升级风险。

## 3. 模块划分

Airway 包含 3 个核心模块，各自单一职责：

### 3.1 Auth Proxy

负责 Clawith 用户到 Bisheng 的身份映射和 session 代理。

**流程：**

1. 验证 Clawith JWT 签名，提取 user_id
2. 查 Redis 缓存（key: `airway:session:{clawith_uid}`）
3. 缓存未命中 → 查 SQLite 用户映射表
4. 映射不存在 → 在 Bisheng 自动注册账号（约定：`clawith_{uid}`）
5. 调用 Bisheng 登录 API 获取 session
6. 缓存 session 到 Redis，TTL 与 Bisheng session 同步
7. 带 session 调用 Bisheng RAG API

**用户映射策略：** SQLite + SQLModel ORM。首次访问时自动创建映射。

```python
class UserMapping(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    clawith_uid: str = Field(index=True, unique=True)
    bisheng_uid: str
    bisheng_username: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### 3.2 MCP Tools

暴露给 Clawith Agent 的工具集。每个工具是薄包装层：参数校验 → 调用 Bisheng Client → 格式化返回。

**MVP 工具（3 个）：**

| 工具 | 说明 | Bisheng API |
|------|------|-------------|
| `knowledge_search` | RAG 检索 | `POST /api/v2/knowledge/search` |
| `knowledge_list` | 知识库列表 | `GET /api/v1/knowledge/list` |
| `knowledge_detail` | 知识库详情 | `GET /api/v1/knowledge/{id}` |

**`knowledge_search` 签名：**
- 输入：`query: str`, `knowledge_id: str`, `top_k: int = 5`
- 输出：`[{ chunk_text, score, source_file }]`

**`knowledge_list` 签名：**
- 输入：`page: int = 1`, `size: int = 20`
- 输出：`[{ id, name, description, file_count }]`

**`knowledge_detail` 签名：**
- 输入：`knowledge_id: str`
- 输出：`{ id, name, description, files: [...], embed_model }`

### 3.3 Bisheng Client

Bisheng API 的 HTTP 客户端封装。

- 异步 HTTP（httpx）
- 自动注入认证 session
- 错误处理和重试（网络错误重试 3 次）
- 响应格式标准化

## 4. 项目结构

```
airway/
├── pyproject.toml              # 项目配置 + 依赖
├── src/
│   └── airway/
│       ├── __init__.py
│       ├── server.py           # MCP Server 入口
│       ├── config.py           # 配置管理 (pydantic-settings)
│       ├── auth/
│       │   ├── __init__.py
│       │   ├── jwt.py          # Clawith JWT 验证
│       │   └── proxy.py        # Bisheng session 代理
│       ├── mcp/
│       │   ├── __init__.py
│       │   └── tools.py        # MCP 工具定义
│       ├── client/
│       │   ├── __init__.py
│       │   └── bisheng.py      # Bisheng API 客户端
│       └── models/
│           ├── __init__.py
│           └── mapping.py      # SQLModel 用户映射
├── tests/
│   ├── test_auth.py
│   ├── test_tools.py
│   └── test_client.py
└── data/                       # SQLite 数据文件 (gitignore)
```

## 5. 技术选型

| 用途 | 库 | 说明 |
|------|-----|------|
| MCP 协议 | `mcp` | 官方 Python SDK，实现 Server 端 |
| HTTP 客户端 | `httpx` | 异步 HTTP，调用 Bisheng API |
| ORM | `sqlmodel` | 用户映射表，SQLite 存储 |
| 配置管理 | `pydantic-settings` | 环境变量 + .env 文件 |
| JWT 验证 | `PyJWT` | 验证 Clawith JWT 签名 |
| 缓存 | `redis-py` | Session 缓存，共享 Redis |

总计 6 个直接依赖。

## 6. 配置项

通过环境变量或 `.env` 文件配置：

```env
# Bisheng
BISHENG_BASE_URL=http://localhost:7860
BISHENG_USERNAME=admin
BISHENG_PASSWORD=***

# Clawith
CLAWITH_JWT_SECRET=***
CLAWITH_JWT_ALGORITHM=HS256

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_KEY_PREFIX=airway:

# Airway
AIRWAY_DB_PATH=./data/airway.db
AIRWAY_LOG_LEVEL=INFO
```

## 7. 部署方式

支持两种传输模式：

**stdio 模式**（Clawith 直接启动子进程）：
```bash
airway serve --transport stdio
```

**SSE 模式**（独立进程，Clawith 远程连接）：
```bash
airway serve --transport sse --port 8080
```

Clawith 侧 MCP Server 配置：
```json
{
  "mcpServers": {
    "airway-rag": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

## 8. 迭代路线

| 阶段 | 范围 |
|------|------|
| **MVP** | 3 个知识库工具（search / list / detail） |
| **v2** | + Workflow 工具（workflow_run / workflow_status） |
| **v3** | + 知识库管理（knowledge_upload）+ 流式对话（chat_stream） |

## 9. 错误处理

- **Bisheng 不可用：** 返回 MCP 错误，提示 Bisheng 服务未就绪
- **JWT 无效：** 返回 MCP 错误，提示认证失败
- **Session 过期：** 自动重新登录，对调用方透明
- **网络错误：** 重试 3 次（指数退避），最终返回错误
- **Redis 不可用：** 降级为每次都调 Bisheng 登录 API（无缓存模式）
