# MCP Tool Contracts: Airway

**Branch**: `001-airway-mcp-proxy` | **Date**: 2026-06-07

## Transport

| Mode | Usage |
|------|-------|
| stdio | 本地开发、Claude Desktop 集成 |
| streamable-http | 生产部署，Clawith Agent 远程调用 |

## Tools

### rag_query

基于知识库的 RAG 检索，返回匹配的文档片段供 Agent 生成答案。

**Input Schema**:
```json
{
  "query": "string (required) - 用户问题，1-2000 字符",
  "knowledge_base": "string (required) - 知识库标识名",
  "top_k": "integer (optional, default=5) - 返回片段数量，1-20"
}
```

**Output** (string):
```
找到 3 个相关片段：

【片段 1】(来源: doc1.pdf, 相关度: 0.95)
产品退货政策：自购买之日起 7 天内...

【片段 2】(来源: doc2.pdf, 相关度: 0.87)
退货流程：1. 联系客服...
```

**Errors**:
- `知识库 "{name}" 不存在` — knowledge_base 名无效
- `查询内容不能为空` — query 为空字符串
- `RAG 服务暂时不可用，请稍后重试` — Bisheng 连接失败

---

### knowledge_list

列出所有已配置的可用的知识库。

**Input Schema**:
```json
{}
```

**Output** (string):
```
可用知识库（共 3 个）：

1. company-faq - 公司常见问题（5 个文档）
2. product-docs - 产品文档（12 个文档）
3. hr-policies - 人事政策（3 个文档）
```

**Errors**:
- `RAG 服务暂时不可用，请稍后重试` — Bisheng 连接失败

---

### knowledge_detail

获取某个知识库的详细信息。

**Input Schema**:
```json
{
  "knowledge_base": "string (required) - 知识库标识名"
}
```

**Output** (string):
```
知识库: company-faq
描述: 公司常见问题解答
文档数: 5
状态: 已就绪
创建时间: 2024-01-15
最近更新: 2024-06-01
```

**Errors**:
- `知识库 "{name}" 不存在` — knowledge_base 名无效
- `RAG 服务暂时不可用，请稍后重试` — Bisheng 连接失败

---

### knowledge_search

在知识库中按关键词搜索文档片段。

**Input Schema**:
```json
{
  "query": "string (required) - 搜索关键词，1-500 字符",
  "knowledge_base": "string (required) - 知识库标识名",
  "top_k": "integer (optional, default=10) - 返回片段数量，1-50"
}
```

**Output** (string):
```
搜索 "退货" 在 company-faq 中找到 4 个结果：

【结果 1】(doc1.pdf, 第 3 页)
产品退货政策：自购买之日起 7 天内可无理由退货...

【结果 2】(faq.md)
Q: 如何申请退货？ A: 请联系客服并提供订单号...
```

**Errors**:
- `知识库 "{name}" 不存在` — knowledge_base 名无效
- `搜索内容不能为空` — query 为空字符串
- `RAG 服务暂时不可用，请稍后重试` — Bisheng 连接失败

## Error Format

所有错误通过 MCP error response 返回，格式为纯文本描述，不暴露内部实现细节。
