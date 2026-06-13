# Implementation Plan: 用户映射完善与 Workflow RAG 对接

**Branch**: `002-user-mapping-workflow-rag` | **Date**: 2026-06-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-user-mapping-workflow-rag/spec.md`

## Summary

完善 MVP 的用户映射机制（从占位实现升级为真实 Bisheng 用户创建），
并新增 `rag_chat` MCP 工具通过 Bisheng Workflow HTTP SSE API 实现
完整 RAG 问答。用户映射使用 Bisheng `/api/v1/user/regist` 创建真实用户，
处理用户名冲突时回退到登录复用。Workflow 对话使用 `POST /api/v2/workflow/invoke`
HTTP SSE 端点，避免 WebSocket 复杂性。

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.12+

**Primary Dependencies**: fastmcp>=3.0, httpx>=0.27, pydantic>=2.0, sqlalchemy[asyncio]>=2.0（均为已有）

**Storage**: PostgreSQL 15+（user_mappings 表扩展）, Redis 7+（已有）

**Testing**: pytest + pytest-asyncio + respx（已有）

**Target Platform**: Linux server（Docker）

**Project Type**: MCP server（已有项目扩展）

**Performance Goals**: 10+ 并发 Agent, rag_chat 30s 超时

**Constraints**: 不修改 Bisheng/Clawith 源码, 通过 Bisheng API 交互

**Scale/Scope**: 1 新 MCP 工具, 1 表字段扩展, 1 新 adapter 模块

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Open-Closed | PASS | 新增 airway 代码，不修改 Bisheng/Clawith |
| II. Single Responsibility | PASS | Airway 仍仅做协议转换，新增 workflow 适配 |
| III. Dependency Inversion | PASS | 新增 BishengWorkflow Protocol 接口 |
| IV. Unified User Identity | PASS | 完善用户映射，从占位升级为真实 Bisheng 用户 |
| V. Shared Infrastructure | PASS | 继续使用共享 PostgreSQL/Redis |
| VI. MVP Iteration | PASS | 两个独立增量：用户映射 + rag_chat |
| VII. Async-First with ORM | PASS | 全 async，httpx SSE streaming |

**Post-Phase 1 re-check**: All gates still PASS. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/002-user-mapping-workflow-rag/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── mcp-tools.md     # rag_chat tool contract
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
airway/
├── server.py                # 新增 rag_chat tool 注册
├── config.py                # 新增 workflow 配置项
├── adapters/
│   ├── protocols.py         # 新增 BishengWorkflow Protocol
│   └── bisheng/
│       ├── auth.py          # 增强：用户注册方法
│       ├── client.py        # 不变
│       └── workflow.py      # 新增：Workflow SSE 客户端
├── models/
│   └── user_mapping.py      # 增强：新字段
└── migrations/
    └── versions/
        └── 002_*.py         # 新增：user_mappings 表字段扩展

tests/
├── unit/
│   ├── test_server.py       # 扩展：rag_chat 测试
│   ├── test_auth.py         # 扩展：用户注册测试
│   └── test_workflow.py     # 新增：Workflow 客户端测试
└── integration/
    └── test_server.py       # 扩展：rag_chat 集成测试
```

**Structure Decision**: 在已有 airway/ 结构上扩展，新增 `adapters/bisheng/workflow.py` 和 `tests/unit/test_workflow.py`。

## Complexity Tracking

No constitution violations. No entries needed.
