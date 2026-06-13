## Context

Bisheng 知识库有两种类型：文档型（上传文件解析）和 QA 型（结构化问答对）。QA 知识库通过独立的 API 管理：列出、添加、删除 QA 条目。Airway 已有 BishengAPIClient 的 GET/POST/DELETE 方法，QA 工具只需调用对应 API 并映射字段。

## Goals / Non-Goals

**Goals:**
- 暴露 QA 知识库的增删查操作给 Clawith Agent
- 复用现有 BishengAPIClient，不引入新依赖

**Non-Goals:**
- 不实现 QA 导入导出（xlsx）
- 不实现 QA 自动生成问题
- 不实现 QA 状态切换

## Decisions

### D1: QA 条目数据结构

Bisheng QA 条目包含 id、question、answer、source、enabled 等字段。Airway 映射核心字段：id、question、answer。

### D2: 参数设计

- `qa_list(knowledge_id)` → 返回 QA 列表
- `qa_add(knowledge_id, question, answer)` → 返回创建的 QA 条目
- `qa_delete(qa_id)` → 返回删除确认

## Risks / Trade-offs

- **[QA 知识库类型判断]** → Agent 需要自行判断知识库类型（通过 knowledge_list 获取 info），Airway 不做类型校验，Bisheng 会返回错误
