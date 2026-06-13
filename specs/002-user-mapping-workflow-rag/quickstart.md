# Quickstart: 用户映射完善与 Workflow RAG 对接

**Branch**: `002-user-mapping-workflow-rag` | **Date**: 2026-06-07

## Prerequisites

- MVP (001-airway-mcp-proxy) 已部署且测试通过
- Bisheng 已部署，用户注册 API 可用
- Bisheng 中已配置好包含知识库引用的 RAG Workflow
- PostgreSQL 中 user_mappings 表已存在

## Setup

```bash
# 更新配置：在 knowledge_bases 中添加 workflow_id
cp config.yaml.example config.yaml
# 编辑 config.yaml

# 运行数据库迁移（添加新字段）
alembic upgrade head

# 运行测试验证
python -m pytest tests/ -v
```

## Validation Scenarios

### Scenario 1: 用户映射自动创建

```bash
python -m pytest tests/unit/test_auth.py::test_register_new_user -v
python -m pytest tests/unit/test_auth.py::test_register_conflict_fallback_login -v
```

**Expected**: 新用户首次调用时自动创建 Bisheng 账号，后续调用复用映射。

### Scenario 2: rag_chat 完整 RAG 问答

```bash
python -m pytest tests/unit/test_server.py::test_rag_chat_success -v
python -m pytest tests/unit/test_workflow.py -v
```

**Expected**: 返回 AI 生成的完整答案，包含会话 ID。

### Scenario 3: 多轮对话上下文

```bash
python -m pytest tests/unit/test_server.py::test_rag_chat_with_chat_id -v
```

**Expected**: 使用 chat_id 实现多轮对话上下文。

### Scenario 4: 错误处理

```bash
python -m pytest tests/unit/test_server.py::test_rag_chat_no_workflow -v
python -m pytest tests/unit/test_workflow.py::test_workflow_timeout -v
```

**Expected**: 无 workflow 配置、超时等场景返回明确错误。

### Scenario 5: 集成测试

```bash
python -m pytest tests/integration/test_server.py -v -k "rag_chat or user_mapping"
```

**Expected**: 全链路测试通过。
