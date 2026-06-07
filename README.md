# Airway

MCP 代理，桥接 Clawith Agent 和 Bisheng RAG 后端。

```
Clawith Agent → MCP Tool → Airway (MCP Server) → Bisheng RAG API
```

## 快速开始

```bash
# 安装依赖
uv pip install -e ".[dev]"

# 配置
cp .env.example .env
# 编辑 .env，填入 Bisheng API 地址和 token

# 启动
python -m airway
```

## MCP 工具

Airway 向 Clawith 暴露以下 MCP 工具：

| 工具 | 说明 | 参数 |
|------|------|------|
| `knowledge_list_tool` | 列出 Bisheng 知识库 | `keyword?` `user_id?` |
| `knowledge_search_tool` | 搜索知识库内容 | `knowledge_id` `query` `user_id?` |
| `knowledge_files_tool` | 列出知识库文件 | `knowledge_id` `user_id?` |

## Clawith MCP 配置

在 Clawith 的 MCP 工具配置中添加：

```json
{
  "url": "http://<airway-host>:8900/sse",
  "transport": "sse"
}
```

## 开发

```bash
# 运行测试
pytest -v

# 运行单个测试
pytest tests/test_bisheng_client.py -v
```

## Docker 部署

```bash
docker compose up -d
```
