# Airway (Superpower 分支)

连接 Clawith Agent 与 Bisheng RAG 后端的 MCP 代理。本分支使用 superpowers 插件驱动结构化开发。

```
Clawith Agent → MCP Tool → Airway → Bisheng API
```

## 架构

- **桥接层设计**：Airway 承担协议转换与请求转发，不持有业务状态
- **开闭原则**：不修改 Bisheng / Clawith 源码，通过新增模块桥接
- **用户统一**：以 Clawith 用户体系为主，JWT 代理映射 Bisheng 身份
- **基础设施共享**：数据库、Redis、对象存储共用
- **可升级**：上游项目独立 `git pull`，Airway 不受影响

## 模块结构

```
src/airway/
  server.py             FastMCP 入口
  config.py             pydantic-settings 配置
  auth/proxy.py         JWT 认证代理（Clawith → Bisheng token 映射）
  mcp/tools.py          MCP Tool 定义
  models/mapping.py     数据模型映射
  client/bisheng.py     Bisheng API 客户端
tests/                  测试（TDD 驱动）
docs/                   设计文档
```

## 快速开始

```bash
pip install -e ".[dev]"
airway                    # 启动 MCP 服务器
```

## 测试

```bash
pytest tests/ -v
```

## 技术栈

Python 3.12 · FastMCP · httpx · pydantic-settings · SQLModel · PyJWT · redis · pytest
