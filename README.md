# Airway

连接 Clawith Agent 与 Bisheng RAG 后端的无状态 MCP 代理。

```
Clawith Agent → MCP Tool → Airway → Bisheng API
```

本分支使用 **SpecKit** 驱动开发：先通过规格定义需求（spec → plan → tasks），再由 agent 实现。

## 架构

- **无状态设计**：Airway 不持有业务状态，仅做协议转换与请求转发
- **开闭原则**：不修改 Bisheng / Clawith 源码，通过新增模块桥接
- **依赖倒置**：通过 `Protocol` 抽象（`adapters/protocols.py`）面向接口编程
- **可升级**：上游项目独立 `git pull`，Airway 不受影响

## 模块结构

```
airway/
├── server.py                       FastMCP 入口，5 个 MCP Tools + 健康检查
├── config.py                       YAML + 环境变量配置（pydantic-settings）
├── errors.py                       AirwayError + to_tool_error 协议
├── __main__.py                     启动入口（stdio / streamable-http）
├── models/
│   └── user_mapping.py             UserMapping ORM 模型
├── migrations/                     Alembic 数据库迁移
│   ├── env.py
│   └── versions/
│       ├── 001_initial.py          UserMapping 表
│       └── 002_add_password_hash.py password_hash 字段
└── adapters/
    ├── protocols.py                BishengAuth / BishengClient / BishengWorkflow 接口
    └── bisheng/
        ├── auth.py                 v1 JWT（RSA 加密登录 + token 缓存）
        ├── client.py               v2 HTTP（知识库 CRUD + chunk 搜索）
        └── workflow.py             Workflow SSE 流式调用

tests/
├── unit/                           单元测试（auth/client/config/server/workflow）
├── integration/                    集成测试（server）
└── fixtures/                       测试夹具

specs/                              SpecKit 规格文档
├── 001-airway-mcp-proxy/           MCP 代理基础能力
└── 002-user-mapping-workflow-rag/  用户映射 + Workflow RAG

.specify/                           SpecKit 配置与模板
```

## MCP 工具

| 工具 | 说明 | 参数 |
|------|------|------|
| `rag_query` | 在知识库中检索相关文档片段 | `query` `knowledge_base` `top_k?` |
| `knowledge_list` | 列出所有可用知识库 | — |
| `knowledge_detail` | 查看指定知识库详情 | `knowledge_base` |
| `knowledge_search` | 搜索知识库内容片段 | `query` `knowledge_base` `top_k?` |
| `rag_chat` | Workflow 驱动的多轮 RAG 问答 | `query` `knowledge_base` `chat_id?` |

首次调用时，Airway 会自动以 `clawith_<uid>` 在 Bisheng 注册账号并写入 `UserMapping`，后续直接复用。

## 快速开始

```bash
# 安装依赖
uv pip install -e ".[dev]"

# 配置（编辑 config.yaml 填入 Bisheng 地址、管理员密码、DB、Redis）
cp config.yaml.example config.yaml

# 初始化数据库
alembic upgrade head

# 启动（默认 stdio 传输）
python -m airway

# 或使用 HTTP 传输
python -m airway --transport streamable-http
```

## Clawith MCP 配置

```json
{
  "url": "http://<airway-host>:8090/mcp",
  "transport": "streamable-http"
}
```

## 测试

```bash
# 全量测试（51 用例）
pytest tests/ -v

# 仅单元测试
pytest tests/unit/ -v

# 单个测试文件
pytest tests/unit/test_server.py -v

# 按名称过滤
pytest -k "test_rag_chat"
```

pytest 配置：`asyncio_mode = "auto"`，`testpaths = ["tests"]`。

## SpecKit 工作流

本分支通过 SpecKit 驱动开发，规格文档为"一等公民"：

```bash
specify init my-project --integration claude   # 项目初始化（已完成）
specify spec      "..."                          # 生成 / 更新 spec.md
specify plan                                     # 生成 plan.md（设计）
specify tasks                                    # 生成 tasks.md（任务清单）
specify analyze                                  # 跨制品一致性检查
specify implement                                # 按 tasks 执行
```

详见 `docs/speckit-guide.md` 与 `specs/` 目录。

## 技术栈

- **Python 3.12** · FastMCP · httpx · pydantic-settings
- **SQLAlchemy 2.0** + asyncpg · Alembic（数据库迁移）
- **Redis**（token 缓存） · cryptography（RSA 加密）
- **测试**：pytest + pytest-asyncio + respx

## 约束

- 不修改 Bisheng 和 Clawith 源码
- Airway 只做协议转换（单一职责）
- 面向接口编程（依赖倒置）

## 参考代码库

- `/Users/zhenglong/ai-native/rag/bisheng/` — Bisheng 源码
- `/Users/zhenglong/ai-native/rag/Clawith/` — Clawith 源码
