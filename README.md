# Airway

连接 Clawith Agent 与 Bisheng RAG 后端的无状态 MCP 代理。

```
Clawith Agent → MCP Tool → Airway → Bisheng API
```

## 架构

- **无状态设计**：Airway 不持有业务状态，仅做协议转换和请求转发
- **开闭原则**：不修改 Bisheng / Clawith 源码，通过新增模块桥接
- **可升级**：上游项目独立 `git pull`，Airway 不受影响

## 模块结构

```
server.py              FastMCP 入口，6 个 MCP Tools
config.py              YAML + 环境变量配置
adapters/bisheng/
  adapter.py           BishengAdapter（状态映射 + 嵌套 input 构造）
  client.py            v2 HTTP 客户端（问答、Workflow SSE、Redis 状态查询）
  auth.py              v1 JWT 客户端（RSA 加密登录 + token 自动刷新）
tests/                 单元测试
docs/                  设计文档
```

## 快速开始

```bash
cp config.yaml.example config.yaml  # 编辑配置
pip install -e ".[dev]"
python server.py                    # 启动 MCP 服务器
```

## 测试

```bash
pytest tests/ -v
```

## 技术栈

Python 3.12 · FastMCP · httpx · pydantic-settings · pytest
