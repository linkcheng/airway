# Tasks: 用户映射完善与 Workflow RAG 对接

**Input**: Design documents from `/specs/002-user-mapping-workflow-rag/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/mcp-tools.md

**Tests**: Constitution 要求 TDD discipline — 每个实现任务前先写失败测试。

**Organization**: Tasks grouped by user story (US1: 用户映射, US2: rag_chat, US3: 多轮对话)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 扩展配置、协议、模型，为 US1 和 US2 提供基础设施

- [x] T001 扩展 KnowledgeBaseEntry 添加 workflow_id 可选字段 in airway/config.py
- [x] T002 [P] 新增 BishengWorkflow Protocol 接口 in airway/adapters/protocols.py
- [x] T003 [P] 新增 UserMapping.password_hash 字段 (String 64) in airway/models/user_mapping.py
- [x] T004 新增 Alembic 迁移脚本，添加 password_hash 列 in airway/migrations/versions/002_add_password_hash.py

**Checkpoint**: 配置、协议、模型就绪，user story 实现可开始

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 核心 adapter 方法，所有 user story 的前置依赖

**⚠️ CRITICAL**: US1 和 US2 的实现都依赖此阶段完成

- [x] T005 在 BishengAuth Protocol 新增 register_user / login_user 方法签名 in airway/adapters/protocols.py
- [x] T006 在 BishengAuthProvider 实现 register_user(user_name, password) → POST /api/v1/user/regist in airway/adapters/bisheng/auth.py
- [x] T007 在 BishengAuthProvider 实现 login_user(user_name, password) → POST /api/v1/user/login，返回 user_id + token in airway/adapters/bisheng/auth.py
- [x] T008 新增 BishengWorkflowAdapter 类骨架 in airway/adapters/bisheng/workflow.py
- [x] T009 实现 BishengWorkflowAdapter.invoke(workflow_id, query, token, session_id?) → SSE 收集完整响应 in airway/adapters/bisheng/workflow.py

**Checkpoint**: auth 注册/登录 + workflow SSE 客户端就绪，user story 实现可并行开始

---

## Phase 3: User Story 1 - 用户自动映射 (Priority: P1) 🎯 MVP

**Goal**: Clawith 用户首次调用工具时，自动创建 Bisheng 账号并建立映射，后续调用复用映射

**Independent Test**: 新 Clawith 用户 ID → 自动创建 Bisheng 用户 → 映射持久化 → 后续调用复用

### Tests for User Story 1 (TDD)

> Write these tests FIRST, ensure they FAIL before implementation

- [x] T010 [P] [US1] 测试 register_user 成功注册新用户 in tests/unit/test_auth.py
- [x] T011 [P] [US1] 测试 register_user 冲突回退登录 (status_code 10605) in tests/unit/test_auth.py
- [x] T012 [P] [US1] 测试 login_user 成功返回 user_id + token in tests/unit/test_auth.py
- [x] T013 [US1] 测试 _ensure_user_mapping 首次调用自动注册并保存映射 in tests/unit/test_server.py
- [x] T014 [US1] 测试 _ensure_user_mapping 已有映射直接返回 in tests/unit/test_server.py
- [x] T015 [US1] 测试 _ensure_user_mapping 注册冲突回退登录 in tests/unit/test_server.py

### Implementation for User Story 1

- [x] T016 [US1] 实现 _ensure_user_mapping 真实用户注册逻辑（替换占位实现）in airway/server.py
- [x] T017 [US1] 实现 register_or_login 编排方法：register → conflict → login → get user_id in airway/adapters/bisheng/auth.py
- [x] T018 [US1] 更新所有现有 MCP 工具（rag_query, knowledge_*）使用映射后的用户身份 in airway/server.py

**Checkpoint**: 用户映射完整可用 — 新用户自动创建，老用户复用映射

---

## Phase 4: User Story 2 - rag_chat 完整 RAG 问答 (Priority: P2)

**Goal**: 新增 rag_chat MCP 工具，通过 Bisheng Workflow SSE 返回 AI 生成的完整答案

**Independent Test**: 调用 rag_chat(query, knowledge_base) → 返回完整答案文本 + session_id

### Tests for User Story 2 (TDD)

> Write these tests FIRST, ensure they FAIL before implementation

- [x] T019 [P] [US2] 测试 BishengWorkflowAdapter.invoke 成功收集 SSE 事件并返回完整文本 in tests/unit/test_workflow.py
- [x] T020 [P] [US2] 测试 BishengWorkflowAdapter.invoke SSE 超时返回错误 in tests/unit/test_workflow.py
- [x] T021 [P] [US2] 测试 BishengWorkflowAdapter.invoke 提取 session_id in tests/unit/test_workflow.py
- [x] T022 [US2] 测试 rag_chat 成功返回完整答案 in tests/unit/test_server.py
- [x] T023 [US2] 测试 rag_chat 知识库未配置 workflow_id 返回错误 in tests/unit/test_server.py
- [x] T024 [US2] 测试 rag_chat 无效知识库名返回错误 in tests/unit/test_server.py

### Implementation for User Story 2

- [x] T025 [US2] 实现 rag_chat MCP tool（调用 _ensure_user_mapping + workflow.invoke）in airway/server.py
- [x] T026 [US2] 实现 _resolve_workflow 辅助方法：从 knowledge_base 名查 workflow_id in airway/server.py

**Checkpoint**: rag_chat 工具完整可用 — 查询 → 映射用户 → Workflow SSE → 返回答案

---

## Phase 5: User Story 3 - 多轮对话上下文 (Priority: P3)

**Goal**: rag_chat 支持 chat_id 参数，实现多轮对话上下文延续

**Independent Test**: 连续两次 rag_chat 传入同一 chat_id → 第二次回答基于前次上下文

### Tests for User Story 3 (TDD)

- [x] T027 [US3] 测试 rag_chat 不传 chat_id 返回结果中包含 session_id in tests/unit/test_server.py
- [x] T028 [US3] 测试 rag_chat 传入 chat_id 传递给 workflow.invoke in tests/unit/test_server.py

### Implementation for User Story 3

- [x] T029 [US3] 为 rag_chat tool 添加可选 chat_id 参数 in airway/server.py
- [x] T030 [US3] 更新 BishengWorkflowAdapter.invoke 支持 session_id 参数 in airway/adapters/bisheng/workflow.py
- [x] T031 [US3] 格式化 rag_chat 输出：前置 session_id 供后续多轮使用 in airway/server.py

**Checkpoint**: 多轮对话完整可用 — chat_id 传递、上下文延续、session_id 返回

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 质量保证和全链路验证

- [x] T032 [P] 运行全量测试确保 37 个 MVP 测试不受影响 via `python -m pytest tests/ -v`
- [x] T033 [P] 运行 quickstart.md 中 Scenario 1-5 验证全链路 in specs/002-user-mapping-workflow-rag/quickstart.md
- [x] T034 代码清理：移除 server.py 中 _ensure_user_mapping 的占位注释 in airway/server.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion - BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 - No dependency on other user stories
- **US2 (Phase 4)**: Depends on Phase 2 - No dependency on US1 (独立可测)
- **US3 (Phase 5)**: Depends on Phase 4 (需要 rag_chat 工具存在)
- **Polish (Phase 6)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Phase 2 → Phase 3，独立可测
- **US2 (P2)**: Phase 2 → Phase 4，独立可测（US2 不依赖 US1 完成）
- **US3 (P3)**: Phase 4 → Phase 5，依赖 US2（需要 rag_chat 工具）

### Parallel Opportunities

- Phase 1: T002 || T003 (不同文件)
- Phase 2: T006 || T007 (同文件不同方法，可并行编写)
- US1 Tests: T010 || T011 || T012 (不同测试场景)
- US2 Tests: T019 || T020 || T021 (不同测试场景)
- Phase 6: T032 || T033 (不同验证方式)

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together:
Task: "T010 测试 register_user 成功注册新用户 in tests/unit/test_auth.py"
Task: "T011 测试 register_user 冲突回退登录 in tests/unit/test_auth.py"
Task: "T012 测试 login_user 成功返回 user_id + token in tests/unit/test_auth.py"

# Then implement sequentially (same files):
Task: "T017 实现 register_or_login 编排方法 in airway/adapters/bisheng/auth.py"
Task: "T016 实现 _ensure_user_mapping 真实用户注册逻辑 in airway/server.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 - 用户映射
4. **STOP and VALIDATE**: 测试新用户自动创建映射、老用户复用
5. 可选择先部署此增量

### Incremental Delivery

1. Setup + Foundational → 基础设施就绪
2. Add US1 → 测试用户映射 → Deploy（MVP 身份升级）
3. Add US2 → 测试 rag_chat → Deploy（RAG 能力升级）
4. Add US3 → 测试多轮对话 → Deploy（体验优化）
5. Polish → 全量回归 → 完成

---

## Notes

- [P] tasks = different files, no dependencies
- TDD: 先写失败测试 → 最小实现 → 重构
- Commit after each task or logical group
- 原有 4 个 MCP 工具行为不变（FR-008）
- 密码生成：`airway_{clawith_user_id}` 的 MD5 哈希，RSA 加密传输
- SSE 超时 30s，收集到 end/over 事件即返回
