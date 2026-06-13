# MCP Tool Contracts: rag_chat

**Branch**: `002-user-mapping-workflow-rag` | **Date**: 2026-06-07

## rag_chat

通过 Bisheng Workflow 执行完整 RAG 问答，返回 AI 生成的答案。

**Input Schema**:
```json
{
  "query": "string (required) - 用户问题，1-2000 字符",
  "knowledge_base": "string (required) - 知识库标识名，必须配置了 workflow_id",
  "chat_id": "string (optional) - 会话 ID，用于多轮对话上下文"
}
```

**Output** (string):
```
[会话 ID: abc123]

产品退货政策如下：

自购买之日起 7 天内，用户可申请无理由退货。退货流程：
1. 联系客服并提供订单号
2. 等待客服确认退货地址
3. 寄回商品并在系统中填写物流单号
4. 收到商品后 3 个工作日内完成退款

参考来源：退货政策.pdf
```

**Errors**:
- `知识库 "{name}" 不存在` — knowledge_base 名无效
- `知识库 "{name}" 未配置 Workflow，请使用 rag_query 进行文档检索` — 无 workflow_id
- `查询内容不能为空` — query 为空字符串
- `RAG 服务暂时不可用，请稍后重试` — Bisheng 连接失败
- `RAG 服务响应超时` — Workflow 执行超过 30 秒
